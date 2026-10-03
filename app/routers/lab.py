from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from .. import database, schemas, auth, models
from ..websocket_manager import manager

router = APIRouter(tags=["Lab"])

def get_db():
    db = database.SessionLocal()
    try: yield db
    finally: db.close()

# ---------- 1. جلب طلبات التحاليل (مسار GET) ----------
@router.get("/requests", response_model=List[schemas.LabRequestResponse])
def get_pending_lab_requests(
    db: Session = Depends(get_db), 
    user: models.User = Depends(auth.require_roles("lab_doctor", "lab_tech", "radiology_tech", "admin"))
):
    requests = db.query(models.LabRequest).filter(models.LabRequest.status == "pending").all()
    
    result = []
    for r in requests:
        patient_name = "بدون اسم"
        clinic_name = "غير محددة"
        
        appt = db.query(models.Appointment).filter(models.Appointment.id == r.appointment_id).first()
        if appt:
            patient = db.query(models.Patient).filter(models.Patient.id == appt.patient_id).first()
            if patient: patient_name = patient.name
            
            clinic = db.query(models.Clinic).filter(models.Clinic.id == appt.clinic_id).first()
            if clinic: clinic_name = clinic.name
            
        result.append({
            "id": r.id,
            "appointment_id": r.appointment_id,
            "required_tests": r.required_tests,
            "status": r.status,
            "patient_name": patient_name,
            "clinic_name": clinic_name # 👈 تمرير العيادة
        })
        
    return result

# ---------- 2. إدخال النتيجة وإرسالها للطبيب (مسار PUT الناقص) ----------
@router.put("/requests/{request_id}/status")
async def update_lab_status(
    request_id: int, 
    result_data: schemas.LabResultInput, 
    db: Session = Depends(get_db), 
    # 👇 تم توحيد الصلاحيات هنا لتشمل جميع الحسابات المتعلقة بالمختبر أو الإدارة
    user: models.User = Depends(auth.require_roles("lab", "lab_tech", "lab_doctor", "radiology_tech", "admin"))
):
    lab_req = db.query(models.LabRequest).filter_by(id=request_id).first()
    if not lab_req: 
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    
    lab_req.status = "completed"
    
    appt = db.query(models.Appointment).filter_by(id=lab_req.appointment_id).first()
    if appt:
        appt.lab_result = result_data.result
        appt.status = "lab_results_ready" 
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="حدث خطأ في قاعدة البيانات")

    await manager.broadcast("doctor_queue", {"action": "lab_results_ready"})
    
    return {"message": "تم إرسال النتائج للطبيب بنجاح"}