import React, { useState, useEffect } from 'react';
import { 
  BarChart3, CheckCircle2, Cpu, Database, Layers, 
  Network, ShieldAlert, Sparkles, Terminal, Zap 
} from 'lucide-react';

export default function ModelInfoTab() {
  const [modelInfo, setModelInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/models/info')
      .then((res) => res.json())
      .then((data) => {
        setModelInfo(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to load model info:', err);
        setLoading(false);
      });
  }, []);

  const perf = modelInfo?.performance || {};
  const topFeats = modelInfo?.top_features || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '20px' }}>
      
      {/* Header */}
      <div className="glass-panel" style={{ padding: '18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--font-display)', fontSize: '1.05rem', color: '#00f0ff' }}>
            <Cpu size={18} /> XGBoost Health Engine Architecture & Transparency
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Trained multi-output gradient-boosted decision tree ensemble with 50 engineered rolling and orbital features.
          </div>
        </div>

        <span className="status-pill pill-low">MODELS ACTIVE & LOADED</span>
      </div>

      {/* Model Performance Scorecard */}
      <div className="glass-panel" style={{ padding: '18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--font-display)', fontSize: '0.9rem', color: '#ffffff', marginBottom: '14px' }}>
          <Layers size={16} color="#8b5cf6" /> Subsystem Model Ensemble Performance
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', fontFamily: 'var(--font-mono)', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '10px 8px' }}>TARGET MODEL</th>
                <th style={{ padding: '10px 8px' }}>ALGORITHM</th>
                <th style={{ padding: '10px 8px' }}>VALIDATION METRIC</th>
                <th style={{ padding: '10px 8px' }}>SCORE / ACCURACY</th>
                <th style={{ padding: '10px 8px' }}>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(perf).map(([key, val]) => (
                <tr key={key} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                  <td style={{ padding: '10px 8px', color: '#00f0ff', fontWeight: 'bold' }}>{key}</td>
                  <td style={{ padding: '10px 8px', color: '#e2e8f0' }}>{val.type}</td>
                  <td style={{ padding: '10px 8px', color: 'var(--text-muted)' }}>{val.metric}</td>
                  <td style={{ padding: '10px 8px', color: '#10b981', fontWeight: 'bold' }}>{val.score}</td>
                  <td style={{ padding: '10px 8px' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#10b981', fontSize: '0.75rem' }}>
                      <CheckCircle2 size={12} /> Ready
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Top 15 Feature Importances */}
      <div className="glass-panel" style={{ padding: '18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--font-display)', fontSize: '0.9rem', color: '#ffffff' }}>
            <BarChart3 size={16} color="#00f0ff" /> Top Feature Importances (Health Score Regressor)
          </div>
          <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            50 Total Engineered Signals
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {Object.entries(topFeats).map(([feat, imp]) => (
            <div key={feat} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ width: '220px', fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: '#cbd5e1' }}>
                {feat}
              </span>
              <div style={{ flex: 1, height: '8px', background: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(100, imp * 250)}%`,
                    background: 'linear-gradient(90deg, #00f0ff, #8b5cf6)',
                    borderRadius: '4px'
                  }}
                />
              </div>
              <span style={{ width: '55px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: '#00f0ff', textAlign: 'right' }}>
                {(imp * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Feature Pipeline Explanation */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        <div className="glass-panel" style={{ padding: '16px' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#00f0ff', marginBottom: '8px' }}>
            1. Temporal Feature Engineering
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            Computes 5-minute and 10-minute rolling means, rolling standard deviations (representing thermal and electrical volatility), and 1st-order differential rates (delta(t) = s(t) - s(t-1)) for all 6 core telemetry signals.
          </p>
        </div>

        <div className="glass-panel" style={{ padding: '16px' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#10b981', marginBottom: '8px' }}>
            2. Orbital Dynamic Linkage
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            Incorporates real-time Keplerian parameters (semi-major axis, eccentricity, inclination, RAAN, argument of perigee, true anomaly) and Cartesian ECI positions directly into the tree decision boundaries.
          </p>
        </div>

        <div className="glass-panel" style={{ padding: '16px' }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#8b5cf6', marginBottom: '8px' }}>
            3. Class Imbalance Mitigation
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            Rare anomaly events (e.g. voltage drop with only 6 positive events out of 4,320 rows) are trained using dynamically calibrated `scale_pos_weight` up to 863x, achieving an Anomaly F1 score of 0.9231.
          </p>
        </div>
      </div>

    </div>
  );
}
