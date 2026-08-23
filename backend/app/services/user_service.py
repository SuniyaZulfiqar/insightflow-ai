import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.auth import UserRegister
from app.services.email_service import send_verification_email

VERIFICATION_CODE_EXPIRY_MINUTES = 15


def get_user_by_email(
    db: Session,
    email: str,
) -> User | None:
    statement = select(User).where(User.email == email)

    return db.scalar(statement)


def _generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _set_new_verification_code(db: Session, user: User) -> str:
    code = _generate_verification_code()

    user.verification_code = code
    user.verification_code_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=VERIFICATION_CODE_EXPIRY_MINUTES
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return code


def create_user(
    db: Session,
    user_data: UserRegister,
) -> User:
    user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role="user",
        is_verified=False,
    )

    db.add(user)
    db.flush()

    workspace = Workspace(
        name=f"{user_data.name}'s Workspace",
        owner_id=user.id,
    )

    db.add(workspace)

    code = _generate_verification_code()
    user.verification_code = code
    user.verification_code_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=VERIFICATION_CODE_EXPIRY_MINUTES
    )

    db.commit()
    db.refresh(user)

    send_verification_email(user.email, user.name, code)

    return user


def verify_user_email(
    db: Session,
    email: str,
    code: str,
) -> User:
    user = get_user_by_email(db, email)

    if not user:
        raise ValueError("No account found for this email.")

    if user.is_verified:
        raise ValueError("This account is already verified.")

    if not user.verification_code or user.verification_code != code:
        raise ValueError("Invalid verification code.")

    if (
        not user.verification_code_expires_at
        or user.verification_code_expires_at < datetime.now(timezone.utc)
    ):
        raise ValueError("This code has expired. Please request a new one.")

    user.is_verified = True
    user.verification_code = None
    user.verification_code_expires_at = None

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def resend_verification_code(
    db: Session,
    email: str,
) -> User:
    user = get_user_by_email(db, email)

    if not user:
        raise ValueError("No account found for this email.")

    if user.is_verified:
        raise ValueError("This account is already verified.")

    code = _set_new_verification_code(db, user)
    send_verification_email(user.email, user.name, code)

    return user
