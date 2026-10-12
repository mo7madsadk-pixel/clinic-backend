# app/database.py
import os
from pathlib import Path
from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# تحميل المتغيرات البيئية
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# سحب الرابط من إعدادات السيرفر بدلاً من كتابته مكشوفاً
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()