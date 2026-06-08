# Imagem do backend FastAPI (host-agnóstica: Railway / Render / Fly / etc.)
FROM python:3.12-slim

WORKDIR /app

# Dependências primeiro (cache de camada).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código + dados + scripts de seed.
COPY app ./app
COPY seed_auth.py seed_changelog.py ./

# O provedor define $PORT (Railway/Render/Fly). Default 8000 em local.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
