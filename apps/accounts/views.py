from django.contrib import messages
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.catalog.models import Subcategory
from apps.core import ratelimit

from . import otp, services
from apps.core.mixins import RoleRequiredMixin

from .forms import (
    ClientProfileForm, ClientSignupForm, DeleteAccountForm, LoginForm, OTPForm, ProviderSignupForm, StyledPasswordChangeForm,
)
from .models import OTPCode, User

LOGIN_FAIL_LIMIT = 5
LOGIN_WINDOW = 15 * 60
BACKEND = "apps.accounts.backends.EmailOrPhoneBackend"


class KoraLoginView(auth_views.LoginView):
    """Connexion ; limite les essais ratés par IP + identifiant ; redirige vers l'espace du rôle."""

    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def _scope_id(self):
        ident = (self.request.POST.get("username") or "").strip().lower()
        return f"{ratelimit.client_ip(self.request)}:{ident}"

    def post(self, request, *args, **kwargs):
        if ratelimit.is_limited("login", self._scope_id(), LOGIN_FAIL_LIMIT):
            form = self.get_form()
            form.add_error(None, _("Trop de tentatives. Réessayez dans quelques minutes."))
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def get_default_redirect_url(self):
        return self.request.user.get_home_url()

    def form_invalid(self, form):
        ratelimit.hit("login", self._scope_id(), LOGIN_WINDOW)
        return super().form_invalid(form)

    def form_valid(self, form):
        ratelimit.reset("login", self._scope_id())
        messages.success(self.request, _("Bienvenue sur Kora !"))
        return super().form_valid(form)


class SignupChoiceView(TemplateView):
    template_name = "accounts/signup_choice.html"


class _SignupBase(FormView):
    """Inscription : crée le compte, connecte l'utilisateur et envoie un code de vérification par e-mail."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(request.user.get_home_url())
        return super().dispatch(request, *args, **kwargs)

    def finish(self, user):
        login(self.request, user, backend=BACKEND)
        otp.issue_otp(user, OTPCode.Channel.EMAIL)
        messages.success(self.request, _("Compte créé ! Un code de vérification vient de vous être envoyé par e-mail."))
        return redirect("accounts:verify")


class ClientSignupView(_SignupBase):
    form_class = ClientSignupForm
    template_name = "accounts/signup_client.html"

    def form_valid(self, form):
        d = form.cleaned_data
        user = services.register_client(
            email=d["email"], password=d["password1"], first_name=d["first_name"], last_name=d["last_name"],
            phone=d["phone"], city=d["city"],
        )
        return self.finish(user)


class ProviderSignupView(_SignupBase):
    form_class = ProviderSignupForm
    template_name = "accounts/signup_provider.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx["form"]
        category_id = form["category"].value() if form.is_bound or form.initial.get("category") else None
        ctx["subcategories"] = _subcategories_for(category_id)
        ctx["selected_subcategories"] = [str(v) for v in (form["subcategories"].value() or [])]
        return ctx

    def form_valid(self, form):
        d = form.cleaned_data
        user = services.register_provider(
            email=d["email"], password=d["password1"], first_name=d["first_name"], last_name=d["last_name"],
            phone=d["whatsapp"], business_name=d["business_name"], category=d["category"],
            subcategories=d["subcategories"], city=d["city"], whatsapp=d["whatsapp"], activity_type=d["activity_type"],
        )
        return self.finish(user)


def _subcategories_for(category_id):
    try:
        return Subcategory.objects.filter(category_id=int(category_id), is_active=True, category__is_active=True)
    except (TypeError, ValueError):
        return Subcategory.objects.none()


class SubcategoryOptionsView(View):
    """Fragment HTMX : cases à cocher des spécialités d'un métier."""

    def get(self, request):
        return render(request, "accounts/partials/subcategory_options.html", {
            "subcategories": _subcategories_for(request.GET.get("category")),
            "selected_subcategories": [],
        })


