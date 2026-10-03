from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Session
from sqlalchemy import or_  # 👈 استيراد دالة or_ للبحث المزدوج
from typing import List, Optional
from pydantic import BaseModel

from .. import database, schemas, auth, models
from ..websocket_manager import manager

router = APIRouter(tags=["Nurse"])

def get_db():
    db = database.SessionLocal()
    try: yield db
    finally: db.close()

class VitalsInput(BaseModel):
    blood_pressure: str
    temperature: str
    weight: str
    nurse_notes: Optional[str] = ""

@router.get("/queue", response_model=List[schemas.AppointmentResponse])
def get_nurse_queue(db: Session = Depends(get_db), user: models.User = Depends(auth.require_roles("nurse", "admin"))):
    return db.query(models.Appointment).options(
        joinedload(models.Appointment.patient),
        joinedload(models.Appointment.clinic) # 👈 جلب اسم العيادة
    ).filter(
        models.Appointment.clinic_id == user.clinic_id, # 👈 التصفية: إظهار مرضى عيادة الممرض فقط
        models.Appointment.status.in_(["scheduled", "checked_in"])
    ).all()
@router.post("/patients/{id}/vitals", response_model=schemas.AppointmentResponse)
async def save_vitals(id: int, vitals: VitalsInput, db: Session = Depends(get_db), user: models.User = Depends(auth.require_roles("nurse", "admin"))):
    
    # 👈 التصحيح الذكي: البحث بمعرف الموعد أو معرف المريض لتجاوز أي نقص في الواجهة
    appt = db.query(models.Appointment).filter(
        or_(models.Appointment.id == id, models.Appointment.patient_id == id)
    ).first()
    
    if not appt: 
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    appt.blood_pressure = vitals.blood_pressure
    appt.temperature = vitals.temperature
    appt.weight = vitals.weight
    appt.nurse_notes = vitals.nurse_notes
    appt.status = "ready_for_doctor"
    
    db.commit()
    db.refresh(appt)
    
    await manager.broadcast("doctor_queue", {"action": "patient_ready"})
    return appt