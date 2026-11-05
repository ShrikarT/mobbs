FROM node:22-bookworm-slim AS web
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY apps/web ./apps/web
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api ./apps/api
COPY contracts ./contracts
COPY migrations ./migrations
COPY --from=web /build/apps/web/dist ./apps/web/dist
ARG APP_COMMIT=unknown
ENV APP_COMMIT=${APP_COMMIT} PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
RUN useradd --create-home mobbs && chown -R mobbs:mobbs /app
USER mobbs
EXPOSE 8000
CMD ["python", "-m", "apps.api.app.server"]
