"""Schemas Pydantic v2 para o IAM — DTOs de request/response HTTP."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Credenciais de login."""

    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    """Resposta de autenticação com tokens JWT."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Segundos até expiração do access token")


class RefreshRequest(BaseModel):
    """Pedido de renovação de token."""

    refresh_token: str


# ─── Tenant ───────────────────────────────────────────────────────────────────

class CreateTenantRequest(BaseModel):
    """Dados para criação de tenant."""

    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")

    @field_validator("slug")
    @classmethod
    def validar_slug(cls, v: str) -> str:
        """Converte slug para minúsculas."""
        return v.lower()


class TenantResponse(BaseModel):
    """Dados públicos do tenant."""

    id: str
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── User ─────────────────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    """Dados para criação de usuário."""

    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=255)
    role: str = Field(default="viewer", pattern=r"^(admin|operator|viewer)$")


class UserResponse(BaseModel):
    """Dados públicos do usuário (sem senha)."""

    id: str
    tenant_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── API Key ──────────────────────────────────────────────────────────────────

class ApiKeyResponse(BaseModel):
    """Resposta de criação de API key (plain_key exibido uma vez)."""

    id: str
    prefix: str
    owner_type: str
    plain_key: str = Field(description="Exibido apenas nesta resposta — armazene com segurança")
    created_at: datetime
