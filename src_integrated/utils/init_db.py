from src_integrated.database.models import Base
from src_integrated.database.db import engine

def init_db():
    print("Initializing database schemas...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully at", engine.url)

if __name__ == "__main__":
    init_db()
