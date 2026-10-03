import sqlite3
import os
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_all_users():
    db_path = "clinic.db"
    if not os.path.exists(db_path) and os.path.exists("app/clinic.db"):
        db_path = "app/clinic.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # قائمة بجميع المستخدمين الأساسيين في النظام
    users = [
        ("doctor@clinic.com", "123456", 1, 0),
        ("reception@clinic.com", "123456", 1, 0),
        ("admin@clinic.com", "123456", 1, 1), # مدير النظام
        ("nurse@clinic.com", "123456", 1, 0),
        ("lab@clinic.com", "123456", 1, 0),
        ("pharmacy@clinic.com", "123456", 1, 0)
    ]
    
    try:
        for email, password, is_active, is_superuser in users:
            hashed_password = pwd_context.hash(password)
            cursor.execute(
                """
                INSERT OR IGNORE INTO users (email, hashed_password, is_active, is_superuser)
                VALUES (?, ?, ?, ?)
                """,
                (email, hashed_password, is_active, is_superuser)
            )
        conn.commit()
        print("All default clinic users created successfully!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_all_users()