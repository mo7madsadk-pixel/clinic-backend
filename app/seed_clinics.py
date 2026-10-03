from app.database import SessionLocal, engine
from app import models

# التأكد من إنشاء الجداول أولاً (إجراء احترازي)
models.Base.metadata.create_all(bind=engine)

def seed():
    db = SessionLocal()
    
    # قائمة العيادات والأقسام المطلوبة
    clinics_to_insert = [
        "عيادة الأطفال",
        "عيادة النسائية",
        "عيادة الأمراض الداخلية",
        "عيادة الأسنان",
        "عيادة التغذية",
        "قسم الإسعاف الأولي",
        "الصيدلية",
        "المختبر"
    ]

    print("جاري التحقق من وجود العيادات...")
    added_count = 0

    try:
        for clinic_name in clinics_to_insert:
            # التحقق لمنع التكرار في حال تشغيل الملف أكثر من مرة
            existing_clinic = db.query(models.Clinic).filter(models.Clinic.name == clinic_name).first()
            
            if not existing_clinic:
                new_clinic = models.Clinic(name=clinic_name)
                db.add(new_clinic)
                added_count += 1
                
        if added_count > 0:
            db.commit()
            print(f"تم حقن {added_count} عيادة/قسم بنجاح في قاعدة البيانات!")
        else:
            print("العيادات موجودة مسبقاً، لم تتم إضافة أي عيادات جديدة.")
            
    except Exception as e:
        db.rollback()
        print(f"حدث خطأ أثناء إدراج البيانات: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()