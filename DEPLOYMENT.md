# Deployment Guide

## 1. Environment Variables

Copy `.env.example` to `.env` and fill in real values. Reference:

| Variable | Required in prod | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | Long, random, unique. `config/settings/prod.py` refuses to start without one |
| `DJANGO_DEBUG` | Yes | Must be `False` in production |
| `DJANGO_ALLOWED_HOSTS` | Yes | Comma-separated domain(s), e.g. `maintenance.example.com` |
| `CSRF_TRUSTED_ORIGINS` | If serving over a custom HTTPS domain | Comma-separated, full origin including scheme |
| `DJANGO_SECURE_SSL_REDIRECT` | No | Defaults `True`; only set `False` if TLS is terminated somewhere Django can't detect via `X-Forwarded-Proto` |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | Yes | PostgreSQL connection |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `DEFAULT_FROM_EMAIL` | For email alerts & password reset | Any standard SMTP provider |

`config/settings/prod.py` raises `ImproperlyConfigured` at startup if `DJANGO_SECRET_KEY` or `DJANGO_ALLOWED_HOSTS` are missing — this is intentional, to prevent an accidental insecure deploy.

## 2. Docker Compose (recommended)

```bash
cp .env.example .env    # fill in real values
docker compose up --build -d
```

What happens on `web` container start (`docker/entrypoint.sh`):
1. Waits for PostgreSQL to accept connections
2. Runs `python manage.py migrate --noinput`
3. Runs `python manage.py collectstatic --noinput` (WhiteNoise serves the result directly)
4. Hands off to Gunicorn (3 workers by default — tune via the `CMD` in `Dockerfile` for your CPU count)

**Create your first superuser and register the ML model** (one-time, after first startup):
```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py load_model_version v1
```

**View logs:**
```bash
docker compose logs -f web
```

**Persisted volumes:** `postgres_data` (database), `static_data` / `media_data`, and `model_registry` (so a container rebuild doesn't lose a retrained model).

## 3. Manual Deployment (VPS, no Docker)

1. Install Python 3.12, PostgreSQL, and a reverse proxy (nginx recommended).
2. `pip install -r requirements.txt` inside a virtualenv.
3. Set environment variables (via `.env`, or your process manager's env config).
4. `python manage.py migrate`
5. `python manage.py collectstatic --noinput`
6. `python manage.py load_model_version v1`
7. Run Gunicorn behind a process manager, e.g. systemd:
   ```ini
   [Unit]
   Description=Smart Predictive Maintenance
   After=network.target postgresql.service

   [Service]
   User=www-data
   WorkingDirectory=/opt/smart_predictive_maintenance
   EnvironmentFile=/opt/smart_predictive_maintenance/.env
   Environment=DJANGO_SETTINGS_MODULE=config.settings.prod
   ExecStart=/opt/smart_predictive_maintenance/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
8. Point nginx at `127.0.0.1:8000`, terminate TLS there (certbot/Let's Encrypt), and forward `X-Forwarded-Proto` — `prod.py` already trusts that header for HTTPS detection.

## 4. Post-Deployment Checklist

- [ ] `python manage.py check --deploy` returns no warnings against your real `.env`
- [ ] HTTPS is actually enforced (visit over `http://` and confirm the redirect)
- [ ] A real superuser exists; default/test accounts from local development are not present
- [ ] The ML model is registered and active (check `/admin/predictions/modelversion/`)
- [ ] Email sending works (trigger a password reset and confirm delivery)
- [ ] Database backups are configured (see below)
- [ ] `DEBUG=False` — visiting a URL that 404s should show Django's plain 404 page, not a traceback

## 5. Database Backups

```bash
# Docker Compose
docker compose exec db pg_dump -U postgres smart_maintenance_db > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T db psql -U postgres smart_maintenance_db < backup_20260711.sql
```
Automate via cron and ship backups off-host — this project doesn't include an automated backup service by design, since destinations/retention policies are deployment-specific.

## 6. Scaling Notes

- **Cache backend:** production settings default to Django's local-memory cache (used to cache the dashboard's expensive plant-wide aggregates for 60s). Fine for a single process; switch to Redis/Memcached once running multiple workers/machines so cache entries are shared.
- **Static files at scale:** WhiteNoise is sufficient for moderate traffic. At high traffic, have nginx or a CDN serve `/static/` directly instead of proxying every static request through Gunicorn.
- **Large exports:** `reports/generators.py` builds CSV/Excel exports fully in memory via pandas — fine at this project's scale; switch to streaming responses if exporting hundreds of thousands of rows becomes a requirement.
- **Database indexes:** already added on the fields each module filters/sorts by most (see each app's `models.py` `Meta.indexes`). Monitor slow queries in production and add more as real usage patterns emerge.
