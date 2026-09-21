from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    TokenRefreshResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.modules.auth.service import (
    login_user,
    refresh_user_token,
    register_user,
    verify_user_email,
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    try:
        user, verification_token = register_user(db, data)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    return RegisterResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        email_verified=user.email_verified,
        verification_token=verification_token,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    try:
        access_token, refresh_token = login_user(
            db,
            data.email,
            data.password,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
)
def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    try:
        user = verify_user_email(db, data.token)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    return VerifyEmailResponse(
        message="Email verified successfully",
        email=user.email,
        email_verified=user.email_verified,
    )


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
)
def refresh_token_endpoint(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    try:
        new_access_token = refresh_user_token(db, data.refresh_token)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        )

    return TokenRefreshResponse(
        access_token=new_access_token,
    )


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "email_verified": current_user.email_verified,
    }