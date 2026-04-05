from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from api_gateway.api.dependencies import DbSession
from api_gateway.core.auth import AdminUser, create_access_token, hash_password, verify_password
from api_gateway.models.user_entity import User
from shared.log_codes import AUTH_LOGIN_FAILED, AUTH_LOGIN_OK, AUTH_REGISTER_CONFLICT, AUTH_REGISTER_OK
from shared.observability import get_logger

logger = get_logger(__name__)

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


@router.post("/register", status_code=201, response_model=UserResponse)
async def register(body: RegisterRequest, db: DbSession):
    """Register a new user."""
    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        logger.warning("Registration conflict", code=AUTH_REGISTER_CONFLICT, username=body.username)
        raise HTTPException(status_code=409, detail="Username already exists") from e
    await db.refresh(user)
    logger.info("User registered", code=AUTH_REGISTER_OK, user_id=str(user.id), username=user.username)
    return UserResponse(id=str(user.id), username=user.username, role=user.role)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: DbSession):
    """Authenticate and receive a JWT token."""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        logger.warning("Login failed", code=AUTH_LOGIN_FAILED, username=body.username)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user.id, user.role)
    logger.info("User logged in", code=AUTH_LOGIN_OK, user_id=str(user.id))
    return TokenResponse(access_token=token)


class UserListItem(BaseModel):
    id: str
    username: str
    role: str
    created_at: str


class UsersListResponse(BaseModel):
    users: list[UserListItem]
    total: int


@router.get("/users", response_model=UsersListResponse)
async def list_users(db: DbSession, _admin: AdminUser):
    """List all users (admin only)."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    count_result = await db.execute(select(func.count()).select_from(User))
    total = count_result.scalar() or 0

    return UsersListResponse(
        users=[
            UserListItem(
                id=str(u.id),
                username=u.username,
                role=u.role,
                created_at=u.created_at.isoformat() if u.created_at else "",
            )
            for u in users
        ],
        total=total,
    )
