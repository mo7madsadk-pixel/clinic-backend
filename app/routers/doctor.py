from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session
from sqlalchemy import or_  # 👈 استيراد دالة or_ للبحث المزدوج
from typing import List, Optional
from pydantic import BaseModel

from .. import database, schemas, auth, models
from ..websocket_manager import manager

router = APIRouter(tags=["Doctor"])

def get_db():
    db = database.SessionLocal()
    try: yield db
    finally: db.close()

# 👈 التعديل هنا: إضافة هيكل الدواء ليدعم المصفوفة
class MedicationItem(BaseModel):
    name: str
    dosage: str

class DiagnosisInput(BaseModel):
    doctor_notes: str
    action: str  # "completed", "lab", "pharmacy"
    lab_tests: Optional[str] = None
    medications: Optional[List[MedicationItem]] = [] # 👈 استقبال قائمة الأدوية بدلاً من دواء واحد

@router.get("/appointments", response_model=List[schemas.AppointmentResponse])
def get_doctor_appointments(db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_roles("doctor", "admin"))):
    return db.query(models.Appointment).options(
        joinedload(models.Appointment.patient),
        joinedload(models.Appointment.clinic) # 👈 جلب اسم العيادة
    ).filter(
        models.Appointment.clinic_id == current_user.clinic_id,
        models.Appointment.status.in_(["ready_for_doctor", "with_doctor", "lab_results_ready", "pharmacy_note"])
    ).all()

@router.post("/appointments/{id}/examine", response_model=schemas.AppointmentResponse)
async def doctor_examine_appointment(id: int, diagnosis: DiagnosisInput, db: Session = Depends(get_db), user: models.User = Depends(auth.require_roles("doctor", "admin"))):
    # البحث بمعرف الموعد أو معرف المريض لتجاوز أي نقص
    appt = db.query(models.Appointment).filter(
        or_(models.Appointment.id == id, models.Appointment.patient_id == id)
    ).first()
    
    if not appt: 
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    appt.doctor_notes = diagnosis.doctor_notes
    
    # 👈 التصحيح: تم إدخال الكود داخل الدالة، وتصحيح المتغيرات (diagnosis بدلاً من payload)
    if diagnosis.action == "pharmacy" and diagnosis.medications:
        for med in diagnosis.medications:
            if med.name.strip(): # التأكد أن الحقل ليس فارغاً
                new_prescription = models.Prescription(
                    appointment_id=appt.id, # 👈 تصحيح المتغير
                    medication_name=med.name,
                    dosage_instructions=med.dosage,
                    status="pending"
                )
                db.add(new_prescription)
                
    # حفظ طلبات المختبر
    elif diagnosis.action == "lab":
        new_lab = models.LabRequest(appointment_id=appt.id, required_tests=diagnosis.lab_tests)
        db.add(new_lab)

    # تحديث الحالة
    if diagnosis.action == "completed":
        appt.status = "pending_checkout"
    else:
        appt.status = diagnosis.action

    db.commit()
    db.refresh(appt)
    
    # إرسال التحديثات عبر الـ WebSockets
    target_queue = f"{diagnosis.action}_queue" if diagnosis.action in ["lab", "pharmacy"] else "receptionist_queue"
    await manager.broadcast(target_queue, {"action": "status_update", "appointment_id": appt.id})
    
    return appt
# أضف هذا المسار في نهاية ملف app/routers/doctor.py

@router.get("/patients/{patient_id}/history")
def get_patient_history(
    patient_id: int, 
    db: Session = Depends(get_db), 
    user: models.User = Depends(auth.require_roles("doctor", "admin"))
):
    # جلب جميع المواعيد السابقة المكتملة لهذا المريض، مرتبة من الأحدث للأقدم
    past_appts = db.query(models.Appointment).options(
        joinedload(models.Appointment.clinic)
    ).filter(
        models.Appointment.patient_id == patient_id,
        models.Appointment.status == "completed"
    ).order_by(models.Appointment.id.desc()).all()

    history = []
    for appt in past_appts:
        # جلب الأدوية التي تم وصفها في هذه الزيارة تحديداً
        prescriptions = db.query(models.Prescription).filter_by(appointment_id=appt.id).all()
        meds = [{"name": p.medication_name, "dosage": p.dosage_instructions} for p in prescriptions]

        history.append({
            "appointment_id": appt.id,
            "date": appt.scheduled_at,
            "clinic_name": appt.clinic.name if appt.clinic else "غير محددة",
            "session_type": appt.session_type,
            "doctor_notes": appt.doctor_notes or "لا يوجد تشخيص مكتوب",
            "lab_result": appt.lab_result or "لم يتم طلب تحاليل",
            "medications": meds
        })
        
    return history