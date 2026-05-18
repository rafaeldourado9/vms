"""Seed unificado: cria tenant + admin + agente + license key (ativada).

Uso:
    python -m vms.scripts.seed \\
        --name "Rafael" \\
        --slug ops-sec \\
        --email admin@gmail.com \\
        --password admin123 \\
        [--model managed|self_hosted] \\
        [--cameras N] \\
        [--days N]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cria tenant + admin + license key ativada.")
    p.add_argument("--name", default="rafael", help="Nome do tenant")
    p.add_argument("--slug", default="ops-sec", help="Slug único")
    p.add_argument("--email", default="admin@gmail.com", help="Email do admin")
    p.add_argument("--password", default="admin123", help="Senha do admin")
    p.add_argument("--model", choices=["managed", "self_hosted"], default="managed")
    p.add_argument("--cameras", type=int, default=0, help="Limite de câmeras (0 = ilimitado)")
    p.add_argument("--days", type=int, default=365, help="Validade da licença em dias")
    return p.parse_args()


async def _run(
    *,
    name: str,
    slug: str,
    email: str,
    password: str,
    model: str,
    cameras: int,
    days: int,
) -> None:
    from sqlalchemy import select

    from vms.billing.models import LicenseKeyModel
    from vms.cameras.models import AgentModel
    from vms.iam.models import ApiKeyModel, TenantModel, UserModel
    from vms.infrastructure.database import close_db, create_engine, get_db_context, init_db
    from vms.infrastructure.security import generate_api_key, hash_password

    engine = create_engine()
    init_db(engine)

    async with get_db_context() as session:
        if await session.scalar(select(TenantModel).where(TenantModel.slug == slug)):
            print(f"ERRO: slug '{slug}' já existe.", file=sys.stderr)
            sys.exit(1)
        if await session.scalar(select(UserModel).where(UserModel.email == email.lower())):
            print(f"ERRO: email '{email}' já existe.", file=sys.stderr)
            sys.exit(1)

        # ── License key ───────────────────────────────────────────────────────
        raw = uuid.uuid4().hex[:24].upper()
        license_key = f"{raw[:4]}-{raw[4:9]}-{raw[9:14]}-{raw[14:19]}-{raw[19:24]}"
        price = 15000.00 if model == "managed" else 20000.00
        now = datetime.now(UTC)

        # ── Tenant ────────────────────────────────────────────────────────────
        tenant = TenantModel(
            id=str(uuid.uuid4()),
            name=name,
            slug=slug,
            is_active=True,
            onboarding_complete=True,
        )
        session.add(tenant)
        await session.flush()

        license_row = LicenseKeyModel(
            id=uuid.uuid4(),
            license_key=license_key,
            tenant_id=uuid.UUID(tenant.id),
            deployment_model=model,
            status="active",
            max_cameras=cameras,
            price_annual=price,
            activated_at=now,
            expires_at=now + timedelta(days=days),
        )
        session.add(license_row)
        await session.flush()

        tenant.license_key_id = str(license_row.id)

        # ── Admin user ────────────────────────────────────────────────────────
        user = UserModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            email=email.lower(),
            hashed_password=hash_password(password),
            full_name="Administrador",
            role="admin",
            is_active=True,
        )
        session.add(user)

        # ── Agente nativo + API key ───────────────────────────────────────────
        agent_id = str(uuid.uuid4())
        agent = AgentModel(
            id=agent_id,
            tenant_id=tenant.id,
            name=f"agent-{slug}",
            status="pending",
            streams_running=0,
            streams_failed=0,
            created_at=now,
        )
        session.add(agent)

        plain_key, key_hash, prefix = generate_api_key()
        session.add(ApiKeyModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            owner_type="agent",
            owner_id=agent_id,
            key_hash=key_hash,
            prefix=prefix,
            is_active=True,
        ))
        await session.flush()

    print("Seed concluído.")
    print(f"  tenant         : {name} ({slug})")
    print(f"  admin email    : {email}")
    print(f"  admin password : {password}")
    print(f"  license key    : {license_key}")
    print(f"  modelo         : {model}")
    print(f"  câmeras        : {'ilimitadas' if cameras == 0 else cameras}")
    print(f"  expira em      : {(now + timedelta(days=days)).date().isoformat()}")
    print(f"  agente API key : {plain_key}")
    print()
    print("Guarde a API key do agente — não será exibida novamente.")

    await close_db()


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(
        name=args.name,
        slug=args.slug,
        email=args.email,
        password=args.password,
        model=args.model,
        cameras=args.cameras,
        days=args.days,
    ))


if __name__ == "__main__":
    main()
