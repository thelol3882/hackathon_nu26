"""Authentication service — register, login, list users."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.core.auth import create_access_token, hash_password, verify_password
from api_gateway.models.user_entity import User
from shared.log_codes import AUTH_LOGIN_FAILED, AUTH_LOGIN_OK, AUTH_REGISTER_CONFLICT, AUTH_REGISTER_OK
from shared.observability import get_logger

logger = get_logger(__name__)


async def register(session: AsyncSession, username: str, password: str, role: str = "operator") -> dict:
    user = User(
        username=username,
        hashed_password=hash_password(password),
        role=role,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        logger.warning("Registration conflict", code=AUTH_REGISTER_CONFLICT, username=username)
        raise HTTPException(status_code=409, detail="Username already exists") from e
    await session.refresh(user)
    logger.info("User registered", code=AUTH_REGISTER_OK, user_id=str(user.id), username=user.username)
    return {"id": str(user.id), "username": user.username, "role": user.role}


async def login(session: AsyncSession, username: str, password: str) -> dict:
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        logger.warning("Login failed", code=AUTH_LOGIN_FAILED, username=username)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user.id, user.role)
    logger.info("User logged in", code=AUTH_LOGIN_OK, user_id=str(user.id))
    return {"access_token": token, "token_type": "bearer"}


async def list_users(session: AsyncSession) -> dict:
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    count_result = await session.execute(select(func.count()).select_from(User))
    total = count_result.scalar() or 0
    return {
        "users": [
            {
                "id": str(u.id),
                "username": u.username,
                "role": u.role,
                "created_at": u.created_at.isoformat() if u.created_at else "",
            }
            for u in users
        ],
        "total": total,
    }
