"""tests/test_payload_base.py"""
import pytest
import time
import requests
from unittest.mock import patch, MagicMock

from payload.base import ScraperPayload

class MockPayload(ScraperPayload):
    def run(self):
        return []

def test_abstract_enforcement():
    with pytest.raises(TypeError):
        # Cannot instantiate abstract class directly
        ScraperPayload()

@patch('payload.base.time.sleep')
@patch('payload.base.random.uniform', return_value=6.0)
def test_polite_delay(mock_uniform, mock_sleep):
    payload = MockPayload()
    payload.polite_delay()
    mock_uniform.assert_called_once_with(5.0, 7.0)
    mock_sleep.assert_called_once_with(6.0)

@patch('payload.base.requests.get')
@patch('payload.base.time.sleep') # Do not want to actually sleep during tests
def test_fetch_page_rotates_agents_and_delays(mock_sleep, mock_get):
    payload = MockPayload()
    mock_resp = MagicMock()
    mock_get.return_value = mock_resp
    
    payload.fetch_page("http://example.com")
    
    mock_get.assert_called_once()
    assert "User-Agent" in mock_get.call_args[1]["headers"]
    mock_sleep.assert_called_once()
    mock_resp.raise_for_status.assert_called_once()

def test_validate_record():
    payload = MockPayload()
    valid_record = {
        "scrape_timestamp": "2026-04-05T00:00:00Z",
        "retailer_id": "dummy",
        "raw_title": "Fake Title",
        "raw_current_price": "100.00",
        "product_url": "http://example.com/item",
        "category": "test",
    }
    assert payload.validate_record(valid_record) is True
    
    invalid_record = valid_record.copy()
    invalid_record.pop("raw_current_price")
    assert payload.validate_record(invalid_record) is False

def test_validate_record_missing_category():
    payload = MockPayload()
    record = {
        "scrape_timestamp": "2026-04-05T00:00:00Z",
        "retailer_id": "dummy",
        "raw_title": "Fake Title",
        "raw_current_price": "100.00",
        "product_url": "http://example.com/item",
    }
    assert payload.validate_record(record) is False
