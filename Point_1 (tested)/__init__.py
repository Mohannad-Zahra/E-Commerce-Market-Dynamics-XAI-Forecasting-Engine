"""
Point_1 — Unified Data Ingestion & ETL Layer
=============================================
Phase 1 of the Wise Purchaser architecture refactor.

Provides:
  - Unified database engine (SQLite → PostgreSQL swappable)
  - Pydantic schemas for all pipeline stages
  - FastAPI routers for Scraper ingestion + ETL processing
  - Core ETL feature extraction engine
"""
