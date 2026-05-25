# Docker — Local Development Guide

## Overview

There are two compose files:

| File | Purpose |
|---|---|
| `docker-compose.yml` | Production-like: gunicorn, Celery worker and beat, Postgres, Redis. Migrates and collects static files on start. No source mount, so rebuild (`docker compose up -d --build`) to pick up code changes. Serves on `WEB_PORT` (default 8500). |
| `docker-compose.dev.yml` | **Development**. Mounts source code into the container so Django's auto-reloader reflects every file change instantly — no rebuild needed. |

**Use `docker-compose.dev.yml` for local development.** It runs only Postgres and the Django dev server; start the production-like file when you need Celery.

---

## First-time setup

### 1. Copy the environment file

```bash
cp .env.example .env
```

Open `.env` and fill in at least:

```env
SECRET_KEY=any-random-string-for-local-dev   # python3 scripts/generate_secret_key.py
DB_PASSWORD=change-me
DEV_ADMIN_PASSWORD=pick-one                  # optional; generated and printed if blank
```

> `DB_HOST` is overridden to `db` (the Postgres service) inside both compose files, so leave it as `127.0.0.1` in `.env`; it only matters when running outside Docker.

### 2. Build the image

Only needed once (or after changing `pyproject.toml` / `uv.lock`):

```bash
make docker-build
# or
docker compose -f docker-compose.dev.yml build
```

### 3. Start services

```bash
make docker-up
```

This starts Postgres and the Django dev server. Django waits for Postgres to be healthy before starting.

The server is available at **http://localhost:8000**
Postgres is exposed on **localhost:5433** (to avoid clashing with a local Postgres instance).

### 4. Set up the database and demo data

In a second terminal (while services are running):

```bash
make docker-setup          # migrate, groups, superuser, seed data, demo transactions
make docker-seed-history   # optional: 120 days of sales for replenishment advice
```

`docker-setup` prints the admin password unless `DEV_ADMIN_PASSWORD` is set.

Admin panel: **http://localhost:8000/admin** (user `admin`)

To create another superuser instead: `make docker-superuser`.

---

## Daily workflow

```bash
make docker-up          # start everything
# edit code — changes are live immediately, no rebuild needed
make docker-logs        # watch server logs
make docker-down        # stop when done
```

---

## Common tasks inside the container

| Task | Command |
|---|---|
| Open a shell | `make docker-shell` |
| Run migrations | `make docker-migrate` |
| Create superuser | `make docker-superuser` |
| Seed data | `make docker-seed` |
| Any manage.py command | `make docker-manage CMD="<command>"` |

### `docker-manage` examples

```bash
make docker-manage CMD="showmigrations"
make docker-manage CMD="makemigrations"
make docker-manage CMD="flush --noinput"
make docker-manage CMD="create_default_groups"
make docker-manage CMD="shell"
```

---

## When do you need to rebuild?

A rebuild (`make docker-build`) is only required when **Python dependencies change**, i.e. after editing `pyproject.toml` or `uv.lock`:

```bash
make docker-down
make docker-build
make docker-up
```

All other changes (Python files, templates, static files, migrations) are picked up automatically through the volume mount.

---

## Port reference

| Service | Host port | Container port |
|---|---|---|
| Django dev server | 8000 | 8000 |
| PostgreSQL | 5433 | 5432 |

---

## Resetting the database

To wipe the Postgres volume and start fresh:

```bash
docker compose -f docker-compose.dev.yml down -v
make docker-up-d
make docker-setup
```

---

## Troubleshooting

**`web` container exits immediately**
Check logs: `make docker-logs`. Usually means Postgres isn't ready yet or `.env` is missing/misconfigured.

**Port 8000 already in use**
Either stop the local Django server (`Ctrl+C`) or change the host port in `docker-compose.dev.yml`:
```yaml
ports:
  - "8001:8000"
```

**Dependency changes not reflected**
Dependencies are baked into the image, not the volume. Run `make docker-build` after any `pyproject.toml` / `uv.lock` change.

**Permission errors on mounted files (Linux)**
Add `user: "${UID}:${GID}"` under the `web` service in `docker-compose.dev.yml` and export those vars in your shell (`export UID GID`).
