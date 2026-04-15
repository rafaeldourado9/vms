"""Script CLI para criação de tenant com usuário administrador e agente nativo.

Uso:
    python -m vms.scripts.create_tenant \\
        --name "Nome do Tenant" \\
        --slug "slug-do-tenant" \\
        --admin-email "admin@exemplo.com" \\
        --admin-password "senha_segura"
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, datetime


def _parse_args() -> argparse.Namespace:
    """Configura e parseia os argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Cria um tenant com usuário administrador inicial e agente nativo."
    )
    parser.add_argument("--name", required=True, help="Nome do tenant")
    parser.add_argument("--slug", required=True, help="Slug único do tenant (ex: empresa-abc)")
    parser.add_argument("--admin-email", required=True, dest="admin_email", help="Email do admin")
    parser.add_argument("--admin-password", required=True, dest="admin_password", help="Senha do admin")
    return parser.parse_args()


async def _run(name: str, slug: str, admin_email: str, admin_password: str) -> None:
    """Executa a criação do tenant, usuário admin e agente nativo."""
    from vms.cameras.models import AgentModel
    from vms.infrastructure.database import close_db, create_engine, get_db_context, init_db
    from vms.infrastructure.security import generate_api_key, hash_password
    from vms.iam.models import ApiKeyModel, TenantModel, UserModel

    engine = create_engine()
    init_db(engine)

    async with get_db_context() as session:
        # Verifica slug duplicado
        from sqlalchemy import select
        existing = await session.scalar(
            select(TenantModel).where(TenantModel.slug == slug)
        )
        if existing:
            print(f"ERRO: Slug '{slug}' já está em uso.", file=sys.stderr)
            sys.exit(1)

        # Cria tenant
        tenant = TenantModel(
            id=str(uuid.uuid4()),
            name=name,
            slug=slug,
            is_active=True,
        )
        session.add(tenant)
        await session.flush()

        # Cria usuário admin
        user = UserModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            email=admin_email.lower(),
            hashed_password=hash_password(admin_password),
            full_name="Administrador",
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        # Cria agente nativo (agente built-in do tenant)
        agent_id = str(uuid.uuid4())
        agent = AgentModel(
            id=agent_id,
            tenant_id=tenant.id,
            name=f"agent-{slug}",
            status="pending",
            streams_running=0,
            streams_failed=0,
            created_at=datetime.now(UTC),
        )
        session.add(agent)
        await session.flush()

        # Cria API key para o agente
        plain_key, key_hash, prefix = generate_api_key()
        api_key = ApiKeyModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            owner_type="agent",
            owner_id=agent_id,
            key_hash=key_hash,
            prefix=prefix,
            is_active=True,
        )
        session.add(api_key)
        await session.flush()

        print(f"Tenant criado com sucesso!")
        print(f"  tenant_id : {tenant.id}")
        print(f"  slug      : {tenant.slug}")
        print(f"  user_id   : {user.id}")
        print(f"  email     : {user.email}")
        print(f"")
        print(f"Agente nativo criado automaticamente:")
        print(f"  agent_id  : {agent_id}")
        print(f"  nome      : {agent.name}")
        print(f"  api_key   : {plain_key}")
        print(f"")
        print(f"  ⚠️  Armazene a API key com segurança — ela não será exibida novamente!")

    await close_db()


def main() -> None:
    """Ponto de entrada do script."""
    args = _parse_args()
    asyncio.run(
        _run(
            name=args.name,
            slug=args.slug,
            admin_email=args.admin_email,
            admin_password=args.admin_password,
        )
    )


if __name__ == "__main__":
    main()
