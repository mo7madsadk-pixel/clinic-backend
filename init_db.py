from app.database import engine, Base
# استيراد جميع النماذج لكي تتعرف عليها قاعدة البيانات
from app import models 

print("جاري إنشاء جداول قاعدة البيانات...")

# بناء الجداول
Base.metadata.create_all(bind=engine)

print("✅ تم إنشاء قاعدة البيانات والجداول بنجاح!")