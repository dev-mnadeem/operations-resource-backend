# Arcadian ERP - Backend

This implies the backend service for the Arcadian ERP system. It is built using Django and Django Rest Framework, featuring a customized admin interface powered by Jazzmin.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Running the Project](#running-the-project)
- [Data Seeding](#data-seeding)
- [Deploying to Heroku](#deploying-to-heroku)
- [Core Features & Modules](#core-features--modules)
- [Code Quality & Linting](#code-quality--linting)
- [Pre-commit Hooks](#pre-commit-hooks)
- [CI/CD](#cicd)
- [Project Structure](#project-structure)

## Prerequisites

- [Python](https://www.python.org/) (>= 3.12)
- [PostgreSQL](https://www.postgresql.org/) (Recommended database)
- [uv](https://github.com/astral-sh/uv) (Recommended for dependency management)

## Installation

1. **Clone the repository:**

   ```bash
   git clone <repository_url>
   cd arcadian-be
   ```

2. **Set up the environment:**

   ```bash
   cp .env.example .env
   ```

3. **Install dependencies:**
   ```bash
   uv sync
   ```
   _Note: This project uses uv; a virtual environment is created automatically._

## Environment Variables

This project uses a `.env` file to store sensitive settings such as database credentials, secret keys, and other configuration variables.

1. **Create your `.env` file**  
    An example `.env` file is included as `.env.example`. Copy it and rename it to `.env`:

   ```bash
   cp .env.example .env
   ```

   or

2. **Edit the** `.env` **file**
   Open `.env` in your editor and update the variables as needed. Typical variables include:

   ```bash
   SECRET_KEY=your-secret-key

   DB_NAME=your_db_name
   DB_USER=your_db_user
   DB_PASSWORD=your_db_password
   DB_HOST=localhost
   DB_PORT=5432

   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

   JWT_ACCESS_TOKEN_MINUTES=60
   JWT_REFRESH_TOKEN_DAYS=1
   ```

## Database Setup

Ensure you have PostgreSQL installed and running.

1.  **Access the PostgreSQL shell:**

    ```bash
    sudo -u postgres psql
    ```

2.  **Create the Database and User:**
    
    Execute the following SQL commands. Ensure the credentials match what you defined in your `.env` file.

    ```sql
    -- Create the database
    CREATE DATABASE arcadian_erp;

    -- Create the user with a password
    CREATE USER erp_user WITH PASSWORD 'supersecretpassword';

    -- Grant privileges
    GRANT ALL PRIVILEGES ON DATABASE arcadian_erp TO erp_user;
    
    -- Optional: detailed configuration for the user
    ALTER ROLE erp_user SET client_encoding TO 'utf8';
    ALTER ROLE erp_user SET default_transaction_isolation TO 'read committed';
    ALTER ROLE erp_user SET timezone TO 'UTC';
    ```

3.  **Exit psql:**

    ```bash
    \q
    ```

## Running the Project

1. **Apply Migrations:**
   Ensure your database is running and configured in `.env`, then run:

   ```bash
   python manage.py migrate
   ```

2. **Create a Superuser:**
   To access the admin panel:

   ```bash
   python manage.py createsuperuser
   ```

3. **Run the Development Server:**

   ```bash
   python manage.py runserver
   ```

   The server will start at `http://127.0.0.1:8000/`.

## Data Seeding

To quickly set up the project with realistic demo data, you can use the `seed_data` management command. This will create:
- **Foundational Data**: Units of Measure (UOMs), Branches, Warehouses.
- **Users & Groups**: Admin, Purchaser, Branch Manager, Receiver, Warehouse Manager.
- **Inventory**: Items, Bill of Materials (BOMs).
- **Supply Chain**: Vendors, Purchase Orders, Goods Receipts.
- **Operations**: Sales Transactions, Inventory Transfers, Stock Adjustments.

Run the seeding command:
```bash
python manage.py seed_data
```

## Deploying to Heroku

The app is configured for Heroku with GitHub integration and Heroku Postgres.

1. **Create the Heroku app** (e.g. `pos-arcadian`): `heroku create pos-arcadian` or create it in the [Heroku dashboard](https://dashboard.heroku.com/).

2. **Add Heroku Postgres**: In the dashboard go to **Resources → Add-ons → Heroku Postgres** (e.g. Mini or Essential-0), or run:
   ```bash
   heroku addons:create heroku-postgresql:mini -a pos-arcadian
   ```
   `DATABASE_URL` is set automatically; do not set it manually.

3. **Set Config Vars** in **Settings → Config Vars** (or via CLI):
   - **SECRET_KEY**: Generate with `python -c "import secrets; print(secrets.token_hex(32))"`.
   - **DEBUG**: `False`
   - **ALLOWED_HOSTS**: `pos-arcadian.herokuapp.com` (and any custom domains).
   - **HEROKU_APP_NAME** (optional): `pos-arcadian` — if set, the app host is added to `ALLOWED_HOSTS` automatically.

4. **Connect GitHub**: In Heroku go to **Deploy → Deployment method → GitHub**, connect your account, select this repo and the branch to deploy (e.g. `main`). Enable "Automatic deploys" if desired.

5. **Deploy**: Push to the connected branch or click "Deploy branch". Heroku runs migrations and `collectstatic` in the release phase, then starts the web dyno.

Heroku uses **uv** for installs (no `requirements.txt`). Required repo files: `Procfile`, `.python-version`, `pyproject.toml`, and `uv.lock` (dependencies include `gunicorn`, `dj-database-url`, `whitenoise`, and `psycopg2-binary`).

## Core Features & Modules

The Arcadian ERP system is composed of several integrated modules:

- **👥 User Management**: Role-based access control (RBAC) with groups and custom permissions.
- **🏢 Branch & Warehouse**: Management of multiple physical locations and stock storage.
- **📦 Inventory & BOM**: Product catalog, multi-location stock tracking, and Bill of Materials for manufacturing/packaging.
- **🛒 Procurement**: Vendor management, Purchase Orders (PO), and Goods Receipts (GR).
- **📋 Demands**: Internal requests for branch/warehouse replenishment.
- **🚚 Transfers & Logistics**: Tracking stock movements between warehouses and branches.
- **💰 Sales & Finance**: Recording sales transactions, vendor invoices, and payment tracking.
- **📊 Reporting**: Integrated dashboard and data analysis tools.

## Code Quality & Linting

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and code formatting. Ruff is configured in `pyproject.toml` and provides fast, comprehensive Python linting and formatting.

### Running Ruff Locally

**Check for linting issues:**
```bash
uv run ruff check .
```

**Auto-fix linting issues:**
```bash
uv run ruff check --fix .
```

**Check formatting:**
```bash
uv run ruff format .
```

**Format code automatically:**
```bash
uv run ruff format .
```

## Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com/) to ensure code quality before commits. Pre-commit hooks will automatically run Ruff linter and formatter on your code before allowing you to commit.

### Setting Up Pre-commit

1. **Install pre-commit hooks:**
   ```bash
   uv run pre-commit install
   ```

2. **Test the hooks (optional):**
   ```bash
   uv run pre-commit run --all-files
   ```

Once installed, pre-commit will automatically run on every commit. If there are linting or formatting issues, the commit will be blocked, and you'll need to fix them before committing.

### Manual Pre-commit Run

To manually run pre-commit on all files:
```bash
uv run pre-commit run --all-files
```

## CI/CD

This project uses GitHub Actions for continuous integration. Every pull request and push to main branches will automatically trigger:

- **Ruff Linting Check**: Ensures code follows linting rules
- **Ruff Format Check**: Ensures code is properly formatted
- **Django Conventions Check**: Validates Django-specific coding conventions and project structure
- **Auto-generated PR Descriptions**: Automatically generates PR descriptions from commit messages and code changes

The CI pipeline will fail if:
- There are any linting errors
- Code is not properly formatted
- Django conventions are violated
- Critical directory structure issues are found

This ensures that all code merged into the repository meets quality standards and follows Django best practices.

### Django Conventions Check

The Django conventions workflow automatically validates:

#### 📁 Directory Structure
- Verifies `apps/` and `config/` directories exist
- Checks for `manage.py` in root directory
- Validates required config files (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`)

#### 📦 Django Apps Structure
- Validates each app in `apps/` has required files:
  - `__init__.py`, `apps.py`, `models.py`, `admin.py`, `views.py`, `tests.py`
- Checks for `migrations/` directory with `__init__.py`
- Ensures proper app structure

#### 📝 Naming Conventions
- Validates app names follow Django conventions (lowercase)
- Checks for proper file naming

#### 🔍 Django Best Practices
- Validates `SECRET_KEY` uses environment variables (not hardcoded)
- Checks `DEBUG` configuration
- Ensures `.env` file is not tracked in git
- Suggests `.env.example` for documentation

#### 🗄️ Migrations
- Checks for unapplied migrations
- Validates migration files structure

#### 📚 Code Quality
- Runs Django's system check (`python manage.py check`)
- Validates Python imports
- Uses Ruff with Django-specific rules (DJ codes)

All checks are **completely free** using GitHub Actions' free tier.

### Auto-generated PR Descriptions

When you open or update a pull request, a GitHub Action automatically generates a comprehensive PR description that includes:

#### 📝 Commits
- Complete list of all commits with:
  - Commit hash and relative time
  - Commit message
  - Author name and email
  - Time span of all commits

#### 👥 Contributors
- Breakdown of contributors and their commit counts

#### 📁 Changed Files
- Detailed file changes with:
  - File status (Added, Modified, Deleted, Renamed)
  - Line-by-line statistics for each file (+additions, -deletions, net change)
  - Summary count of file types

#### 📊 File Type Breakdown
- Analysis of changed file types (e.g., `.py`, `.yml`, `.md`)
- Count of files per extension type

#### 📂 Affected Directories
- List of directories affected by changes
- File count per directory

#### 📈 Detailed Statistics
- Overall change statistics
- Total lines added/removed with net change
- Average additions per file
- File change counts

#### 🔍 Change Analysis
- Automatic detection of:
  - Database migrations
  - Test file changes
  - Configuration file changes (with warning)
  - Documentation updates

#### 📋 Summary
- Overview generated from commit messages (up to 10 commits)

The description is automatically updated when you push new commits to the PR. If you've already written a custom description, it won't be overwritten unless it was previously auto-generated.

**Note**: This feature is completely free and uses GitHub Actions' free tier (2,000 minutes/month).

## Project Structure

```
arcadian-be/
├── apps/                 # Application modules (Business logic)
├── config/               # Project configuration
│   ├── settings.py       # Main settings file
│   ├── urls.py           # Root URL configuration
│   └── ...
├── .github/              # GitHub configuration
│   └── workflows/        # GitHub Actions workflows
│       ├── lint.yml      # Linting and formatting CI workflow
│       ├── django-conventions.yml  # Django conventions and structure check
│       └── pr-description.yml  # Auto-generate PR descriptions
├── .env                  # Environment variables (git-ignored)
├── .env.example          # Example environment variables
├── .pre-commit-config.yaml  # Pre-commit hooks configuration
├── manage.py             # Django command-line utility
├── pyproject.toml        # Project metadata and dependencies
└── README.md             # Project documentation
```
