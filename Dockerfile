FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH="/app"

WORKDIR /app

# System dependencies (ca-certificates for HTTPS, curl for debugging if needed)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (project uses uv locally, keep the same workflow)
RUN pip install --no-cache-dir uv

# Copy dependency metadata first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Install project dependencies using uv (respects pyproject + lockfile)
RUN uv sync --frozen --no-dev

# Copy the rest of the application code
COPY . .

EXPOSE 8000

# Default command: run Django dev server inside the container
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]

