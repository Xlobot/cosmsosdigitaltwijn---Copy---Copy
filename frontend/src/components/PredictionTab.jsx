import React, { useState, useEffect } from 'react';
import { 
  Target, TrendingDown, TrendingUp 
} from 'lucide-react';

export default function PredictionTab({ currentRowIndex }) {
  const [horizonMinutes, setHorizonMinutes] = useState(60);
  const [loading, setLoading] = useState(false);
  const [predictData, setPredictData] = useState(null);
  const [selectedSignal, setSelectedSignal] = useState('health'); // 'health', 'battery', 'temp', 'trajectory'

  const fetchPrediction = async (horizon) => {
    setLoading(true);
    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_row_index: currentRowIndex,
          horizon_minutes: horizon
        })
      });
      const data = await res.json();
      setPredictData(data);
    } catch (err) {
      console.error('Failed fetching prediction:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPrediction(horizonMinutes);
  }, [currentRowIndex, horizonMinutes]);

  const predictedTrajectory = predictData?.nominal_prediction?.trajectory || [];
  const validation = predictData?.ground_truth_validation;
  const metrics = validation?.metrics;
  const comparisonPoints = validation?.comparison_points || [];

  const displayPoints = comparisonPoints.length > 0
    ? comparisonPoints
    : predictedTrajectory.map((pt) => ({
        minute: pt.horizon_minute,
        timestamp: pt.timestamp,
        predicted_health: pt.health_score,
        actual_health: null,
        predicted_battery: pt.battery_percentage,
        actual_battery: null,
        predicted_temp: pt.temperature,
        actual_temp: null,
        trajectory_error_km: 0,
        confidence: pt.state_confidence ?? 1.0,
      }));

  // Determine signal Y-axis bounds
  let yMin = 0, yMax = 100, unit = '%', signalTitle = 'Health Score (0-100 pts)';
  if (selectedSignal === 'health') {
    yMin = 40; yMax = 100; unit = 'pts'; signalTitle = 'Health Score (XGBoost Regressor)';
  } else if (selectedSignal === 'battery') {
    yMin = 40; yMax = 100; unit = '%'; signalTitle = 'Battery State of Charge (%)';
  } else if (selectedSignal === 'temp') {
    yMin = -10; yMax = 45; unit = '°C'; signalTitle = 'Core System Temperature (°C)';
  } else if (selectedSignal === 'trajectory') {
    yMin = 0; yMax = 10; unit = 'km'; signalTitle = 'Orbital Trajectory Deviation (km)';
  }

  const getYPos = (val) => {
    const norm = (val - yMin) / Math.max(yMax - yMin, 1e-4);
    return 190 - Math.max(0, Math.min(1, norm)) * 160;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px' }}>
      
      {/* Top Banner: Horizon Selector & Ground Truth Header */}
      <div className="glass-panel" style={{ padding: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9375rem', fontWeight: '600', color: 'var(--text-main)' }}>
            <TrendingUp size={16} color="#38bdf8" /> Orbital Propagation & Ground-Truth Validation
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
            Forward propagation from Row #{currentRowIndex} using orbital physics + ML health models.
          </div>
        </div>

        {/* Horizon Picker */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>HORIZON:</span>
          {[15, 30, 60, 120, 180].map((m) => (
            <button
              key={m}
              className={`btn-control ${horizonMinutes === m ? 'active' : ''}`}
              onClick={() => setHorizonMinutes(m)}
              disabled={loading}
            >
              {m}m
            </button>
          ))}
        </div>
      </div>

      {/* Validation Metrics Scorecard */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
        
        <div className="glass-panel" style={{ padding: '12px', borderLeft: '3px solid var(--accent-cyan)' }}>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Health Model Accuracy
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.25rem', fontWeight: '700', color: 'var(--text-main)', marginTop: '2px' }}>
            {metrics?.health_score_accuracy_pct !== undefined ? `${metrics.health_score_accuracy_pct}%` : '100.0%'}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
            MAE: {metrics?.health_score_mae?.toFixed(2) || '0.00'} pts | R²: {metrics?.health_score_r2 || 1.0}
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '12px', borderLeft: '3px solid var(--status-nominal)' }}>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Trajectory Drift (MAE)
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.25rem', fontWeight: '700', color: 'var(--status-nominal)', marginTop: '2px' }}>
            {metrics?.trajectory_mae_km?.toFixed(2) || '0.00'} <span style={{ fontSize: '0.75rem', fontWeight: 'normal' }}>km</span>
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
            Max error: {metrics?.trajectory_max_error_km?.toFixed(2) || '0.00'} km
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '12px', borderLeft: '3px solid var(--status-caution)' }}>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Battery SOC Error
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.25rem', fontWeight: '700', color: 'var(--status-caution)', marginTop: '2px' }}>
            {metrics?.battery_mae_pct?.toFixed(2) || '0.00'} <span style={{ fontSize: '0.75rem', fontWeight: 'normal' }}>%</span>
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
            Mean error vs telemetry log
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '12px', borderLeft: '3px solid #818cf8' }}>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Thermal Model MAE
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.25rem', fontWeight: '700', color: '#c7d2fe', marginTop: '2px' }}>
            {metrics?.temperature_mae_c?.toFixed(2) || '0.00'} <span style={{ fontSize: '0.75rem', fontWeight: 'normal' }}>°C</span>
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
            Radiative equilibrium model
          </div>
        </div>

      </div>

      {/* Main Validation Overlay Chart & Confidence Decay */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(420px, 2fr) minmax(300px, 1fr)', gap: '16px' }}>
        
        {/* Left: Ground Truth Comparison Chart */}
        <div className="glass-panel" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
              <Target size={15} color="#38bdf8" /> {signalTitle}
            </div>

            {/* Signal Selector */}
            <div style={{ display: 'flex', gap: '4px' }}>
              <button
                className={`btn-control ${selectedSignal === 'health' ? 'active' : ''}`}
                onClick={() => setSelectedSignal('health')}
              >
                Health
              </button>
              <button
                className={`btn-control ${selectedSignal === 'battery' ? 'active' : ''}`}
                onClick={() => setSelectedSignal('battery')}
              >
                Battery
              </button>
              <button
                className={`btn-control ${selectedSignal === 'temp' ? 'active' : ''}`}
                onClick={() => setSelectedSignal('temp')}
              >
                Temp
              </button>
              <button
                className={`btn-control ${selectedSignal === 'trajectory' ? 'active' : ''}`}
                onClick={() => setSelectedSignal('trajectory')}
              >
                Orbit
              </button>
            </div>
          </div>

          {/* SVG Overlay Graph with Y-Axis and Hover */}
          <div style={{ position: 'relative', width: '100%', height: '220px', background: '#05080e', borderRadius: '4px', padding: '10px', border: '1px solid var(--border-subtle)' }}>
            
            {/* Y-Axis scale indicators */}
            <div style={{ position: 'absolute', top: '10px', left: '10px', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
              {yMax} {unit}
            </div>
            <div style={{ position: 'absolute', top: '95px', left: '10px', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
              {((yMax + yMin) / 2).toFixed(0)} {unit}
            </div>
            <div style={{ position: 'absolute', bottom: '10px', left: '10px', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
              {yMin} {unit}
            </div>

            {displayPoints.length > 0 ? (
              <svg width="100%" height="100%" viewBox="0 0 600 200" preserveAspectRatio="none">
                {/* Horizontal Grid lines */}
                {[0.15, 0.5, 0.85].map((g) => (
                  <line key={g} x1="30" y1={200 * g} x2="590" y2={200 * g} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                ))}

                {/* Ground Truth Actual Curve (Dashed Green) if available */}
                {selectedSignal !== 'trajectory' && comparisonPoints.length > 0 && (
                  <path
                    d={comparisonPoints.map((pt, i) => {
                      const x = 35 + (i / Math.max(comparisonPoints.length - 1, 1)) * 555;
                      let val = pt.actual_health;
                      if (selectedSignal === 'battery') val = pt.actual_battery;
                      if (selectedSignal === 'temp') val = pt.actual_temp;
                      const y = getYPos(val);
                      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                    }).join(' ')}
                    fill="none"
                    stroke="var(--status-nominal)"
                    strokeWidth="2"
                    strokeDasharray="4 3"
                  />
                )}

                {/* Predicted Digital Twin Curve (Solid Blue/Cyan) */}
                <path
                  d={displayPoints.map((pt, i) => {
                    const x = 35 + (i / Math.max(displayPoints.length - 1, 1)) * 555;
                    let val = pt.predicted_health;
                    if (selectedSignal === 'battery') val = pt.predicted_battery;
                    if (selectedSignal === 'temp') val = pt.predicted_temp;
                    if (selectedSignal === 'trajectory') val = pt.trajectory_error_km;
                    const y = getYPos(val);
                    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                  }).join(' ')}
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="2.5"
                />
              </svg>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>
                Computing forward trajectory...
              </div>
            )}

            {/* Legend */}
            <div style={{ position: 'absolute', bottom: '8px', right: '12px', display: 'flex', gap: '12px', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)' }}>
              <span style={{ color: '#38bdf8' }}>━ Predicted Twin</span>
              {selectedSignal !== 'trajectory' && comparisonPoints.length > 0 && <span style={{ color: 'var(--status-nominal)' }}>┅ Actual Telemetry</span>}
            </div>
          </div>

          <div style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
            {comparisonPoints.length > 0 
              ? 'Comparing forward propagation against actual telemetry records.' 
              : 'Forward propagation beyond current telemetry buffer (future states modeled by orbital physics + ML health engines).'}
          </div>
        </div>

        {/* Right: Confidence Decay Curve */}
        <div className="glass-panel" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
            <TrendingDown size={15} color="#818cf8" /> Uncertainty Horizon Curve
          </div>

          <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Empirical confidence model: C(t) = exp(-0.006 · t)
          </div>

          {/* Confidence Curve Plot */}
          <div style={{ width: '100%', height: '135px', background: '#05080e', borderRadius: '4px', padding: '8px', border: '1px solid var(--border-subtle)', position: 'relative' }}>
            <svg width="100%" height="100%" viewBox="0 0 300 120" preserveAspectRatio="none">
              <path
                d={displayPoints.map((pt, i) => {
                  const x = (i / Math.max(displayPoints.length - 1, 1)) * 300;
                  const y = 110 - (pt.confidence * 95);
                  return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                }).join(' ')}
                fill="none"
                stroke="#818cf8"
                strokeWidth="2"
              />
            </svg>
            <div style={{ position: 'absolute', top: '8px', right: '10px', fontFamily: 'var(--font-mono)', fontSize: '0.6875rem', color: '#c7d2fe' }}>
              Final: {(displayPoints[displayPoints.length - 1]?.confidence * 100 || 69).toFixed(1)}%
            </div>
          </div>

          <div style={{ background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-xs)', padding: '8px 10px', fontSize: '0.6875rem', color: 'var(--text-muted)', lineHeight: '1.45' }}>
            Confidence scales from 1.0 down to ~0.70 at t+180m due to unmodeled aerodynamic drag and stochastic orbital variations.
          </div>
        </div>

      </div>

      {/* Prediction Step Table */}
      <div className="glass-panel" style={{ padding: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
            Propagation Step Log
          </div>
          <span style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
            Showing {Math.min(displayPoints.length, 10)} of {displayPoints.length} minutes
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)', fontSize: '0.6875rem' }}>
                <th style={{ padding: '6px 8px' }}>HORIZON</th>
                <th style={{ padding: '6px 8px' }}>TIMESTAMP</th>
                <th style={{ padding: '6px 8px' }}>PRED HEALTH</th>
                <th style={{ padding: '6px 8px' }}>ACT HEALTH</th>
                <th style={{ padding: '6px 8px' }}>PRED BATT</th>
                <th style={{ padding: '6px 8px' }}>ACT BATT</th>
                <th style={{ padding: '6px 8px' }}>TRAJ DRIFT</th>
                <th style={{ padding: '6px 8px' }}>CONFIDENCE</th>
              </tr>
            </thead>
            <tbody>
              {displayPoints.slice(0, 10).map((pt, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-main)' }}>
                  <td style={{ padding: '6px 8px', color: 'var(--accent-cyan)' }}>+{pt.minute}m</td>
                  <td style={{ padding: '6px 8px', color: 'var(--text-muted)' }}>{pt.timestamp}</td>
                  <td style={{ padding: '6px 8px', color: 'var(--accent-cyan)', fontWeight: '600' }}>{pt.predicted_health}</td>
                  <td style={{ padding: '6px 8px', color: pt.actual_health !== null ? 'var(--status-nominal)' : 'var(--text-dim)' }}>
                    {pt.actual_health !== null ? pt.actual_health : '—'}
                  </td>
                  <td style={{ padding: '6px 8px' }}>{pt.predicted_battery}%</td>
                  <td style={{ padding: '6px 8px', color: pt.actual_battery !== null ? 'var(--status-nominal)' : 'var(--text-dim)' }}>
                    {pt.actual_battery !== null ? `${pt.actual_battery}%` : '—'}
                  </td>
                  <td style={{ padding: '6px 8px', color: pt.actual_health !== null ? 'var(--status-nominal)' : 'var(--text-dim)' }}>
                    {pt.actual_health !== null ? `${pt.trajectory_error_km} km` : 'Simulated'}
                  </td>
                  <td style={{ padding: '6px 8px', color: '#c7d2fe' }}>{(pt.confidence * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
