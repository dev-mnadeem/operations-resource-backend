# Makefile Reference

Run `make` (no target) to print a quick summary. Full reference below.

---

## First-time setup

| Command | Description |
|---|---|
| `make setup-first-time` | Full one-shot local setup: migrate → groups → superuser → seed → Faker transactions |
| `make docker-setup` | Same as above, but runs inside the already-started dev container |

`setup-first-time` is idempotent — safe to re-run. Existing records are skipped via `get_or_create`; Faker transaction data accumulates on each run.

**Options** (pass via `make docker-manage CMD="setup_dev <flags>"`):

| Flag | Default | Description |
|---|---|---|
| `--username` | `admin` | Superuser username |
| `--password` | `admin1234` | Superuser password |
| `--email` | `admin@arcadian.local` | Superuser email |
| `--skip-migrate` | off | Skip running migrations |
| `--skip-seed` | off | Skip `seed_data`; only generate Faker transactions |

---

## Local development

These commands run directly on your machine using `uv run`.

### Server

| Command | Description |
|---|---|
| `make run` | Start the Django development server at `http://localhost:8000` |

### Database

| Command | Description |
|---|---|
| `make migrate` | Apply all pending migrations |
| `make makemigrations` | Generate new migration files from model changes |
| `make showmigrations` | Print migration status for every app |
| `make flush` | Wipe all data from the database (keeps schema) |

### Setup & fixtures

| Command | Description |
|---|---|
| `make superuser` | Interactive prompt to create a Django admin user |
| `make create-groups` | Create default role groups (Admin, Purchaser, etc.) |
| `make create-inventory` | Seed default Units of Measure, categories, and items |
| `make create-products` | Seed default product categories and products |
| `make seed-data` | Seed mock transactions (sales, purchases, demands) — run after the three commands above |
| `make collectstatic` | Collect static files into `STATIC_ROOT` |

Recommended first-run order:
```bash
make migrate
make superuser
make create-groups
make create-inventory
make create-products
make seed-data
```

### Django shell & apps

| Command | Description |
|---|---|
| `make shell` | Open the Django interactive shell |
| `make app` | Prompt for a name and scaffold a new app inside `apps/` |

### Code quality

| Command | Description |
|---|---|
| `make lint` | Run `ruff check` — report issues without changing files |
| `make lint-fix` | Run `ruff check --fix` — auto-fix safe issues |
| `make format` | Run `ruff format` — reformat all Python files |
| `make format-check` | Check formatting without making changes (used in CI) |
| `make fmt` | `lint-fix` + `format` in one step — use this before committing |

### Testing

| Command | Description |
|---|---|
| `make test` | Run the full Django test suite |

---

## Docker (dev — live reload)

These commands wrap `docker compose -f docker-compose.dev.yml`. See [`docs/docker.md`](docker.md) for the full Docker guide.

### Lifecycle

| Command | Description |
|---|---|
| `make docker-up` | Start Postgres + Django in the foreground (logs printed to terminal) |
| `make docker-up-d` | Start in detached/background mode |
| `make docker-down` | Stop and remove containers (data volume is preserved) |
| `make docker-build` | Rebuild the web image — required after `pyproject.toml` / `uv.lock` changes |
| `make docker-logs` | Tail logs from all running services |

### Inside the container

| Command | Description |
|---|---|
| `make docker-shell` | Open a `bash` shell inside the `web` container |
| `make docker-migrate` | Run `manage.py migrate` inside the container |
| `make docker-superuser` | Run `manage.py createsuperuser` inside the container |
| `make docker-seed` | Run `manage.py seed_data` inside the container |
| `make docker-manage CMD="<cmd>"` | Run any `manage.py` command inside the container |

**`docker-manage` examples:**
```bash
make docker-manage CMD="showmigrations"
make docker-manage CMD="makemigrations demands"
make docker-manage CMD="create_default_groups"
make docker-manage CMD="flush --noinput"
```
