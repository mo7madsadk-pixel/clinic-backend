from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session
from typing import List
from .. import database, schemas, auth, models
from ..websocket_manager import manager

router = APIRouter(tags=["Pharmacy"])

def get_db():
    db = database.SessionLocal()
    try: yield db
    finally: db.close()

@router.get("/prescriptions", response_model=List[schemas.PrescriptionResponse])
def get_pending_prescriptions(
    db: Session = Depends(get_db), 
    user: models.User = Depends(auth.require_roles("pharmacist", "assistant_pharmacist", "admin"))
):
    prescriptions = db.query(models.Prescription).filter(models.Prescription.status == "pending").all()
    
    result = []
    for p in prescriptions:
        patient_name = "بدون اسم"
        clinic_name = "غير محددة"
        
        appt = db.query(models.Appointment).filter(models.Appointment.id == p.appointment_id).first()
        if appt:
            patient = db.query(models.Patient).filter(models.Patient.id == appt.patient_id).first()
            if patient: patient_name = patient.name
            
            clinic = db.query(models.Clinic).filter(models.Clinic.id == appt.clinic_id).first()
            if clinic: clinic_name = clinic.name
            
        result.append({
            "id": p.id,
            "appointment_id": p.appointment_id,
            "medication_name": p.medication_name,
            "dosage_instructions": p.dosage_instructions,
            "status": p.status,
            "patient_name": patient_name,
            "clinic_name": clinic_name # 👈 تمرير العيادة
        })
        
    return result

@router.put("/prescriptions/{presc_id}/status")
async def process_prescription(
    presc_id: int, 
    data: schemas.PharmacyNoteInput, 
    db: Session = Depends(get_db), 
    user: models.User = Depends(auth.require_roles("pharmacist", "assistant_pharmacist", "admin"))
):
    presc = db.query(models.Prescription).filter_by(id=presc_id).first()
    if not presc:
        raise HTTPException(status_code=404, detail="الوصفة غير موجودة")
        
    appt = db.query(models.Appointment).filter_by(id=presc.appointment_id).first()
    
    # 👈 تم تصحيح الخطأ المطبعي (iif -> if)
    if data.action == "dispensed":
        presc.status = "dispensed"
        presc.dispensed_by_id = user.id
        if appt: 
            appt.status = "completed" # إغلاق الزيارة وتسجيلها كمكتملة
    elif data.action == "out_of_stock":
        presc.status = "out_of_stock"
        if appt:
            appt.pharmacist_note = data.note or "الدواء غير متوفر"
            appt.status = "pharmacy_note" # إعادة توجيه للطبيب لتعديل الوصفة
            
    db.commit()
    await manager.broadcast("doctor_queue", {"action": "pharmacy_update"})
    await manager.broadcast("receptionist_queue", {"action": "checkout_ready"})
    
    return {"message": "تم تحديث حالة الوصفة بنجاح"}