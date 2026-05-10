import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, DailyRecommendation, Subscriber, EmailAuditLog
from email_service import dispatch_pending_emails, _send_via_resend_with_retry

# Setup in-memory database for testing
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Recreate tables for each test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@patch("email_service.SessionLocal")
@patch("email_service.resend.Emails.send")
def test_dispatch_success_and_idempotency(mock_resend_send, mock_session_local, db_session):
    # Mock the SessionLocal to return our test db_session
    mock_session_local.return_value = db_session
    
    # Mock Resend API response
    mock_resend_send.return_value = {"id": "test_resend_id_123"}
    
    # 1. Insert 3 'Approved' recommendations
    for i in range(3):
        rec = DailyRecommendation(
            model_id=f"test_model_{i}",
            model=f"Model {i}",
            r_score=90.0 + i,
            status="Approved",
            emailed=False
        )
        db_session.add(rec)
        
    # 2. Insert 1 active subscriber
    sub = Subscriber(email="test@example.com", name="Test User", category="laptop", active=1)
    db_session.add(sub)
    db_session.commit()
    
    # 3. Trigger dispatch
    result = dispatch_pending_emails()
    
    # Verify: 1 email sent (containing 3 recommendations)
    assert result["sent"] == 1
    assert result["failed"] == 0
    
    # Verify Resend was called exactly once
    mock_resend_send.assert_called_once()
    
    # Verify emailed flag was set to True on all 3 recommendations
    recs = db_session.query(DailyRecommendation).all()
    assert all(r.emailed is True for r in recs)
    
    # Verify Audit log has 3 entries (one for each recommendation sent to the subscriber)
    audits = db_session.query(EmailAuditLog).all()
    assert len(audits) == 3
    assert all(a.status == "SUCCESS" for a in audits)
    
    # 4. Trigger dispatch AGAIN (Idempotency test)
    mock_resend_send.reset_mock()
    result_second = dispatch_pending_emails()
    
    # Verify no emails sent the second time
    assert result_second["sent"] == 0
    mock_resend_send.assert_not_called()

@patch("email_service.resend.Emails.send")
def test_exponential_backoff_retry(mock_resend_send):
    # Simulate Resend API failing 2 times, then succeeding
    mock_resend_send.side_effect = [
        Exception("API Timeout"),
        Exception("500 Internal Error"),
        {"id": "success_id_456"}
    ]
    
    # Call the retry wrapper directly to test tenacity logic
    resend_id = _send_via_resend_with_retry("test@example.com", "Test", "<p>Test</p>")
    
    assert resend_id == "success_id_456"
    assert mock_resend_send.call_count == 3
