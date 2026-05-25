PYTHON=uv run python
MANAGE=$(PYTHON) manage.py

# Docker compose files
DC=docker compose
DC_DEV=$(DC) -f docker-compose.dev.yml

.DEFAULT_GOAL := help
APPS_DIR=apps

help:
	@echo ""
	@echo "Local development:"
	@echo "  make run               Run development server"
	@echo "  make migrate           Apply migrations"
	@echo "  make makemigrations    Create migrations"
	@echo "  make shell             Django shell"
	@echo "  make superuser         Create superuser"
	@echo "  make create-groups     Create default role groups (Admin, Purchaser, etc.)"
	@echo "  make create-inventory  Create default inventory UOMs, Categories, and Items"
	@echo "  make create-products   Create default product Categories and Products"
	@echo "  make seed-data         Seed the database with mock transactions (sales, purchases)"
	@echo "  make collectstatic     Collect static files"
	@echo "  make test              Run tests"
	@echo "  make app               Create a new Django app"
	@echo "  make showmigrations    Show migration status"
	@echo "  make lint              Lint the codebase"
	@echo "  make lint-fix          Fix linting issues"
	@echo "  make format            Format the codebase"
	@echo "  make format-check      Check code formatting"
	@echo "  make fmt               Lint and format the codebase"
	@echo "  make flush             Flush the database"
	@echo ""
	@echo "First-time setup:"
	@echo "  make setup-first-time  Run migrate + groups + superuser + seed + Faker transactions"
	@echo "  make docker-setup      Same as above but inside the running dev container"
	@echo ""
	@echo "Docker (dev — live reload, no rebuild needed for code changes):"
	@echo "  make docker-up         Start all services with live reload (docker-compose.dev.yml)"
	@echo "  make docker-down       Stop and remove containers"
	@echo "  make docker-build      Rebuild the web image (needed after dep changes)"
	@echo "  make docker-logs       Tail logs from all services"
	@echo "  make docker-shell      Open a bash shell inside the web container"
	@echo "  make docker-migrate    Run migrations inside the web container"
	@echo "  make docker-superuser  Create superuser inside the web container"
	@echo "  make docker-seed       Seed the database inside the web container"
	@echo "  make docker-manage     Run any manage.py command: make docker-manage CMD='showmigrations'"
	@echo ""


run:
	$(MANAGE) runserver

migrate:
	$(MANAGE) migrate

makemigrations:
	$(MANAGE) makemigrations
showmigrations:
	$(MANAGE) showmigrations

shell:
	$(MANAGE) shell

superuser:
	$(MANAGE) createsuperuser

create-groups:
	$(MANAGE) create_default_groups

collectstatic:
	$(MANAGE) collectstatic --noinput

test:
	$(MANAGE) test

app:
	@read -p "App name: " name; \
	$(MANAGE) startapp $$name $(APPS_DIR)/$$name
lint:
	uv run ruff check .

lint-fix:
	uv run ruff check . --fix

format:
	uv run ruff format .

format-check:
	uv run ruff format . --check
fmt:
	make lint-fix
	make format
flush:
	$(MANAGE) flush --noinput

seed-data:
	$(MANAGE) seed_data

create-inventory:
	$(MANAGE) create_default_inventory

create-products:
	$(MANAGE) create_default_products

# ── First-time setup ──────────────────────────────────────────────────────────

setup-first-time:
	$(MANAGE) setup_dev

# ── Docker targets (uses docker-compose.dev.yml) ──────────────────────────────

docker-up:
	$(DC_DEV) up

docker-up-d:
	$(DC_DEV) up -d

docker-down:
	$(DC_DEV) down

docker-build:
	$(DC_DEV) build --no-cache web

docker-logs:
	$(DC_DEV) logs -f

docker-shell:
	$(DC_DEV) exec web bash

docker-migrate:
	$(DC_DEV) exec web uv run python manage.py migrate

docker-superuser:
	$(DC_DEV) exec web uv run python manage.py createsuperuser

docker-seed:
	$(DC_DEV) exec web uv run python manage.py seed_data

docker-manage:
	$(DC_DEV) exec web uv run python manage.py $(CMD)

docker-setup:
	$(DC_DEV) exec web uv run python manage.py setup_dev