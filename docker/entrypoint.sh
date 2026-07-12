#!/bin/sh
set -e

echo "Waiting for database at ${DB_HOST:-db}:${DB_PORT:-5432}..."
attempt=0
max_attempts=30
until python -c "
import socket, sys, os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect((os.environ.get('DB_HOST', 'db'), int(os.environ.get('DB_PORT', 5432))))
    s.close()
except OSError:
    sys.exit(1)
" ; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$max_attempts" ]; then
        echo "Database did not become available in time. Exiting."
        exit 1
    fi
    echo "Database not ready yet (attempt $attempt/$max_attempts) — retrying in 2s..."
    sleep 2
done
echo "Database is up."

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Startup checks complete. Handing off to: $*"
exec "$@"
