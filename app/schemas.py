# app/schemas.py
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

# ==========================================
# 1. ENUMS (حالات الموعد)
# ==========================================
class AppointmentStatus(str, Enum):
    scheduled = "scheduled"
    checked_in = "checked_in"
    with_nurse = "with_nurse"
    ready_for_doctor = "ready_for_doctor"
    with_doctor = "with_doctor"
    lab = "lab"
    pharmacy = "pharmacy"
    lab_results_ready = "lab_results_ready" 
    pharmacy_note = "pharmacy_note" 
    completed = "completed"

# ==========================================
# 2. PATIENTS (المرضى)
# ==========================================
class PatientCreate(BaseModel):
    name: str
    age: int

class PatientResponse(BaseModel):
    id: int
    name: str
    age: int

    class Config:
        from_attributes = True

# ==========================================
# 3. CLINICS (العيادات)
# ==========================================
class ClinicBase(BaseModel):
    name: str

class ClinicCreate(ClinicBase):
    pass

class ClinicResponse(ClinicBase):
    id: int

    class Config:
        from_attributes = True

# ==========================================
# 4. APPOINTMENTS (المواعيد)
# ==========================================
class AppointmentCreate(BaseModel):
    patient_id: int
    clinic_id: int
    session_type: str
    scheduled_at: str

class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    clinic_id: int
    session_type: str
    status: str
    scheduled_at: str
    blood_pressure: Optional[str] = None
    temperature: Optional[str] = None
    weight: Optional[str] = None
    nurse_notes: Optional[str] = None
    doctor_notes: Optional[str] = None
    lab_result: Optional[str] = None
    pharmacist_note: Optional[str] = None
    
    # العلاقات (لإظهار الأسماء في الواجهة)
    patient: Optional[PatientResponse] = None
    clinic: Optional[ClinicResponse] = None

    class Config:
        from_attributes = True

# ==========================================
# 5. LAB & PHARMACY (المختبر والصيدلية)
# ==========================================
class LabRequestResponse(BaseModel):
    id: int
    appointment_id: int
    required_tests: str
    status: str
    patient_name: Optional[str] = None
    clinic_name: Optional[str] = None 

    class Config:
        from_attributes = True

class LabResultInput(BaseModel):
    result: str

class PrescriptionResponse(BaseModel):
    id: int
    appointment_id: int
    medication_name: str
    dosage_instructions: str
    status: str
    patient_name: Optional[str] = None
    clinic_name: Optional[str] = None 

    class Config:
        from_attributes = True

class PharmacyNoteInput(BaseModel):
    action: str # "dispensed" or "out_of_stock"
    note: Optional[str] = None

# ==========================================
# 6. DOCTOR EXAMINATIONS (فحص الطبيب)
# ==========================================
class MedicationItem(BaseModel):
    name: str
    dosage: str

class ExaminePayload(BaseModel):
    doctor_notes: str
    action: str
    lab_tests: Optional[str] = None
    medications: Optional[List[MedicationItem]] = []

# ==========================================
# 7. USERS & AUTH (المستخدمين والصلاحيات)
# ==========================================
class Token(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")

class UserBase(BaseModel):
    email: EmailStr
    role: str
    full_name: Optional[str] = None
    clinic_id: Optional[int] = None

class UserCreate(UserBase):
    username: str
    password: str

class UserCreateWithRole(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

class User(UserResponse):
    pass

# ==========================================
# 8. OPTIONAL/LEGACY (ملاحظات وعلامات حيوية منفصلة إن لزمت)
# ==========================================
class VitalsBase(BaseModel):
    appointment_id: int
    heart_rate: Optional[int] = None
    blood_pressure: Optional[str] = None
    temperature: Optional[float] = None
    respiratory_rate: Optional[int] = None

class Vitals(VitalsBase):
    id: int
    class Config:
        from_attributes = True

class ConsultationBase(BaseModel):
    appointment_id: int
    notes: str

class ConsultationCreate(ConsultationBase):
    pass

class Consultation(ConsultationBase):
    id: int
    class Config:
        from_attributes = True