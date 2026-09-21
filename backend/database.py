import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

load_dotenv(Path(__file__).resolve().parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine, class_=Session, autoflush=False, autocommit=False
)

Base = SQLModel
# Engine = DB connection manager
# SessionLocal = DB session factory

# ပြီးတော့ engine က database ကို "ဘယ်လိုချိတ်မလဲ", SessionLocal က "ချိတ်ပြီးရင် database နဲ့ အလုပ်လုပ်မယ့် session ကို ဘယ်လိုဖန်တီးမလဲ" ဆိုတာပါ။
