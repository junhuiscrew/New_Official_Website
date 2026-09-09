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
COPY infra/nginx/nginx.conf infra/nginx/nginx.staging.conf infra/nginx/nginx.phase37.conf infra/nginx/nginx.local-domain-demo-edge.conf /workspace/infra/nginx/
COPY docker-compose.yml docker-compose.staging.yml docker-compose.phase37.yml docker-compose.local-domain.yml docker-compose.demo-r2.yml docker-compose.local-domain.demo-edge.yml /workspace/
COPY data/demo-r2/input/demo-content-v1.json /workspace/data/demo-r2/input/demo-content-v1.json
COPY scripts/phase37-local-https.ps1 /workspace/scripts/phase37-local-https.ps1
COPY .gitignore .env.example /workspace/
COPY infra/docker/README.md /workspace/infra/docker/README.md
COPY docs/architecture/migration-runtime-strategy.md /workspace/docs/architecture/migration-runtime-strategy.md

ENV PROJECT_ROOT=/workspace

FROM base AS runtime

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
