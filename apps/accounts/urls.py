from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.KoraLoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("inscription/", views.SignupChoiceView.as_view(), name="signup"),
    path("inscription/client/", views.ClientSignupView.as_view(), name="signup_client"),
    path("inscription/artisan/", views.ProviderSignupView.as_view(), name="signup_provider"),
    path("inscription/specialites/", views.SubcategoryOptionsView.as_view(), name="subcategories"),
    path("profil/", views.ProfileView.as_view(), name="profile"),
    path("mot-de-passe/modifier/", views.PasswordChangeView.as_view(), name="password_change"),
    path("supprimer/", views.DeleteAccountView.as_view(), name="delete"),
    path("verification/", views.VerifyView.as_view(), name="verify"),
    path("verification/renvoyer/", views.ResendOTPView.as_view(), name="verify_resend"),
    # Mot de passe oublié
    path("mot-de-passe/oublie/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset_form.html",
        email_template_name="accounts/emails/password_reset_email.txt",
        subject_template_name="accounts/emails/password_reset_subject.txt",
        success_url=reverse_lazy("accounts:password_reset_done"),
    ), name="password_reset"),
    path("mot-de-passe/envoye/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html"), name="password_reset_done"),
    path("mot-de-passe/reinitialiser/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url=reverse_lazy("accounts:password_reset_complete"),
    ), name="password_reset_confirm"),
    path("mot-de-passe/termine/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"), name="password_reset_complete"),
]
