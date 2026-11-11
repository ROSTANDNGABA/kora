# Kora

Plateforme web de mise en relation entre clients et artisans / prestataires de services au Cameroun.
*Le savoir-faire camerounais, à portée de main.*

État actuel : **les sept phases sont livrées** (modèles et authentification, pages publiques, interface client, dashboard prestataire, messagerie et notifications, back-office administrateur, durcissement et recette).

## Installation

Prérequis : Python 3.12+ (testé en 3.13), Node 20+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # puis adapter les valeurs
npm install
npm run build                   # copie htmx/alpine/lucide/chart.js/polices dans static/ + compile Tailwind
python manage.py migrate
python manage.py seed_demo      # données de démo + 5 comptes prêts à l'emploi
python manage.py runserver
```

Pendant le développement, lancer aussi `npm run css:watch` dans un second terminal.

## Commandes utiles

| Commande | Rôle |
|---|---|
| `python manage.py seed_demo` | Génère les données de démo (`--reset` pour les régénérer, développement uniquement) |
| `python manage.py test` | Lance les tests |
| `python manage.py check --deploy` | Contrôle de sécurité pour la production |
| `npm run css:build` | Recompile Tailwind (minifié) |
| `python manage.py collectstatic` | Statiques pour la production (WhiteNoise) |

## Structure

```
config/            settings, urls, wsgi/asgi
apps/
  accounts/        User personnalisé (rôle, téléphone), connexion e-mail ou téléphone
  core/            mixins (RoleRequiredMixin), context processors, template tags, pages communes
  catalog/ providers/ requests_app/ reviews/ favorites/ cms/   modèles, sélecteurs, vues publiques et client
  messaging/ notifications/      conversations client/prestataire, centre de notifications
  dashboard_provider/            espace prestataire (11 onglets)
  dashboard_admin/               back-office (13 onglets), permissions par module, journal d'audit
