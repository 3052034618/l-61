from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.database import get_db
from app.config import settings
from app.schemas import schemas
from app.services import auth
from app import models

router = APIRouter(prefix="/auth", tags=["认证"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


@router.post("/login", response_model=schemas.Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=schemas.User)
def register(
    user_in: schemas.UserCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    return auth.create_user(db, user_in)


@router.get("/me", response_model=schemas.User)
def get_current_user_info(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    user = auth.get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )
    return user
