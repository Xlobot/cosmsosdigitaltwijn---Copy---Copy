import React, { useState, useEffect } from 'react';
import { 
  AlertTriangle, Check, CheckCircle2, ChevronRight, GitFork, 
  Lightbulb, Play, Rocket, Shield, Sliders, Sparkles, Thermometer, Zap 
} from 'lucide-react';

export default function ExperimentTab({ currentRowIndex, currentState }) {
  const [horizonMinutes, setHorizonMinutes] = useState(60);
  const [loading, setLoading] = useState(false);
  const [forkData, setForkData] = useState(null);
  const [activeTab, setActiveTab] = useState('comparison'); // 'comparison', 'sandbox'

  // Custom scenario state
  const [customDeltaV, setCustomDeltaV] = useState(15.0);
  const [customThrustDur, setCustomThrustDur] = useState(25);
  const [customPayload, setCustomPayload] = useState('FORCE_OFF');
  const [customThermalSlew, setCustomThermalSlew] = useState(30);

  const runScenarioSimulation = async (customScenarios = null) => {
    setLoading(true);
    try {
      const payload = {
        start_row_index: currentRowIndex,
        horizon_minutes: horizonMinutes,
        scenarios: customScenarios || []
      };
      const res = await fetch('/api/fork', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      setForkData(data);
    } catch (err) {
      console.error('Failed to run scenario simulation:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runScenarioSimulation();
  }, [currentRowIndex, horizonMinutes]);

  const handleRunCustom = () => {
    const customList = [
      {
        scenario_id: 'SCN-NOMINAL',
        scenario_label: 'Scenario A: Nominal Flight Path',
        payload_override: 'KEEP',
        delta_v_prograde_ms: 0.0,
        thermal_slew_deg: 0.0
      },
      {
        scenario_id: 'SCN-CUSTOM',
        scenario_label: `Custom Maneuver (ΔV ${customDeltaV} m/s, ${customPayload})`,
        payload_override: customPayload,
        delta_v_prograde_ms: customDeltaV,
        thrust_duration_s: customThrustDur,
        thermal_slew_deg: customThermalSlew
      }
    ];
    runScenarioSimulation(customList);
    setActiveTab('comparison');
  };

  const scenarios = forkData?.scenarios || [];
  const aiRec = forkData?.ai_recommendation;

  const getScenarioColor = (idx) => {
    if (idx === 0) return '#00f0ff'; // Cyan
    if (idx === 1) return '#10b981'; // Emerald
    if (idx === 2) return '#8b5cf6'; // Purple
    return '#f59e0b'; // Amber
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '20px' }}>
      
      {/* Top Controls: Forking Trigger & Horizon */}
      <div className="glass-panel" style={{ padding: '18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--font-display)', fontSize: '1.05rem', color: '#8b5cf6' }}>
            <GitFork size={18} /> Counterfactual Scenario Forking & "What-If" Analysis
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Forked from live snapshot <strong>{currentState?.twin_state_id || 'TWIN-000001'}</strong> (Row #{currentRowIndex}). Simulating parallel operational branches.
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 'bold' }}>HORIZON:</span>
          {[30, 60, 90, 120].map((m) => (
            <button
              key={m}
              className={`btn-control ${horizonMinutes === m ? 'active' : ''}`}
              onClick={() => setHorizonMinutes(m)}
              disabled={loading}
            >
              {m} min
            </button>
          ))}
          <button
            className={`btn-control ${activeTab === 'sandbox' ? 'active' : ''}`}
            onClick={() => setActiveTab(activeTab === 'sandbox' ? 'comparison' : 'sandbox')}
          >
            <Sliders size={14} /> Custom Sandbox
          </button>
        </div>
      </div>

      {/* Custom Sandbox Panel if Active */}
      {activeTab === 'sandbox' && (
        <div className="glass-panel glass-panel-glow" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--font-display)', fontSize: '0.9rem', color: '#00f0ff' }}>
            <Sliders size={16} /> Custom Control Parameter Sandbox
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
                Prograde Delta-V Burn (m/s): <strong style={{ color: '#00f0ff' }}>{customDeltaV} m/s</strong>
              </label>
              <input
                type="range"
                min="-30"
                max="30"
                step="1"
                value={customDeltaV}
                onChange={(e) => setCustomDeltaV(parseFloat(e.target.value))}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
                Burn Duration: <strong style={{ color: '#00f0ff' }}>{customThrustDur} s</strong>
              </label>
              <input
                type="range"
                min="5"
                max="120"
                step="5"
                value={customThrustDur}
                onChange={(e) => setCustomThrustDur(parseInt(e.target.value))}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
                Payload Power Override:
              </label>
              <select
                value={customPayload}
                onChange={(e) => setCustomPayload(e.target.value)}
                style={{ width: '100%' }}
              >
                <option value="FORCE_OFF">FORCE_OFF (Power Shedding)</option>
                <option value="FORCE_ON">FORCE_ON (Full Observation)</option>
                <option value="DUTY_CYCLE_50">DUTY_CYCLE_50 (5m ON / 5m OFF)</option>
                <option value="KEEP">KEEP (Nominal Cycle)</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
                Radiator Slew Angle: <strong style={{ color: '#00f0ff' }}>{customThermalSlew}°</strong>
              </label>
              <input
                type="range"
                min="0"
                max="60"
                step="5"
                value={customThermalSlew}
                onChange={(e) => setCustomThermalSlew(parseInt(e.target.value))}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '6px' }}>
            <button className="btn-primary" onClick={handleRunCustom} disabled={loading}>
              <Play size={14} style={{ display: 'inline', marginRight: '6px' }} /> Simulate Forked Scenario
            </button>
          </div>
        </div>
      )}

      {/* Explainable AI Decision Engine Box (The Mission Assistant & Explainability Tier) */}
      {aiRec && (
        <div className="glass-panel" style={{
          padding: '18px',
          background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.18) 0%, rgba(16, 185, 129, 0.12) 100%)',
          border: '1px solid rgba(139, 92, 246, 0.4)',
          borderRadius: 'var(--radius-md)',
          boxShadow: '0 0 24px rgba(139, 92, 246, 0.2)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
            <div style={{ background: '#8b5cf6', padding: '6px', borderRadius: '50%', display: 'flex' }}>
              <Lightbulb size={18} color="#ffffff" />
            </div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 'bold', fontSize: '0.92rem', color: '#ddd6fe', letterSpacing: '0.6px' }}>
              EXPLAINABLE AI RECOMMENDATION & TRADE-OFF REASONING
            </div>
          </div>

          <div style={{ fontSize: '0.86rem', lineHeight: '1.55', color: '#f1f5f9', background: 'rgba(5, 10, 24, 0.5)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.06)' }}>
            {aiRec.executive_summary}
          </div>
        </div>
      )}

      {/* Side-by-Side Candidate Scenarios Matrix */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        {scenarios.map((scn, idx) => {
          const color = getScenarioColor(idx);
          const isWinner = aiRec?.recommended_scenario_id === scn.scenario_id;
          const sumry = scn.summary;

          return (
            <div
              key={scn.scenario_id}
              className={`glass-panel ${isWinner ? 'glass-panel-glow' : ''}`}
              style={{
                padding: '18px',
                borderTop: `4px solid ${color}`,
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: '0.72rem', color: color, fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    {scn.scenario_id}
                  </div>
                  <div style={{ fontFamily: 'var(--font-display)', fontSize: '0.95rem', fontWeight: 'bold', color: '#ffffff', marginTop: '2px' }}>
                    {scn.scenario_label}
                  </div>
                </div>
                {isWinner && (
                  <span className="status-pill pill-low" style={{ background: 'rgba(16, 185, 129, 0.25)' }}>
                    RECOMMENDED
                  </span>
                )}
              </div>

              {/* Metrics Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', fontSize: '0.78rem' }}>
                <div style={{ background: 'rgba(255,255,255,0.04)', padding: '8px', borderRadius: '6px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Final Health:</span>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 'bold', color: color }}>
                    {sumry.final_health_score} pts
                  </div>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.04)', padding: '8px', borderRadius: '6px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Min Battery:</span>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 'bold', color: sumry.min_battery_pct < 30 ? '#ef4444' : '#ffffff' }}>
                    {sumry.min_battery_pct}%
                  </div>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.04)', padding: '8px', borderRadius: '6px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Peak Temp:</span>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.1rem', fontWeight: 'bold', color: sumry.max_temperature_c > 45 ? '#ef4444' : '#ffffff' }}>
                    {sumry.max_temperature_c}°C
                  </div>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.04)', padding: '8px', borderRadius: '6px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Risk Level:</span>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1.0rem', fontWeight: 'bold', color: sumry.final_risk_level === 'LOW' ? '#10b981' : '#f59e0b' }}>
                    {sumry.final_risk_level}
                  </div>
                </div>
              </div>

              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
                Controls: {scn.controls?.payload_override} | ΔV: {scn.controls?.delta_v_prograde_ms || 0} m/s | Rad Slew: {scn.controls?.thermal_slew_deg || 0}°
              </div>
            </div>
          );
        })}
      </div>

      {/* Multi-Curve Scenario Comparison Chart */}
      <div className="glass-panel" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: '0.88rem', color: '#ffffff' }}>
            Parallel Health Score Trajectory Comparison
          </div>
          <div style={{ display: 'flex', gap: '12px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
            {scenarios.map((scn, idx) => (
              <span key={scn.scenario_id} style={{ color: getScenarioColor(idx) }}>
                ● {scn.scenario_label.split(':')[0]}
              </span>
            ))}
          </div>
        </div>

        {/* SVG Multi-Line Chart */}
        <div style={{ width: '100%', height: '220px', background: 'rgba(5, 10, 24, 0.7)', borderRadius: '8px', padding: '12px', border: '1px solid var(--border-subtle)' }}>
          {scenarios.length > 0 ? (
            <svg width="100%" height="100%" viewBox="0 0 600 180" preserveAspectRatio="none">
              {[0.25, 0.5, 0.75].map((g) => (
                <line key={g} x1="0" y1={180 * g} x2="600" y2={180 * g} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
              ))}

              {scenarios.map((scn, idx) => {
                const color = getScenarioColor(idx);
                const traj = scn.trajectory || [];
                if (traj.length === 0) return null;

                const pathD = traj.map((pt, i) => {
                  const x = (i / Math.max(traj.length - 1, 1)) * 600;
                  const val = pt.health_score;
                  const y = 170 - (val / 100) * 150;
                  return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
                }).join(' ');

                return (
                  <path
                    key={scn.scenario_id}
                    d={pathD}
                    fill="none"
                    stroke={color}
                    strokeWidth={idx === 1 ? 3.5 : 2}
                  />
                );
              })}
            </svg>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
              Calculating Scenario Forecasts...
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
