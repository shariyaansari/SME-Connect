from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import User
from app.modules.auth.schemas import RegisterRequest
from app.core.security import (
    create_access_token,
    create_email_verification_token,
    create_refresh_token,
    hash_password,
    verify_email_verification_token,
    verify_password,
    verify_refresh_token,
)


def register_user(db: Session, data: RegisterRequest) -> tuple[User, str]:
    normalized_email = data.email.lower().strip()

    existing_user = db.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )

    if existing_user:
        raise ValueError("Email is already registered")

    user = User(
        name=data.name.strip(),
        email=normalized_email,
        password_hash=hash_password(data.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    verification_token = create_email_verification_token(user.id, user.email)
    return user, verification_token


def login_user(db: Session, email: str, password: str) -> tuple[str, str]:
    normalized_email = email.lower().strip()

    user = db.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )

    if not user or not verify_password(
        password,
        user.password_hash,
    ):
        raise ValueError("Invalid email or password")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return access_token, refresh_token


def verify_user_email(db: Session, token: str) -> User:
    user_id, token_email = verify_email_verification_token(token)

    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    if user.email.lower().strip() != token_email.lower().strip():
        raise ValueError("Email does not match token")

    user.email_verified = True
    db.commit()
    db.refresh(user)

    return user


def refresh_user_token(db: Session, refresh_token: str) -> str:
    user_id = verify_refresh_token(refresh_token)

    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    return create_access_token(user.id)