import requests
import json

url = "http://localhost:8000/ingest/testing-queue"
payload = {
    "batch_id": "test_batch_1",
    "limit": 10
}

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
