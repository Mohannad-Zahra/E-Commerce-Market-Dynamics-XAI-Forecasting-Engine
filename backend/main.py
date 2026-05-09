"""
main.py  –  FastAPI application backed by electronics_history.db
"""
from __future__ import annotations
import re
import logging
import threading
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

import requests
import schemas
from database import get_db, engine
from ml_models import (
    predict_price_onnx,
    predict_stability_onnx,
    NEW_FEATURES,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(
    title="E-Commerce XAI Forecasting Engine",
    description=(
        "FastAPI backend serving 1,790 real Egyptian electronics products "
        "from `electronics_history.db` plus three ML forecasting models."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Retailer detection from product_id URL ─────────────────────────────────────

def _retailer(product_id: str) -> str:
    if "2b.com.eg" in product_id:      return "2b_egypt"
    if "sigma-computer" in product_id: return "sigma_computer"
    if "dream2000" in product_id:      return "dream2000"
    if "btech.com" in product_id:      return "btech"
    return "other"


# ── Category inference from cpu_tier / gpu_tier / title ─────────────────────

def _category(row: dict) -> str:
    title = (row.get("raw_title") or "").lower()
    
    # 1. MOBILES (Expanded for Tecno, Huawei, itel, etc.)
    if any(k in title for k in [
        "iphone", "samsung galaxy", "redmi", "xiaomi", "oppo", "vivo", "realme", "infinix", 
        "honor", "hmd", "motorola", "moto ", "nokia", "google pixel", "tecno", "huawei", 
        "zte", "itel", "pova", "spark", "camon", "phantom", "zero 30", "zero ultra", "y90", "y70"
    ]):
        return "mobiles"
    
    # 2. TABLETS (Specific catch for Idea Tab and MatePad)
    if any(k in title for k in ["ipad", "tablet", "tab ", "tab s", "tab a", "idea tab", "matepad", "t-tab", "pad 6", "pad x"]):
        return "tablets"

    # 3. LAPTOPS (Priority series + Mobile CPU signatures)
    if any(k in title for k in [
        "laptop", "notebook", "aspire", "vivobook", "ideapad", "macbook", "zenbook", "pavilion", 
        "legion", "loq", "nitro", "rog ", "strix", "victus", "predator", "alienware", "omen", 
        "tuf ", "katana", "sword", "vector", "stealth", "thin ", "cyborg", "bravo", "thinkpad", 
        "latitude", "vostro", "xps", "probook", "elitebook", "surface", "proart", "raider", 
        "prestige", "modern 14", "modern 15", "expertbook", "a16", "hx ", "hs ", "fhd", "qhd", "15.6", "14-inch"
    ]):
        return "laptops"
        
    # 4. MONITORS
    if any(k in title for k in ["monitor", "display", "screen", "24-inch", "27-inch", "32-inch", "curved monitor"]):
        return "monitors"
        
    # 5. PC COMPONENTS (RAM, SSD, GPU, CPU, PSU)
    is_gpu = any(k in title for k in ["gpu", "graphics card", "rtx", "gtx", "rx 6", "rx 7", "rx 5", "radeon"])
    is_cpu = any(k in title for k in ["processor", "cpu", "ryzen", "intel core", "core i3", "core i5", "core i7", "core i9", "12100", "12400", "13400", "13900", "14900", "7600x", "7800x3d"])
    is_mem = any(k in title for k in ["ddr4", "ddr5", "ram", "memory", "udimm", "sodimm", "3200mhz", "3600mhz", "4800mhz", "5200mhz", "6000mhz", "cl16", "cl18", "cl22", "cl30"])
    is_storage = any(k in title for k in ["ssd", "nvme", "m.2", "hdd", "hard disk", "sata", "barracuda", "solid state drive", "980 pro", "990 pro", "lexar", "kingston fury", "crucial p3"])
    is_mobo = any(k in title for k in ["motherboard", "mainboard", "h610", "b660", "b760", "z690", "z790", "am4", "am5", "lga1700"])
    is_power_case = any(k in title for k in ["psu", "power supply", "cpu cooler", "case fan", "chassis", "liquid cooler", "tower case"])
    
    if is_gpu or is_cpu or is_mem or is_storage or is_mobo or is_power_case:
        return "pc-components"
        
    # 6. ACCESSORIES
    if any(k in title for k in [
        "keyboard", "mouse", "headset", "headphone", "speaker", "earbuds", "airpods", 
        "flash drive", "usb", "pendrive", "webcam", "mic", "cable", "adapter", "charger", 
        "bag", "case", "dock", "hub", "stylus", "pen "
    ]):
        return "accessories"
        
    # 7. GAMING CONSOLES
    if any(k in title for k in ["playstation", "ps5", "ps4", "xbox", "controller", "gamepad", "nintendo", "switch joy-con"]):
        return "gaming-consoles"
        
    return "electronics"


def _brand(row: dict) -> str:
    title = (row.get("raw_title") or "").lower()
    for b in ["apple", "samsung", "lenovo", "asus", "acer", "dell", "hp", "msi",
              "xiaomi", "oppo", "vivo", "realme", "infinix", "kingston",
              "pny", "antec", "seagate", "western digital", "redragon"]:
        if b in title:
            return b.title()
    return "Unknown"


_THUMB_FALLBACK = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='300'%3E%3Crect fill='%23f8fafc' width='400' height='300'/%3E%3Ctext fill='%2364748b' font-family='sans-serif' font-size='20' x='200' y='155' text-anchor='middle'%3EElectronics%3C/text%3E%3C/svg%3E"

# Category → SVG colour pair (bg, text) for inline data URI thumbnails (Light Theme)
_CAT_THUMB: dict[str, tuple[str, str]] = {
    "laptops":         ("f0f9ff", "0ea5e9"),
    "mobiles":         ("faf5ff", "8b5cf6"),
    "tablets":         ("f0fdf4", "10b981"),
    "pc-components":   ("fff7ed", "f97316"),
    "monitors":        ("fff1f2", "f43f5e"),
    "accessories":     ("fefce8", "eab308"),
    "gaming-consoles": ("fef2f2", "ef4444"),
    "electronics":     ("f8fafc", "64748b"),
}


def _thumbnail(row: dict) -> str:
    """Return an instant inline SVG data URI — no external network request."""
    cat   = _category(row)
    brand = _brand(row)
    bg, fg = _CAT_THUMB.get(cat, ("1e293b", "94a3b8"))
    label = brand[:14]  # keep label short
    # URL-encode just the characters needed for a data URI
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='400' height='300'>"
        f"<rect fill='#{bg}' width='400' height='300'/>"
        f"<text fill='#{fg}' font-family='Inter,sans-serif' font-size='22' "
        f"font-weight='700' x='200' y='140' text-anchor='middle'>{label}</text>"
        f"<text fill='#{fg}99' font-family='Inter,sans-serif' font-size='13' "
        f"x='200' y='168' text-anchor='middle'>{cat.replace('-',' ').upper()}</text>"
        f"</svg>"
    )
    # Minimal safe encoding for a data URI
    encoded = (
        svg
        .replace("#", "%23")
        .replace("'", "%27")
        .replace("<", "%3C")
        .replace(">", "%3E")
        .replace(" ", "%20")
    )
    return f"data:image/svg+xml,{encoded}"


def _thumbnail_from_row(row: dict) -> tuple[str, list[str]]:
    """
    Prefer scraped product page image URL (joined from products.thumbnail);
    fall back to inline category/brand SVG.
    """
    import json
    
    thumb = None
    images = []
    
    # Try parsing images JSON
    images_raw = row.get("product_images")
    if images_raw:
        try:
            images = json.loads(images_raw)
        except:
            pass
            
    # Use first image as thumbnail if available
    if images:
        import os
        filtered = []
        seen_fnames = set()
        first_prefix = None
        
        for img in images:
            fname = os.path.basename(img).lower()
            if not fname: continue
            
            # Use the first valid image to determine the product prefix (heuristic)
            if first_prefix is None:
                first_prefix = fname.split('-')[0] if '-' in fname else fname[:4]
                
            # Keep if unique filename AND matches the product's prefix
            if fname not in seen_fnames and fname.startswith(first_prefix):
                filtered.append(img)
                seen_fnames.add(fname)
        
        images = filtered[:10] # Cap to avoid UI clutter
        if images:
            thumb = images[0]
            
    if not thumb:
        # Fallback to single thumbnail column
        url = row.get("product_thumbnail")
        if url and isinstance(url, str):
            u = url.strip()
            if u.lower().startswith(("http://", "https://")):
                thumb = u
                images = [u]
                
    if thumb:
        return thumb, images
        
    svg = _thumbnail(row)
    return svg, [svg]


def _to_product(row: dict, numeric_id: int) -> dict:
    discount = 0.0
    base = row.get("base_price_egp") or 0
    current = row.get("price_egp") or 0
    if base and current and base > current:
        discount = round((base - current) / base * 100, 1)

    cat = _category(row)
    thumb, images = _thumbnail_from_row(row)
    vol = row.get("volatility_score") or 0

    return {
        "id":                  numeric_id,
        "title":               row.get("raw_title") or "Unknown Product",
        "description":         row.get("raw_title") or "Professional electronics with AI-enhanced market analysis.",
        "price":               round(current or base, 2),
        "originalPrice":       round(base, 2) if base else None,
        "discountPercentage":  discount,
        "rating":              round(4.0 + min(vol / 100, 0.5), 1),
        "stock":               5 + (numeric_id % 15),
        "brand":               _brand(row),
        "category":            cat,
        "thumbnail":           thumb,
        "images":              images,
        "retailer_id":         _retailer(row.get("product_id", "")),
        "product_url":         row.get("product_id", ""),
        "scrape_timestamp":    row.get("latest_ts") or row.get("scrape_timestamp", ""),
        "volatility_score":    round(vol, 2),
        "official_egp_usd":    row.get("official_egp_usd"),
        "cpi_inflation":       row.get("cpi_inflation"),
        "is_major_sale_period": row.get("is_major_sale_period"),
        "compute_potential":   row.get("compute_potential"),
        "delta_p_1d":          row.get("delta_p_1d"),
        "delta_p_7d":          row.get("delta_p_7d"),
        "delta_p_14d":         row.get("delta_p_14d"),
        "vol_30d":             row.get("vol_30d"),
        "competitor_scarcity": row.get("competitor_scarcity_count"),
    }


# ── Core query: one row per unique product (latest snapshot) ─────────────────

_LATEST_PRODUCTS_SQL = text("""
    SELECT
        agg.product_id,
        agg.raw_title,
        agg.latest_ts,
        agg.price_egp,
        agg.base_price_egp,
        agg.official_egp_usd,
        agg.cpi_inflation,
        agg.is_major_sale_period,
        agg.compute_potential,
        agg.delta_p_1d,
        agg.delta_p_7d,
        agg.delta_p_14d,
        agg.vol_30d,
        agg.competitor_scarcity_count,
        agg.volatility_score,
        agg.category,
        pt.thumbnail AS product_thumbnail,
        pt.images AS product_images
    FROM (
        SELECT
            product_id,
            raw_title,
            MAX(scrape_timestamp) AS latest_ts,
            price_t_plus_14 AS price_egp,
            price_t_plus_14 AS base_price_egp,
            official_egp_usd,
            cpi_inflation,
            is_major_sale_period,
            compute_potential,
            delta_p_1d,
            delta_p_7d,
            delta_p_14d,
            vol_30d,
            competitor_scarcity_count,
            stability_score AS volatility_score,
            category
        FROM master_training_features
        GROUP BY product_id
    ) AS agg
    LEFT JOIN products pt ON pt.product_url = agg.product_id
    ORDER BY agg.price_egp DESC
""")


# ═══════════════════════════════════════════════════════════════════════════════
# Product endpoints
# ═══════════════════════════════════════════════════════════════════════════════

_CACHE_LOCK = threading.Lock()
_CACHED_PRODUCTS = None
_CACHED_CATEGORIES = None
_CACHED_STATS = None

def get_cached_data(db: Session):
    global _CACHED_PRODUCTS, _CACHED_CATEGORIES, _CACHED_STATS
    if _CACHED_PRODUCTS is None:
        with _CACHE_LOCK:
            if _CACHED_PRODUCTS is None:
                log.info("Loading master product cache...")
                rows = db.execute(_LATEST_PRODUCTS_SQL).mappings().all()
                products = []
                cats = set()
                for i, r in enumerate(rows):
                    p = _to_product(dict(r), i + 1)
                    products.append(p)
                    cats.add(p["category"])
                _CACHED_PRODUCTS = products
                _CACHED_CATEGORIES = sorted(cats)
                
                # Pre-calculate stats
                r1 = db.execute(text("SELECT COUNT(*) as total FROM master_training_features")).mappings().first()
                r3 = db.execute(text("SELECT MIN(scrape_timestamp) as first, MAX(scrape_timestamp) as last FROM master_training_features")).mappings().first()
                r4 = db.execute(text("SELECT MIN(price_t_plus_14) as lo, MAX(price_t_plus_14) as hi, AVG(price_t_plus_14) as avg FROM master_training_features")).mappings().first()
                
                _CACHED_STATS = {
                    "total_rows":     r1["total"],
                    "unique_products":len(products),
                    "date_from":      r3["first"],
                    "date_to":        r3["last"],
                    "price_min_egp":  round(r4["lo"], 2) if r4["lo"] else 0,
                    "price_max_egp":  round(r4["hi"], 2) if r4["hi"] else 0,
                    "price_avg_egp":  round(r4["avg"], 2) if r4["avg"] else 0,
                }
                
                log.info("Master product cache loaded. Unique products: %d", len(products))
    return _CACHED_PRODUCTS, _CACHED_CATEGORIES, _CACHED_STATS

@app.get("/api/products", summary="Paginated product list (one record per unique product, latest price)")
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    products, _, _ = get_cached_data(db)
    page = products[skip: skip + limit]
    return {"products": page, "total": len(products), "skip": skip, "limit": limit}


@app.get("/api/products/search", summary="Full-text search on product titles")
def search_products(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    products, _, _ = get_cached_data(db)
    query_lower = q.lower()
    matched = [p for p in products if query_lower in p["title"].lower()]
    return {"products": matched[:50], "total": len(matched)}


@app.get("/api/products/categories", summary="Distinct inferred categories")
def list_categories(db: Session = Depends(get_db)):
    _, cats, _ = get_cached_data(db)
    return cats


@app.get("/api/products/category/{category}", summary="Products by inferred category")
def products_by_category(
    category: str,
    limit: int = Query(200, ge=1, le=500, description="Max products to return (use 20 for home page sliders)"),
    db: Session = Depends(get_db),
):
    products, _, _ = get_cached_data(db)
    matched = [p for p in products if p["category"] == category]
    return {"products": matched[:limit], "total": len(matched)}


@app.get("/api/products/{product_id}", summary="Single product by numeric position ID")
def get_product(product_id: int, db: Session = Depends(get_db)):
    products, _, _ = get_cached_data(db)
    idx  = product_id - 1
    if idx < 0 or idx >= len(products):
        raise HTTPException(status_code=404, detail="Product not found")
    return products[idx]


@app.get("/api/products/{product_id}/history", summary="Price history for a specific product")
def get_price_history(product_id: int, db: Session = Depends(get_db)):
    """Returns daily price history for use in charts."""
    products, _, _ = get_cached_data(db)
    idx = product_id - 1
    if idx < 0 or idx >= len(products):
        raise HTTPException(status_code=404, detail="Product not found")

    url = products[idx]["product_url"]
    history_sql = text("""
        SELECT scrape_timestamp, 
               price_t_plus_14 AS price_egp, 
               stability_score AS volatility_score,
               official_egp_usd
        FROM master_training_features
        WHERE product_id = :url
        ORDER BY scrape_timestamp ASC
    """)
    hist = db.execute(history_sql, {"url": url}).mappings().all()
    return {
        "product_id":  product_id,
        "product_url": url,
        "history": [dict(h) for h in hist],
    }


@app.get("/api/stats", summary="Database statistics")
def get_stats(db: Session = Depends(get_db)):
    _, _, stats = get_cached_data(db)
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# ML Forecasting endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/forecast/features", summary="Feature metadata for the new XAI models")
def get_feature_metadata():
    return {
        "xai_forecast": {
            "n_features":   14,
            "feature_names": NEW_FEATURES,
            "description":  "14-feature XAI model predicting 14d price and stability.",
        }
    }


@app.post(
    "/api/forecast/price/onnx",
    response_model=schemas.PriceForecastResponse,
    summary="Model 1 – 14d Price Forecast (ONNX)",
)
def forecast_price_onnx(body: schemas.PriceForecastRequest):
    try:
        return predict_price_onnx(body.features)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")


@app.post(
    "/api/forecast/stability",
    response_model=schemas.StabilityResponse,
    summary="Model 2 – Stability Scorer (ONNX)",
)
def forecast_stability(body: schemas.StabilityRequest):
    try:
        return predict_stability_onnx(body.features)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {e}")


# ── Chat Proxy (N8N) ──────────────────────────────────────────────────────────

@app.post("/api/chat", summary="Proxy chat requests to n8n AI Agent")
def chat_proxy(body: dict):
    """
    Proxies chat messages to the n8n webhook to avoid CORS issues.
    Expects {"message": "...", "sessionId": "..."}
    """
    n8n_url = "https://abdelrhaman.abdelrhaman.cfd/webhook/b5600934-fe67-4a10-a00b-9eca3ffaf01d/chat"
    
    try:
        # Standardize the payload so n8n always finds what it needs
        payload = {
            "chatInput": body.get("message") or body.get("chatInput"),
            "message": body.get("message") or body.get("chatInput"),
            "sessionId": body.get("chatId") or body.get("sessionId"),
            "chatId": body.get("chatId") or body.get("sessionId"),
            "url": body.get("url"),
            "route": body.get("route", "general")
        }
        
        response = requests.post(
            n8n_url,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        # Try to return JSON if n8n returned JSON, otherwise return text
        try:
            return response.json()
        except:
            return {"output": response.text}
            
    except requests.exceptions.RequestException as e:
        log.error(f"N8N Proxy Error: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to reach AI Agent: {str(e)}")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "db": "electronics_history.db", "models": 2}
