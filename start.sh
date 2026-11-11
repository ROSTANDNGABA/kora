#!/usr/bin/env bash
set -o errexit

echo "===> Application des migrations..."
python manage.py migrate --no-input

if [ "$SEED_DEMO" = "true" ]; then
    echo "===> Initialisation des données de démo..."
    python manage.py seed_demo || true
fi

echo "===> Démarrage de Gunicorn sur 0.0.0.0:${PORT:-8000}..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
