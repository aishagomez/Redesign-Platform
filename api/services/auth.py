from datetime import datetime, timedelta, timezone
import os
import secrets
from typing import Optional

# Workaround para incompatibilidad passlib + bcrypt>=4.x
import bcrypt
if not hasattr(bcrypt, '__about__'):
    bcrypt.__about__ = type('about', (), {'__version__': bcrypt.__version__})()

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models import User
from schemas.user import UserCreate
from schemas.token import TokenData

# ── Configuración ──────────────────────────────────────────────────────────────
SECRET_KEY = "CHANGE_ME_IN_PRODUCTION"   # ← mover a variable de entorno
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24    # 24 horas
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "example1234")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_ROLE = "admin"
USER_ROLE = "user"
GUEST_EMAIL = "guest@example.com"
GUEST_USERNAME = "guest"
GUEST_ROLE = "guest"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Hashing ────────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ────────────────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        email: str = payload.get("email")
        role: str = payload.get("role")
        if user_id is None:
            raise credentials_exception
        return TokenData(user_id=int(user_id), email=email, role=role)
    except JWTError:
        raise credentials_exception


# ── Operaciones de BD ──────────────────────────────────────────────────────────
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def register_user(db: Session, data: UserCreate) -> User:
    if get_user_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está registrado",
        )
    if get_user_by_username(db, data.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario ya está en uso",
        )
    user = User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        role=USER_ROLE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no registrado",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta desactivada",
        )
    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def is_admin_user(user: User | None) -> bool:
    return bool(user and getattr(user, "role", USER_ROLE) == ADMIN_ROLE)


def is_admin_user_id(db: Session, user_id: int) -> bool:
    user = db.query(User).filter(User.id == user_id).first()
    return is_admin_user(user)


def is_guest_user_id(db: Session, user_id: int) -> bool:
    return db.query(User.id).filter(User.id == user_id, User.role == GUEST_ROLE).first() is not None


def ensure_bootstrap_admin(db: Session) -> User:
    admin = get_user_by_email(db, ADMIN_EMAIL)
    migrating_legacy_admin = False
    if not admin:
        # Migrate the previous hard-coded bootstrap admin to the configured identity.
        admin = (
            db.query(User)
            .filter(User.role == ADMIN_ROLE, User.username == "admin")
            .order_by(User.id.asc())
            .first()
        )
        migrating_legacy_admin = admin is not None
    if admin:
        updated = False
        if admin.email != ADMIN_EMAIL:
            admin.email = ADMIN_EMAIL
            updated = True
        if migrating_legacy_admin and not verify_password(ADMIN_PASSWORD, admin.password_hash):
            admin.password_hash = hash_password(ADMIN_PASSWORD)
            updated = True
        if not admin.is_active:
            admin.is_active = True
            updated = True
        if admin.role != ADMIN_ROLE:
            admin.role = ADMIN_ROLE
            updated = True
        if admin.username != ADMIN_USERNAME:
            admin.username = ADMIN_USERNAME
            updated = True
        if updated:
            db.commit()
            db.refresh(admin)
        return admin

    admin = User(
        username=ADMIN_USERNAME,
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        role=ADMIN_ROLE,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def ensure_guest_user(db: Session) -> User:
    guest = get_user_by_email(db, GUEST_EMAIL)
    if guest:
        if guest.role != GUEST_ROLE or guest.username != GUEST_USERNAME:
            raise RuntimeError("The reserved guest account conflicts with an existing user")
        if not guest.is_active:
            guest.is_active = True
            db.commit()
            db.refresh(guest)
        return guest

    guest = User(
        username=GUEST_USERNAME,
        email=GUEST_EMAIL,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=GUEST_ROLE,
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)
    return guest
