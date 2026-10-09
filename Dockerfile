# Single-container build: the FastAPI backend serves the compiled React app.
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx vite build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app backend/app
COPY tests/fixtures/job_descriptions tests/fixtures/job_descriptions
COPY --from=web /app/frontend/dist frontend/dist
RUN useradd --create-home appuser && mkdir -p /app/data /app/uploads && chown -R appuser /app/data /app/uploads
USER appuser
ENV DATABASE_URL=sqlite:////app/data/interviewforge.db \
    UPLOAD_DIR=/app/uploads \
    FRONTEND_DIST=/app/frontend/dist \
    OLLAMA_BASE_URL=http://host.docker.internal:11434
WORKDIR /app/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
