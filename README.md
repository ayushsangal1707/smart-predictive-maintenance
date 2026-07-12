# Smart Predictive Maintenance System

A Django-based predictive maintenance platform built for a BHEL internship project. It tracks industrial machines, ingests sensor data, predicts failure risk with a trained ML model, and manages the resulting maintenance workflow end-to-end — from a sensor reading, to a risk prediction, to a scheduled repair, to a report.

## Features

- **Authentication & Roles** — Admin / Engineer / Manager, with role-based access control throughout
- **Machine Management** — full CRUD, search, filters, pagination
- **Sensor Data** — manual entry, CSV/Excel upload (with per-row validation and error reporting), reading history with filters and charts
- **Predictive Maintenance (ML)** — Random Forest / Decision Tree classifier (scikit-learn), trained offline, with feature engineering (rolling mean/std, rate of change) on real sensor history
- **Dashboard** — plant-wide health overview, risk distribution, monthly reports, live sensor trend charts, search & filters
- **Maintenance Management** — requests, engineer assignment, scheduling, status workflow, comments, unified history timeline, in-app notifications
- **Reports & Exports** — CSV, Excel, and PDF (plant summary) exports
- **Email Alerts** — critical-risk predictions and maintenance assignments, with per-user opt-out
- **Audit Logging** — who did what, when, from where — searchable and filterable, Admin-only
- **Dark Mode**, a **Settings** page, and the usual **Profile** page

## Tech Stack

- **Backend:** Django 6, PostgreSQL
- **ML:** scikit-learn, pandas, NumPy, joblib
- **Frontend:** Bootstrap 5, Chart.js, vanilla JS (no build step)
- **Reports:** reportlab (PDF), openpyxl/pandas (Excel/CSV)
- **Deployment:** Docker, Gunicorn, WhiteNoise

## Project Structure

```
config/            Project settings (base/dev/prod), root URLs
core/               Shared base template, middleware, audit log, email/rate-limit utilities
accounts/           Auth, roles, profile, settings
equipment/           Machine (equipment) CRUD
sensors/            Sensor definitions + readings, CSV/Excel upload
predictions/        ML pipeline (predictions/ml/) + Django integration
dashboard/           Plant-wide dashboard
maintenance/        Maintenance requests, notifications
reports/            CSV/Excel/PDF export
```

Each app follows the same internal layout: `models.py`, `views.py`, `forms.py`, `urls.py`, `admin.py`, `templates/<app>/`.

## Local Setup (without Docker)

1. **Clone and enter the project, create a virtualenv:**
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # edit .env: set a real DJANGO_SECRET_KEY, DB credentials, etc.
   ```

3. **Set up PostgreSQL** (or point `.env` at an existing instance), then:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. **Register the trained ML model** (bundled in `predictions/ml/model_registry/`):
   ```bash
   python manage.py load_model_version v1
   ```

5. **Run it:**
   ```bash
   python manage.py runserver
   ```
   Visit `http://127.0.0.1:8000`. `DJANGO_SETTINGS_MODULE` defaults to `config.settings.dev` (see `manage.py`).

## Running with Docker

```bash
cp .env.example .env   # fill in real values
docker compose up --build
```
This starts PostgreSQL and the Django app (via Gunicorn + WhiteNoise), running migrations and `collectstatic` automatically on startup. See **DEPLOYMENT.md** for production details.

## Retraining the ML Model

```bash
python predictions/ml/train.py
python manage.py load_model_version v2   # registers the new version as active
```
`train.py` explains every step (data generation, feature engineering, train/test split, evaluation) in its own output.
## Running Tests

```bash
python manage.py test
```
56 tests covering models, forms, views, permissions, the ML prediction pipeline (using the real bundled model), and a full end-to-end integration test that walks through the entire workflow: create machine → define sensors → upload readings → run prediction → raise maintenance request → assign → complete → export report.

## Default Roles

| Role | Can do |
|---|---|
| **Admin** | Everything, including audit logs and model management |
| **Manager** | View everything, assign engineers, manage maintenance requests |
| **Engineer** | Manage machines/sensors, run predictions, work assigned maintenance requests |

## License

Internal BHEL internship project — not licensed for external distribution.
