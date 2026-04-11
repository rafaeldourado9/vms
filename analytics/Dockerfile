FROM python:3.12-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Dependências de sistema necessárias para OpenCV e libs nativas
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Garante pip e setuptools atualizados antes de instalar dependências
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY pyproject.toml .
RUN pip install --no-cache-dir .

# ─── Produção ─────────────────────────────────────────────────────────────────
FROM base AS production

COPY src/ src/

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8001/health').raise_for_status()" || exit 1

CMD ["uvicorn", "analytics.main:app", "--host", "0.0.0.0", "--port", "8001"]
