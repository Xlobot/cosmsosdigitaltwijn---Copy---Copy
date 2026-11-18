import React, { useState, useEffect, useRef } from 'react';
import {
  Orbit, Activity, TrendingUp, GitFork, Brain,
  Radio, Cpu, Zap, ShieldCheck, Compass,
  Layers, ArrowRight, Play, ExternalLink, Satellite,
  Thermometer, CheckCircle2, Sparkles, Clock, Globe,
  Lock, UserPlus
} from 'lucide-react';
import './LandingPage.css';
import astronautHero from '../assets/astronaut_hero.jpg';

// Interactive Starfield & Constellation Canvas
function StarfieldCanvas() {
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: -1000, y: -1000 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationId;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', handleResize);

    const handleMouseMove = (e) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    };
    window.addEventListener('mousemove', handleMouseMove);

    // Initialize 160 stars with depth layers
    const numStars = 160;
    const stars = Array.from({ length: numStars }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 1.5 + 0.5,
      speedX: (Math.random() - 0.5) * 0.15,
      speedY: (Math.random() - 0.5) * 0.15,
      alpha: Math.random() * 0.7 + 0.2,
      baseAlpha: Math.random() * 0.7 + 0.2,
      twinkleSpeed: Math.random() * 0.02 + 0.005,
      twinkleDir: 1
    }));

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Render Stars
      stars.forEach((star) => {
        // Twinkle
        star.alpha += star.twinkleSpeed * star.twinkleDir;
        if (star.alpha > 0.95) star.twinkleDir = -1;
        if (star.alpha < star.baseAlpha * 0.4) star.twinkleDir = 1;

        // Drift
        star.x += star.speedX;
        star.y += star.speedY;

        if (star.x < 0) star.x = width;
        if (star.x > width) star.x = 0;
        if (star.y < 0) star.y = height;
        if (star.y > height) star.y = 0;

        ctx.fillStyle = `rgba(224, 242, 254, ${star.alpha})`;
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
        ctx.fill();

        // Mouse proximity subtle constellation link
        const dx = mouseRef.current.x - star.x;
        const dy = mouseRef.current.y - star.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 120) {
          ctx.strokeStyle = `rgba(56, 189, 248, ${(1 - dist / 120) * 0.25})`;
          ctx.lineWidth = 0.7;
          ctx.beginPath();
          ctx.moveTo(star.x, star.y);
          ctx.lineTo(mouseRef.current.x, mouseRef.current.y);
          ctx.stroke();
        }
      });

      animationId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return <canvas ref={canvasRef} className="landing-canvas-bg" />;
}

