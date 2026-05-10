import sys
import os
from pathlib import Path

# Ensure the root directory is in the path for imports
sys.path.append(str(Path(__file__).parent.parent))

from ETL.Data_Pipeline.features import run_etl_pipeline

def main():
    print("=" * 60)
    print("  Unified ETL Orchestrator v1.0")
    print("=" * 60)
    
    # 1. Feature Extraction & Engineering
    run_etl_pipeline()
    
    # 2. Forecasting (To be integrated)
    print("\n[INFO] Initializing Forecasting Layer...")
    
    # 3. Verification (To be integrated)
    print("[INFO] Initializing Agentic Verification Layer...")
    
    print("\n" + "=" * 60)
    print("  Pipeline Execution Finished")
    print("=" * 60)

if __name__ == "__main__":
    main()
