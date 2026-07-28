#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."
python manage.py migrate --noinput
python manage.py check
exec python manage.py runserver "$@"
