# src/ops/dlq_drain/Dockerfile
# Cloud Run Job image for the dlq-drain ops job.
# Build context must be the repo root: docker build -f src/ops/dlq_drain/Dockerfile .
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv export --no-dev --no-emit-workspace --no-hashes --format requirements-txt > requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/shared /app/shared
COPY src/ops/dlq_drain /app/ops/dlq_drain
ENV PYTHONPATH=/app
CMD ["python", "-m", "ops.dlq_drain"]
