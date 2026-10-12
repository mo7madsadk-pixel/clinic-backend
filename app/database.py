# app/database.py
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite database in the project root. Adjust path as needed.
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = "postgresql://postgres.qvxsqqohbntgdyjqvmix:Asd.zxc.123@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

engine = create_engine(
    DATABASE_URL,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()