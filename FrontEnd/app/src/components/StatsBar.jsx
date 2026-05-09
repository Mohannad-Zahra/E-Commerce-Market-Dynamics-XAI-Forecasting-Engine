import React, { useEffect, useState } from 'react';
import { apiFetch } from '../api';

const fmt = (n) =>
  n >= 1_000_000
    ? (n / 1_000_000).toFixed(1) + 'M'
    : n >= 1_000
    ? (n / 1_000).toFixed(0) + 'K'
    : String(n);

const fmtEGP = (n) =>
  Number(n).toLocaleString('en-EG', { maximumFractionDigits: 0 });

const StatCard = ({ label, value, sub }) => (
  <div className="stat-card">
    <span className="stat-value">{value}</span>
    <span className="stat-label">{label}</span>
    {sub && <span className="stat-sub">{sub}</span>}
  </div>
);

const StatsBar = () => {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    apiFetch('/api/stats')
      .then(setStats)
      .catch(() => {}); // silently hide if backend is down
  }, []);

  if (!stats) return null;

  return (
    <div className="stats-bar">
      <div className="stats-inner">
        <div className="stats-title">
          <span className="stats-live-dot" />
          Live Market Data
        </div>
        <div className="stats-grid">
          <StatCard
            label="Price Records"
            value={fmt(stats.total_rows)}
            sub="scraped snapshots"
          />
          <StatCard
            label="Unique Products"
            value={fmt(stats.unique_products)}
            sub="tracked live"
          />
          <StatCard
            label="Lowest Price"
            value={`EGP ${fmtEGP(stats.price_min_egp)}`}
            sub="in catalogue"
          />
          <StatCard
            label="Highest Price"
            value={`EGP ${fmtEGP(stats.price_max_egp)}`}
            sub="in catalogue"
          />
          <StatCard
            label="Avg Price"
            value={`EGP ${fmtEGP(stats.price_avg_egp)}`}
            sub="market average"
          />
          <StatCard
            label="Data Range"
            value={stats.date_from?.slice(0, 10) ?? '—'}
            sub={`to ${stats.date_to?.slice(0, 10) ?? '—'}`}
          />
        </div>
      </div>
    </div>
  );
};

export default StatsBar;