templates/         base.html, partials/, components/, dashboard/ (coquille commune), dashboard_provider/, dashboard_admin/
static/src/        input.css (design system Tailwind)
```

## Design system

Page de démonstration des composants : `/design-system/` (uniquement si `DJANGO_DEBUG=True`).

## Sécurité

Voir la section « Sécurité et déploiement » plus bas.

## Comptes de démo

Créés par `python manage.py seed_demo`. Mot de passe commun : **`Kora2026!`**

| Compte | Rôle | Arrive sur |
|---|---|---|
| `admin@kora.cm` | Super-administrateur (tous les modules) | `/back-office/` |
| `moderateur@kora.cm` | Équipe, rôle Modérateur (prestataires, avis, signalements, contenu) | `/back-office/` |
| `support@kora.cm` | Équipe, rôle Support (clients, demandes, signalements, communication) | `/back-office/` |
| `prestataire@kora.cm` | Plombier à Douala, profil actif et vérifié | `/prestataire/` |
| `client@kora.cm` | Client | `/` |

Les 40 prestataires comptent 33 actifs, 5 en attente, 1 suspendu et 1 refusé, pour tester la file de validation.

## Authentification

- Inscription client (`/compte/inscription/client/`) et artisan (`/compte/inscription/artisan/`, avec choix du métier et des spécialités).
- Un artisan est créé en statut `PENDING` : invisible publiquement jusqu'à validation admin.
- Vérification par code à 6 chiffres (non bloquante) : en dev, le code s'affiche dans le terminal (e-mail via la console, SMS via `apps/core/sms.py`).
- Limitation de débit : 5 échecs de connexion / 15 min (par IP + identifiant), 10 essais OTP / 10 min, 3 renvois de code / 10 min.
- Mot de passe oublié : le lien de réinitialisation s'affiche dans le terminal en dev.

## Pages publiques (phase 2)

- `/` : landing page (hero avec recherche, catégories, compteurs, prestataires à la une, villes, témoignages, FAQ). Tout vient de la base : seuls les prestataires actifs sont comptés et affichés, les témoignages sont des avis visibles de 4 étoiles et plus avec commentaire, signés « Prénom N. ».
- `/recherche/?q=…&ville=…` : recherche insensible aux accents et à la casse (métier, catégorie, nom de l'entreprise). Chaque recherche de la première page est enregistrée (`SearchQuery`) pour les statistiques du back-office.
- `/categorie/<slug>/?specialite=…&ville=…` : liste des prestataires d'une catégorie, filtrable.
- `/faq/` et `/page/<slug>/` : pages éditables depuis le CMS (seules les pages publiées sont accessibles).
- SEO : `sitemap.xml`, `robots.txt`, balises canonical, Open Graph, Twitter, JSON-LD (Organization, WebSite avec SearchAction). Les pages privées sont en `noindex`.
- Réseaux sociaux : renseigner `SOCIAL_FACEBOOK`, `SOCIAL_INSTAGRAM`, `SOCIAL_TIKTOK`, `SOCIAL_YOUTUBE` dans `.env`. Une icône sans URL n'apparaît pas.
- Les cartes prestataires n'ont pas encore de lien vers une fiche : elle arrive en phase 3.

## Interface client (phase 3)

| Page | URL |
|---|---|
| Recherche (filtres HTMX) | `/recherche/` |
| Catégorie | `/categorie/<slug>/` |
| Fiche prestataire | `/artisans/<slug>/` |
| Clic WhatsApp (compté, puis redirection `wa.me`) | `/artisans/<slug>/whatsapp/` |
| Demande de devis | `/artisans/<slug>/devis/` |
| Accueil client | `/mon-espace/` |
| Mes demandes / détail | `/mes-demandes/`, `/mes-demandes/<id>/` |
| Avis (création, modification 48 h) | `/mes-demandes/<id>/avis/`, `/avis/<id>/modifier/` |
| Favoris et recherches enregistrées | `/favoris/`, `/favoris/?onglet=recherches` |
| Signalement | `/signaler/provider/<id>/`, `/signaler/review/<id>/` |
| Compte, mot de passe, suppression | `/compte/profil/`, `/compte/mot-de-passe/modifier/`, `/compte/supprimer/` |

Points à connaître :
- Les filtres (ville, catégorie, spécialité, note, budget, vérifié, tri) fonctionnent aussi sans JavaScript : le formulaire reste un GET classique. Avec HTMX, seul le bloc `#results` est remplacé et l'URL est mise à jour.
- Une vue de fiche est comptée une fois par session et par prestataire ; le propriétaire ne gonfle pas ses chiffres. Un clic WhatsApp est compté une fois par session.
- Les numéros camerounais saisis sans indicatif reçoivent automatiquement `237` dans le lien WhatsApp. Le numéro n'est jamais affiché dans la page.
- Toute transition de statut d'une demande passe par `apps/requests_app/services.py` (transitions valides uniquement, notification à l'autre partie). Le dashboard prestataire (phase 4) réutilisera ces fonctions.
- Supprimer son compte anonymise l'utilisateur (e-mail, nom, téléphone, favoris) et conserve ses avis sous « Client Kora ».
- Limites : 10 demandes de devis par jour et par client, 5 photos de 5 Mo maximum par demande, 30 recherches enregistrées.
- Le bouton « Envoyer un message » de la fiche ouvre (ou retrouve) la conversation avec le prestataire.

## Dashboard prestataire (phase 4)

Espace `/prestataire/`, onglets : tableau de bord, profil, portfolio, services, disponibilités et zones, demandes, messages, avis, statistiques, vérification, notifications, paramètres.

