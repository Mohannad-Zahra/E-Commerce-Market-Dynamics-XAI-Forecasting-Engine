# Duplication & Version Resolution Log

Based on the architectural audit, the following redundancies and outdated artifacts have been identified. Below is the strict "Source of Truth" regarding what is active and what should be archived to prevent namespace pollution.

## 1. Volatility ML Components
- **Active/Newest Version**: `Vola Score/` 
  - **Reasoning**: Confirmed by lead engineer. This directory holds the active logic computing price deltas and stability parameters before passing data downstream.
- **Outdated/Redundant Version**: `Volatility score ML pipeline/`
  - **Reasoning**: This folder contains older pipeline scripts (`phase1-7.py`) and outdated `.parquet` files that have been superseded. 
  - **Action Required**: Safely archive `Volatility score ML pipeline/` to a `legacy/` directory or delete it entirely.

## 2. Web Scraper Components
- **Active/Newest Version**: Root `Web Scrapper/`
  - **Reasoning**: Contains the active `watchdog.py`, Playwright payloads, and batch execution scripts used in production.
- **Outdated/Redundant Version**: `E-Commerce Market Dynamics & XAI Forecasting Engine/`
  - **Reasoning**: This directory contains a redundant git wrapper and a cloned `Web Scrapper/` folder. It creates path confusion.
  - **Action Required**: Move unique documentation (`General Documents/`, `README.md`) out of this folder to the root/docs, and then archive/delete the entire `E-Commerce Market Dynamics & XAI Forecasting Engine/` folder.

## 3. Test Data / Messy Data
- **Active Data State**: Clean test data is handled within the components dynamically.
- **Messy Data Location**: `oldData_need the scrape_time to update for it to work/`
  - **Reasoning**: Contains historical/messy JSON dumps from April 2026. This data is valid for system testing but currently unstructured and clutters the root.
  - **Action Required**: Create an ingestion script to merge all JSON files in this folder into a single test file, and route it to the first component (ETL) for unified processing. Afterwards, archive the individual raw `.json` files.
