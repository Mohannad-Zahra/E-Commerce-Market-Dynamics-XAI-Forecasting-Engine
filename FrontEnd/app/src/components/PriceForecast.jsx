import { useState, useCallback } from 'react';

const API = 'http://localhost:8000';

/* ── Feature definitions ─────────────────────────────────────────────── */

const XAI_FIELDS = [
  { key: 'compute_potential',         label: 'Compute Potential',        tip: 'CPU/GPU power index (0-1)',                  defaultVal: 0.11,   step: 0.01 },
  { key: 'delta_p_7d',                label: '7d Price Change',          tip: 'Price movement over last 7 days',            defaultVal: 0,      step: 100 },
  { key: 'delta_p_14d',               label: '14d Price Change',         tip: 'Price movement over last 14 days',           defaultVal: 0,      step: 100 },
  { key: 'delta_p_1d',                label: '1d Price Change',          tip: 'Price movement since yesterday',             defaultVal: 0,      step: 100 },
  { key: 'vol_30d',                   label: '30d Volatility',           tip: 'Rolling 30-day volatility',                  defaultVal: 0.05,   step: 0.01 },
  { key: 'official_egp_usd',          label: 'Official EGP/USD',         tip: 'Official exchange rate',                     defaultVal: 48.5,   step: 0.1 },
  { key: 'cpi_inflation',             label: 'CPI Inflation %',           tip: 'Current inflation rate',                     defaultVal: 35.0,   step: 0.1 },
  { key: 'is_major_sale_period',      label: 'Major Sale Period (0/1)',  tip: '1 if White Friday, Eid, etc.',               defaultVal: 0,      step: 1, min: 0, max: 1 },
  { key: 'competitor_scarcity_count', label: 'Competitor Scarcity',      tip: 'Number of out-of-stock competitors',         defaultVal: 2,      step: 1, min: 0 },
  { key: 'volume_weight',             label: 'Volume Weight',            tip: 'Shipping volume/weight index',               defaultVal: 1.1,    step: 0.1 },
  { key: 'D_months',                  label: 'Market Age (Months)',      tip: 'Months since product release',               defaultVal: 24,     step: 1, min: 0 },
  { key: 'k',                         label: 'Growth Constant (k)',      tip: 'Market saturation constant',                 defaultVal: 0.0003, step: 0.0001 },
  { key: 'import_lambda',             label: 'Import Lambda',            tip: 'Import restriction impact factor',           defaultVal: 0.8,    step: 0.1 },
  { key: 'missing_release_date',      label: 'Missing Rel. Date (0/1)',  tip: '1 if release date is unknown',               defaultVal: 0,      step: 1, min: 0, max: 1 },
];

/* ── Sub-components ──────────────────────────────────────────────────── */

function FieldInput({ field, value, onChange }) {
  return (
    <div className="feature-field">
      <label className="field-label" title={field.tip}>
        <span className="field-name">{field.label}</span>
        <span className="field-tip">ℹ {field.tip}</span>
      </label>
      <input
        type="number"
        value={value}
        step={field.step}
        min={field.min ?? undefined}
        max={field.max ?? undefined}
        onChange={e => onChange(parseFloat(e.target.value) || 0)}
        className="field-input"
      />
    </div>
  );
}

function ResultCard({ result, type }) {
  if (!result) return null;
  const isError = result.error;

  return (
    <div className={`result-card ${isError ? 'result-error' : 'result-ok'}`}>
      <div className="result-model">{result.model || 'Error'}</div>
      {isError ? (
        <p className="result-error-msg">{result.error}</p>
      ) : type === 'price' ? (
        <div className="result-row result-highlight">
          <span>14d Predicted Price</span>
          <strong>EGP {result.predicted_price_egp?.toLocaleString('en-EG', { minimumFractionDigits: 2 })}</strong>
        </div>
      ) : (
        <div className="result-row result-highlight">
          <span>Stability Score</span>
          <strong>{result.predicted_stability_score?.toFixed(4)}</strong>
        </div>
      )}
    </div>
  );
}

/* ── Main component ──────────────────────────────────────────────────── */

