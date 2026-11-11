#!/usr/bin/env bash
# Arrêter le script dès qu'une commande échoue
set -o errexit

echo "===> [1/5] Installation des dépendances Frontend (npm)..."
npm install

echo "===> [2/5] Compilation des assets Frontend (Tailwind & vendor)..."
npm run build

echo "===> [3/5] Installation des dépendances Python..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "===> [4/5] Collecte des fichiers statiques pour WhiteNoise..."
python manage.py collectstatic --no-input

echo "===> [5/5] Application des migrations de base de données..."
python manage.py migrate --no-input

# Initialisation optionnelle des données de test
if [ "$SEED_DEMO" = "true" ]; then
    echo "===> Initialisation des données de démo..."
    python manage.py seed_demo || true
fi

echo "===> Build terminé avec succès !"
