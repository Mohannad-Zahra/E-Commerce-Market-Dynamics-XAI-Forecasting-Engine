"""
llm_service.py
==============
Calls the Groq API (OpenAI-compatible) to generate a short, user-friendly
explanation for why a laptop candidate is recommended.

Input  : one candidate dict from recommendations.json
Output : plain-English explanation string (3-5 sentences)
"""

import os
import time
from typing import Any, Dict

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
MODEL_NAME   = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are a product recommendation analyst explaining laptop deals to everyday shoppers.
Explain why this laptop is a good buy right now using only the data provided.

Rules:
- Do NOT mention SHAP, ML models, or technical terms
- Focus on price trends, value-for-money, and market timing
- Be concise and friendly – 3 to 5 sentences maximum
- Write as if speaking to a non-technical buyer"""

FALLBACK = (
    "Unable to generate an AI explanation right now. "
    "Based on recent market data, this laptop shows favorable pricing conditions."
)

MAX_RETRIES    = 2
TIMEOUT_SECS   = 12


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(candidate: Dict[str, Any]) -> str:
    """Build the user message from a candidate dict."""
    drivers = candidate.get("shap_drivers") or {}
    # Convert driver dict to a readable list (top 3 by absolute value)
    top_drivers = sorted(drivers.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
    driver_text = ", ".join(f"{k}" for k, _ in top_drivers) if top_drivers else "N/A"

    return (
        f"Model: {candidate.get('model', 'N/A')}\n"
        f"Current Price: {candidate.get('current_price', 'N/A')}\n"
        f"14-day Average Price: {candidate.get('price_14d_avg', 'N/A')}\n"
        f"Forecasted Price (14 days): {candidate.get('forecasted_price', 'N/A')}\n"
        f"Market Classification: {candidate.get('classification', 'N/A')}\n"
        f"Recommendation Score: {candidate.get('r_score', 'N/A')}\n"
        f"Key Price Factors: {driver_text}\n\n"
        "Explain why this laptop is a good buy right now in 3-5 simple sentences."
    )


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def generate_explanation(candidate: Dict[str, Any]) -> str:
    """
    Generate a human-readable explanation for one candidate.

    Parameters
    ----------
    candidate : dict  –  one item from recommendations.json

    Returns
    -------
    str  –  plain-English explanation, or FALLBACK if the API fails.
    """
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_prompt(candidate)},
        ],
        "temperature": 0.2,
        "max_tokens":  200,
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=TIMEOUT_SECS)

            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"].strip()
                if text:
                    return text

            # Retry on transient server errors / rate-limit
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue

            break   # Non-retriable error (e.g. 400 bad request)

        except (requests.exceptions.RequestException, KeyError, IndexError):
            if attempt < MAX_RETRIES:
                time.sleep(1)
            else:
                break

    return FALLBACK
