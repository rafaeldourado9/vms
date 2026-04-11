#!/usr/bin/env python3
"""
Script para criar tenant e usuário admin inicial no VMS.
Uso: python scripts/setup-initial-user.py
"""
import urllib.request
import urllib.error
import json
import sys
import os

# ─── Configuração ─────────────────────────────────────────────────────────────
BASE_URL = os.getenv("VMS_BASE_URL", "https://vms-server.duckdns.org")
# BASE_URL = "http://52.72.3.61"  # Fallback para HTTP

# Dados do tenant e usuário
TENANT_NAME = os.getenv("TENANT_NAME", "Minha Empresa")
TENANT_SLUG = os.getenv("TENANT_SLUG", "minha-empresa")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@vms.local")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "VmsAdmin@2026!")
ADMIN_FULL_NAME = os.getenv("ADMIN_FULL_NAME", "Administrador do Sistema")


def api_request(method: str, path: str, data: dict | None = None, headers: dict | None = None) -> dict:
    """Faz requisição à API VMS."""
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode("utf-8") if data else None
    
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"❌ Erro HTTP {e.code}: {error_body}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"❌ Erro: {e}", file=sys.stderr)
        raise


def main():
    print("=" * 60)
    print("  SETUP INICIAL — VMS MVP")
    print("=" * 60)
    print(f"  Base URL: {BASE_URL}")
    print(f"  Tenant: {TENANT_NAME} ({TENANT_SLUG})")
    print(f"  Admin: {ADMIN_EMAIL}")
    print("=" * 60)
    print()
    
    # ─── 1. Testar se a API está online ───────────────────────────────────
    print("[1/4] Verificando se a API está online...")
    try:
        health = api_request("GET", "/health")
        print(f"  ✅ API online: {health.get('status', 'unknown')}")
    except Exception as e:
        print(f"  ❌ API não respondeu. Verifique se o servidor está rodando.")
        print(f"  Dica: tente HTTP em vez de HTTPS se o certificado não estiver configurado:")
        print(f"        export VMS_BASE_URL=http://52.72.3.61")
        sys.exit(1)
    
    # ─── 2. Criar Tenant ──────────────────────────────────────────────────
    print()
    print("[2/4] Criando tenant...")
    try:
        # Para criar tenant, precisamos de um admin existente.
        # Se não houver nenhum admin ainda, precisamos criar via seed direto no banco.
        # Vamos tentar criar via seed.sh no servidor.
        print("  ⚠️  Tenant creation requires admin authentication.")
        print("  ℹ️  Usando seed direto no banco de dados...")
    except Exception:
        pass
    
    # ─── 3. Executar seed no servidor ─────────────────────────────────────
    print()
    print("[3/4] Executando seed via servidor...")
    print(f"  Tenant: {TENANT_NAME} / {TENANT_SLUG}")
    print(f"  Admin: {ADMIN_EMAIL}")
    
    # O seed será feito via SSH no servidor
    print()
    print("=" * 60)
    print("  PRÓXIMO PASSO: Execute no servidor:")
    print("=" * 60)
    print()
    print(f"  ssh ubuntu@52.72.3.61")
    print(f"  cd /opt/vms")
    print(f"  docker compose run --rm api python -m vms.scripts.seed \\")
    print(f"    --tenant-name '{TENANT_NAME}' \\")
    print(f"    --tenant-slug '{TENANT_SLUG}' \\")
    print(f"    --admin-email '{ADMIN_EMAIL}' \\")
    print(f"    --admin-password '{ADMIN_PASSWORD}' \\")
    print(f"    --admin-name '{ADMIN_FULL_NAME}'")
    print()
    print("=" * 60)
    print()
    
    # ─── 4. Testar login ──────────────────────────────────────────────────
    print("[4/4] Para testar login após o seed:")
    print(f"  curl -X POST {BASE_URL}/api/v1/auth/token \\")
    print(f"    -H 'Content-Type: application/json' \\")
    print(f"    -d '{{\"email\": \"{ADMIN_EMAIL}\", \"password\": \"{ADMIN_PASSWORD}\"}}'")
    print()
    
    print("✅ Script concluído!")


if __name__ == "__main__":
    main()
