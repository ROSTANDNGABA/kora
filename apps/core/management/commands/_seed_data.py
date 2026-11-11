"""Données statiques utilisées par seed_demo (catalogue, noms, textes)."""

CATEGORIES = [
    {
        "name": "Couture & Stylisme", "slug": "couture-stylisme", "icon": "scissors", "color": "#F36F21",
        "description": "Couturiers, stylistes et modélistes pour vos tenues sur mesure, retouches et créations.",
        "subs": ["Couturiers", "Couturières", "Stylistes", "Retouches", "Modélistes"],
        "fields": [
            ("Types de vêtements", "types_vetements", "TEXT", ""),
            ("Tissus travaillés", "tissus", "TEXT", ""),
            ("Sur mesure", "sur_mesure", "BOOLEAN", ""),
            ("Délai moyen (jours)", "delai_moyen", "NUMBER", ""),
        ],
    },
    {
        "name": "Coiffure & Esthétique", "slug": "coiffure-esthetique", "icon": "sparkles", "color": "#E91E63",
        "description": "Coiffeuses, barbiers, maquilleuses et esthéticiennes, au salon ou à domicile.",
        "subs": ["Coiffeuse", "Barbier", "Maquilleuse", "Esthéticienne", "Manucure"],
        "fields": [
            ("Types de coiffures", "types_coiffures", "TEXT", ""),
            ("Lieu de prestation", "lieu", "CHOICE", "Domicile\nSalon\nDomicile et salon"),
        ],
    },
    {
        "name": "Cuisine & Pâtisserie", "slug": "cuisine-patisserie", "icon": "chef-hat", "color": "#F5B800",
        "description": "Chefs, pâtissiers et traiteurs pour vos repas, gâteaux et événements.",
        "subs": ["Chef cuisinier", "Pâtissier", "Traiteur"],
        "fields": [
            ("Spécialités", "specialites", "TEXT", ""),
            ("Nombre de convives max", "convives", "NUMBER", ""),
            ("Événements", "evenements", "BOOLEAN", ""),
        ],
    },
    {
        "name": "Menuiserie & Bricolage", "slug": "menuiserie-bricolage", "icon": "hammer", "color": "#8B5A2B",
        "description": "Menuisiers, ébénistes et bricoleurs : meubles, portes, réparations.",
        "subs": ["Menuisier", "Ébéniste", "Bricoleur"],
        "fields": [
            ("Matériaux", "materiaux", "TEXT", ""),
            ("Fabrication sur mesure", "sur_mesure", "BOOLEAN", ""),
            ("Réparations", "reparations", "BOOLEAN", ""),
        ],
    },
    {
        "name": "Peinture & Décoration", "slug": "peinture-decoration", "icon": "paintbrush", "color": "#7C4DFF",
        "description": "Peintres, décorateurs et plâtriers pour embellir vos intérieurs et façades.",
        "subs": ["Peintre", "Décorateur", "Plâtrier / faux plafond"],
        "fields": [
            ("Types de chantiers", "chantiers", "TEXT", ""),
            ("Fournitures incluses", "fournitures", "BOOLEAN", ""),
        ],
    },
    {
        "name": "Poterie & Sculpture", "slug": "poterie-sculpture", "icon": "shapes", "color": "#C2571A",
        "description": "Potiers, sculpteurs et artisans d'art : pièces uniques et commandes personnalisées.",
        "subs": ["Potier", "Sculpteur", "Artisan d'art"],
        "fields": [
            ("Matières", "matieres", "TEXT", ""),
            ("Type de production", "production", "CHOICE", "Pièces uniques\nSéries\nPièces uniques et séries"),
            ("Commandes personnalisées", "personnalise", "BOOLEAN", ""),
        ],
    },
    {
        "name": "Services Numériques", "slug": "services-numeriques", "icon": "monitor-smartphone", "color": "#2F80ED",
        "description": "Développeurs, designers et experts marketing pour votre présence en ligne.",
        "subs": ["Développeur", "Designer", "Marketing"],
        "fields": [
            ("Technologies", "technologies", "TEXT", ""),
            ("Lien du portfolio", "portfolio_url", "TEXT", ""),
            ("Mode de travail", "mode", "CHOICE", "Freelance\nAgence"),
            ("Télétravail possible", "teletravail", "BOOLEAN", ""),
        ],
    },
    {
        "name": "Mécanique & Électricité", "slug": "mecanique-electricite", "icon": "wrench", "color": "#5B9E2D",
        "description": "Mécaniciens, électriciens, frigoristes et dépanneurs auto.",
        "subs": ["Mécanicien", "Électricien", "Frigoriste", "Dépanneur auto"],
        "fields": [
            ("Types d'interventions", "interventions", "TEXT", ""),
            ("Urgences", "urgence", "BOOLEAN", ""),
            ("Déplacement", "deplacement", "BOOLEAN", ""),
        ],
    },
    {
        "name": "Plomberie", "slug": "plomberie", "icon": "droplets", "color": "#1D9BF0",
        "description": "Plombiers, chauffagistes et dépanneurs pour fuites, installations et sanitaires.",
        "subs": ["Plombier", "Chauffagiste", "Dépannage"],
        "fields": [
            ("Urgence 24/7", "urgence_24_7", "BOOLEAN", ""),
            ("Déplacement", "deplacement", "BOOLEAN", ""),
            ("Types de pannes", "pannes", "TEXT", ""),
        ],
    },
    {
        "name": "Maçonnerie & Construction", "slug": "maconnerie-construction", "icon": "brick-wall", "color": "#6B7280",
        "description": "Maçons, entrepreneurs et équipes de rénovation pour vos chantiers.",
        "subs": ["Maçon", "Entrepreneur", "Rénovation"],
        "fields": [
            ("Types de chantiers", "chantiers", "TEXT", ""),
            ("Taille de l'équipe", "equipe", "NUMBER", ""),
            ("Devis sur visite", "devis_visite", "BOOLEAN", ""),
        ],
    },
]

