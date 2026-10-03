# app/routers/receptionist.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List

# Internal project imports
from .. import models, schemas
from ..database import SessionLocal
from ..auth import require_roles
from ..websocket_manager import manager

router = APIRouter()

# ---------- DB session ----------
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------- GET /clinics ----------
@router.get("/clinics", response_model=List[schemas.ClinicResponse])
def get_shared_clinics(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("receptionist", "admin", "doctor", "nurse", "lab", "pharmacy"))
):
    # OPTIMIZATION: Simple query, but wrapped in error handling for resilience.
    try:
        return db.query(models.Clinic).all()
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error occurred while fetching clinics.")

# ---------- GET /appointments ----------
@router.get("/appointments", response_model=List[schemas.AppointmentResponse])
def get_all_appointments(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("receptionist", "admin"))
):
    # PERFORMANCE OPTIMIZATION: Fetching ALL appointments ever created will cause memory leaks/crashes as the DB grows.
    # We should order by date (newest first) and apply a reasonable limit (e.g., 200) or filter by non-completed status.
    try:
        return (
            db.query(models.Appointment)
            .options(
                joinedload(models.Appointment.patient),
                joinedload(models.Appointment.clinic) # 👈 الإضافة الجديدة هنا لجلب بيانات العيادة
            )
            .order_by(models.Appointment.id.desc())
            .limit(200) # Prevents overloading memory
            .all()
        )
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Failed to fetch appointments.")
# ---------- 1. POST /patients ----------
@router.post("/patients", response_model=schemas.PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_data: schemas.PatientCreate, 
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("receptionist", "admin"))
):
    # BEST PRACTICE: Strip whitespace to maintain data cleanliness.
    clean_name = patient_data.name.strip()
    new_patient = models.Patient(name=clean_name, age=patient_data.age)
    
    try:
        db.add(new_patient)
        db.commit()
        db.refresh(new_patient)
        return new_patient
    except IntegrityError:
        # RESILIENCE: Handle duplicate records or DB constraints gracefully.
        db.rollback()
        raise HTTPException(status_code=400, detail="Patient data violates database constraints.")

# ---------- 2. GET /patients/search ----------
@router.get("/patients/search", response_model=List[schemas.PatientResponse])
def search_patients(
    query: str, 
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("receptionist", "admin"))
):
    # OPTIMIZATION: Prevent empty searches from returning everything.
    if not query or not query.strip():
        return []

    clean_query = query.strip()
    
    # PERFORMANCE & UX: Used `.ilike` for case-insensitive search (better than .contains in Postgres).
    # Added `.limit(50)` to prevent the server from crashing if the query matches thousands of generic names.
    search_filter = (
        or_(models.Patient.name.ilike(f"%{clean_query}%"), models.Patient.id == int(clean_query))
        if clean_query.isdigit() 
        else models.Patient.name.ilike(f"%{clean_query}%")
    )

    return db.query(models.Patient).filter(search_filter).limit(50).all()

# ---------- 3. POST /appointments ----------
@router.post("/appointments", status_code=status.HTTP_201_CREATED, response_model=schemas.AppointmentResponse)
async def create_appointment(
    appointment_data: schemas.AppointmentCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("receptionist", "admin")),
):
    # RESILIENCE: Validate foreign keys explicitly BEFORE insertion to avoid 500 Internal Server Errors.
    patient_exists = db.query(models.Patient.id).filter(models.Patient.id == appointment_data.patient_id).first()
    if not patient_exists:
        raise HTTPException(status_code=404, detail="Patient not found.")
        
    clinic_exists = db.query(models.Clinic.id).filter(models.Clinic.id == appointment_data.clinic_id).first()
    if not clinic_exists:
        raise HTTPException(status_code=404, detail="Clinic not found.")

    new_appointment = models.Appointment(
        patient_id=appointment_data.patient_id,
        clinic_id=appointment_data.clinic_id,
        session_type=appointment_data.session_type,
        scheduled_at=appointment_data.scheduled_at,
        status="scheduled"
    )
    
    try:
        db.add(new_appointment)
        db.commit()
        db.refresh(new_appointment)
        
        # Load the patient relationship manually so the response model doesn't fail if it requires patient data
        new_appointment.patient = db.query(models.Patient).get(appointment_data.patient_id)
        
        await manager.broadcast(
            "receptionist_queue",
            {"action": "new_appointment", "appointment": new_appointment.id},
        )
        return new_appointment
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Failed to create appointment due to database constraint.")

# ---------- POST /patients/{appointment_id}/checkin ----------
@router.post("/patients/{appointment_id}/checkin", response_model=schemas.AppointmentResponse)
async def checkin_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_roles("receptionist", "admin")),
):
    appt = db.query(models.Appointment).filter(models.Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appt.status != "scheduled":
        raise HTTPException(status_code=400, detail=f"Cannot check in; current status is {appt.status}")

    appt.status = "checked_in"
    db.commit()
    db.refresh(appt)

    await manager.broadcast("nurse_queue", {"action": "appointment_updated", "appointment": appt.id})
    return appt

# ---------- POST /appointments/{id}/checkout ----------
@router.post("/appointments/{id}/checkout")
async def finalize_checkout(
    id: int, 
    db: Session = Depends(get_db), 
    user: models.User = Depends(require_roles("receptionist", "admin"))
):
    # BUG FIX / LOGICAL FLAW: If 'id' matched 'patient_id', it could return an OLD, already completed appointment.
    # Now it strictly checks that the appointment is NOT already 'completed'.
    appt = db.query(models.Appointment).filter(
        or_(models.Appointment.id == id, models.Appointment.patient_id == id),
        models.Appointment.status != "completed"
    ).first()
    
    if not appt: 
        raise HTTPException(status_code=404, detail="No active appointment found for this ID.")
        
    appt.status = "completed"
    
    db.commit()
    db.refresh(appt)
    
    await manager.broadcast("receptionist_queue", {"action": "appointment_completed"})
    
    return {"message": "تم إغلاق الملف وأرشفته بنجاح"}