- Tableau de bord : vues, clics WhatsApp, demandes reçues et acceptées, note, taux de réponse, courbe sur 30 jours (Chart.js), dernières demandes, liste de complétion du profil.
- Profil : les champs propres au métier viennent des `CategoryField` définis par l'admin. Changer de métier crée une demande (`pending_category`) que l'admin valide ; le profil garde son ancien métier d'ici là.
- Portfolio : envoi multiple, légendes, réordonnancement, suppression. Chaque image est contrôlée par Pillow, réduite à 1600 px au plus et ré-encodée (les métadonnées EXIF disparaissent). Le nombre de photos et le poids maximal se règlent dans le back-office.
- Demandes : filtres par statut, acceptation, refus avec motif, envoi de devis, passage en cours puis terminé. Tout passe par `apps/requests_app/services.py`, donc le client est prévenu à chaque étape. Un profil non actif peut consulter ses demandes mais pas y répondre.
- Les statistiques journalières (`ProviderDailyStat`) sont alimentées à chaque vue de fiche et clic WhatsApp. Elles commencent à l'installation de cette phase : l'historique d'avant n'existe pas.
- Vérification : pièce d'identité (PDF, JPG, PNG, contrôlée sur le contenu réel du fichier) et preuve d'activité facultative. Un seul dossier en cours à la fois.

## Messagerie et notifications (phase 5)

- `/messages/` : liste des conversations avec compteur de non-lus, fil de discussion (rafraîchi toutes les 10 s par HTMX, sans WebSocket), pièce jointe image, 2000 caractères maximum, 20 messages par minute.
- Une seule conversation par couple client/prestataire. Un message notifie le destinataire une seule fois tant qu'il n'a pas lu la conversation.
- `/notifications/` : liste, ouverture d'une notification (la marque lue puis redirige vers une URL locale uniquement), « tout marquer comme lu ». La cloche et les badges du menu se mettent à jour à chaque page.
- Les pages partagées (messagerie, notifications, changement de mot de passe) prennent le gabarit du rôle connecté : navbar client, shell prestataire ou shell admin.

## Back-office administrateur (phase 6)

Espace `/back-office/`. Menu brun repliable avec pastilles (profils à valider, vérifications, signalements), recherche globale en haut.

| Onglet | Ce qu'on y fait |
|---|---|
| Tableau de bord | KPI, courbes d'inscriptions, répartition des demandes, prestataires par catégorie et par ville, activité récente, export CSV des indicateurs |
| Clients | Recherche, filtres, tri, détail avec historique, suspension, réactivation, suppression, export CSV |
| Prestataires | File de validation (valider ou refuser avec motif), changements de métier à approuver, badge vérifié, mise en avant, suspension, édition, export CSV |
| Vérifications | Consultation des pièces, approbation (attribue le badge) ou refus motivé |
| Catégories et champs | CRUD des catégories, des spécialités et des champs spécifiques (texte, nombre, choix, case à cocher) |
| Villes et quartiers | CRUD, activation. Une ville utilisée par des prestataires ne se supprime pas, elle se désactive |
| Demandes | Supervision, annulation motivée, message de médiation aux deux parties, export CSV |
| Avis | Masquer, rétablir, supprimer ; filtres signalés, notes basses, masqués. La note du prestataire est recalculée |
| Signalements | Traitement (résolu avec action éventuelle sur la cible, ou rejeté) ; l'auteur est prévenu |
| Contenu | Bannières, pages statiques, FAQ, prestataires mis en avant |
| Communication | Annonce à tous, aux clients ou aux prestataires ; notification ciblée par e-mail |
| Équipe | Création des membres, rôles par groupe Django, activation |
| Journal d'audit | Qui, quoi, quand, IP, avant/après ; filtres et export CSV |
| Paramètres | Slogan, WhatsApp et e-mail de contact, poids maximal des images, photos maximum par portfolio |

Règles appliquées partout :
- Toute action sensible est un POST protégé par CSRF, précédé d'une modale de confirmation, avec motif obligatoire quand il est transmis à l'intéressé.
- Chaque action écrit une ligne dans le journal d'audit (acteur, adresse IP, détail avant/après) et prévient la personne concernée par une notification.
- Les mots de passe provisoires ne sont jamais écrits dans le journal.
- Les exports CSV préfixent d'une apostrophe toute cellule commençant par `=`, `+`, `-` ou `@` (injection de formules Excel).

