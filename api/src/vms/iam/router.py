"""Rotas HTTP do IAM — autenticação, tenants, usuários."""

from fastapi import APIRouter, status
from sqlalchemy.ext.asyncio import AsyncSession

from vms.core.config import get_settings
from vms.core.deps import AdminUser, CurrentUser, DbSession
from vms.iam.repository import ApiKeyRepository, TenantRepository, UserRepository
from vms.iam.schemas import (
    CreateTenantRequest,
    CreateUserRequest,
    LoginRequest,
    RefreshRequest,
    TenantResponse,
    TokenResponse,
    UserResponse,
)
from vms.iam.service import ApiKeyService, AuthService, TenantService, UserService

router = APIRouter()


def _make_auth_service(db: AsyncSession) -> AuthService:
    return AuthService(UserRepository(db), ApiKeyRepository(db))


def _make_user_service(db: AsyncSession) -> UserService:
    return UserService(UserRepository(db), TenantRepository(db))


# ─── Auth ─────────────────────────────────────────────────────────────────────

@router.post(
    "/auth/token",
    response_model=TokenResponse,
    summary="Obter tokens JWT",
    tags=["auth"],
)
async def login(body: LoginRequest, db: DbSession) -> TokenResponse:
    """
    Autentica usuário e retorna access + refresh tokens.

    Rate limit: 5/min por IP (configurado no middleware).
    """
    settings = get_settings()

    # Em instalações single-tenant, o tenant vem do slug no subdomínio.
    # Para simplificar no MVP, usamos o tenant do usuário encontrado por email.
    # TODO: suporte a multi-tenant por subdomínio no header X-Tenant
    user_repo = UserRepository(db)

    # Busca em todos os tenants pelo email (fallback para MVP single-instance)
    from sqlalchemy import select
    from vms.iam.models import UserModel
    stmt = select(UserModel).where(
        UserModel.email == body.email.lower(),
        UserModel.is_active.is_(True),
    )
    user_model = await db.scalar(stmt)
    if not user_model:
        from vms.core.exceptions import AuthenticationError
        raise AuthenticationError()

    svc = _make_auth_service(db)
    access, refresh = await svc.authenticate_user(
        body.email, body.password, user_model.tenant_id
    )
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Renovar tokens JWT",
    tags=["auth"],
)
async def refresh_token(body: RefreshRequest, db: DbSession) -> TokenResponse:
    """Renova access + refresh tokens a partir de um refresh token válido."""
    settings = get_settings()
    svc = _make_auth_service(db)
    access, refresh = await svc.refresh_access_token(body.refresh_token)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )


# ─── Tenants ─────────────────────────────────────────────────────────────────

@router.post(
    "/tenants",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar tenant",
    tags=["tenants"],
)
async def create_tenant(
    body: CreateTenantRequest,
    db: DbSession,
    _claims: AdminUser,
) -> TenantResponse:
    """Cria novo tenant. Requer role admin."""
    svc = TenantService(TenantRepository(db))
    tenant = await svc.create_tenant(body.name, body.slug)
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
    )


# ─── Usuários ─────────────────────────────────────────────────────────────────

@router.get(
    "/users/me",
    response_model=UserResponse,
    summary="Perfil do usuário atual",
    tags=["users"],
)
async def get_me(claims: CurrentUser, db: DbSession) -> UserResponse:
    """Retorna dados do usuário autenticado."""
    svc = _make_user_service(db)
    user = await svc.get_user(claims.user_id, claims.tenant_id)
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar usuário",
    tags=["users"],
)
async def create_user(
    body: CreateUserRequest,
    claims: AdminUser,
    db: DbSession,
) -> UserResponse:
    """Cria usuário no tenant do admin autenticado."""
    from vms.iam.domain import UserRole
    svc = _make_user_service(db)
    user = await svc.create_user(
        tenant_id=claims.tenant_id,
        email=str(body.email),
        password=body.password,
        full_name=body.full_name,
        role=UserRole(body.role),
    )
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )
