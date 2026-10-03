# app/auth.py
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import database, schemas, models  # 👈 أضفنا models هنا
from . import database as db_session

# ----------------------------------------------------------------------
# 1️⃣  Settings
# ----------------------------------------------------------------------
SECRET_KEY = "YOUR_SUPER_SECRET_KEY"  # replace with env var in prod
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ----------------------------------------------------------------------
# 2️⃣  Password hashing
# ----------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ----------------------------------------------------------------------
# 3️⃣  JWT helpers
# ----------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ----------------------------------------------------------------------
# 4️⃣  Dependency – get current user
# ----------------------------------------------------------------------
def get_auth_db():
    db = db_session.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    db: Session = Depends(get_auth_db),
    token: str = Depends(oauth2_scheme),
):
    payload = decode_token(token)
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    # البحث عن طريق الإيميل
    user = db.query(models.User).filter(models.User.email == username).first()
    
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
        
    # 👈 التعديل الأول: التحقق مما إذا كان الحساب موقوفاً (Soft Deleted)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="هذا الحساب موقوف، يرجى مراجعة الإدارة"
        )
        
    return user


# ----------------------------------------------------------------------
# 5️⃣  Role based dependency factory
# ----------------------------------------------------------------------
def require_roles(*roles: str):
    def role_checker(user: models.User = Depends(get_current_user)):
        # 👈 التعديل الثاني: تفعيل نظام حماية الصلاحيات فعلياً (RBAC)
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"لا تملك الصلاحيات الكافية للوصول. الصلاحيات المطلوبة: {', '.join(roles)}"
            )
        return user

    return role_checker