CITIES = [
    ("Yaoundé", "Centre", ["Bastos", "Mvan", "Biyem-Assi", "Mendong", "Essos", "Nlongkak"]),
    ("Douala", "Littoral", ["Akwa", "Bonanjo", "Bonapriso", "Makepe", "Bonamoussadi", "Deido"]),
    ("Bafoussam", "Ouest", ["Tamdja", "Djeleng", "Kamkop"]),
    ("Dschang", "Ouest", ["Foto", "Fokoué"]),
    ("Bamenda", "Nord-Ouest", ["Up Station", "Commercial Avenue", "Mankon"]),
    ("Maroua", "Extrême-Nord", ["Domayo", "Kakataré"]),
    ("Ngaoundéré", "Adamaoua", ["Dang", "Joli Soir"]),
    ("Buea", "Sud-Ouest", ["Molyko", "Great Soppo"]),
    ("Bertoua", "Est", ["Mokolo", "Nkolbikon"]),
]
CITY_WEIGHTS = [5, 5, 2, 1, 2, 1, 1, 1, 1]
ENGLISH_CITIES = {"Bamenda", "Buea"}

FIRST_F = ["Chantal", "Pauline", "Carine", "Estelle", "Nadège", "Sandrine", "Rosine", "Flora", "Mireille", "Solange", "Brigitte", "Aïcha", "Larissa", "Josiane", "Clarisse", "Ornella"]
FIRST_M = ["Jean-Pierre", "Paul", "Emmanuel", "Serge", "Hervé", "Landry", "Brice", "Ghislain", "Christian", "Patrick", "Armand", "Boris", "Rodrigue", "Arnaud", "Léonard", "Cyrille"]
LAST = ["Mballa", "Nguemo", "Tchoumi", "Fotso", "Kamga", "Ndongo", "Essomba", "Mbarga", "Tchatchouang", "Nkeng", "Ngono", "Atangana", "Njoya", "Biyong", "Kouam", "Talla", "Tagne", "Hamadou", "Abba", "Onana"]
LAST_EN = ["Fon", "Ndi", "Awah", "Tabi", "Mbah", "Ewane", "Achu", "Fomum"]

BUSINESS_FORMS = {
    "couture-stylisme": ["Atelier {L}", "Couture {L}", "Mode {F}"],
    "coiffure-esthetique": ["Salon {F}", "Beauté {L}", "Chez {F}"],
    "cuisine-patisserie": ["Délices de {F}", "Saveurs {L}", "Traiteur {L}"],
    "menuiserie-bricolage": ["Menuiserie {L}", "Bois & Fils {L}", "Atelier du Bois {L}"],
    "peinture-decoration": ["Couleurs {L}", "Déco {L}", "Peinture {L} & Fils"],
    "poterie-sculpture": ["Terre & Feu {L}", "Atelier d'Art {L}", "Argile {F}"],
    "services-numeriques": ["{L} Digital", "WebStudio {L}", "{F} Tech"],
    "mecanique-electricite": ["Garage {L}", "Électro {L}", "Auto Service {L}"],
    "plomberie": ["Plomberie {L}", "{L} Dépannage", "Aqua {L}"],
    "maconnerie-construction": ["Bâtiment {L}", "Construction {L} & Fils", "Maçonnerie {L}"],
}

