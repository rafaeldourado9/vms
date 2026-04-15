"""Seed: popula pricing rules padrão (storage + analytics plugins)."""
from __future__ import annotations

import asyncio

from sqlalchemy import text
from vms.infrastructure.database import get_session_factory


async def seed_pricing_rules() -> None:
    """Cria pricing rules padrão se não existirem."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM pricing_rules"))
        count = result.scalar() or 0
        if count >= 3:
            print(f"pricing_rules já populada ({count} regras)")
            return

        rules = [
            # Storage mensal
            {
                "usage_type": "storage",
                "unit": "GB/mês",
                "price_per_unit": 0.15,  # R$ 0,15 por GB/mês
                "description": "Armazenamento de gravações por mês",
            },
            # Analytics plugins — preço por câmera/mês que usa o plugin
            {
                "usage_type": "intrusion",
                "unit": "câmera/mês",
                "price_per_unit": 29.90,
                "description": "Detecção de intrusão por câmera",
            },
            {
                "usage_type": "people_count",
                "unit": "câmera/mês",
                "price_per_unit": 19.90,
                "description": "Contagem de pessoas por câmera",
            },
            {
                "usage_type": "vehicle_count",
                "unit": "câmera/mês",
                "price_per_unit": 19.90,
                "description": "Contagem de veículos por câmera",
            },
            {
                "usage_type": "face_recognition",
                "unit": "câmera/mês",
                "price_per_unit": 49.90,
                "description": "Reconhecimento facial por câmera",
            },
            {
                "usage_type": "lpr",
                "unit": "câmera/mês",
                "price_per_unit": 39.90,
                "description": "Leitura de placas (LPR) por câmera",
            },
            {
                "usage_type": "fire_smoke",
                "unit": "câmera/mês",
                "price_per_unit": 34.90,
                "description": "Detecção de fogo/fumaça por câmera",
            },
            {
                "usage_type": "ppe_detection",
                "unit": "câmera/mês",
                "price_per_unit": 24.90,
                "description": "Detecção de EPI por câmera",
            },
            {
                "usage_type": "biker_detection",
                "unit": "câmera/mês",
                "price_per_unit": 24.90,
                "description": "Detecção de ciclistas por câmera",
            },
            {
                "usage_type": "horse_cart",
                "unit": "câmera/mês",
                "price_per_unit": 24.90,
                "description": "Detecção de carroça por câmera",
            },
        ]

        for r in rules:
            await session.execute(text("""
                INSERT INTO pricing_rules (usage_type, unit, price_per_unit, description, is_active)
                VALUES (:usage_type, :unit, :price_per_unit, :description, true)
                ON CONFLICT (usage_type) DO NOTHING
            """), r)

        await session.commit()
        print(f"pricing_rules populada com {len(rules)} regras")


if __name__ == "__main__":
    asyncio.run(seed_pricing_rules())
