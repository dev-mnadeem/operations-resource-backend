FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH="/app" \
    # Run tools from the project venv. `uv run` would also try to sync the
    # dev dependency group, which this image deliberately leaves out.
    PATH="/app/.venv/bin:$PATH" \
    UV_NO_SYNC=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "uv>=0.9,<1" \
    && useradd --create-home --uid 1000 app

# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=app:app . .
RUN chown app:app /app

USER app
EXPOSE 8000

# Development default; docker-compose.yml runs gunicorn instead.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
