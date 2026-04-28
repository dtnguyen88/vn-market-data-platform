# src/ops/coverage_check/Dockerfile
# Cloud Run Job image for the coverage-check ops job.
# Build context must be the repo root: docker build -f src/ops/coverage_check/Dockerfile .
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv export --no-dev --format requirements-txt > requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/shared /app/shared
COPY src/ops/coverage_check /app/ops/coverage_check
ENV PYTHONPATH=/app
CMD ["python", "-m", "ops.coverage_check"]
