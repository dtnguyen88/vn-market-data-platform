# src/ops/data_quality/Dockerfile
# Cloud Run Job image for the data-quality ops job.
# Build context must be the repo root: docker build -f src/ops/data_quality/Dockerfile .
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
COPY src/ops/data_quality /app/ops/data_quality
ENV PYTHONPATH=/app
CMD ["python", "-m", "ops.data_quality"]
