import React, { useState, useEffect } from 'react';
import { 
  GitFork, Lightbulb, Play, Sliders 
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
    if (idx === 0) return '#38bdf8'; // Cyan/Blue
    if (idx === 1) return '#10b981'; // Emerald
    if (idx === 2) return '#818cf8'; // Indigo
    return '#f59e0b'; // Amber
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px' }}>
      
      {/* Top Controls: Forking Trigger & Horizon */}
      <div className="glass-panel" style={{ padding: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9375rem', fontWeight: '600', color: 'var(--text-main)' }}>
            <GitFork size={16} color="#38bdf8" /> Counterfactual Scenario Forking
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
            Branching from state <strong>{currentState?.twin_state_id || 'TWIN-000001'}</strong> (Row #{currentRowIndex}). Simulating parallel operational decisions.
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>HORIZON:</span>
          {[30, 60, 90, 120].map((m) => (
            <button
              key={m}
              className={`btn-control ${horizonMinutes === m ? 'active' : ''}`}
              onClick={() => setHorizonMinutes(m)}
              disabled={loading}
            >
              {m}m
            </button>
          ))}
          <button
            className={`btn-control ${activeTab === 'sandbox' ? 'active' : ''}`}
            onClick={() => setActiveTab(activeTab === 'sandbox' ? 'comparison' : 'sandbox')}
          >
            <Sliders size={13} /> Sandbox Controls
          </button>
        </div>
      </div>

      {/* Custom Sandbox Panel if Active */}
      {activeTab === 'sandbox' && (
        <div className="glass-panel" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '12px', border: '1px solid var(--accent-primary)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
            <Sliders size={15} color="#38bdf8" /> Maneuver & Control Parameters
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
            <div>
              <label style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px', fontFamily: 'var(--font-mono)' }}>
                Prograde Delta-V: <span style={{ color: 'var(--accent-cyan)' }}>{customDeltaV} m/s</span>
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
              <label style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px', fontFamily: 'var(--font-mono)' }}>
                Burn Duration: <span style={{ color: 'var(--accent-cyan)' }}>{customThrustDur} s</span>
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
              <label style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px', fontFamily: 'var(--font-mono)' }}>
                Payload Command:
              </label>
              <select
                value={customPayload}
                onChange={(e) => setCustomPayload(e.target.value)}
                style={{ width: '100%' }}
              >
                <option value="FORCE_OFF">FORCE_OFF (Power Shedding)</option>
                <option value="FORCE_ON">FORCE_ON (Continuous)</option>
                <option value="DUTY_CYCLE_50">DUTY_CYCLE_50 (5m ON / 5m OFF)</option>
                <option value="KEEP">KEEP (Nominal Cycle)</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px', fontFamily: 'var(--font-mono)' }}>
                Radiator Slew Angle: <span style={{ color: 'var(--accent-cyan)' }}>{customThermalSlew}°</span>
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

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
            <button className="btn-primary" onClick={handleRunCustom} disabled={loading}>
              <Play size={13} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle' }} /> Run Simulation
            </button>
          </div>
        </div>
      )}

      {/* Decision Analysis Assessment */}
      {aiRec && (
        <div className="glass-panel" style={{
          padding: '14px',
          borderLeft: '3px solid var(--accent-cyan)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Lightbulb size={16} color="#38bdf8" />
            <div style={{ fontWeight: '600', fontSize: '0.8125rem', color: 'var(--text-main)', letterSpacing: '0.02em' }}>
              AUTOMATED FLIGHT DECISION ASSESSMENT & TRADE-OFFS
            </div>
          </div>

          <div style={{ fontSize: '0.8125rem', lineHeight: '1.5', color: '#cbd5e1', background: 'var(--bg-surface-elevated)', padding: '10px 12px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
            {aiRec.executive_summary}
          </div>
        </div>
      )}

      {/* Side-by-Side Candidate Scenarios Matrix */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
        {scenarios.map((scn, idx) => {
          const color = getScenarioColor(idx);
          const isWinner = aiRec?.recommended_scenario_id === scn.scenario_id;
          const sumry = scn.summary;

          return (
            <div
              key={scn.scenario_id}
              className="glass-panel"
              style={{
                padding: '14px',
                borderTop: `3px solid ${color}`,
                display: 'flex',
                flexDirection: 'column',
                gap: '10px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: '0.6875rem', color: color, fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>
                    {scn.scenario_id}
                  </div>
                  <div style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-main)', marginTop: '2px' }}>
                    {scn.scenario_label}
                  </div>
                </div>
                {isWinner && (
                  <span className="status-pill pill-low">
                    RECOMMENDED
                  </span>
                )}
              </div>

              {/* Metrics Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px', fontSize: '0.75rem' }}>
                <div style={{ background: 'var(--bg-surface-elevated)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-dim)', fontSize: '0.6875rem' }}>Final Health:</span>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: '700', color: color }}>
                    {sumry.final_health_score} pts
                  </div>
                </div>

                <div style={{ background: 'var(--bg-surface-elevated)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-dim)', fontSize: '0.6875rem' }}>Min Battery:</span>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: '700', color: sumry.min_battery_pct < 30 ? 'var(--status-critical)' : 'var(--text-main)' }}>
                    {sumry.min_battery_pct}%
                  </div>
                </div>

                <div style={{ background: 'var(--bg-surface-elevated)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-dim)', fontSize: '0.6875rem' }}>Peak Temp:</span>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: '700', color: sumry.max_temperature_c > 45 ? 'var(--status-critical)' : 'var(--text-main)' }}>
                    {sumry.max_temperature_c}°C
                  </div>
                </div>

                <div style={{ background: 'var(--bg-surface-elevated)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                  <span style={{ color: 'var(--text-dim)', fontSize: '0.6875rem' }}>Risk Level:</span>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9375rem', fontWeight: '700', color: sumry.final_risk_level === 'LOW' ? 'var(--status-nominal)' : 'var(--status-caution)' }}>
                    {sumry.final_risk_level}
                  </div>
                </div>
              </div>

              <div style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px', fontFamily: 'var(--font-mono)' }}>
                Cmd: {scn.controls?.payload_override} | ΔV: {scn.controls?.delta_v_prograde_ms || 0} m/s | Rad: {scn.controls?.thermal_slew_deg || 0}°
              </div>
            </div>
          );
        })}
      </div>

      {/* Multi-Curve Scenario Comparison Chart */}
      <div className="glass-panel" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
            Comparative Subsystem Health Forecast
          </div>
          <div style={{ display: 'flex', gap: '12px', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)' }}>
            {scenarios.map((scn, idx) => (
              <span key={scn.scenario_id} style={{ color: getScenarioColor(idx) }}>
                ● {scn.scenario_label.split(':')[0]}
              </span>
            ))}
          </div>
        </div>

        {/* SVG Multi-Line Chart */}
        <div style={{ width: '100%', height: '200px', background: '#05080e', borderRadius: '4px', padding: '10px', border: '1px solid var(--border-subtle)' }}>
          {scenarios.length > 0 ? (
            <svg width="100%" height="100%" viewBox="0 0 600 180" preserveAspectRatio="none">
              {[0.25, 0.5, 0.75].map((g) => (
                <line key={g} x1="0" y1={180 * g} x2="600" y2={180 * g} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
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
                    strokeWidth={idx === 1 ? 2.5 : 1.5}
                  />
                );
              })}
            </svg>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>
              Calculating scenario branches...
            </div>
          )}
        </div>
      </div>

    </div>
  );
}