DESCRIPTIONS = {
    "couture-stylisme": "Tenues sur mesure, pagnes et wax, robes de cérémonie et retouches soignées. Plus de dix ans d'expérience.",
    "coiffure-esthetique": "Tresses, tissages, coupes et soins. Je me déplace aussi à domicile pour mariages et événements.",
    "cuisine-patisserie": "Cuisine camerounaise et pâtisserie fine pour vos repas de famille, baptêmes et mariages.",
    "menuiserie-bricolage": "Fabrication de meubles, portes, placards et petites réparations, avec du bois de qualité.",
    "peinture-decoration": "Peinture intérieure et extérieure, enduits, faux plafonds et conseils déco pour toute la maison.",
    "poterie-sculpture": "Poteries, sculptures et objets décoratifs façonnés à la main, pièces uniques ou commandes personnalisées.",
    "services-numeriques": "Sites web, applications, identité visuelle et gestion des réseaux sociaux pour artisans et PME.",
    "mecanique-electricite": "Diagnostic, entretien et dépannage rapide, installations électriques aux normes.",
    "plomberie": "Fuites, installations sanitaires, chauffe-eau et dépannage. Intervention rapide et devis clair.",
    "maconnerie-construction": "Fondations, élévation, dallage et rénovation. Équipe sérieuse, chantiers suivis de bout en bout.",
}

SERVICES = {
    "couture-stylisme": [("Robe de cérémonie sur mesure", "FROM", 25000, 60000, 7200), ("Chemise en pagne", "FIXED", 8000, 15000, 2880), ("Retouche (ourlet, ajustement)", "FIXED", 1500, 5000, 120)],
    "coiffure-esthetique": [("Tresses africaines", "FROM", 5000, 15000, 240), ("Coupe et brushing", "FIXED", 3000, 8000, 90), ("Maquillage de mariée", "FROM", 20000, 50000, 120)],
    "cuisine-patisserie": [("Gâteau d'anniversaire", "FROM", 15000, 40000, 1440), ("Buffet pour 50 personnes", "QUOTE", 0, 0, 480), ("Plat du jour livré", "FIXED", 2500, 6000, 60)],
    "menuiserie-bricolage": [("Porte en bois massif", "FROM", 60000, 150000, 4320), ("Placard sur mesure", "QUOTE", 0, 0, 2880), ("Petite réparation", "FIXED", 3000, 10000, 60)],
    "peinture-decoration": [("Peinture d'une pièce", "FROM", 30000, 80000, 1440), ("Faux plafond (le m²)", "FIXED", 4000, 8000, 480), ("Conseil déco à domicile", "FIXED", 10000, 25000, 90)],
    "poterie-sculpture": [("Vase en terre cuite", "FIXED", 7000, 25000, 4320), ("Sculpture sur commande", "QUOTE", 0, 0, 10080), ("Atelier initiation poterie", "FIXED", 10000, 20000, 180)],
    "services-numeriques": [("Site vitrine", "FROM", 150000, 400000, 14400), ("Logo et charte graphique", "FROM", 40000, 120000, 4320), ("Gestion des réseaux sociaux (mois)", "FIXED", 50000, 150000, 0)],
    "mecanique-electricite": [("Diagnostic complet", "FIXED", 5000, 15000, 60), ("Installation électrique", "QUOTE", 0, 0, 480), ("Vidange et entretien", "FROM", 12000, 30000, 90)],
    "plomberie": [("Réparation de fuite", "FROM", 5000, 20000, 90), ("Installation sanitaire", "QUOTE", 0, 0, 480), ("Débouchage canalisation", "FIXED", 8000, 20000, 60)],
    "maconnerie-construction": [("Dallage / chape (le m²)", "FIXED", 3000, 6000, 480), ("Construction de mur", "QUOTE", 0, 0, 4320), ("Rénovation de salle de bain", "FROM", 150000, 400000, 10080)],
}

FIELD_TEXT = {
    "types_vetements": ["Robes, chemises, costumes, tenues de cérémonie", "Pagnes, kabas, tenues traditionnelles", "Uniformes et tenues d'entreprise"],
    "tissus": ["Wax, bazin, soie", "Pagne, coton, lin", "Tissus africains et importés"],
    "types_coiffures": ["Tresses, tissages, vanilles", "Coupes, coloration, lissage", "Coiffures de mariée et soins"],
    "specialites": ["Ndolé, poulet DG, poisson braisé", "Gâteaux de mariage, beignets, viennoiseries", "Cuisine camerounaise et internationale"],
    "materiaux": ["Iroko, moabi, ayous", "Bois local et contreplaqué", "Bois massif et métal"],
    "chantiers": ["Maisons, bureaux, façades", "Rénovation et finitions", "Villas et immeubles"],
    "matieres": ["Argile, terre cuite", "Bois, bronze, pierre", "Raphia, perles, calebasse"],
    "technologies": ["Django, React, PostgreSQL", "WordPress, Figma, SEO", "Flutter, Node.js, Firebase"],
    "portfolio_url": ["https://exemple.cm/portfolio"],
    "interventions": ["Climatisation, groupes électrogènes, tableaux", "Moteur, freins, suspension", "Câblage, éclairage, dépannage"],
    "pannes": ["Fuites, chasse d'eau, chauffe-eau", "Canalisations bouchées, robinetterie", "Pompes et surpresseurs"],
}

