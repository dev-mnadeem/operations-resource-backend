import os
from pathlib import Path

import dj_database_url
from celery.schedules import crontab
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


SECRET_KEY = os.getenv("SECRET_KEY")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
_allowed = [
    h.strip() for h in (os.getenv("ALLOWED_HOSTS") or "").split(",") if h.strip()
]
_heroku_app = os.getenv("HEROKU_APP_NAME")
if _heroku_app:
    _allowed.append(f"{_heroku_app}.herokuapp.com")
# Allow any Heroku app host (e.g. pos-arcadian-e44c4c032373.herokuapp.com)
_allowed.append(".herokuapp.com")
ALLOWED_HOSTS = _allowed

AUTH_USER_MODEL = "users.User"

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "admin:index"
LOGOUT_REDIRECT_URL = "/admin/login/"
ROOT_URLCONF = "config.urls"


INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.users",
    "apps.branch",
    "apps.warehouse",
    "apps.inventory",
    "apps.sales",
    "apps.demands",
    "apps.purchases",
    "apps.transfers",
    "apps.payments",
    "apps.reports",
    "apps.products",
    "apps.common",
    "cloudinary",
    "cloudinary_storage",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.IdempotencyMiddleware",
]

# Allow admin lookup popups (Jazzmin modal iframe) to load; same-origin only
X_FRAME_OPTIONS = "SAMEORIGIN"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if os.getenv("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.config(
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    db_engine = os.getenv("DB_ENGINE")
    if not db_engine:
        # Local/dev convenience: allow booting the app without Postgres.
        # If you want Postgres, set DB_ENGINE/DB_* (or DATABASE_URL).
        db_engine = "django.db.backends.sqlite3"
    DATABASES = {
        "default": {
            "ENGINE": db_engine,
            "NAME": os.getenv("DB_NAME") or (BASE_DIR / "db.sqlite3"),
            "USER": os.getenv("DB_USER"),
            "PASSWORD": os.getenv("DB_PASSWORD"),
            "HOST": os.getenv("DB_HOST"),
            "PORT": os.getenv("DB_PORT"),
        }
    }


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    # {
    #     "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    # },
    # {
    #     "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    # },
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Karachi"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Cloudinary media storage
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": os.getenv("CLOUDINARY_API_KEY"),
    "API_SECRET": os.getenv("CLOUDINARY_API_SECRET"),
}

# Use Cloudinary only if credentials are provided, otherwise fallback to local FileSystemStorage
if all(
    [
        CLOUDINARY_STORAGE["CLOUD_NAME"],
        CLOUDINARY_STORAGE["API_KEY"],
        CLOUDINARY_STORAGE["API_SECRET"],
    ]
):
    STORAGES = {
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
}