Permissions : une permission Django par module (`dashboard_admin.module_clients`, `module_providers`, etc.). Trois groupes sont créés automatiquement à la migration : **Administrateur complet**, **Modérateur**, **Support**. Un membre sans accès à un module n'en voit pas l'entrée au menu, et reçoit un 403 s'il en tape l'adresse. Seul un super-administrateur peut modifier un autre super-administrateur, et personne ne peut désactiver son propre compte.

## Sécurité et déploiement (phase 7)

En place :
- CSRF sur tous les formulaires et sur HTMX ; actions sensibles uniquement en POST ; déconnexion en POST.
- Isolation entre comptes vérifiée par des tests (demandes, conversations, avis, dashboards) : un identifiant d'un autre compte donne un 404.
- Contenus saisis par les utilisateurs échappés par les templates (test d'injection `<script>` sur les pages client, prestataire et admin). Le JSON-LD est échappé séparément.
- Téléversements : images validées et ré-encodées par Pillow, pièces de vérification contrôlées sur leurs premiers octets, tailles limitées.
- Les pièces d'identité sont stockées dans `private_media/`, hors de `MEDIA_ROOT`. Elles ne sont lisibles que par les administrateurs du module Prestataires, via une vue qui journalise chaque consultation.
- En-têtes : `Content-Security-Policy`, `Permissions-Policy`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`, `Cache-Control: private, no-store` sur toutes les zones connectées.
- Limitation de débit : connexion, OTP, envoi de messages, demandes de devis.
- Production (`DJANGO_DEBUG=False`) : cookies `Secure`, HSTS 30 jours, redirection HTTPS, clé secrète obligatoire.

À savoir avant de mettre en ligne :
1. La CSP autorise `'unsafe-inline'` et `'unsafe-eval'` pour les scripts, parce que la version standard d'Alpine.js exige `unsafe-eval` et que certaines pages embarquent des données JSON en ligne. Elle bloque quand même toute ressource externe. Passer à la version CSP d'Alpine et à des nonces la durcirait, au prix d'une réécriture des attributs Alpine.
2. Le serveur web doit servir `/media/` mais **jamais** `private_media/`. Sauvegarder les deux dossiers.
3. `check --deploy` ne signale que `SECURE_HSTS_PRELOAD`, laissé désactivé volontairement : l'inscription à la liste de préchargement est difficile à annuler.
4. `/django-admin/` reste monté pour les super-utilisateurs. Si le back-office suffit, retirer la ligne correspondante dans `config/urls.py`.
5. Les rafraîchissements de messagerie par polling suffisent pour quelques centaines d'utilisateurs simultanés. Au-delà, passer aux WebSockets (Channels).
6. Le cache de limitation de débit utilise le cache Django par défaut (mémoire locale). Avec plusieurs processus, configurer Redis ou Memcached, sinon chaque processus compte à part.

Variables d'environnement : voir `.env.example` (`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, `EMAIL_BACKEND`, `SMS_BACKEND`, `SUPPORT_WHATSAPP`, `SOCIAL_*`, `SECURE_SSL_REDIRECT`). `UPLOAD_MAX_MB` et `PORTFOLIO_MAX_ITEMS` ne sont plus que des valeurs de départ : les réglages du back-office les remplacent.

## Limites connues

- Traduction anglaise : les chaînes passent par gettext et le sélecteur de langue fonctionne, mais le fichier `.po` anglais n'est pas rédigé. L'interface reste en français.
- Aucun audit Lighthouse n'a été exécuté dans cet environnement. Les images sont en lazy loading, les polices sont locales et le CSS est minifié, mais les scores restent à mesurer sur votre hébergement.
- Un prestataire n'a qu'une ville de rattachement, plus des quartiers. La notion de « villes desservies » multiples demanderait un changement de modèle.
- Les bannières actives (3 au maximum) s'affichent en bandeau au-dessus du hero ; le hero lui-même reste fixe.
- L'envoi réel de SMS et d'e-mails dépend de vos fournisseurs : en développement tout passe par la console.

