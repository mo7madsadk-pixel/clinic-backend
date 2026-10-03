from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel

# استيرادات المشروع (تأكد من مطابقتها لهيكلة ملفاتك)
from .. import database, schemas, auth, models

# تعريف الـ Router
router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])

# دالة الاتصال بقاعدة البيانات
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------
# نماذج البيانات (Schemas) الخاصة بالتعديلات
# ---------------------------------------------------------
class UserUpdate(BaseModel):
    role: Optional[str] = None
    clinic_id: Optional[int] = None

class PasswordReset(BaseModel):
    new_password: str


# ---------------------------------------------------------
# مسارات الإحصائيات والعيادات (ميزاتك الأصلية)
# ---------------------------------------------------------
@router.get("/clinics", response_model=List[schemas.ClinicResponse])
def get_all_clinics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("admin"))
):
    clinics = db.query(models.Clinic).all()
    return clinics

@router.get("/stats")
async def admin_stats(
    user: schemas.User = Depends(auth.require_roles("admin")),
    db: Session = Depends(get_db),
):
    counts = db.query(models.Appointment.status, func.count(models.Appointment.id)).group_by(models.Appointment.status).all()
    # 👈 التصحيح الجذري: إزالة .value لأن المتغير status هو نص (String) أصلاً
    return {"stats": {status: count for status, count in counts}}

@router.post("/users", response_model=schemas.UserResponse)
def create_user_by_admin(
    user_data: schemas.UserCreateWithRole, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("admin"))
):
    existing_user = db.query(models.User).filter_by(email=user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مستخدم مسبقاً")
    
    hashed_password = auth.get_password_hash(user_data.password)
    new_user = models.User(
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role,
        clinic_id=user_data.clinic_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ---------------------------------------------------------
# مسارات إدارة حسابات المستخدمين (القسم الجديد)
# ---------------------------------------------------------

# 1. عرض جميع الحسابات المُنشأة
@router.get("/users", response_model=List[schemas.UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("admin"))
):
    return db.query(models.User).all()

# 2. تعديل بيانات المستخدم (العيادة والصلاحية)
@router.put("/users/{user_id}")
def update_user_profile(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("admin"))
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    if user_data.role:
        user.role = user_data.role
    if user_data.clinic_id is not None:
        user.clinic_id = user_data.clinic_id
        
    db.commit()
    return {"message": "تم تحديث بيانات المستخدم بنجاح"}

# 3. إيقاف / تنشيط الحساب (Soft Delete)
@router.put("/users/{user_id}/status")
def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("admin"))
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    # عكس حالة الحساب الحالية
    user.is_active = not user.is_active
    db.commit()
    return {"is_active": user.is_active, "message": "تم تغيير حالة الحساب بنجاح"}

# 4. التحكم بكلمة المرور (إعادة التعيين)
@router.put("/users/{user_id}/password")
def reset_user_password(
    user_id: int,
    pwd_data: PasswordReset,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_roles("admin"))
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    
    user.hashed_password = auth.get_password_hash(pwd_data.new_password)
    db.commit()
    return {"message": "تم إعادة تعيين كلمة المرور بنجاح"}