# Data Processing & Price Calculation Report

This report details the specific pipeline used to generate `Dataset_Pipeline_Processed.csv` and the mathematical logic for calculating the `price_final` from the `baseline_egp`.

---

## 1. Final Price Calculation Logic
The `price_final` is calculated using a **Lifecycle Depreciation Model**. This model adjusts the baseline price based on how long a product has been in the market relative to its global release date.

### The Formula
$$\text{price\_final} = \text{baseline\_egp} \times e^{-k \cdot D}$$

| Variable | Description |
| :--- | :--- |
| **`baseline_egp`** | The initial calibrated price (before depreciation). |
| **$e$** | Euler's number ($\approx 2.71828$). |
| **$k$** | **Depreciation Constant**: Determined by the product's scarcity (`import_lambda`). |
| **$D$** | **Product Age**: The number of days between the Global Release Date and the Transaction Date. |

### Depreciation Constant ($k$) Assignment
The value of $k$ determines the rate of price decay. It is assigned based on the `import_lambda` (scarcity indicator):
*   **High Scarcity (`import_lambda >= 0.9`)**: $k = 0.0005$ (Slowest decay)
*   **Moderate Scarcity (`import_lambda >= 0.6`)**: $k = 0.0011$ (Standard decay)
*   **Local/Common (`import_lambda < 0.6`)**: $k = 0.0$ (No depreciation)

---

## 2. Production Pipeline: `Dataset_Pipeline_Processed.csv`
The generation of the final processed dataset follows a three-step transformation sequence to prepare it for machine learning.

### Step A: Data Ingestion & Pricing (`produce_main_dataset.py`)
1.  **Release Date Mapping**: Merges raw titles with a global release date dictionary.
2.  **Age Calculation**: Computes $D$ (Days since release).
3.  **Depreciation Application**: Calculates the `multiplier` ($e^{-k \cdot D}$) and applies it to `price_egp` to get `price_final`.
4.  **Output**: `Dataset_Main.csv`.

### Step B: Feature Refinement (`refine_pipeline.py`)
1.  **Cleaning**: Removes high-volatility noise and redundant columns.
2.  **Output**: `Dataset_Refined.csv`.

### Step C: Processing & Feature Engineering (`process_pipeline.py`)
This is the final stage that produces `Dataset_Pipeline_Processed.csv`.
1.  **Time-Series Aggregation**:
    *   Calculates `price_14d_avg`: A 14-day rolling mean of `price_final` per product.
2.  **Temporal Scaling**:
    *   Converts `D` (days) into `D_months` (Months since release) by dividing by **30.436875**.
3.  **Hardware Categorization**:
    *   Transforms `ram_gb_ordinal` and `storage_ordinal` into categorical bins (e.g., '8-16', '256-512').
4.  **Column Pruning**: Drops raw date strings and legacy features to minimize leakage.

---

## 3. Summary of Key Indicators
*   **Primary Baseline**: `price_egp`
*   **Primary Target**: `price_final`
*   **Primary Feature**: `D_months` (Scaled product age)
*   **Contextual Feature**: `price_14d_avg` (Short-term trend)

**Status**: Pipeline execution verified. `Dataset_Pipeline_Processed.csv` is optimized for regression and time-series forecasting.