## Recette (liste de contrôle manuelle)

Réinitialiser les données avec `python manage.py seed_demo --reset` puis dérouler. Mot de passe de tous les comptes : `Kora2026!`.

**Visiteur**
- [ ] `/` s'affiche, les compteurs et les catégories sont réels ; la recherche « plombier » trouve des résultats, « zzzz » affiche « Aucun résultat ».
- [ ] Les filtres de recherche changent la liste sans recharger la page et l'URL reste partageable.
- [ ] Une fiche prestataire actif s'ouvre ; une fiche en attente donne un 404.
- [ ] `robots.txt` interdit `/back-office/`, `/prestataire/`, `/messages/`.

**Client** (`client@kora.cm`)
- [ ] Demande de devis avec photo : elle apparaît dans « Mes demandes ».
- [ ] Ajout et retrait d'un favori ; enregistrement d'une recherche.
- [ ] Bouton « Envoyer un message » : la conversation s'ouvre ; un message envoyé apparaît côté prestataire.
- [ ] Avis possible seulement sur une demande terminée, modifiable 48 h.
- [ ] Signalement d'un prestataire : visible côté admin.

**Prestataire** (`prestataire@kora.cm`)
- [ ] Le tableau de bord affiche les KPI et la courbe ; la liste de complétion renvoie vers les bonnes pages.
- [ ] Profil : modifier la description, cocher un champ propre au métier, demander un changement de métier (doit rester « en attente »).
- [ ] Portfolio : envoyer 2 photos, légender, déplacer, supprimer ; un fichier texte renommé en `.jpg` est refusé.
- [ ] Services : créer un service « Sur devis » et un service à prix fixe ; un prix fixe sans montant est refusé.
- [ ] Disponibilités : fermer le dimanche ; une fermeture avant l'ouverture est refusée ; le mode congés est pris en compte sur la fiche.
- [ ] Demandes : ouvrir une demande (elle passe en « Vue » et le client est notifié), envoyer un devis, accepter, démarrer, terminer.
- [ ] Avis : répondre publiquement à un avis.
- [ ] Vérification : envoyer un PDF ; un second envoi est refusé tant que le premier est en cours.

**Administrateur** (`admin@kora.cm`)
- [ ] Tableau de bord : chiffres cohérents avec les listes, graphiques visibles, export CSV.
- [ ] Prestataires : refuser une inscription sans motif (impossible), avec motif (le prestataire est notifié, une ligne apparaît dans l'audit) ; valider une autre (elle devient visible au public).
- [ ] Vérifications : ouvrir la pièce, approuver (badge visible sur la fiche), refuser avec motif.
- [ ] Catégories : créer un champ « choix » avec deux options ; il apparaît dans le profil des prestataires de la catégorie. Supprimer une catégorie utilisée est refusé.
- [ ] Avis : masquer un avis, vérifier que la note du prestataire est recalculée et que l'auteur est notifié.
- [ ] Signalements : traiter avec action (masquer l'avis) ; l'auteur du signalement est notifié.
- [ ] Communication : envoyer une annonce aux prestataires ; le prestataire de démo la voit dans ses notifications.
- [ ] Équipe : créer un membre « Support », se connecter avec : il ne voit pas Prestataires, Équipe, Audit, et obtient un 403 sur ces adresses.
- [ ] Audit : filtrer par acteur et par action, exporter.
- [ ] Paramètres : passer la limite de photos à 1 ; un prestataire ne peut plus en envoyer plus.

**Sécurité**
- [ ] Déconnecté, `/back-office/` renvoie vers la connexion ; connecté en client, il renvoie vers l'espace client.
- [ ] Les en-têtes `Content-Security-Policy` et `Cache-Control: private, no-store` sont présents sur `/back-office/` (outils de développement du navigateur).
- [ ] `python manage.py test` passe entièrement ; `python manage.py makemigrations --check` ne signale rien.
