import os
import subprocess
import threading
from typing import Dict, Any

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel

from database.models import SessionLocal, DailyRecommendation, ElectronicsHistory, EmailAuditLog
from email_service import dispatch_pending_emails

app = FastAPI(title="Recommendation System API")

KILL_FLAG_FILE = "kill_flag.txt"
PIPELINE_LOG_FILE = "pipeline.log"

pipeline_process = None

@app.get("/metrics")
def get_metrics() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        total_history = db.query(ElectronicsHistory).count()
        total_recs = db.query(DailyRecommendation).count()
        
        # Email metrics
        total_emails = db.query(EmailAuditLog).count()
        successful_emails = db.query(EmailAuditLog).filter(EmailAuditLog.status == 'SUCCESS').count()
        success_rate = (successful_emails / total_emails * 100) if total_emails > 0 else 0.0

        return {
            "total_candidates_scraped": total_history,
            "total_recommendations_made": total_recs,
            "total_emails_attempted": total_emails,
            "email_success_rate": round(success_rate, 2),
            "status": "Running" if pipeline_process and pipeline_process.poll() is None else "Idle"
        }
    finally:
        db.close()

@app.get("/logs")
def get_logs(lines: int = 50) -> Dict[str, Any]:
    if not os.path.exists(PIPELINE_LOG_FILE):
        return {"logs": ["No logs available yet."]}
    
    with open(PIPELINE_LOG_FILE, "r", encoding="utf-8") as f:
        # Read the last N lines
        all_lines = f.readlines()
        recent_lines = all_lines[-lines:]
    return {"logs": recent_lines}

@app.get("/recommendations")
def get_recommendations(limit: int = 10) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        recs = db.query(DailyRecommendation).order_by(DailyRecommendation.recommended_at.desc()).limit(limit).all()
        return {
            "recommendations": [
                {
                    "model": r.model,
                    "r_score": r.r_score,
                    "classification": r.classification,
                    "confidence": r.confidence,
                    "status": r.status,
                    "emailed": r.emailed,
                    "recommended_at": r.recommended_at.isoformat() if r.recommended_at else None
                } for r in recs
            ]
        }
    finally:
        db.close()

@app.post("/trigger")
def trigger_pipeline():
    global pipeline_process
    if pipeline_process and pipeline_process.poll() is None:
        raise HTTPException(status_code=400, detail="Pipeline is already running.")
    
    if os.path.exists(KILL_FLAG_FILE):
        os.remove(KILL_FLAG_FILE)

    # Launch main_pipeline.py as a separate process and pipe output to log file
    log_file = open(PIPELINE_LOG_FILE, "a", encoding="utf-8")
    pipeline_process = subprocess.Popen(
        ["python", "main_pipeline.py"],
        stdout=log_file,
        stderr=subprocess.STDOUT
    )
    return {"message": "Batch pipeline triggered successfully."}

@app.post("/kill")
def kill_pipeline():
    global pipeline_process
    
    # Touch kill flag file
    with open(KILL_FLAG_FILE, "w") as f:
        f.write("kill")
        
    if pipeline_process and pipeline_process.poll() is None:
        pipeline_process.terminate()
        return {"message": "Pipeline kill signal sent and process terminated."}
        
    return {"message": "Kill flag set, but no pipeline was currently running."}

@app.post("/retrain")
def retrain_models():
    # Placeholder for triggering retrain process
    return {"message": "Manual retrain triggered successfully."}

@app.post("/events/batch-complete")
def handle_batch_complete(background_tasks: BackgroundTasks):
    """
    Webhook triggered by main_pipeline.py when the daily batch finishes.
    """
    background_tasks.add_task(dispatch_pending_emails)
    return {"message": "Batch complete event received. Email dispatch initiated in background."}
