import React from 'react';
import { 
  Activity, Battery, CheckCircle2, Compass, Gauge, ShieldAlert, Sun, Thermometer, Zap 
} from 'lucide-react';
import OrbitGlobe3D from './OrbitGlobe3D';

// Helper for Circular Progress Gauge
function CircularProgress({ value, label, size = 76, strokeWidth = 6, color }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedVal = Math.min(100, Math.max(0, value));
  const offset = circumference - (clampedVal / 100) * circumference;

  let computedColor = color;
  if (!computedColor) {
    if (value >= 80) computedColor = 'var(--status-nominal)';
    else if (value >= 60) computedColor = 'var(--status-caution)';
    else if (value >= 40) computedColor = '#f97316';
    else computedColor = 'var(--status-critical)';
  }

  return (
    <div className="gauge-card">
      <div className="gauge-svg-wrap" style={{ width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="#1e293b"
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
            style={{ transition: 'stroke-dashoffset 0.25s ease' }}
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

    // Subtle horizontal grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let y = 25; y < height; y += 30) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const n = timelineData.length;
    const stepX = width / Math.max(n - 1, 1);

    // Plot helper
    const drawLine = (key, color, minVal, maxVal, lineWidth = 1.5) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = lineWidth;
      ctx.beginPath();
      timelineData.forEach((pt, i) => {
        const val = pt[key] ?? 0;
        const norm = (val - minVal) / Math.max(maxVal - minVal, 1e-4);
        const x = i * stepX;
        const y = height - 16 - norm * (height - 32);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    };

    // Draw signals
    drawLine('battery_percentage', '#10b981', 0, 100);
    drawLine('temperature', '#f59e0b', -10, 60);
    drawLine('health_score', '#38bdf8', 0, 100, 2);

    // Draw active cursor playhead
    const cursorX = Math.min(width, Math.max(0, (currentIndex / Math.max(n - 1, 1)) * width));
    ctx.strokeStyle = 'rgba(248, 250, 252, 0.7)';
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(cursorX, 0);
    ctx.lineTo(cursorX, height);
    ctx.stroke();
    ctx.setLineDash([]);

  }, [timelineData, currentIndex]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <div style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Mission Telemetry Stream (Past Orbit Window)
        </div>
        <div style={{ display: 'flex', gap: '14px', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)' }}>
          <span style={{ color: '#38bdf8' }}>● Health Score</span>
          <span style={{ color: '#10b981' }}>● Battery %</span>
          <span style={{ color: '#f59e0b' }}>● Temperature (°C)</span>
        </div>
      </div>
      <canvas
        ref={canvasRef}
        width={900}
        height={130}
        style={{ width: '100%', height: '130px', background: '#05080e', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}
      />
    </div>
  );
}

export default function RealTimeTab({ state, timeline, orbitPoints, isPlaying, totalRows = 4320 }) {
  if (!state) {
    return <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Connecting to Telemetry Downlink...</div>;
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px' }}>
      
      {/* Flight Operations Status Banner */}
      {isAnom ? (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 16px',
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid #ef4444',
          borderRadius: 'var(--radius-sm)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ background: '#ef4444', padding: '6px', borderRadius: '4px', display: 'flex' }}>
              <ShieldAlert size={18} color="#ffffff" />
            </div>
            <div>
              <div style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', fontSize: '0.8125rem', color: '#fca5a5', letterSpacing: '0.04em' }}>
                EXCURSION DETECTED: {state.anomaly_parameter ? state.anomaly_parameter.toUpperCase().replace('_', ' ') : 'CORE SYSTEM'}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#cbd5e1', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                Confidence: {(anomConf * 100).toFixed(1)}% | Anomaly Probability: {(anomProb * 100).toFixed(1)}%
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
          padding: '8px 14px',
          background: 'rgba(16, 185, 129, 0.06)',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          borderRadius: 'var(--radius-sm)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle2 size={16} color="#10b981" />
            <span style={{ fontSize: '0.75rem', color: '#6ee7b7', fontFamily: 'var(--font-mono)' }}>
              All telemetry channels within nominal bounds.
            </span>
          </div>
          <span className="status-pill pill-low">NOMINAL FLIGHT</span>
        </div>
      )}

      {/* Main Grid: 3D Orbit Globe on Left + Subsystem Health on Right */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(400px, 1.25fr) minmax(340px, 1fr)', gap: '16px' }}>
        
        {/* Left Column: 3D Orbit Globe */}
        <div className="glass-panel" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
              <Compass size={15} color="#38bdf8" /> 3D Orbital Trajectory & Attitude
            </div>
            <span style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              STATE: {state.twin_state_id || 'TWIN-000001'}
            </span>
          </div>

          <div style={{ height: '400px', width: '100%' }}>
            <OrbitGlobe3D telemetry={state} orbitPoints={orbitPoints} isPlaying={isPlaying} />
          </div>
        </div>

        {/* Right Column: Health Engine Subsystems */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          {/* Master Health Gauges Panel */}
          <div className="glass-panel" style={{ padding: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
                <Activity size={15} color="#38bdf8" /> Subsystem Health Index
              </div>
              <span className={`status-pill pill-${risk.toLowerCase()}`}>
                RISK: {risk}
              </span>
            </div>

            <div className="gauge-grid">
              <CircularProgress value={healthScore} label="Overall" size={76} strokeWidth={6} />
              <CircularProgress value={battHealth} label="Battery" size={72} strokeWidth={5.5} />
              <CircularProgress value={thermHealth} label="Thermal" size={72} strokeWidth={5.5} />
              <CircularProgress value={pwrHealth} label="Power" size={72} strokeWidth={5.5} />
              <CircularProgress value={payloadHealth} label="Payload" size={72} strokeWidth={5.5} />
            </div>
          </div>

          {/* Key Electrical & Power Telemetry */}
          <div className="glass-panel" style={{ padding: '14px', flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px', fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              <Zap size={14} color="#f59e0b" /> Power & Environmental Status
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
              <div className="tel-card">
                <div className="tel-card-title">
                  <span>Battery Reserve</span>
                  <Battery size={13} color="#10b981" />
                </div>
                <div className="tel-card-value">
                  {battPct.toFixed(1)} <span className="tel-card-unit">% ({battV.toFixed(1)} V)</span>
                </div>
              </div>

              <div className="tel-card">
                <div className="tel-card-title">
                  <span>Core Temp</span>
                  <Thermometer size={13} color={tempC > 40 ? '#ef4444' : '#38bdf8'} />
                </div>
                <div className="tel-card-value" style={{ color: tempC > 40 ? '#f87171' : 'var(--text-main)' }}>
                  {tempC.toFixed(1)} <span className="tel-card-unit">°C</span>
                </div>
              </div>

              <div className="tel-card">
                <div className="tel-card-title">
                  <span>Solar Generation</span>
                  <Sun size={13} color="#f59e0b" />
                </div>
                <div className="tel-card-value">
                  {solarPwr.toFixed(0)} <span className="tel-card-unit">W</span>
                </div>
              </div>

              <div className="tel-card">
                <div className="tel-card-title">
                  <span>Total Consumption</span>
                  <Zap size={13} color="#94a3b8" />
                </div>
                <div className="tel-card-value">
                  {totDraw.toFixed(0)} <span className="tel-card-unit">W</span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

      {/* Downlink Telemetry Matrix */}
      <div className="glass-panel" style={{ padding: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
            <Gauge size={15} color="#38bdf8" /> Downlink Telemetry Matrix
          </div>
          <span style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
            {Number(totalRows || 4320).toLocaleString()} Records Synced
          </span>
        </div>

        <div className="telemetry-matrix">
          <div className="tel-card">
            <div className="tel-card-title">Battery Current</div>
            <div className="tel-card-value">
              {battI > 0 ? `+${battI.toFixed(2)}` : battI.toFixed(2)} <span className="tel-card-unit">A ({battI > 0 ? 'CHG' : 'DISCHG'})</span>
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

      {/* Multi-Stream Telemetry Chart */}
      <div className="glass-panel" style={{ padding: '14px' }}>
        <TelemetryStreamChart timelineData={timeline} currentIndex={state.source_row_index || 0} />
      </div>

    </div>
  );
}
