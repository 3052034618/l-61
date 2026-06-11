from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app import models
from app.schemas import schemas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_user(db: Session, user_in: schemas.UserCreate) -> models.User:
    hashed_password = get_password_hash(user_in.password)
    db_user = models.User(
        username=user_in.username,
        password_hash=hashed_password,
        full_name=user_in.full_name,
        role=user_in.role,
        store_id=user_in.store_id
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_current_user(db: Session, token: str) -> Optional[models.User]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except Exception:
        return None
    
    user = db.query(models.User).filter(models.User.username == username).first()
    return user
