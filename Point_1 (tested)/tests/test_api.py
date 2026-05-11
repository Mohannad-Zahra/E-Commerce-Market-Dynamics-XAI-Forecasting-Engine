"""
test_api.py — API Integration Tests
=====================================
Tests the FastAPI endpoints using TestClient (no real server needed).
Uses an in-memory SQLite database for complete isolation.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from Point_1.db.engine import Base, get_db
from Point_1.main import app


# ── Test database setup ──────────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///./test_point_1.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealth:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["tables_created"] is True

    def test_root(self):
        r = client.get("/")
        assert r.status_code == 200
        assert "Point 1" in r.json()["service"]


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Lifecycle
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchLifecycle:
    def test_create_batch(self):
        r = client.post("/api/batch/start", json={"category": "laptop", "target_count": 5})
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "CREATED"
        assert data["category"] == "laptop"
        assert "batch_" in data["batch_id"]

    def test_batch_status(self):
        r = client.post("/api/batch/start", json={"category": "all", "target_count": 10})
        bid = r.json()["batch_id"]
        r2 = client.get(f"/api/batch/{bid}/status")
        assert r2.status_code == 200
        assert r2.json()["batch_id"] == bid

    def test_batch_not_found(self):
        r = client.get("/api/batch/nonexistent/status")
        assert r.status_code == 404

    def test_list_batches(self):
        client.post("/api/batch/start", json={"category": "laptop", "target_count": 5})
        client.post("/api/batch/start", json={"category": "phone", "target_count": 10})
        r = client.get("/api/batch/list")
        assert r.status_code == 200
        assert len(r.json()) >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# Scraper Ingestion
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_PRODUCTS = [
    {
        "retailer_id": "2b_egypt",
        "raw_title": "Lenovo LOQ Gaming Laptop 16GB RAM 512GB SSD RTX 4060",
        "raw_current_price": 42999.0,
        "raw_original_price": 49999.0,
        "product_url": "https://2b.com.eg/lenovo-loq-rtx4060",
    },
    {
        "retailer_id": "sigma_computer",
        "raw_title": "Samsung Galaxy S24 Ultra Snapdragon 8 Gen 3 12GB 256GB",
        "raw_current_price": 72000.0,
        "product_url": "https://sigma.com/samsung-s24-ultra",
    },
]


class TestScrapeIngestion:
    def _create_batch(self):
        r = client.post("/api/batch/start", json={"category": "all", "target_count": 10})
        return r.json()["batch_id"]

    def test_ingest_products(self):
        bid = self._create_batch()
        r = client.post(f"/api/batch/{bid}/ingest", json=SAMPLE_PRODUCTS)
        assert r.status_code == 200
        data = r.json()
        assert data["inserted_count"] == 2
        assert data["skipped_count"] == 0
        assert data["total_in_batch"] == 2

    def test_ingest_nonexistent_batch(self):
        r = client.post("/api/batch/fake_batch/ingest", json=SAMPLE_PRODUCTS)
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# ETL Processing
# ═══════════════════════════════════════════════════════════════════════════════

class TestETLProcessing:
    def _ingest_batch(self):
        r = client.post("/api/batch/start", json={"category": "all", "target_count": 10})
        bid = r.json()["batch_id"]
        client.post(f"/api/batch/{bid}/ingest", json=SAMPLE_PRODUCTS)
        return bid

    def test_run_etl(self):
        bid = self._ingest_batch()
        r = client.post(f"/api/etl/run/{bid}")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "COMPLETED"
        assert data["processed_count"] == 2
        assert data["feature_columns"] > 10
        assert "Laptop" in data["category_distribution"]
        assert "Phone" in data["category_distribution"]

    def test_etl_status_after_run(self):
        bid = self._ingest_batch()
        client.post(f"/api/etl/run/{bid}")
        r = client.get(f"/api/etl/status/{bid}")
        assert r.status_code == 200
        assert r.json()["status"] == "COMPLETED"

    def test_etl_no_data(self):
        r = client.post("/api/batch/start", json={"category": "all", "target_count": 10})
        bid = r.json()["batch_id"]
        r2 = client.post(f"/api/etl/run/{bid}")
        assert r2.status_code == 404

    def test_get_processed_products(self):
        bid = self._ingest_batch()
        client.post(f"/api/etl/run/{bid}")
        r = client.get(f"/api/etl/processed/{bid}")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        products = data["products"]
        laptop = [p for p in products if p["category"] == "Laptop"][0]
        assert laptop["gpu"] == "RTX 4060"
        assert laptop["gpu_tier_num"] == 6
        assert laptop["is_gaming"] is True
        assert laptop["compute_potential"] is not None

    def test_full_pipeline_flow(self):
        """End-to-end: create batch → ingest → ETL → verify."""
        # Create
        r1 = client.post("/api/batch/start", json={"category": "laptop", "target_count": 5})
        assert r1.status_code == 201
        bid = r1.json()["batch_id"]

        # Ingest
        r2 = client.post(f"/api/batch/{bid}/ingest", json=SAMPLE_PRODUCTS)
        assert r2.json()["inserted_count"] == 2

        # ETL
        r3 = client.post(f"/api/etl/run/{bid}")
        assert r3.json()["status"] == "COMPLETED"
        assert r3.json()["processed_count"] == 2

        # Verify
        r4 = client.get(f"/api/batch/{bid}/status")
        assert r4.json()["status"] == "COMPLETED"
        assert r4.json()["etl_count"] == 2

        # Check health reflects new data
        r5 = client.get("/health")
        assert r5.json()["total_batches"] >= 1
        assert r5.json()["total_raw_records"] >= 2
        assert r5.json()["total_processed_records"] >= 2