JAZZMIN_SETTINGS = {
    "site_title": "Arcadian Admin Panel",
    "site_header": "Arcadian Admin",
    "site_brand": "Arcadian Admin",
    "welcome_sign": "Welcome to the Arcadian Admin Panel",
    "copyright": "Arcadian Ltd",
    # List of model admins to search from the search bar, search bar omitted if excluded
    # If you want to use a single search field you dont need to use a list, you can use a simple string
    "search_model": [],
    # Field name on user model that contains avatar ImageField/URLField/Charfield or a callable that receives the user
    "user_avatar": None,
    ############
    # Top Menu #
    ############
    # Links to put along the top menu
    "topmenu_links": [
        {"name": "Home", "url": "admin:index"},
        {"model": "purchases.Notification"},
    ],
    # Additional links to include in the user menu on the top right ("app" url type is not allowed)
    "usermenu_links": None,
    "show_sidebar": True,
    "navigation_expanded": True,
    # Hide these apps when generating side menu e.g (auth)
    "hide_apps": [],
    # Hide these models when generating side menu (e.g auth.user)
    # Notification is in topmenu_links only; hide from sidebar and dashboard
    "hide_models": ["purchases.Notification"],
    # List of apps (and/or models) to base side menu ordering off of (does not need to contain all apps/models)
    "order_with_respect_to": [
        "auth",
        "users",
        "branch",
        "sales",
        "demands",
        "inventory",
        "products",
        "transfers",
        "purchases",
        "payments",
        "warehouse",
        "reports",
    ],
    # Custom links to append to app groups, keyed on app name
    "custom_links": {},
    # Custom icons for side menu apps/models See https://fontawesome.com/icons?d=gallery&m=free&v=5.0.0,5.0.1,5.0.10,5.0.11,5.0.12,5.0.13,5.0.2,5.0.3,5.0.4,5.0.5,5.0.6,5.0.7,5.0.8,5.0.9,5.1.0,5.1.1,5.2.0,5.3.0,5.3.1,5.4.0,5.4.1,5.4.2,5.13.0,5.12.0,5.11.2,5.11.1,5.10.0,5.9.0,5.8.2,5.8.1,5.7.2,5.7.1,5.7.0,5.6.3,5.5.0,5.4.2
    "icons": {
        "auth": "fas fa-shield-alt",
        "auth.Group": "fas fa-users",
        "users": "fas fa-user-friends",
        "users.User": "fas fa-user",
        "branch": "fas fa-store-alt",
        "branch.Branch": "fas fa-store",
        "warehouse": "fas fa-warehouse",
        "warehouse.Warehouse": "fas fa-warehouse",
        "warehouse.WarehouseInventory": "fas fa-boxes",
        "warehouse.WarehouseTransaction": "fas fa-exchange-alt",
        "warehouse.WarehouseRequest": "fas fa-file-export",
        "warehouse.WarehouseRequestItem": "fas fa-list-ul",
        "inventory": "fas fa-cubes",
        "inventory.UnitOfMeasure": "fas fa-ruler-combined",
        "inventory.InventoryItem": "fas fa-cube",
        "inventory.InventoryCategory": "fas fa-folder-open",
        "inventory.BOM": "fas fa-cogs",
        "inventory.BOMItem": "fas fa-cog",
        "inventory.StockCycleCount": "fas fa-redo-alt",
        "inventory.StockAdjustment": "fas fa-adjust",
        "sales": "fas fa-cash-register",
        "sales.SalesTransaction": "fas fa-receipt",
        "sales.InventoryConsumption": "fas fa-chart-line",
        "demands": "fas fa-clipboard-list",
        "demands.Demand": "fas fa-clipboard-check",
        "demands.DemandItem": "fas fa-list-alt",
        "purchases": "fas fa-shopping-cart",
        "purchases.Vendor": "fas fa-truck",
        "purchases.PurchaseOrder": "fas fa-file-invoice-dollar",
        "purchases.PurchaseOrderItem": "fas fa-list-ol",
        "purchases.GoodsReceipt": "fas fa-dolly",
        "purchases.GoodsReceiptItem": "fas fa-box-open",
        "purchases.ReceiptImage": "fas fa-image",
        "purchases.Notification": "fas fa-bell",
        "transfers": "fas fa-shipping-fast",
        "transfers.Transfer": "fas fa-truck-loading",
        "transfers.TransferItem": "fas fa-box",
        "payments": "fas fa-money-check-alt",
        "payments.VendorInvoice": "fas fa-file-invoice",
        "payments.Payment": "fas fa-wallet",
        "payments.PaymentDocument": "fas fa-file-alt",
        "reports": "fas fa-chart-bar",
        "reports.AuditLog": "fas fa-history",
        "products.Product": "fas fa-shopping-bag",
        "products.ProductCategory": "fas fa-tags",
    },
    # Icons that are used when one is not manually specified
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    # Use modals instead of popups
    "related_modal_active": True,
    ###############
    # Change view #
    ###############
    # Render out the change view as a single form, or in tabs, current options are
    # - single
    # - horizontal_tabs (default)
    # - vertical_tabs
    # - collapsible
    # - carousel
    "changeform_format": "single",
    "custom_css": "css/admin_filters.css",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": None,
    "accent": None,
    "navbar": None,
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "litera",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

# Celery Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {
    "fetch-sales-emails": {
        "task": "apps.sales.tasks.fetch_and_process_sales_emails",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "schedule-cycle-counts": {
        "task": "apps.inventory.tasks.schedule_cycle_counts",
        "schedule": crontab(hour=6, minute=0),  # 06:00 daily
    },
}

# Email Notification Configuration
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in ("true", "1", "yes")

# Logging — stdout so Heroku log drain forwards to Papertrail automatically
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": os.getenv("DB_LOG_LEVEL", "WARNING"),
            "propagate": False,
        },
    },
}
