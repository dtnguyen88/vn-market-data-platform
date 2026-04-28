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
COPY src/vnmarket /app/vnmarket
COPY src/research_app /app/research_app
ENV PYTHONPATH=/app
ENV PORT=8080
EXPOSE 8080
CMD ["streamlit", "run", "research_app/__main__.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]
