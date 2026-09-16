# Sentinel V1 -- single Cloud Run service (Contracts V1-Scoped S23, Build
# Checklist Phase 4.4). One container, one service, in-process modules,
# serving both the FastAPI backend and the compiled React UI (mega-prompt
# Section 12: "Cloud Run (backend + UI)" -- no separate frontend hosting).

FROM node:22-slim AS ui-build

WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui ./
# Production API calls must be relative (same-origin as this container
# serves both the API and the SPA) -- otherwise Vite bakes ui/src/lib/api.ts's
# local-dev fallback (http://localhost:8000) into the bundle at build time,
# and every deployed browser tries to call its own machine instead of Cloud
# Run. Local `npm run dev` is unaffected: this ENV only applies inside this
# build stage, not to `.env`/`vite dev`.
ENV VITE_API_BASE_URL=""
RUN npm run build

FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared ./shared
COPY services ./services
COPY data/seed ./data/seed
COPY --from=ui-build /ui/dist ./ui/dist

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
