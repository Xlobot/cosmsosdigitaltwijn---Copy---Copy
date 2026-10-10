import React from 'react';
import { 
  Activity, AlertTriangle, Battery, BatteryCharging, CheckCircle2, 
  Cpu, Flame, Gauge, Radio, ShieldAlert, Sparkles, Sun, Thermometer, Zap 
} from 'lucide-react';
import OrbitGlobe3D from './OrbitGlobe3D';

// Helper for Circular Progress SVG
function CircularProgress({ value, label, size = 80, strokeWidth = 7, color }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(100, Math.max(0, value)) / 100) * circumference;

  let computedColor = color;
  if (!computedColor) {
    if (value >= 80) computedColor = '#10b981';
    else if (value >= 60) computedColor = '#f59e0b';
    else if (value >= 40) computedColor = '#f97316';
    else computedColor = '#ef4444';
  }

  return (
    <div className="gauge-card">
      <div className="gauge-svg-wrap" style={{ width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth={strokeWidth}
            fill="transparent"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={computedColor}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            fill="transparent"
            style={{ transition: 'stroke-dashoffset 0.35s ease, stroke 0.35s ease' }}
          />
        </svg>
        <div className="gauge-center-text" style={{ color: computedColor }}>
          {Math.round(value)}%
        </div>
      </div>
      <div className="gauge-label">{label}</div>
    </div>
  );
}

// Telemetry Multi-Stream Canvas Chart
function TelemetryStreamChart({ timelineData, currentIndex }) {
  const canvasRef = React.useRef(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !timelineData || timelineData.length === 0) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // Grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let y = 30; y < height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const n = timelineData.length;
    const stepX = width / Math.max(n - 1, 1);

    // Plot helper
    const drawLine = (key, color, minVal, maxVal, lineWidth = 2) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.beginPath();
      timelineData.forEach((pt, i) => {
        const val = pt[key] ?? 0;
        const norm = (val - minVal) / Math.max(maxVal - minVal, 1e-4);
        const x = i * stepX;
        const y = height - 20 - norm * (height - 40);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    };

    // Draw signals
    drawLine('battery_percentage', '#10b981', 0, 100);
    drawLine('temperature', '#f59e0b', -10, 60);
    drawLine('health_score', '#00f0ff', 0, 100, 2.5);

    // Draw active cursor playhead
    const cursorX = Math.min(width, Math.max(0, (currentIndex / Math.max(n - 1, 1)) * width));
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(cursorX, 0);
    ctx.lineTo(cursorX, height);
    ctx.stroke();
    ctx.setLineDash([]);

  }, [timelineData, currentIndex]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div style={{ fontSize: '0.8rem', fontWeight: 'bold', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
          Mission Telemetry Stream (Past Orbit)
        </div>
        <div style={{ display: 'flex', gap: '14px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
          <span style={{ color: '#00f0ff' }}>● Health Score</span>
          <span style={{ color: '#10b981' }}>● Battery %</span>
          <span style={{ color: '#f59e0b' }}>● Temperature (°C)</span>
        </div>
      </div>
      <canvas
        ref={canvasRef}
        width={900}
        height={140}
        style={{ width: '100%', height: '140px', background: 'rgba(5, 10, 24, 0.65)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}
      />
    </div>
  );
}

export default function RealTimeTab({ state, timeline, orbitPoints, isPlaying }) {
  if (!state) {
    return <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading Telemetry Stream...</div>;
  }

  const num = (v, fallback = 0) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
  };

  const isAnom = Boolean(state.anomaly_flag) || (num(state.anomaly_probability) >= 0.5);
  const healthScore = num(state.health_score, 85.0);
  const battHealth = num(state.battery_health, 90.0);
  const thermHealth = num(state.thermal_health, 88.0);
  const pwrHealth = num(state.power_health, 92.0);
  const payloadHealth = num(state.payload_health, 100.0);

  const battPct = num(state.battery_percentage, 85.0);
  const battV = num(state.battery_voltage, 8.2);
  const battI = num(state.battery_current, 4.5);
  const tempC = num(state.temperature, 24.5);
  const solarPwr = num(state.solar_power_input, 0.0);
  const totDraw = num(state.power_draw, 35.0);
  const payloadStatus = String(state.payload_status ?? 'ON');
  const payloadPwr = num(state.payload_power_draw, 0.0);
  const comms = String(state.communication_status ?? 'LINKED');
  const fuelPct = num(state.fuel_remaining_pct, 100.0);
  const anomConf = num(state.anomaly_confidence, 0);
  const anomProb = num(state.anomaly_probability, 0);
  const risk = String(state.risk_level || 'LOW');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '20px' }}>
      
      {/* Top Anomaly Alert Banner if Triggered */}
      {isAnom ? (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 20px',
          background: 'linear-gradient(90deg, rgba(239, 68, 68, 0.25) 0%, rgba(139, 92, 246, 0.15) 100%)',
          border: '1px solid #ef4444',
          borderRadius: 'var(--radius-md)',
          boxShadow: '0 0 20px rgba(239, 68, 68, 0.3)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{ background: '#ef4444', padding: '8px', borderRadius: '50%', display: 'flex' }}>
              <ShieldAlert size={22} color="#ffffff" />
            </div>
            <div>
              <div style={{ fontFamily: 'var(--font-display)', fontWeight: 'bold', color: '#ff5555', letterSpacing: '0.8px' }}>
                ANOMALY DETECTED: {state.anomaly_parameter ? state.anomaly_parameter.toUpperCase().replace('_', ' ') : 'CORE SYSTEM'}
              </div>
              <div style={{ fontSize: '0.82rem', color: '#fecaca', marginTop: '2px' }}>
                XGBoost Diagnostic Model confidence: <strong>{(anomConf * 100).toFixed(1)}%</strong> | Anomaly Probability: <strong>{(anomProb * 100).toFixed(1)}%</strong>. Immediate telemetry triage recommended.
              </div>
            </div>
          </div>
          <span className="status-pill pill-critical">RISK: {risk}</span>
        </div>
      ) : (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 18px',
          background: 'rgba(16, 185, 129, 0.08)',
          border: '1px solid rgba(16, 185, 129, 0.25)',
          borderRadius: 'var(--radius-md)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CheckCircle2 size={18} color="#10b981" />
            <span style={{ fontSize: '0.82rem', color: '#6ee7b7' }}>
              Health Engine nominal. Zero channel anomalies detected in current orbital arc.
            </span>
          </div>
          <span className="status-pill pill-low">NOMINAL FLIGHT</span>
        </div>
      )}

      {/* Main Grid: 3D Orbit Globe on Left + Subsystem Health on Right */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(400px, 1.2fr) minmax(350px, 1fr)', gap: '20px' }}>
        
        {/* Left Column: 3D Orbit Globe */}
        <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--font-display)', fontSize: '0.9rem', color: '#00f0ff' }}>
              <Gauge size={16} /> 3D Orbital Trajectory & Attitude Digital Twin
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              STATE ID: {state.twin_state_id || 'TWIN-000001'}
            </span>
          </div>

          <div style={{ height: '420px', width: '100%' }}>
            <OrbitGlobe3D telemetry={state} orbitPoints={orbitPoints} isPlaying={isPlaying} />
          </div>
        </div>

        {/* Right Column: Health Engine Subsystems & Radar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          {/* Master Health Gauges Panel */}
          <div className="glass-panel" style={{ padding: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--font-display)', fontSize: '0.9rem', color: '#ffffff' }}>
                <Sparkles size={16} color="#00f0ff" /> ML Health Engine Subsystems
              </div>
              <span className={`status-pill pill-${risk.toLowerCase()}`}>
                RISK: {risk}
              </span>
            </div>

            <div className="gauge-grid">
              <CircularProgress value={healthScore} label="Overall Health" size={88} strokeWidth={8} />
              <CircularProgress value={battHealth} label="Battery Health" size={80} strokeWidth={7} />
              <CircularProgress value={thermHealth} label="Thermal Health" size={80} strokeWidth={7} />
              <CircularProgress value={pwrHealth} label="Power Health" size={80} strokeWidth={7} />
              <CircularProgress value={payloadHealth} label="Payload Health" size={80} strokeWidth={7} />
            </div>
          </div>

          {/* Key Electrical & Power Telemetry */}
          <div className="glass-panel" style={{ padding: '16px', flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              <Zap size={15} color="#f59e0b" /> Power & Environmental Subsystems
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
              <div className="tel-card">
                <div className="tel-card-title">
                  <span>Battery Reserve</span>
                  <Battery size={14} color="#10b981" />
                </div>
                <div className="tel-card-value">
                  {battPct.toFixed(1)} <span className="tel-card-unit">% ({battV.toFixed(1)} V)</span>
                </div>
              </div>

              <div className="tel-card">
                <div className="tel-card-title">
                  <span>Core Temp</span>
                  <Thermometer size={14} color={tempC > 40 ? '#ef4444' : '#00f0ff'} />
                </div>
                <div className="tel-card-value" style={{ color: tempC > 40 ? '#f87171' : '#ffffff' }}>
                  {tempC.toFixed(1)} <span className="tel-card-unit">°C</span>
                </div>
              </div>

              <div className="tel-card">
                <div className="tel-card-title">
                  <span>Solar Generation</span>
                  <Sun size={14} color="#f59e0b" />
                </div>
                <div className="tel-card-value">
                  {solarPwr.toFixed(0)} <span className="tel-card-unit">W</span>
                </div>
              </div>

              <div className="tel-card">
                <div className="tel-card-title">
                  <span>Total Consumption</span>
                  <Zap size={14} color="#8b5cf6" />
                </div>
                <div className="tel-card-value">
                  {totDraw.toFixed(0)} <span className="tel-card-unit">W</span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* 12-Channel Telemetry Matrix */}
      <div className="glass-panel" style={{ padding: '18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontFamily: 'var(--font-display)', fontSize: '0.88rem', color: '#00f0ff' }}>
            <Activity size={16} /> Real-Time Telemetry Matrix (Group 1 Synchronized)
          </div>
          <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            4,320 Telemetry Records Synced
          </span>
        </div>

        <div className="telemetry-matrix">
          <div className="tel-card">
            <div className="tel-card-title">Battery Current</div>
            <div className="tel-card-value">
              {battI > 0 ? `+${battI.toFixed(2)}` : battI.toFixed(2)} <span className="tel-card-unit">A ({battI > 0 ? 'Charging' : 'Discharging'})</span>
            </div>
          </div>

          <div className="tel-card">
            <div className="tel-card-title">Payload Subsystem</div>
            <div className="tel-card-value" style={{ color: payloadStatus === 'ON' ? '#10b981' : '#94a3b8' }}>
              {payloadStatus} <span className="tel-card-unit">({payloadPwr.toFixed(0)} W)</span>
            </div>
          </div>

          <div className="tel-card">
            <div className="tel-card-title">Comms Link</div>
            <div className="tel-card-value" style={{ color: comms === 'LINKED' ? '#10b981' : '#f59e0b' }}>
              {comms}
            </div>
          </div>

          <div className="tel-card">
            <div className="tel-card-title">Fuel Remaining</div>
            <div className="tel-card-value">
              {fuelPct.toFixed(1)} <span className="tel-card-unit">%</span>
            </div>
          </div>

          <div className="tel-card">
            <div className="tel-card-title">Semi-Major Axis</div>
            <div className="tel-card-value">
              {num(state.semi_major_axis, 6780).toFixed(1)} <span className="tel-card-unit">km</span>
            </div>
          </div>

          <div className="tel-card">
            <div className="tel-card-title">Inclination</div>
            <div className="tel-card-value">
              {num(state.inclination, 51.64).toFixed(2)} <span className="tel-card-unit">deg</span>
            </div>
          </div>
        </div>
      </div>

      {/* Multi-Stream Chart */}
      <div className="glass-panel" style={{ padding: '16px' }}>
        <TelemetryStreamChart timelineData={timeline} currentIndex={state.source_row_index || 0} />
      </div>

    </div>
  );
}
