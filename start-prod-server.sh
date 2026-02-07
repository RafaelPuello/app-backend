#!/bin/sh
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn backend.wsgi --bind 0.0.0.0:8002 --timeout 60 --access-logfile - --error-logfile -