NEEDS = {
    "couture-stylisme": "Bonjour, je voudrais une tenue de cérémonie pour un mariage le mois prochain. Pouvez-vous me proposer un devis ?",
    "coiffure-esthetique": "Bonjour, je cherche une coiffeuse pour des tresses ce week-end, si possible à domicile.",
    "cuisine-patisserie": "Bonjour, j'organise un anniversaire pour 30 personnes et j'ai besoin d'un gâteau et d'un buffet.",
    "menuiserie-bricolage": "Bonjour, j'ai besoin d'un placard sur mesure pour ma chambre. Je peux envoyer les dimensions.",
    "peinture-decoration": "Bonjour, je souhaite repeindre mon salon et deux chambres. Quel serait le prix ?",
    "poterie-sculpture": "Bonjour, je voudrais des vases décoratifs personnalisés pour ma boutique.",
    "services-numeriques": "Bonjour, je veux un site vitrine pour mon commerce avec un catalogue de produits.",
    "mecanique-electricite": "Bonjour, mon installation disjoncte souvent. Pouvez-vous passer faire un diagnostic ?",
    "plomberie": "Bonjour, j'ai une fuite sous mon évier depuis hier. Pouvez-vous intervenir rapidement ?",
    "maconnerie-construction": "Bonjour, je veux faire construire un mur de clôture de 20 mètres. Pouvez-vous venir voir le terrain ?",
}

REVIEWS = {
    5: ["Travail impeccable, ponctuel et très professionnel. Je recommande vivement.", "Excellent résultat, au-delà de mes attentes. Merci !", "Très bon contact, prix correct et résultat parfait."],
    4: ["Très bien dans l'ensemble, petit retard mais le résultat est au rendez-vous.", "Bon travail et bon rapport qualité-prix. Je referai appel à lui.", "Sérieux et à l'écoute, je suis satisfait."],
    3: ["Correct, mais quelques détails à améliorer. Délai un peu long.", "Le travail est fait, sans plus. Communication à améliorer."],
    2: ["Le résultat ne correspond pas tout à fait à ce qui était convenu.", "Beaucoup de retard, dommage."],
    1: ["Très déçu, le rendez-vous n'a pas été respecté.", "Qualité insuffisante par rapport au prix payé."],
}
REPLIES = ["Merci beaucoup pour votre confiance, au plaisir de vous revoir !", "Merci pour votre retour, c'était un plaisir de travailler pour vous.", "Merci ! N'hésitez pas à me recontacter pour vos prochains projets."]

CHAT = [
    ("client", "Bonjour, êtes-vous disponible cette semaine ?"),
    ("provider", "Bonjour ! Oui, je peux passer jeudi après-midi. Quelle est votre adresse ?"),
    ("client", "Je suis à Bonamoussadi, près du carrefour. Je vous envoie une photo."),
    ("provider", "Parfait, merci. Je vous envoie un devis dans la soirée."),
    ("client", "Super, merci beaucoup !"),
]

FAQ = [
    ("Comment trouver un artisan sur Kora ?", "Choisissez une catégorie ou tapez un métier et une ville dans la barre de recherche, puis comparez les profils, les avis et les réalisations."),
    ("Kora est-il gratuit pour les clients ?", "Oui. Rechercher, contacter un prestataire et demander un devis sont gratuits."),
    ("Comment devenir artisan sur Kora ?", "Créez un compte artisan, choisissez votre métier et complétez votre profil. Notre équipe le valide avant sa publication."),
    ("Comment sont vérifiés les prestataires ?", "Les prestataires peuvent déposer une pièce d'identité et un justificatif d'activité. Après contrôle manuel, ils reçoivent le badge « vérifié »."),
    ("Puis-je laisser un avis ?", "Oui, une fois la prestation terminée. Vous disposez de 48 h pour modifier votre avis."),
    ("Mon numéro de téléphone est-il visible ?", "Non. Les échanges passent par WhatsApp ou par la messagerie de Kora."),
]

STATIC_PAGES = [
    ("a-propos", "À propos de Kora", "Kora met en relation les clients et les artisans du Cameroun. Notre mission : donner de la visibilité au savoir-faire local et rendre la recherche d'un professionnel simple et fiable."),
    ("cgu", "Conditions générales d'utilisation", "Texte de démonstration. Les conditions générales d'utilisation définitives seront rédigées et validées avant le lancement."),
    ("confidentialite", "Politique de confidentialité", "Texte de démonstration. Kora collecte uniquement les données nécessaires au service et ne publie jamais votre numéro de téléphone."),
]
