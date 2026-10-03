from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

# استدعاء ملف أدوات التشفير، قاعدة البيانات، والـ schemas
from app import auth, database, schemas
from app.models import User  

router = APIRouter(tags=["auth"])

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # الواجهة الأمامية سترسل الإيميل داخل حقل username حسب معايير OAuth2
    user = db.query(User).filter(User.email == form_data.username).first()
    
    # 1. التحقق من وجود المستخدم وصحة كلمة المرور
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="البريد الإلكتروني أو كلمة المرور غير صحيحة",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. 👈 التعديل الهام جداً: التحقق من حالة الحساب (منع الحسابات الموقوفة من الدخول)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذا الحساب موقوف، يرجى مراجعة الإدارة"
        )
    
    # 3. توليد التوكن فقط إذا كان الحساب موجوداً، بياناته صحيحة، وحالته "نشط"
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

# ---------------------------------------------------------
# المسار الجديد: جلب بيانات المستخدم الحالي (للتحقق من الصلاحية والتوجيه)
# ---------------------------------------------------------
@router.get("/me", response_model=schemas.UserResponse)
async def read_users_me(current_user: User = Depends(auth.get_current_user)):
    return current_user