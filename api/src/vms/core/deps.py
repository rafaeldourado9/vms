"""FastAPI dependencies: banco de dados, autenticação, tenant."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from vms.core.database import get_session_factory
from vms.core.security import decode_token

_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


# ─── Sessão de banco ──────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency que fornece sessão async do banco."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]


# ─── Claims do token ──────────────────────────────────────────────────────────

class TokenClaims:
    """Claims extraídos do JWT após validação."""

    def __init__(self, user_id: str, tenant_id: str, role: str) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role

    @property
    def is_admin(self) -> bool:
        """Retorna True se o usuário tem role admin."""
        return self.role == "admin"


async def get_current_user(
    token: Annotated[str | None, Depends(_oauth2)] = None,
) -> TokenClaims:
    """Valida JWT e retorna claims do usuário autenticado."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação obrigatório",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise JWTError("Tipo de token inválido")
        return TokenClaims(
            user_id=payload["sub"],
            tenant_id=payload["tenant_id"],
            role=payload["role"],
        )
    except (JWTError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUser = Annotated[TokenClaims, Depends(get_current_user)]


def require_admin(claims: CurrentUser) -> TokenClaims:
    """Dependency que exige role admin."""
    if not claims.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão de administrador necessária",
        )
    return claims


AdminUser = Annotated[TokenClaims, Depends(require_admin)]


# ─── API Key (agents, analytics) ─────────────────────────────────────────────

async def get_api_key(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Extrai API key do header Authorization: ApiKey vms_xxx."""
    if not authorization or not authorization.startswith("ApiKey "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header 'Authorization: ApiKey <key>' obrigatório",
        )
    return authorization.removeprefix("ApiKey ").strip()


ApiKeyHeader = Annotated[str, Depends(get_api_key)]
