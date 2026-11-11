#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py seed
# Creates the admin once; harmless if it already exists
python manage.py createsuperuser --noinput || true