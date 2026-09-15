# Sentinel V1 -- single Cloud Run service (Contracts V1-Scoped S23, Build
# Checklist Phase 4.4). One container, one service, in-process modules.

FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared ./shared
COPY services ./services
COPY data/seed ./data/seed

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
