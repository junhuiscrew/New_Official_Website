FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/app ./app
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/alembic ./alembic

RUN pip install --no-cache-dir .

EXPOSE 8000

FROM base AS test

RUN pip install --no-cache-dir '.[test]'
COPY apps/api/tests ./tests
COPY apps/admin/nuxt.config.ts /workspace/apps/admin/nuxt.config.ts
COPY apps/admin/Dockerfile /workspace/apps/admin/Dockerfile
COPY apps/website/Dockerfile /workspace/apps/website/Dockerfile
COPY infra/nginx/nginx.staging.conf /workspace/infra/nginx/nginx.staging.conf
COPY docker-compose.yml docker-compose.staging.yml /workspace/
COPY docs/architecture/migration-runtime-strategy.md /workspace/docs/architecture/migration-runtime-strategy.md

ENV PROJECT_ROOT=/workspace

FROM base AS runtime

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
