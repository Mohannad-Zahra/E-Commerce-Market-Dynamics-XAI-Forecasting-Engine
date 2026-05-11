# Point 1: Data Ingestion & ETL Layer

This folder contains the implementation of the first phase of the unified architecture refactor.

## 📋 Steps to Run the System

Follow these steps in order to set up and run the Data Ingestion & ETL layer.

### 1. (Optional) Import Historical Data
If you have existing data in `data/ECom_Forecast_XAI_data.csv`, you can import it into the new unified database by running:
```powershell
python Point_1/seed_data.py
```
*This script processes the 651MB file in chunks to ensure system stability.*

### 2. Start the FastAPI Server
To start the backend service for Point 1:
```powershell
uvicorn Point_1.main:app --port 8001 --reload
```
Once running, you can access:
- **Interactive API Docs (Swagger)**: [http://localhost:8001/docs](http://localhost:8001/docs)
- **Health Check**: [http://localhost:8001/health](http://localhost:8001/health)

### 3. Run Automated Tests
To verify that everything is working correctly:
```powershell
python -m pytest Point_1/tests/ -v
```

---

## 🏗️ Directory Structure
- `api/`: FastAPI routers for scraper ingestion and ETL triggers.
- `db/`: Database engine, SQLAlchemy models, and Pydantic schemas.
- `ETL/`: Core feature extraction engine.
- `tests/`: 50 automated tests covering all logic.
- `seed_data.py`: Script to import legacy CSV data.
- `main.py`: Main entry point for the FastAPI application.
