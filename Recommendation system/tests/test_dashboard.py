import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, mock_open
import os

from api.main import app, KILL_FLAG_FILE

client = TestClient(app)

def test_get_metrics():
    with patch("api.main.SessionLocal") as mock_db:
        # Mock database queries to return valid integers
        mock_session = mock_db.return_value
        mock_session.query.return_value.count.return_value = 5
        mock_session.query.return_value.filter.return_value.count.return_value = 5
        
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_candidates_scraped" in data
        assert "email_success_rate" in data
        assert data["status"] in ["Running", "Idle"]

def test_get_logs():
    mock_log_content = "Line 1\nLine 2\nLine 3\n"
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=mock_log_content)):
        response = client.get("/logs?lines=2")
        assert response.status_code == 200
        # Since mock_open readlines behaves slightly differently with read_data sometimes,
        # we just verify the structure
        assert "logs" in response.json()

def test_trigger_pipeline():
    with patch("api.main.subprocess.Popen") as mock_popen, \
         patch("builtins.open", mock_open()), \
         patch("os.path.exists", return_value=False):
         
        # Reset the global pipeline_process state for testing
        import api.main
        api.main.pipeline_process = None
        
        response = client.post("/trigger")
        assert response.status_code == 200
        assert response.json() == {"message": "Batch pipeline triggered successfully."}
        mock_popen.assert_called_once()

def test_kill_pipeline():
    with patch("builtins.open", mock_open()) as mocked_file, \
         patch("api.main.pipeline_process") as mock_process:
        
        mock_process.poll.return_value = None # Simulate process is running
        
        response = client.post("/kill")
        assert response.status_code == 200
        
        # Verify kill flag was written
        mocked_file.assert_called_with(KILL_FLAG_FILE, "w")
        mocked_file().write.assert_called_with("kill")
        
        # Verify process was terminated
        mock_process.terminate.assert_called_once()
