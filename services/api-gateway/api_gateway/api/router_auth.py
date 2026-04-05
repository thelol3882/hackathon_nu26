from fastapi import APIRouter
from pydantic import BaseModel

from api_gateway.api.dependencies import DbSession
from api_gateway.core.auth import AdminUser
from api_gateway.services import auth_service

router = APIRouter()


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "operator"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    role: str


class UserListItem(BaseModel):
    id: str
    username: str
    role: str
    created_at: str


class UsersListResponse(BaseModel):
    users: list[UserListItem]
    total: int


@router.post("/register", status_code=201, response_model=UserResponse)
async def register(body: RegisterRequest, db: DbSession, _admin: AdminUser):
    """Register a new user (admin only)."""
    result = await auth_service.register(db, body.username, body.password, body.role)
    return UserResponse(**result)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DbSession):
    """Authenticate and receive a JWT token."""
    result = await auth_service.login(db, body.username, body.password)
    return TokenResponse(**result)


@router.get("/users", response_model=UsersListResponse)
async def list_users(db: DbSession, _admin: AdminUser):
    """List all users (admin only)."""
    result = await auth_service.list_users(db)
    return UsersListResponse(**result)
