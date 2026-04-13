"""Seed: popula billing plans padrão na tabela billing_plans."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import text
from vms.core.database import get_session_factory


async def seed_billing_plans() -> None:
    """Cria os 3 planos padrão se não existirem."""
    factory = get_session_factory()
    async with factory() as session:
        # Verifica se já existe
        result = await session.execute(text("SELECT COUNT(*) FROM billing_plans"))
        count = result.scalar() or 0
        if count >= 3:
            print(f"billing_plans já populada ({count} planos)")
            return

        plans = [
            {
                "slug": "free",
                "name": "Gratuito",
                "description": "Para testar o sistema. Até 3 câmeras.",
                "price_monthly": 0,
                "max_cameras": 3,
                "max_storage_gb": 50,
                "max_ai_cameras": 0,
                "features": '{"recording": true, "live_view": true, "events": true, "analytics": false, "priority_support": false}',
            },
            {
                "slug": "pro",
                "name": "Profissional",
                "description": "Para pequenas e médias empresas. Até 20 câmeras com IA.",
                "price_monthly": 299.90,
                "max_cameras": 20,
                "max_storage_gb": 500,
                "max_ai_cameras": 10,
                "features": '{"recording": true, "live_view": true, "events": true, "analytics": true, "priority_support": true, "forensic_export": true}',
            },
            {
                "slug": "enterprise",
                "name": "Enterprise",
                "description": "Para grandes operações. Câmeras ilimitadas com IA.",
                "price_monthly": 999.90,
                "max_cameras": None,
                "max_storage_gb": 5000,
                "max_ai_cameras": None,
                "features": '{"recording": true, "live_view": true, "events": true, "analytics": true, "priority_support": true, "forensic_export": true, "custom_integrations": true, "sla": true}',
            },
        ]

        for p in plans:
            await session.execute(text("""
                INSERT INTO billing_plans (slug, name, description, price_monthly, max_cameras, max_storage_gb, max_ai_cameras, features)
                VALUES (:slug, :name, :description, :price, :max_cameras, :max_storage_gb, :max_ai_cameras, :features::jsonb)
                ON CONFLICT (slug) DO NOTHING
            """), p)

        await session.commit()
        print(f"billing_plans populada com {len(plans)} planos")


if __name__ == "__main__":
    asyncio.run(seed_billing_plans())
