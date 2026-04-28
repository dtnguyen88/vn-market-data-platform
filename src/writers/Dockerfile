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
COPY src/writers /app/writers
ENV PYTHONPATH=/app
ENV PORT=8080
EXPOSE 8080
CMD ["uvicorn", "writers.__main__:app", "--host", "0.0.0.0", "--port", "8080"]
