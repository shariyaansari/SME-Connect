from sqlalchemy import select
from sqlalchemy.orm import Session
from pwdlib import PasswordHash

from app.database.models import User
from app.modules.auth.schemas import RegisterRequest
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)


password_hash = PasswordHash.recommended()


def register_user(db: Session, data: RegisterRequest) -> User:
    existing_user = db.scalar(
        select(User).where(User.email == data.email)
    )

    if existing_user:
        raise ValueError("Email is already registered")

    user = User(
        name=data.name,
        email=data.email,
        password_hash=password_hash.hash(data.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

def login_user(db: Session, email: str, password: str) -> tuple[str, str]:
    user = db.scalar(
        select(User).where(User.email == email)
    )

    if not user or not verify_password(
        password,
        user.password_hash,
    ):
        raise ValueError("Invalid email or password")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return access_token, refresh_token