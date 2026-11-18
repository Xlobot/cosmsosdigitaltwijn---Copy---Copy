import React, { useState, useEffect } from 'react';
import { 
  BarChart3, CheckCircle2, Cpu, Layers 
} from 'lucide-react';

export default function ModelInfoTab() {
  const [modelInfo, setModelInfo] = useState(null);

  useEffect(() => {
    fetch('/api/models/info')
      .then((res) => res.json())
      .then((data) => {
        setModelInfo(data);
      })
      .catch((err) => {
        console.error('Failed to load model info:', err);
      });
  }, []);

  const perf = modelInfo?.performance || {};
  const topFeats = modelInfo?.top_features || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px' }}>
      
      {/* Header */}
      <div className="glass-panel" style={{ padding: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9375rem', fontWeight: '600', color: 'var(--text-main)' }}>
            <Cpu size={16} color="#38bdf8" /> XGBoost Health Engine Architecture
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
            Multi-output gradient-boosted decision tree ensemble with 50 engineered orbital & telemetry features.
          </div>
        </div>

        <span className="status-pill pill-low">MODELS ACTIVE</span>
      </div>

      {/* Model Performance Scorecard */}
      <div className="glass-panel" style={{ padding: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)', marginBottom: '12px' }}>
          <Layers size={15} color="#818cf8" /> Subsystem Model Ensemble Performance
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)', fontSize: '0.6875rem' }}>
                <th style={{ padding: '8px' }}>TARGET MODEL</th>
                <th style={{ padding: '8px' }}>ALGORITHM</th>
                <th style={{ padding: '8px' }}>VALIDATION METRIC</th>
                <th style={{ padding: '8px' }}>SCORE / ACCURACY</th>
                <th style={{ padding: '8px' }}>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(perf).map(([key, val]) => (
                <tr key={key} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '8px', color: 'var(--accent-cyan)', fontWeight: '600' }}>{key}</td>
                  <td style={{ padding: '8px', color: 'var(--text-main)' }}>{val.type}</td>
                  <td style={{ padding: '8px', color: 'var(--text-muted)' }}>{val.metric}</td>
                  <td style={{ padding: '8px', color: 'var(--status-nominal)', fontWeight: '600' }}>{val.score}</td>
                  <td style={{ padding: '8px' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--status-nominal)', fontSize: '0.6875rem' }}>
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
      <div className="glass-panel" style={{ padding: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
            <BarChart3 size={15} color="#38bdf8" /> Top Feature Importances (Health Regressor)
          </div>
          <span style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
            50 Total Engineered Signals
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {Object.entries(topFeats).map(([feat, imp]) => (
            <div key={feat} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ width: '220px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: '#cbd5e1' }}>
                {feat}
              </span>
              <div style={{ flex: 1, height: '6px', background: 'var(--border-subtle)', borderRadius: '2px', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(100, imp * 250)}%`,
                    background: 'var(--accent-cyan)',
                    borderRadius: '2px'
                  }}
                />
              </div>
              <span style={{ width: '50px', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', textAlign: 'right' }}>
                {(imp * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Feature Pipeline Explanation */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
        <div className="glass-panel" style={{ padding: '14px' }}>
          <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--accent-cyan)', marginBottom: '6px' }}>
            1. Temporal Feature Engineering
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            Computes 5-minute and 10-minute rolling means, rolling standard deviations (representing thermal and electrical volatility), and 1st-order differential rates for all 6 core telemetry signals.
          </p>
        </div>

        <div className="glass-panel" style={{ padding: '14px' }}>
          <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--status-nominal)', marginBottom: '6px' }}>
            2. Orbital Dynamic Linkage
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            Incorporates real-time Keplerian parameters (semi-major axis, eccentricity, inclination, RAAN, argument of perigee, true anomaly) and Cartesian ECI positions directly into the tree decision boundaries.
          </p>
        </div>

        <div className="glass-panel" style={{ padding: '14px' }}>
          <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: '#a5b4fc', marginBottom: '6px' }}>
            3. Class Imbalance Calibration
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            Rare anomaly events (e.g. voltage drop with only 6 positive events out of 4,320 rows) are trained using dynamically calibrated `scale_pos_weight` up to 863x, achieving an Anomaly F1 score of 0.9231.
          </p>
        </div>
      </div>

    </div>
  );
}
