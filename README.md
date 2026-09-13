# Benjamin Locher Music

An album-first public music catalog and private release studio for Benjamin Locher. The application syncs Suno playlists as albums, manages approved audio downloads, edits metadata and timed lyrics, and prepares/releases catalog updates through Too Lost.

## Stack

- Django + Django REST Framework
- React + TypeScript + Vite
- PostgreSQL
- Celery + Redis
- Nginx and systemd in production

## Local setup

```bash
cp .env.example .env
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
python backend/manage.py migrate
python backend/manage.py createsuperuser
python backend/manage.py runserver
```

Run `npm run dev --prefix frontend` in another terminal. The Vite dev server proxies `/api` to Django.

## Integration posture

Suno has no supported account API. The app stores an encrypted session ID and cookie captured from a Suno session, refreshes short-lived bearer tokens, limits sync traffic, imports playlists only, and requires a deliberate confirmation before requesting or saving audio. Suno credentials and passwords are never requested by the app.

Too Lost uses OAuth 2.0 and a versioned REST API. Register the deployment in the Too Lost developer portal, then configure a sandbox access token in Studio → Integrations. Submission payloads are stored as immutable snapshots for auditing and retry safety.

## Deployment

Production follows the Daily Office host pattern: push to a bare Git repository on the Linode host; its post-receive hook checks out the tree, installs Python and Node dependencies, builds React, migrates and collects static files, then restarts Gunicorn and Celery via systemd. See `deploy/`.
