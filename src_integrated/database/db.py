import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database file location
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wise_purchaser.sqlite')
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
