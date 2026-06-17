# Stage 1 — build the Next.js frontend into static files
FROM node:22-alpine AS frontend
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# NODE_ENV=production is set by `next build`; next.config.js maps that to
# an empty API base so fetch("/dashboard/sample") hits the same origin.
RUN npm run build

# Stage 2 — Python runtime with the pre-built frontend baked in
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /app/out ./frontend_out
ENV SERVE_FRONTEND=1
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
