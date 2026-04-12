# ─── Base com CUDA (GPU) ────────────────────────────────────────────────────
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
RUN mkdir -p src && pip install --no-cache-dir .

# ─── Produção GPU (CUDA) ───────────────────────────────────────────────────
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS gpu

# Instalar Python e dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && ln -sf /usr/bin/python3.12 /usr/bin/python \
    && ln -sf /usr/bin/python3.12 /usr/bin/python3 \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Instalar PyTorch com suporte a CUDA
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    torch torchvision \
    --index-url https://download.pytorch.org/whl/cu124

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8001/health').raise_for_status()" || exit 1

CMD ["uvicorn", "analytics.main:app", "--host", "0.0.0.0", "--port", "8001"]

# ─── Produção CPU (fallback) ─────────────────────────────────────────────────
FROM base AS cpu

COPY src/ src/

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8001/health').raise_for_status()" || exit 1

CMD ["uvicorn", "analytics.main:app", "--host", "0.0.0.0", "--port", "8001"]

# ─── Target padrão: GPU ─────────────────────────────────────────────────────
FROM gpu AS production