export default function LandingPage({
  onEnter,
  currentState,
  totalRows = 4320,
  generatorInfo = null,
  anomalies = [],
  currentUser = null,
  onOpenAuth = () => {},
  onLogout = () => {}
}) {
  const [utcTime, setUtcTime] = useState('');
  const [activeSubsystem, setActiveSubsystem] = useState('eps');

  // Live UTC Clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(now.toISOString().slice(11, 19) + ' UTC');
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  // Telemetry computations
  const altitudeKm = currentState?.position_x !== undefined
    ? Math.max(200, Math.round(Math.sqrt(
        Math.pow(currentState.position_x, 2) +
        Math.pow(currentState.position_y, 2) +
        Math.pow(currentState.position_z, 2)
      ) - 6371))
    : 562;

  const velocityMag = currentState?.velocity_mag !== undefined
    ? Number(currentState.velocity_mag).toFixed(2)
    : '7.58';

  const healthScore = currentState?.health_index !== undefined
    ? Number(currentState.health_index).toFixed(1)
    : '98.4';

  const batteryVoltage = currentState?.battery_voltage !== undefined
    ? Number(currentState.battery_voltage).toFixed(1)
    : '28.4';

  const riskLevel = currentState?.risk_level || 'LOW';
  const anomalyCount = Array.isArray(anomalies) ? anomalies.length : 31;
  const isGeneratorConnected = generatorInfo?.is_connected ?? true;

  // Subsystem specifications and live telemetry data
  const subsystems = {
    eps: {
      name: 'Electrical Power Subsystem (EPS)',
      code: 'EPS-01',
      icon: Zap,
      color: '#f59e0b',
      status: 'OPTIMAL',
      metrics: [
        { label: 'BUS VOLTAGE', value: `${batteryVoltage} V`, sub: 'Nominal Range: 24-32V' },
        { label: 'BATTERY HEALTH', value: `${healthScore}%`, sub: 'Degradation Model active' },
        { label: 'SOLAR ARRAY FLUX', value: '1,361 W/m²', sub: 'Sun Vector Alignment 98.2%' },
        { label: 'DEPTH OF DISCHARGE', value: '14.2%', sub: 'LEO Orbit Eclipse Cycle' }
      ],
      description:
        'Dual triple-junction GaAs solar arrays driving a regulated 28V power bus with lithium-ion energy storage. Monitored continuously via multi-output regression for micro-shorts and cyclic thermal stress.'
    },
    adcs: {
      name: 'Attitude Determination & Control (ADCS)',
      code: 'ADCS-02',
      icon: Compass,
      color: '#38bdf8',
      status: 'STABLE',
      metrics: [
        { label: 'POINTING ERROR', value: '0.042°', sub: 'Earth Nadir Lock' },
        { label: 'WHEEL SPEED X', value: '3,410 RPM', sub: 'Max Rating: 6,000 RPM' },
        { label: 'WHEEL SPEED Y', value: '2,890 RPM', sub: 'Momentum Bias Nominal' },
        { label: 'STAR TRACKERS', value: '2 OF 2', sub: 'Catalog Locked (48 stars)' }
      ],
      description:
        '3-axis reaction wheel cluster augmented with magnetic torque rods and autonomous dual star trackers. Maintains nadir tracking and payload aperture orientation with sub-arcminute pointing precision.'
    },
    tcs: {
      name: 'Thermal Control Subsystem (TCS)',
      code: 'TCS-03',
      icon: Thermometer,
      color: '#ef4444',
      status: 'NOMINAL',
      metrics: [
        { label: 'PAYLOAD CORE TEMP', value: '+18.4 °C', sub: 'Nominal Operating Window' },
        { label: 'BATTERY TEMP', value: '+14.1 °C', sub: 'Heater Duty Cycle: 12%' },
        { label: 'RADIATOR OUTFLOW', value: '42.8 W/m²', sub: 'Deep Space Heat Sink' },
        { label: 'GRADIENT SPREAD', value: 'Δ 8.2 °C', sub: 'Structural Thermal Margin' }
      ],
      description:
        'Passive multi-layer insulation (MLI) blankets paired with high-conductivity heat pipes and thermostatically controlled patch heaters across all avionics bays and optical instruments.'
    },
    prop: {
      name: 'Propulsion & Orbital Vectoring (PROP)',
      code: 'PROP-04',
      icon: Orbit,
      color: '#10b981',
      status: 'STANDBY',
      metrics: [
        { label: 'MONOPROPELLANT', value: '4.82 kg', sub: 'Hydrazine Tank Margin' },
        { label: 'REMAINING ΔV', value: '142.6 m/s', sub: 'De-orbit Reserve: 85 m/s' },
        { label: 'THRUST SPECIFIC ISP', value: '228 s', sub: 'Steady-State Pulse ISP' },
        { label: 'ORBITAL PREDICTION', value: 'J2 KEPLER', sub: 'Decay Compensation Ready' }
      ],
      description:
        'Catalytic monopropellant thrusters configured for in-plane phasing, semi-major axis maintenance, collision avoidance, and eventual controlled atmospheric re-entry de-orbit.'
    },
    ttc: {
      name: 'Tracking, Telemetry & Command (TT&C)',
      code: 'TTC-05',
      icon: Radio,
      color: '#818cf8',
      status: 'LINKED',
      metrics: [
        { label: 'DOWNLINK FREQ', value: '2,245.5 MHz', sub: 'S-Band Spacecraft Link' },
        { label: 'SIGNAL-TO-NOISE (SNR)', value: '18.4 dB', sub: 'Direct LOS Elevation 42°' },
        { label: 'NEXT PASS CONTACT', value: 'SVALBARD', sub: 'AOS in 14m 20s' },
        { label: 'DATA STREAM RATE', value: '1.0 Hz SYNC', sub: `${totalRows.toLocaleString()} frames synchronized` }
      ],
      description:
        'Omni-directional and directional S-Band transceivers delivering real-time telemetry streaming, commanding, and two-way Doppler ranging across international ground station networks.'
    }
  };

  const currentSub = subsystems[activeSubsystem] || subsystems.eps;

  return (
    <div className="landing-page">
      {/* Dynamic Starfield Background Canvas */}
      <StarfieldCanvas />
      <div className="landing-grid-overlay" />
      <div className="landing-glow-spot" />

      <div className="landing-content">
        {/* Top Aerospace Navbar */}
        <header className="landing-nav">
          <div className="landing-brand">
            <div className="landing-brand-logo">
              <Orbit size={22} />
            </div>
            <div>
              <div className="landing-brand-title">
                COSMOS <span className="landing-brand-tag">DT-1</span>
              </div>
              <div style={{ fontSize: '0.625rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.04em' }}>
                AUTONOMOUS FLIGHT DIGITAL TWIN
              </div>
            </div>
          </div>

          <div className="landing-nav-stats">
            <div className="landing-stat-chip">
              <Clock size={12} color="#38bdf8" />
              <span>{utcTime}</span>
            </div>

            <div className="landing-stat-chip">
              <Radio size={12} color={isGeneratorConnected ? '#10b981' : '#f59e0b'} />
              <span>STREAM: <strong>{isGeneratorConnected ? 'LIVE 1.0Hz' : 'OFFLINE'}</strong></span>
            </div>

            <div className="landing-stat-chip">
              <ShieldCheck size={12} color="#10b981" />
              <span>RISK: <strong>{riskLevel}</strong></span>
            </div>

            <div className="landing-stat-chip">
              <DatabaseStat count={totalRows} />
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {currentUser ? (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '4px 10px',
                borderRadius: '6px',
                backgroundColor: currentUser.role === 'admin' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 189, 248, 0.12)',
                border: `1px solid ${currentUser.role === 'admin' ? 'rgba(239, 68, 68, 0.35)' : 'rgba(56, 189, 248, 0.3)'}`,
                fontFamily: 'var(--font-mono)',
                fontSize: '0.75rem',
                color: currentUser.role === 'admin' ? '#f87171' : '#38bdf8'
              }}>
                <span>{currentUser.username.toUpperCase()} ({currentUser.role === 'admin' ? 'ADMIN • ALL ACCESS' : 'OPERATOR'})</span>
                {currentUser.role === 'admin' && (
                  <button
                    onClick={() => onOpenAuth('new_user')}
                    title="Admin: Manage Users and Decide Permissions"
                    style={{
                      background: 'rgba(239, 68, 68, 0.25)',
                      border: '1px solid rgba(239, 68, 68, 0.45)',
                      borderRadius: '4px',
                      color: '#fca5a5',
                      padding: '2px 6px',
                      cursor: 'pointer',
                      fontSize: '0.6875rem',
                      fontWeight: '600'
                    }}
                  >
                    + USERS / PERMISSIONS
                  </button>
                )}
                <button
                  onClick={onLogout}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#94a3b8',
                    cursor: 'pointer',
                    fontSize: '0.6875rem',
                    textDecoration: 'underline'
                  }}
                >
                  LOGOUT
                </button>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <button
                  className="landing-stat-chip"
                  onClick={() => onOpenAuth('login')}
                  style={{ cursor: 'pointer', borderColor: 'rgba(56, 189, 248, 0.4)', color: '#38bdf8', padding: '6px 12px' }}
                >
                  <Lock size={12} color="#38bdf8" />
                  <strong>LOG IN / SIGN IN</strong>
                </button>
                <button
                  className="landing-stat-chip"
                  onClick={() => onOpenAuth('new_user')}
                  style={{ cursor: 'pointer', borderColor: 'rgba(148, 163, 184, 0.3)', color: '#94a3b8', padding: '6px 12px' }}
                >
                  <UserPlus size={12} color="#94a3b8" />
                  <strong>NEW USER</strong>
                </button>
              </div>
            )}

            <button
              className="landing-enter-btn-top"
              onClick={() => onEnter('realtime')}
              title="Launch Full Cockpit Telemetry Operations"
            >
              <span>LAUNCH COCKPIT</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </header>

        {/* Hero Section */}
        <section className="landing-hero">
          <div className="landing-badge-eyebrow">
            <Sparkles size={14} color="#38bdf8" />
            <span>Autonomous Satellite Digital Twin Engine</span>
            <span style={{ opacity: 0.4 }}>•</span>
            <span style={{ color: '#34d399' }}>LEO Flight Operations</span>
          </div>

          <h1 className="landing-hero-title">
            Intelligent Orbital Operations &{' '}
            <span className="landing-hero-gradient-text">Predictive Flight Telemetry</span>
          </h1>

          <p className="landing-hero-desc">
            Continuous synthetic telemetry streaming, high-fidelity Keplerian J2 orbital propagation,
            multi-output XGBoost health degradation forecasting, and real-time autonomous Mission
            Intelligence for spacecraft fleet operations.
          </p>

          {/* Primary Call to Action */}
          <div className="landing-hero-cta">
            <button
              className="landing-btn-primary"
              onClick={() => onEnter('realtime')}
              aria-label="Enter Mission Control Cockpit"
            >
              <Play size={16} fill="currentColor" />
              <span>ENTER MISSION CONTROL</span>
              <ArrowRight size={16} />
            </button>

            <button
              className="landing-btn-secondary"
              onClick={() => onEnter('mission_intel')}
              aria-label="Open Mission Intelligence Module"
            >
              <Brain size={16} color="#38bdf8" />
              <span>Explore Mission Intelligence</span>
            </button>
          </div>

          {/* Live Telemetry HUD Strip */}
          <div className="landing-hud-strip">
            <div className="landing-hud-cell">
              <span className="landing-hud-label">
                <Globe size={11} color="#38bdf8" /> ORBITAL REGIME
              </span>
              <span className="landing-hud-value">LEO POLAR</span>
              <span className="landing-hud-sub">Alt: {altitudeKm} km</span>
            </div>

            <div className="landing-hud-cell">
              <span className="landing-hud-label">
                <Compass size={11} color="#38bdf8" /> VELOCITY
              </span>
              <span className="landing-hud-value">{velocityMag} km/s</span>
              <span className="landing-hud-sub">Inclination: 97.4°</span>
            </div>

            <div className="landing-hud-cell">
              <span className="landing-hud-label">
                <Zap size={11} color="#f59e0b" /> BATTERY HEALTH
              </span>
              <span className="landing-hud-value" style={{ color: '#34d399' }}>{healthScore}%</span>
              <span className="landing-hud-sub">{batteryVoltage} V Bus</span>
            </div>

            <div className="landing-hud-cell">
              <span className="landing-hud-label">
                <Cpu size={11} color="#818cf8" /> ML INFERENCE
              </span>
              <span className="landing-hud-value">50 SIGNALS</span>
              <span className="landing-hud-sub">XGBoost 2.0 Regressor</span>
            </div>

            <div className="landing-hud-cell">
              <span className="landing-hud-label">
                <Activity size={11} color={anomalyCount > 0 ? '#f59e0b' : '#34d399'} /> ANOMALIES
              </span>
              <span className="landing-hud-value" style={{ color: anomalyCount > 0 ? '#fbbf24' : '#34d399' }}>
                {anomalyCount} DETECTED
              </span>
              <span className="landing-hud-sub">Isolation Forest</span>
            </div>

            <div className="landing-hud-cell">
              <span className="landing-hud-label">
                <Radio size={11} color="#38bdf8" /> TELEMETRY STREAM
              </span>
              <span className="landing-hud-value">{totalRows.toLocaleString()}</span>
              <span className="landing-hud-sub">Records Synced</span>
            </div>
          </div>

          {/* Quick Module Jump Chips */}
          <div className="landing-quick-nav">
            <span style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginRight: '6px' }}>
              DIRECT ACCESS:
            </span>
            <button className="landing-chip-btn" onClick={() => onEnter('realtime')}>
              <Activity size={12} color="#38bdf8" /> Telemetry Replay &amp; 3D Globe
            </button>
            <button className="landing-chip-btn" onClick={() => onEnter('predict')}>
              <TrendingUp size={12} color="#818cf8" /> Orbit Propagation &amp; Forecast
            </button>
            <button className="landing-chip-btn" onClick={() => onEnter('mission_intel')}>
              <Brain size={12} color="#38bdf8" /> Mission Intelligence &amp; Scenarios
            </button>
          </div>
        </section>

        {/* 4 Pillars Grid Section */}
        <section className="landing-section">
          <div className="landing-section-header">
            <div className="landing-section-tag">System Capabilities</div>
            <h2 className="landing-section-title">The Four Operational Pillars of Cosmos</h2>
            <p className="landing-section-desc">
              Engineered for satellite flight directors, mission planners, and spacecraft engineers
              managing mission-critical orbital assets.
            </p>
          </div>

          <div className="landing-pillars-grid">
            {/* Pillar 1 */}
            <div className="landing-pillar-card">
              <div>
                <div className="landing-pillar-icon" style={{ background: 'rgba(56, 189, 248, 0.1)', color: '#38bdf8' }}>
                  <Activity size={24} />
                </div>
                <div className="landing-pillar-num">MODULE 01</div>
                <h3 className="landing-pillar-title">Real-Time Telemetry & 3D Earth Globe</h3>
                <p className="landing-pillar-text">
                  60 FPS synchronized playback across 4,300+ orbital frames. Full 3D photorealistic Earth
                  visualization with solar terminators, true ground tracks, and multi-subsystem telemetry graphs.
                </p>
              </div>
              <button className="landing-pillar-action" onClick={() => onEnter('realtime')}>
                <span>Launch Telemetry Engine</span>
                <ArrowRight size={13} />
              </button>
            </div>

            {/* Pillar 2 */}
            <div className="landing-pillar-card">
              <div>
                <div className="landing-pillar-icon" style={{ background: 'rgba(129, 140, 248, 0.1)', color: '#818cf8' }}>
                  <TrendingUp size={24} />
                </div>
                <div className="landing-pillar-num">MODULE 02</div>
                <h3 className="landing-pillar-title">Predictive Degradation & RUL Forecasting</h3>
                <p className="landing-pillar-text">
                  Multi-output gradient-boosted decision trees evaluate 50 flight features simultaneously to
                  forecast future component degradation, voltage drop, and remaining useful life with confidence intervals.
                </p>
              </div>
              <button className="landing-pillar-action" onClick={() => onEnter('predict')}>
                <span>Launch Forecasting Engine</span>
                <ArrowRight size={13} />
              </button>
            </div>

            {/* Pillar 3 */}
            <div className="landing-pillar-card">
              <div>
                <div className="landing-pillar-icon" style={{ background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b' }}>
                  <GitFork size={24} />
                </div>
                <div className="landing-pillar-num">MODULE 03</div>
                <h3 className="landing-pillar-title">Branching Scenario & What-If Forking</h3>
                <p className="landing-pillar-text">
                  Branch off any historical point in time to run high-thrust delta-V burn simulations,
                  attitude reorientations, and failure recoveries without disturbing nominal telemetry flight logs.
                </p>
              </div>
              <button className="landing-pillar-action" onClick={() => onEnter('mission_intel')}>
                <span>Launch Scenario Simulator</span>
                <ArrowRight size={13} />
              </button>
            </div>

            {/* Pillar 4 */}
            <div className="landing-pillar-card">
              <div>
                <div className="landing-pillar-icon" style={{ background: 'rgba(236, 72, 153, 0.1)', color: '#ec4899' }}>
                  <Brain size={24} />
                </div>
                <div className="landing-pillar-num">MODULE 04</div>
                <h3 className="landing-pillar-title">Autonomous Mission Intelligence</h3>
                <p className="landing-pillar-text">
                  Multi-objective Pareto optimization weighing flight safety, energy conservation, orbital lifespan,
                  and ground station link viability to recommend prioritized corrective maneuvers for anomalous conditions.
                </p>
              </div>
              <button className="landing-pillar-action" onClick={() => onEnter('mission_intel')}>
                <span>Launch Mission Intelligence</span>
                <ArrowRight size={13} />
              </button>
            </div>
          </div>
        </section>

        {/* Interactive Subsystems Inspector Section */}
        <section className="landing-section">
          <div className="landing-section-header">
            <div className="landing-section-tag">Telemetry Architecture</div>
            <h2 className="landing-section-title">Spacecraft Subsystems Live Telemetry</h2>
            <p className="landing-section-desc">
              Inspect flight avionics parameters across the 5 primary spacecraft subsystems.
            </p>
          </div>

          <div className="landing-subsystems-panel">
            {/* Subsystem Tabs */}
            <div className="landing-subsystem-tabs">
              {Object.entries(subsystems).map(([key, sub]) => {
                const IconComponent = sub.icon;
                const isActive = activeSubsystem === key;
                return (
                  <button
                    key={key}
                    className={`landing-subsystem-tab ${isActive ? 'active' : ''}`}
                    onClick={() => setActiveSubsystem(key)}
                  >
                    <IconComponent size={14} color={isActive ? '#38bdf8' : sub.color} />
                    <span>{sub.code}</span>
                  </button>
                );
              })}
            </div>

            {/* Subsystem Details & Metrics */}
            <div className="landing-subsystem-detail">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: '#10b981',
                    boxShadow: '0 0 8px #10b981'
                  }} />
                  <span style={{ fontSize: '1.0625rem', fontWeight: '700', color: '#ffffff' }}>
                    {currentSub.name}
                  </span>
                  <span className="status-pill pill-low">{currentSub.status}</span>
                </div>

                <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', lineHeight: '1.6' }}>
                  {currentSub.description}
                </p>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '6px' }}>
                  <button
                    className="landing-btn-secondary"
                    style={{ padding: '8px 16px', fontSize: '0.75rem' }}
                    onClick={() => onEnter('realtime')}
                  >
                    <Activity size={12} color="#38bdf8" />
                    <span>View Live {currentSub.code} Telemetry Stream</span>
                  </button>
                </div>
              </div>

              {/* 4 Metrics for this Subsystem */}
              <div className="landing-subsystem-metric-grid">
                {currentSub.metrics.map((m, idx) => (
                  <div key={idx} className="landing-metric-box">
                    <span className="landing-metric-box-label">{m.label}</span>
                    <span className="landing-metric-box-val">{m.value}</span>
                    <span style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {m.sub}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Technical Architecture Specs */}
        <section className="landing-section">
          <div className="landing-section-header">
            <div className="landing-section-tag">Flight Specifications</div>
            <h2 className="landing-section-title">Enterprise Flight Operations Architecture</h2>
          </div>

          <div className="landing-specs-grid">
            <div className="landing-spec-card">
              <span className="landing-spec-card-title">Propagator Engine</span>
              <span className="landing-spec-card-value">Keplerian + J2 Oblateness</span>
              <span className="landing-spec-card-desc">
                High-fidelity 2-body numerical solver accounting for Earth oblateness drift and orbital nodal regression.
              </span>
            </div>

            <div className="landing-spec-card">
              <span className="landing-spec-card-title">Health Regressors</span>
              <span className="landing-spec-card-value">XGBoost 2.0 Multi-Output</span>
              <span className="landing-spec-card-desc">
                Ensemble of 50 engineered features evaluating degradation trends and bus battery health in under 15ms.
              </span>
            </div>

            <div className="landing-spec-card">
              <span className="landing-spec-card-title">Telemetry Ingestion</span>
              <span className="landing-spec-card-value">1.0 Hz Synthetic Feed</span>
              <span className="landing-spec-card-desc">
                Non-blocking REST API stream emitting continuous LEO sensor state to maintain real-time situational awareness.
              </span>
            </div>

            <div className="landing-spec-card">
              <span className="landing-spec-card-title">Intelligence Engine</span>
              <span className="landing-spec-card-value">Pareto-Optimal Matrix</span>
              <span className="landing-spec-card-desc">
                Multi-objective decision scoring generating ranked mitigation maneuvers with feasibility and trade-offs.
              </span>
            </div>
          </div>
        </section>

        {/* Final Launch Banner */}
        <section className="landing-banner">
          <div className="landing-banner-box">
            <div style={{ position: 'relative', zIndex: 2 }}>
              <h2>Enter the Mission Control Cockpit</h2>
              <p>
                Take full control of satellite telemetry replay, 3D orbit visualization, predictive health forecasting,
                and autonomous anomaly mitigation.
              </p>
            </div>

            <div style={{ position: 'relative', zIndex: 2, display: 'flex', gap: '12px' }}>
              <button
                className="landing-btn-primary"
                onClick={() => onEnter('realtime')}
                style={{ whiteSpace: 'nowrap' }}
              >
                <span>ENTER MISSION CONTROL</span>
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="landing-footer">
          <div>
            <span>COSMOS FLIGHT DIGITAL TWIN &bull; CIVIL & COMMERCIAL SATELLITE OPERATIONS &bull; VERSION 2.4.0</span>
          </div>
          <div>
            <span>AUTONOMOUS ORBITAL OPERATIONS &bull; REST API CONNECTED</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

function DatabaseStat({ count }) {
  return (
    <span>RECORDS: <strong>{count ? count.toLocaleString() : '4,320+'}</strong></span>
  );
}
