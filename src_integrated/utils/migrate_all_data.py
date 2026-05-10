import os
import json
import pandas as pd
from urllib.parse import urlparse
from sqlalchemy.orm import sessionmaker
from src_integrated.database.db import engine
from src_integrated.database.models import Product, MacroEconomic, PriceHistory, MLForecastShap
from datetime import datetime
from tqdm import tqdm

def extract_retailer(url):
    if pd.isna(url):
        return 'unknown'
    domain = urlparse(url).netloc
    if '2b.com.eg' in domain:
        return '2b_egypt'
    elif 'sigma-computer' in domain:
        return 'sigma-computer'
    elif 'dream2000' in domain:
        return 'dream2000'
    return domain.replace('www.', '').split('.')[0]

def migrate_data():
    csv_path = r'C:\Users\mohan\OneDrive\Desktop\Wise Purchaser\forecast+shap\ECom_Forecast_XAI_data.csv'
    release_dates_path = r'C:\Users\mohan\OneDrive\Desktop\Wise Purchaser\release_dates_dictionary_v4.json'
    
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    print("Reading CSV (this may take a minute)...")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows.")

    # Load release dates dictionary
    release_dates = {}
    if os.path.exists(release_dates_path):
        with open(release_dates_path, 'r', encoding='utf-8') as f:
            release_dates = json.load(f)

    # Extract retailer from product_id
    df['retailer_id'] = df['product_id'].apply(extract_retailer)

    Session = sessionmaker(bind=engine)
    session = Session()

    # Pre-fetch existing IDs to speed up "get-or-create"
    print("Pre-fetching existing products and macro dates...")
    existing_product_ids = {p[0] for p in session.query(Product.id).all()}
    existing_macro_dates = {m[0] for m in session.query(MacroEconomic.date_id).all()}

    try:
        print("Starting migration...")
        # Batch processing
        batch_size = 500
        for i in tqdm(range(0, len(df), batch_size)):
            batch_df = df.iloc[i : i + batch_size]
            
            for _, row in batch_df.iterrows():
                scrape_timestamp_str = str(row['scrape_timestamp'])
                try:
                    scrape_timestamp = datetime.strptime(scrape_timestamp_str, "%Y-%m-%d")
                except ValueError:
                    scrape_timestamp = datetime.strptime(scrape_timestamp_str, "%Y-%m-%d %H:%M:%S")
                
                date_id = scrape_timestamp.date()

                # 1. MacroEconomic
                if date_id not in existing_macro_dates:
                    macro = MacroEconomic(
                        date_id=date_id,
                        official_egp_usd=row.get('official_egp_usd', 0.0),
                        cpi_inflation=row.get('cpi_inflation', 0.0),
                        import_lambda=row.get('import_lambda', 0.0),
                        multiplier=row.get('multiplier', 0.0),
                        is_major_sale_period=bool(row.get('is_major_sale_period', False)),
                        sale_event_label=str(row['sale_event_label']) if pd.notna(row.get('sale_event_label')) else None
                    )
                    session.add(macro)
                    existing_macro_dates.add(date_id)
                
                # 2. Product
                product_id = row['product_id']
                if product_id not in existing_product_ids:
                    raw_title = row['raw_title']
                    date_str = release_dates.get(raw_title)
                    if not date_str and pd.notna(row.get('global_release_date_str')):
                        date_str = str(row['global_release_date_str'])
                    
                    release_date_obj = None
                    if date_str and date_str != 'nan':
                        try:
                            parts = date_str.split('-')
                            if len(parts) >= 2:
                                release_date_obj = datetime(int(parts[0]), int(parts[1]), 1).date()
                            elif len(parts) == 1:
                                release_date_obj = datetime(int(parts[0]), 1, 1).date()
                        except Exception:
                            pass
                    
                    product = Product(
                        id=product_id,
                        retailer_id=row['retailer_id'],
                        raw_title=raw_title,
                        product_url=product_id,
                        category=row.get('category', 'Unknown'),
                        global_release_date_str=date_str if date_str and date_str != 'nan' else None,
                        global_release_date=release_date_obj,
                        missing_release_date=bool(row.get('missing_release_date', False)),
                        compute_potential=row.get('compute_potential')
                    )
                    session.add(product)
                    existing_product_ids.add(product_id)
                
                # Flush every now and then to ensure macro/product are available for FKs
                # but we've already handled the logic to avoid duplicates using sets.
                
                # 3. PriceHistory
                ph = PriceHistory(
                    product_id=product_id,
                    date_id=date_id,
                    scrape_timestamp=scrape_timestamp,
                    raw_current_price=row.get('price_final', 0.0),
                    competitor_scarcity_count=int(row.get('competitor_scarcity_count', 0)),
                    volume_weight=row.get('volume_weight', 0.0),
                    k=row.get('k', 0.0),
                    D_months=row.get('D_months', 0.0),
                    delta_p_1d=row.get('delta_p_1d', 0.0),
                    delta_p_7d=row.get('delta_p_7d', 0.0),
                    delta_p_14d=row.get('delta_p_14d', 0.0),
                    vol_30d=row.get('vol_30d', 0.0)
                )
                session.add(ph)
                session.flush() # Need this to get ph.id for MLForecastShap

                # 4. MLForecastShap
                shap = MLForecastShap(
                    price_history_id=ph.id,
                    stability_score=row.get('stability_score', 0.0),
                    predicted_stability_score=row.get('predicted_stability_score', 0.0),
                    price_t_plus_14=row.get('price_t_plus_14', 0.0),
                    shap_compute_potential=row.get('shap_compute_potential', 0.0),
                    shap_delta_p_7d=row.get('shap_delta_p_7d', 0.0),
                    shap_delta_p_14d=row.get('shap_delta_p_14d', 0.0),
                    shap_delta_p_1d=row.get('shap_delta_p_1d', 0.0),
                    shap_vol_30d=row.get('shap_vol_30d', 0.0),
                    shap_official_egp_usd=row.get('shap_official_egp_usd', 0.0),
                    shap_cpi_inflation=row.get('shap_cpi_inflation', 0.0),
                    shap_is_major_sale_period=row.get('shap_is_major_sale_period', 0.0),
                    shap_competitor_scarcity_count=row.get('shap_competitor_scarcity_count', 0.0),
                    shap_volume_weight=row.get('shap_volume_weight', 0.0),
                    shap_D_months=row.get('shap_D_months', 0.0),
                    shap_k=row.get('shap_k', 0.0),
                    shap_import_lambda=row.get('shap_import_lambda', 0.0),
                    shap_missing_release_date=row.get('shap_missing_release_date', 0.0),
                    shap_base_expected_price=row.get('shap_base_expected_price', 0.0),
                    
                    delta_shap_compute_potential=row.get('delta_shap_compute_potential', 0.0),
                    delta_shap_delta_p_7d=row.get('delta_shap_delta_p_7d', 0.0),
                    delta_shap_delta_p_14d=row.get('delta_shap_delta_p_14d', 0.0),
                    delta_shap_delta_p_1d=row.get('delta_shap_delta_p_1d', 0.0),
                    delta_shap_vol_30d=row.get('delta_shap_vol_30d', 0.0),
                    delta_shap_official_egp_usd=row.get('delta_shap_official_egp_usd', 0.0),
                    delta_shap_cpi_inflation=row.get('delta_shap_cpi_inflation', 0.0),
                    delta_shap_is_major_sale_period=row.get('delta_shap_is_major_sale_period', 0.0),
                    delta_shap_competitor_scarcity_count=row.get('delta_shap_competitor_scarcity_count', 0.0),
                    delta_shap_volume_weight=row.get('delta_shap_volume_weight', 0.0),
                    delta_shap_D_months=row.get('delta_shap_D_months', 0.0),
                    delta_shap_k=row.get('delta_shap_k', 0.0),
                    delta_shap_import_lambda=row.get('delta_shap_import_lambda', 0.0),
                    delta_shap_missing_release_date=row.get('delta_shap_missing_release_date', 0.0)
                )
                session.add(shap)

            session.commit() # Commit every batch
            
        print("Migration complete.")
    except Exception as e:
        session.rollback()
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    migrate_data()