export default function PriceForecast({ product }) {
  const [xaiVals, setXaiVals] = useState(() => {
    const defaults = XAI_FIELDS.reduce((acc, f) => { acc[f.key] = f.defaultVal; return acc; }, {});
    if (product) {
      return {
        ...defaults,
        compute_potential: product.compute_potential ?? defaults.compute_potential,
        delta_p_1d: product.delta_p_1d ?? defaults.delta_p_1d,
        delta_p_7d: product.delta_p_7d ?? defaults.delta_p_7d,
        delta_p_14d: product.delta_p_14d ?? defaults.delta_p_14d,
        vol_30d: product.vol_30d ?? defaults.vol_30d,
        official_egp_usd: product.official_egp_usd ?? defaults.official_egp_usd,
        cpi_inflation: product.cpi_inflation ?? defaults.cpi_inflation,
        is_major_sale_period: product.is_major_sale_period ?? defaults.is_major_sale_period,
        competitor_scarcity_count: product.competitor_scarcity ?? defaults.competitor_scarcity_count,
      };
    }
    return defaults;
  });

  const [priceResult, setPriceResult]   = useState(null);
  const [stabilityResult, setStabilityResult] = useState(null);
  const [loading, setLoading] = useState({});

  const setXaiVal = (key, val) => setXaiVals(v => ({ ...v, [key]: val }));

  const callApi = async (url, body, setter, key) => {
    setLoading(l => ({ ...l, [key]: true }));
    setter(null);
    try {
      const res = await fetch(`${API}${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) setter({ error: data.detail || 'Server error' });
      else setter(data);
    } catch (e) {
      setter({ error: e.message });
    } finally {
      setLoading(l => ({ ...l, [key]: false }));
    }
  };

  const xaiFeatureArray = () => XAI_FIELDS.map(f => xaiVals[f.key] ?? 0);

  return (
    <div className="forecast-root">
      <div className="forecast-header">
        <h2>🤖 XAI Market Forecasting</h2>
        <p>New 14-feature models predicting stability and future price based on macroeconomic and market factors.</p>
      </div>

      <div className="forecast-section">
        <div className="section-title">
          <span className="section-icon">📈</span>
          <div>
            <h3>Market Parameters</h3>
            <small>Adjust the features below to run live XAI inference.</small>
          </div>
        </div>

        <div className="fields-grid">
          {XAI_FIELDS.map(f => (
            <FieldInput
              key={f.key}
              field={f}
              value={xaiVals[f.key] ?? f.defaultVal}
              onChange={val => setXaiVal(f.key, val)}
            />
          ))}
        </div>

        <div className="btn-row">
          <button
            className="btn btn-blue"
            disabled={loading['price']}
            onClick={() => callApi('/api/forecast/price/onnx', { features: xaiFeatureArray() }, setPriceResult, 'price')}
          >
            {loading['price'] ? '⏳ Running…' : '▶ Predict 14d Price'}
          </button>
          <button
            className="btn btn-green"
            disabled={loading['stability']}
            onClick={() => callApi('/api/forecast/stability', { features: xaiFeatureArray() }, setStabilityResult, 'stability')}
          >
            {loading['stability'] ? '⏳ Running…' : '▶ Check Stability'}
          </button>
        </div>

        <div className="results-row">
          <ResultCard result={priceResult} type="price" />
          <ResultCard result={stabilityResult} type="stability" />
        </div>
      </div>

      <style>{`
        .forecast-root {
          font-family: 'Inter', system-ui, sans-serif;
          background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
          border-radius: 16px;
          padding: 32px;
          color: #e2e8f0;
          margin-top: 32px;
        }
        .forecast-header { margin-bottom: 24px; }
        .forecast-header h2 { font-size: 1.7rem; font-weight: 700; color: #fff; margin: 0 0 6px; }
        .forecast-header p  { color: #94a3b8; font-size: 0.9rem; margin: 0; }

        .forecast-section {
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 12px;
          padding: 24px;
          margin-bottom: 24px;
        }
        .section-title { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 20px; }
        .section-icon  { font-size: 2rem; line-height: 1; }
        .section-title h3 { font-size: 1.1rem; font-weight: 600; color: #fff; margin: 0 0 4px; }
        .section-title small { color: #64748b; font-size: 0.78rem; }

        .fields-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
          gap: 12px;
          margin-bottom: 16px;
        }
        .feature-field { display: flex; flex-direction: column; gap: 4px; }
        .field-label   { display: flex; flex-direction: column; cursor: help; }
        .field-name    { font-size: 0.78rem; font-weight: 500; color: #cbd5e1; }
        .field-tip     { font-size: 0.68rem; color: #475569; margin-top: 1px; }
        .field-input {
          background: rgba(0,0,0,0.4);
          border: 1px solid rgba(255,255,255,0.15);
          border-radius: 6px;
          color: #e2e8f0;
          padding: 6px 10px;
          font-size: 0.82rem;
          outline: none;
          transition: border-color 0.2s;
        }
        .field-input:focus { border-color: #6366f1; }

        .current-price-row {
          display: flex; align-items: center; gap: 12px;
          margin-bottom: 16px;
          color: #94a3b8; font-size: 0.82rem;
        }
        .current-price-input { width: 160px; }

        .btn-row { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }
        .btn {
          padding: 10px 22px; border-radius: 8px; border: none; cursor: pointer;
          font-weight: 600; font-size: 0.88rem; transition: opacity 0.2s, transform 0.1s;
          color: #fff;
        }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn:not(:disabled):hover { opacity: 0.88; transform: translateY(-1px); }
        .btn-blue   { background: linear-gradient(135deg,#2563eb,#4f46e5); }
        .btn-purple { background: linear-gradient(135deg,#7c3aed,#a855f7); }
        .btn-green  { background: linear-gradient(135deg,#059669,#10b981); }

        .results-row { display: flex; flex-wrap: wrap; gap: 14px; }
        .result-card {
          flex: 1; min-width: 220px;
          border-radius: 10px;
          padding: 16px 20px;
        }
        .result-ok    { background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.3); }
        .result-error { background: rgba(239,68,68,0.12);  border: 1px solid rgba(239,68,68,0.3); }
        .result-model { font-size: 0.75rem; color: #64748b; margin-bottom: 10px; font-style: italic; }
        .result-row   { display: flex; justify-content: space-between; align-items: center; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 0.85rem; }
        .result-row:last-child { border-bottom: none; }
        .result-highlight strong { color: #34d399; font-size: 1.05rem; }
        .result-error-msg { color: #f87171; font-size: 0.83rem; }
      `}</style>
    </div>
  );
}
