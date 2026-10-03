from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class AppointmentStatus(str, enum.Enum):
    scheduled = "scheduled"
    with_doctor = "with_doctor"
    lab = "lab"
    pharmacy = "pharmacy"
    completed = "completed"
    cancelled = "cancelled"

class LabStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"

class PrescriptionStatus(str, enum.Enum):
    pending = "pending"
    dispensed = "dispensed"

# جدول العيادات
class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    # علاقة عكسية لمعرفة الكادر الطبي التابع لهذه العيادة
    staff = relationship("User", back_populates="clinic")

# جدول المستخدمين
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="patient")
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)

    # مفتاح أجنبي يربط الموظف بالعيادة
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=True)
    clinic = relationship("Clinic", back_populates="staff")

# 👈 1. جدول المريض (يجب تعريفه قبل المواعيد لسلامة الربط)
class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True) # رقم الملف الطبي (MRN)
    name = Column(String, index=True, nullable=False)
    age = Column(Integer, nullable=False)
    
    # علاقة لجلب كل زيارات المريض التاريخية
    appointments = relationship("Appointment", back_populates="patient")

# 👈 2. جدول المواعيد / الزيارات (Appointments / Visits)
class Appointment(Base):
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True) # رقم الزيارة
    
    # الربط الحقيقي مع السجل الثابت للمريض
    patient_id = Column(Integer, ForeignKey("patients.id"), index=True, nullable=False)
    patient = relationship("Patient", back_populates="appointments")
    
    session_type = Column(String, default="استشارة أولية") # نوع الزيارة (استشارة أولية / جلسة متابعة)
    scheduled_at = Column(String)
    status = Column(String, default="scheduled")
    version = Column(Integer, default=1)
    
    # --- الحقول السريرية والعلاجية ---
    blood_pressure = Column(String, nullable=True)
    temperature = Column(String, nullable=True)
    weight = Column(String, nullable=True)
    nurse_notes = Column(String, nullable=True)
    doctor_notes = Column(String, nullable=True)
    lab_result = Column(String, nullable=True)          # نتيجة المختبر
    pharmacist_note = Column(String, nullable=True)     # ملاحظة الصيدلي (غير متوفر/بديل)
    
    # ربط الموعد بالعيادة حصرياً
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=True)
    clinic = relationship("Clinic")

# جدول طلبات التحاليل (المختبر)
class LabRequest(Base):
    __tablename__ = "lab_requests"
    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"))
    required_tests = Column(String, nullable=False) # أنواع التحاليل المطلوبة
    status = Column(String, default=LabStatus.pending.value)
    technician_id = Column(Integer, ForeignKey("users.id"), nullable=True)

# جدول الوصفات الطبية (الصيدلية)
class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"))
    medication_name = Column(String, nullable=False) # اسم الدواء
    dosage_instructions = Column(String, nullable=False) # الجرعات
    status = Column(String, default=PrescriptionStatus.pending.value)
    dispensed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

def validate_transition(current_status: str, new_status: str):
    valid_transitions = {
        "scheduled": ["with_doctor", "cancelled"],
        "with_doctor": ["completed", "lab", "pharmacy"],
        "lab": ["with_doctor", "completed"],
        "pharmacy": ["completed"],
        "completed": []
    }
    return True