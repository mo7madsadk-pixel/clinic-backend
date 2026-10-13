# app/main.py
import os
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, WebSocketException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import database, models, auth
from .database import engine
from .websocket_manager import manager
from .routers import receptionist, nurse, doctor, admin, lab, pharmacy, auth as auth_router

# 1. إنشاء تطبيق FastAPI
app = FastAPI(
    title="Medical Clinic Management API",
    description="FastAPI backend for a medical clinic MVP",
    version="0.1.0",
)

# 2. إنشاء الجداول في قاعدة البيانات
models.Base.metadata.create_all(bind=engine)

# 3. زرع البيانات الأساسية (العيادات وحساب الإدارة) عند الإقلاع
@app.on_event("startup")
def startup_db_seed():
    db = database.SessionLocal()
    try:
        departments = [
            "عيادة الأطفال (Pediatrics)",
            "العيادة النسائية (Obstetrics & Gynecology)",
            "العيادة الداخلية (Internal Medicine)",
            "عيادة الأسنان (Dentistry)",
            "عيادة التغذية (Nutrition)",
            "قسم الإسعاف الأولي (First Aid / Emergency)",
            "الصيدلية (Pharmacy)",
            "المختبر والأشعة (Laboratory & Radiology)"
        ]
        for dept_name in departments:
            existing_dept = db.query(models.Clinic).filter_by(name=dept_name).first()
            if not existing_dept:
                db.add(models.Clinic(name=dept_name))
        db.commit()

        # زرع المشرف الافتراضي
        admin_user = db.query(models.User).filter_by(email="admin@clinic.com").first()
        if not admin_user:
            hashed_password = auth.get_password_hash("123456")
            new_admin = models.User(
                email="admin@clinic.com",
                hashed_password=hashed_password,
                role="admin",
                is_superuser=True,
                clinic_id=1
            )
            db.add(new_admin)
            db.commit()
    finally:
        db.close()
        
# 4. إعدادات CORS
origins = [
    "http://localhost:3000",
    "https://clinic-frontend-clinic-frontend.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Middleware لجلسة قاعدة البيانات
@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    request.state.db = database.SessionLocal()
    try:
        response = await call_next(request)
    finally:
        request.state.db.close()
    return response

# 6. تسجيل المسارات (Routers)
# 👈 التعديل الأول: تم إزالة `prefix` من مسار الـ admin لأنه مُعرف مسبقاً داخل ملف `admin.py`.
# أبقينا الـ `prefix` للمسارات الأخرى لأنك لم تقم بتعريفها داخل ملفاتها (حسب الأكواد السابقة).
app.include_router(receptionist.router, prefix="/api/v1/receptionist")
app.include_router(nurse.router, prefix="/api/v1/nurse")
app.include_router(doctor.router, prefix="/api/v1/doctor")
app.include_router(admin.router) # 👈 تم حل مشكلة التكرار والـ 404 هنا
app.include_router(lab.router, prefix="/api/v1/lab")
app.include_router(pharmacy.router, prefix="/api/v1/pharmacy")
app.include_router(auth_router.router, prefix="/api/v1/auth")

# 7. WebSockets
@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    try:
        await manager.connect(websocket, room_id)
        while True:
            data = await websocket.receive_text()
            try:
                # 👈 التعديل الثاني: إضافة await هنا لمنع انهيار الـ WebSocket
                msg = await websocket.receive_json() 
            except Exception:
                msg = {"data": data}
            await manager.broadcast(room_id, msg)
    except WebSocketDisconnect:
        await manager.disconnect(websocket, room_id)
    except WebSocketException as exc:
        await manager.disconnect(websocket, room_id)
        raise exc

@app.get("/health")
async def health():
    # 👈 التعديل الثالث: تم إزالة القوس الزائد في نهاية السطر
    return JSONResponse(content={"status": "ok", "time": os.urandom(8).hex()})