class VerifyView(LoginRequiredMixin, FormView):
    """Saisie du code reçu. Non bloquant : l'utilisateur peut « Plus tard »."""

    form_class = OTPForm
    template_name = "accounts/verify.html"
    OTP_FAIL_LIMIT = 10

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.email_verified:
            messages.info(request, _("Votre adresse e-mail est déjà vérifiée."))
            return redirect(request.user.get_home_url())
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = self.request.user
        if ratelimit.is_limited("otp", str(user.pk), self.OTP_FAIL_LIMIT):
            form.add_error("code", _("Trop de tentatives. Réessayez dans quelques minutes."))
            return self.form_invalid(form)
        result = otp.verify_otp(user, OTPCode.Channel.EMAIL, form.cleaned_data["code"])
        if result == otp.OTPResult.OK:
            ratelimit.reset("otp", str(user.pk))
            messages.success(self.request, _("Adresse e-mail vérifiée. Merci !"))
            return redirect(user.get_home_url())
        ratelimit.hit("otp", str(user.pk), 10 * 60)
        errors = {
            otp.OTPResult.WRONG: _("Code incorrect."),
            otp.OTPResult.EXPIRED: _("Ce code a expiré. Demandez-en un nouveau."),
            otp.OTPResult.LOCKED: _("Trop d'essais pour ce code. Demandez-en un nouveau."),
            otp.OTPResult.MISSING: _("Aucun code actif. Demandez-en un nouveau."),
        }
        form.add_error("code", errors[result])
        return self.form_invalid(form)


class ResendOTPView(LoginRequiredMixin, View):
    """Renvoie un code (3 envois max par 10 minutes)."""

    def post(self, request):
        if ratelimit.is_limited("otp-send", str(request.user.pk), 3):
            messages.error(request, _("Trop de demandes de code. Patientez quelques minutes."))
        else:
            ratelimit.hit("otp-send", str(request.user.pk), 10 * 60)
            otp.issue_otp(request.user, OTPCode.Channel.EMAIL)
            messages.success(request, _("Un nouveau code vous a été envoyé."))
        return redirect("accounts:verify")


class _ClientAccountMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.CLIENT,)


class ProfileView(_ClientAccountMixin, FormView):
    """Mon compte (client) : informations, photo, langue, préférences de notification."""

    template_name = "accounts/profile.html"
    form_class = ClientProfileForm
    success_url = reverse_lazy("accounts:profile")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, _("Vos informations ont été enregistrées."))
        response = redirect(self.get_success_url())
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, user.language, max_age=365 * 24 * 3600, samesite="Lax")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_section"] = "account"
        return ctx


class PasswordChangeView(RoleRequiredMixin, auth_views.PasswordChangeView):
    """Changement de mot de passe, ouvert à tous les rôles connectés (le gabarit s'adapte à l'espace)."""

    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm

    def get_success_url(self):
        return reverse("dashboard_provider:settings") if self.request.user.is_provider else (
            reverse("dashboard_admin:settings") if self.request.user.is_admin_role else reverse("accounts:profile"))

    def form_valid(self, form):
        messages.success(self.request, _("Votre mot de passe a été modifié."))
        return super().form_valid(form)


class DeleteAccountView(_ClientAccountMixin, FormView):
    """Suppression du compte : confirmation par mot de passe, puis anonymisation.

    Les avis déjà publiés restent (ils apparaissent sous « Client Kora ») pour ne pas fausser les notes."""

    template_name = "accounts/delete_account.html"
    form_class = DeleteAccountForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        user.favorites.all().delete()
        user.saved_searches.all().delete()
        user.notifications.all().delete()
        user.first_name = user.last_name = ""
        user.email = f"supprime-{user.pk}@kora.invalid"
        user.phone, user.avatar, user.is_active = None, "", False
        user.set_unusable_password()
        user.save()
        logout(self.request)
        messages.success(self.request, _("Votre compte a été supprimé."))
        return redirect("core:home")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["nav_section"] = "account"
        return ctx
