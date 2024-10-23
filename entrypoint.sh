#!/bin/bash

# Wait for PostgreSQL to be available
while ! nc -z db 5432; do
  echo "Waiting for PostgreSQL..."
  sleep 1
done

# Apply database migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn to serve the Django app
gunicorn techcity.wsgi:application --bind 0.0.0.0:8000 --workers 4

# Start NGINX
nginx -g 'daemon off;'
