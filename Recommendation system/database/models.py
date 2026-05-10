import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

DB_FILE = os.environ.get("DB_FILE", "laptops_data.db")
DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ElectronicsHistory(Base):
    __tablename__ = "electronics_history"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String, index=True, nullable=False)
    model = Column(String, nullable=False)
    current_price = Column(Float)
    price_14d_avg = Column(Float)
    forecasted_price = Column(Float)
    r_score = Column(Float)
    classification = Column(String)
    confidence = Column(String)
    shap_drivers = Column(Text)
    ingested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

class DailyRecommendation(Base):
    __tablename__ = "daily_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String, index=True, nullable=False)
    model = Column(String, nullable=False)
    r_score = Column(Float, index=True)
    classification = Column(String)
    confidence = Column(String)
    llm_explanation = Column(Text)
    recommended_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # New fields for B2C Action Layer
    status = Column(String, default="Approved", index=True)
    emailed = Column(Boolean, default=False, index=True)
    email_error = Column(String, nullable=True)
    dispatched_at = Column(DateTime, nullable=True)

class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String)
    category = Column(String, default="laptop", index=True)
    active = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class EmailAuditLog(Base):
    __tablename__ = "email_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    recommendation_id = Column(Integer, nullable=False, index=True)
    recipient_email = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False) # e.g., 'SUCCESS', 'FAILED'
    error_message = Column(Text, nullable=True)
    attempted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
