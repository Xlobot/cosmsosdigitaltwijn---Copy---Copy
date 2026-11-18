import React, { useState, useEffect, useRef } from 'react';
import {
  Activity, Brain, ChevronLeft, ChevronRight,
  GitFork, Pause, Play, RotateCcw,
  TrendingUp, Orbit, Home
} from 'lucide-react';
import RealTimeTab from './components/RealTimeTab';
import PredictionTab from './components/PredictionTab';
import ExperimentTab from './components/ExperimentTab';
import MissionIntelligenceTab from './components/MissionIntelligenceTab';
import LandingPage from './components/LandingPage';
import ErrorBoundary from './components/ErrorBoundary';
import LoginModal from './components/LoginModal';
import { ensureAuthenticated, getStoredUser, clearStoredAuth } from './auth';

export default function App() {
  const [viewMode, setViewMode] = useState('landing'); // 'landing' (entry landing page) or 'cockpit' (flight operations)
  const [activeTab, setActiveTab] = useState('realtime'); // 'realtime', 'predict', 'fork', 'mission_intel'
  const [rowIndex, setRowIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playSpeed, setPlaySpeed] = useState(1); // 1x, 2x, 5x, 10x, 30x, 60x

  // In-Memory Telemetry Dataset Cache
  const datasetCacheRef = useRef([]);
  const [datasetLoaded, setDatasetLoaded] = useState(false);
  const [totalRows, setTotalRows] = useState(4320);
  const [generatorInfo, setGeneratorInfo] = useState(null);
  const [currentState, setCurrentState] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [orbitPoints, setOrbitPoints] = useState([]);

  const [currentUser, setCurrentUser] = useState(getStoredUser());
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [loginModalTab, setLoginModalTab] = useState('login');

  const openLoginModal = (tab = 'login') => {
    setLoginModalTab(tab);
    setIsLoginModalOpen(true);
  };

  // Authenticate user session with 15-min JWT token
  useEffect(() => {
    ensureAuthenticated()
      .then((user) => {
        if (user) setCurrentUser(user);
      })
      .catch(() => {});

    const onAuthChanged = (e) => {
      setCurrentUser(e.detail.isAuthenticated ? e.detail.user : null);
    };
    const onAuthExpired = () => {
      openLoginModal('login');
    };

    window.addEventListener('cosmos:auth-changed', onAuthChanged);
    window.addEventListener('cosmos:auth-expired', onAuthExpired);
    return () => {
      window.removeEventListener('cosmos:auth-changed', onAuthChanged);
      window.removeEventListener('cosmos:auth-expired', onAuthExpired);
    };
  }, []);

  const playIntervalRef = useRef(null);

  // Poll system status to detect live telemetry generator stream updates
  useEffect(() => {
    const checkStatus = () => {
      fetch('/api/status')
        .then((res) => res.json())
        .then((status) => {
          if (status.dataset_total_rows) {
            setTotalRows(status.dataset_total_rows);
          }
          if (status.generator) {
            setGeneratorInfo(status.generator);
          }
        })
        .catch(() => {});
    };

    checkStatus();
    const interval = setInterval(checkStatus, 4000);
    return () => clearInterval(interval);
  }, []);

  // 1. Preload Full Dataset & Anomalies Registry on startup and when user session changes
  useEffect(() => {
    // Load Anomalies
    fetch('/api/anomalies')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) setAnomalies(data);
      })
      .catch((err) => console.error('Error fetching anomalies:', err));

    // Load initial 1-orbit track points
    fetch('/api/timeline?start=0&count=95&step=1')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data)) setOrbitPoints(data);
      })
      .catch((err) => console.error('Error fetching orbit points:', err));

    // Load initial state
    fetch('/api/state?index=0')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && typeof data === 'object' && !Array.isArray(data) && data.timestamp) {
          setCurrentState(data);
        }
      })
      .catch((err) => console.error('Error fetching initial state:', err));

    // Preload all dataset rows for instantaneous client replay
    fetch('/api/dataset/all')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          datasetCacheRef.current = data;
          setDatasetLoaded(true);
          setTotalRows(data.length);
          // Set initial timeline slice
          setTimeline(data.slice(0, 90));
          setCurrentState((prev) => prev || data[0]);
        }
      })
      .catch((err) => console.error('Dataset preload error:', err));
  }, [currentUser]);

  // Update current state and timeline when rowIndex changes (instant from cache or network fallback)
  useEffect(() => {
    const cache = datasetCacheRef.current;
    if (cache.length > rowIndex) {
      // Instant in-memory update
      const st = cache[rowIndex];
      setCurrentState(st);

      // Extract rolling 90-minute timeline window
      const startIdx = Math.max(0, rowIndex - 60);
      const endIdx = Math.min(cache.length, startIdx + 90);
      setTimeline(cache.slice(startIdx, endIdx));
    } else {
      // Network fallback
      fetch(`/api/state?index=${rowIndex}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && typeof data === 'object' && !Array.isArray(data) && data.timestamp) {
            setCurrentState(data);
          }
        })
        .catch((err) => console.error('Error fetching state:', err));

      const startIdx = Math.max(0, rowIndex - 60);
      fetch(`/api/timeline?start=${startIdx}&count=90&step=1`)
        .then((res) => (res.ok ? res.json() : []))
        .then((data) => {
          if (Array.isArray(data)) {
            setTimeline(data);
          }
        })
        .catch((err) => console.error('Error fetching timeline:', err));
    }
  }, [rowIndex, currentUser]);

  // 60 FPS Smooth Playback loop
  useEffect(() => {
    if (isPlaying) {
      // Playback interval calibrated to speed
      const intervalMs = Math.max(20, Math.floor(1000 / playSpeed));
      playIntervalRef.current = setInterval(() => {
        setRowIndex((prev) => {
          if (prev >= totalRows - 1) {
            setIsPlaying(false);
            return totalRows - 1;
          }
          return prev + 1;
        });
      }, intervalMs);
    } else {
      if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    }

    return () => {
      if (playIntervalRef.current) clearInterval(playIntervalRef.current);
    };
  }, [isPlaying, playSpeed, totalRows]);

  // Keyboard shortcut listener
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (viewMode !== 'cockpit') return;
      // If typing in input/select, ignore
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;

      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying((p) => !p);
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        const step = e.shiftKey ? 10 : 1;
        setRowIndex((r) => Math.min(totalRows - 1, r + step));
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        const step = e.shiftKey ? 10 : 1;
        setRowIndex((r) => Math.max(0, r - step));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [totalRows, viewMode]);

  const handleStep = (delta) => {
    setIsPlaying(false);
    setRowIndex((prev) => Math.max(0, Math.min(totalRows - 1, prev + delta)));
  };

  const handleScrubberClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    const targetIdx = Math.floor(pos * (totalRows - 1));
    setRowIndex(Math.max(0, Math.min(totalRows - 1, targetIdx)));
  };

  const handleJumpToAnomaly = (targetRow) => {
    setIsPlaying(false);
    setRowIndex(targetRow);
  };

  const currentTs = currentState?.timestamp || '2019-12-09T00:00:00Z';
  const riskLevel = String(currentState?.risk_level || 'LOW');

  // Landing Page Entry Screen
  if (viewMode === 'landing') {
    return (
      <>
        <LandingPage
          onEnter={(targetTab) => {
            if (targetTab) setActiveTab(targetTab);
            setViewMode('cockpit');
          }}
          currentState={currentState}
          totalRows={totalRows}
          generatorInfo={generatorInfo}
          anomalies={anomalies}
          currentUser={currentUser}
          onOpenAuth={openLoginModal}
          onLogout={clearStoredAuth}
        />
        <LoginModal
          isOpen={isLoginModalOpen}
          onClose={() => setIsLoginModalOpen(false)}
          onLoginSuccess={(u) => setCurrentUser(u)}
          initialTab={loginModalTab}
        />
      </>
    );
  }

  return (
    <div className="app-container">

      {/* Top Aerospace Navbar */}
      <header className="top-navbar">
        <div
          className="brand-section"
          onClick={() => setViewMode('landing')}
          style={{ cursor: 'pointer' }}
          title="Return to Mission Portal Overview"
        >
          <div className="brand-logo">
            <Orbit size={18} />
          </div>
          <div>
            <div className="brand-title">COSMOS</div>
            <div className="brand-subtitle">FLIGHT DIGITAL TWIN</div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="nav-tabs">
          <button
            className="nav-tab-btn"
            onClick={() => setViewMode('landing')}
            title="Return to Mission Portal Overview"
            style={{ borderColor: 'rgba(56, 189, 248, 0.3)' }}
          >
            <Home size={14} color="#38bdf8" /> Mission Portal
          </button>
          <button
            className={`nav-tab-btn ${activeTab === 'realtime' ? 'active' : ''}`}
            onClick={() => setActiveTab('realtime')}
          >
            <Activity size={14} /> Telemetry Replay
          </button>
          <button
            className={`nav-tab-btn ${activeTab === 'predict' ? 'active' : ''}`}
            onClick={() => setActiveTab('predict')}
          >
            <TrendingUp size={14} /> Propagation & Forecast
          </button>
          <button
            className={`nav-tab-btn ${activeTab === 'mission_intel' || activeTab === 'fork' ? 'active' : ''}`}
            onClick={() => setActiveTab('mission_intel')}
          >
            <Brain size={14} /> Mission Intelligence &amp; Scenarios
          </button>
        </div>

        {/* Live Satellite Info & Risk Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {generatorInfo && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 8px',
              borderRadius: '4px',
              background: generatorInfo.is_connected ? 'rgba(16, 185, 129, 0.1)' : 'rgba(100, 116, 139, 0.15)',
              border: `1px solid ${generatorInfo.is_connected ? 'rgba(16, 185, 129, 0.3)' : 'rgba(100, 116, 139, 0.3)'}`,
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6875rem',
              color: generatorInfo.is_connected ? '#34d399' : '#94a3b8'
            }}>
              <span style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: generatorInfo.is_connected ? '#10b981' : '#64748b'
              }} />
              {generatorInfo.is_connected ? 'GENERATOR STREAM' : 'STANDBY'}
            </div>
          )}
          <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
            <div style={{ fontSize: '0.8125rem', color: '#f8fafc', fontWeight: '600' }}>ISS-25544</div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
              {currentTs.replace('T', ' ').replace('Z', ' UTC')}
            </div>
          </div>
          <span className={`status-pill pill-${riskLevel.toLowerCase()}`}>
            {riskLevel}
          </span>

          {/* Operator Authentication Status & RBAC Controls */}
          {currentUser ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '3px 8px',
                borderRadius: '4px',
                backgroundColor: currentUser.role === 'admin' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 189, 248, 0.1)',
                border: `1px solid ${currentUser.role === 'admin' ? 'rgba(239, 68, 68, 0.35)' : 'rgba(56, 189, 248, 0.3)'}`,
                fontFamily: 'var(--font-mono)',
                fontSize: '0.6875rem',
                color: currentUser.role === 'admin' ? '#f87171' : '#38bdf8'
              }}>
                <span style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: currentUser.role === 'admin' ? '#ef4444' : '#38bdf8'
                }} />
                <span>{currentUser.username.toUpperCase()} ({currentUser.role === 'admin' ? 'ADMIN • ALL ACCESS' : 'OPERATOR'})</span>
                <button
                  onClick={clearStoredAuth}
                  title="Log out operator session"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#94a3b8',
                    cursor: 'pointer',
                    padding: '0 2px',
                    marginLeft: '4px',
                    fontSize: '0.625rem',
                    textDecoration: 'underline'
                  }}
                >
                  LOGOUT
                </button>
              </div>

              {currentUser.role === 'admin' && (
                <button
                  onClick={() => openLoginModal('new_user')}
                  title="Admin: Manage Users and Decide Permissions"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    backgroundColor: 'rgba(239, 68, 68, 0.2)',
                    border: '1px solid rgba(239, 68, 68, 0.4)',
                    color: '#fca5a5',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.6875rem',
                    fontWeight: '600',
                    cursor: 'pointer'
                  }}
                >
                  + USERS / PERMISSIONS
                </button>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                onClick={() => openLoginModal('login')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '4px 10px',
                  borderRadius: '4px',
                  backgroundColor: 'rgba(2, 132, 199, 0.25)',
                  border: '1px solid #0284c7',
                  color: '#38bdf8',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.6875rem',
                  fontWeight: '600',
                  cursor: 'pointer'
                }}
              >
                LOG IN / SIGN IN
              </button>

              <button
                onClick={() => openLoginModal('new_user')}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '4px 10px',
                  borderRadius: '4px',
                  backgroundColor: 'rgba(148, 163, 184, 0.1)',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  color: '#94a3b8',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.6875rem',
                  fontWeight: '500',
                  cursor: 'pointer'
                }}
              >
                NEW USER
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Master Replay & Scrubber Control Deck */}
      <section className="playback-bar">
        {/* Play / Step Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          <button className="btn-control" onClick={() => handleStep(-10)} title="Step -10m (Shift+Left)">
            -10m
          </button>
          <button className="btn-control" onClick={() => handleStep(-1)} title="Step -1m (Left Arrow)">
            <ChevronLeft size={14} />
          </button>
          <button
            className={`btn-control ${isPlaying ? 'active' : ''}`}
            onClick={() => setIsPlaying(!isPlaying)}
            style={{ width: '34px', justifyContent: 'center' }}
            title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
          >
            {isPlaying ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <button className="btn-control" onClick={() => handleStep(1)} title="Step +1m (Right Arrow)">
            <ChevronRight size={14} />
          </button>
          <button className="btn-control" onClick={() => handleStep(10)} title="Step +10m (Shift+Right)">
            +10m
          </button>
          <button className="btn-control" onClick={() => { setIsPlaying(false); setRowIndex(0); }} title="Rewind to T=0">
            <RotateCcw size={13} />
          </button>
        </div>

        {/* Speed Multiplier Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
          {[1, 2, 5, 10, 30, 60].map((spd) => (
            <button
              key={spd}
              className={`btn-control ${playSpeed === spd ? 'active' : ''}`}
              style={{ padding: '3px 6px', fontSize: '0.6875rem' }}
              onClick={() => setPlaySpeed(spd)}
            >
              {spd}x
            </button>
          ))}
        </div>

        {/* Interactive Scrubber with Anomaly Markers */}
        <div className="scrubber-container">
          {(() => {
            const safeMax = Math.max(1, totalRows - 1);
            const progressPct = Math.max(0, Math.min(100, (rowIndex / safeMax) * 100));
            return (
              <>
                <div
                  className="scrubber-track-wrap"
                  onClick={handleScrubberClick}
                  role="slider"
                  tabIndex={0}
                  aria-label="Orbit timeline playback scrubber"
                  aria-valuemin={0}
                  aria-valuemax={safeMax}
                  aria-valuenow={rowIndex}
                  onKeyDown={(e) => {
                    if (e.key === 'ArrowRight') handleStep(e.shiftKey ? 10 : 1);
                    else if (e.key === 'ArrowLeft') handleStep(e.shiftKey ? -10 : -1);
                    else if (e.key === 'Home') setRowIndex(0);
                    else if (e.key === 'End') setRowIndex(safeMax);
                  }}
                >
                  <div className="scrubber-track">
                    <div
                      className="scrubber-progress"
                      style={{ width: `${progressPct}%` }}
                    />
                  </div>
                  <div
                    className="scrubber-thumb"
                    style={{ left: `${progressPct}%` }}
                  />

                  {/* Render Anomaly Ticks */}
                  {Array.isArray(anomalies) && anomalies.map((anom, i) => {
                    const leftPct = Math.max(0, Math.min(100, (Number(anom.row_index) / safeMax) * 100));
                    return (
                      <div
                        key={`anom-${anom.row_index}-${i}`}
                        className="anomaly-marker"
                        style={{ left: `${leftPct}%` }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleJumpToAnomaly(Number(anom.row_index));
                        }}
                        title={`Anomaly: ${anom.description || 'Telemetry fault'} (Row #${anom.row_index})`}
                      />
                    );
                  })}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
                  <span>T=0 (Stream Start)</span>
                  <span style={{ color: 'var(--text-accent)' }}>
                    Row {rowIndex + 1} / {totalRows} ({progressPct.toFixed(1)}%)
                  </span>
                  <span>T+{totalRows}m (Live Buffer)</span>
                </div>
              </>
            );
          })()}
        </div>

        {/* Jump-To-Anomaly Event Dropdown */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>JUMP:</span>
          <select
            style={{ maxWidth: '220px', fontSize: '0.6875rem', padding: '3px 6px' }}
            onChange={(e) => {
              if (e.target.value !== '') {
                handleJumpToAnomaly(parseInt(e.target.value));
              }
            }}
            value=""
          >
            <option value="">Anomaly Events ({Array.isArray(anomalies) ? anomalies.length : 0})...</option>
            {Array.isArray(anomalies) && anomalies.map((a, i) => (
              <option key={`opt-${a.row_index}-${i}`} value={a.row_index}>
                #{a.row_index} {String(a.parameter || 'system').toUpperCase()} ({String(a.timestamp || '').slice(11, 16) || '??:??'})
              </option>
            ))}
          </select>
        </div>
      </section>

      {/* Main Tab Content View */}
      <main style={{ flex: 1, maxWidth: '1600px', width: '100%', margin: '0 auto' }}>
        <ErrorBoundary key={activeTab}>
          {activeTab === 'realtime' && (
            <RealTimeTab
              state={currentState}
              timeline={timeline}
              orbitPoints={orbitPoints}
              isPlaying={isPlaying}
              totalRows={totalRows}
            />
          )}

          {activeTab === 'predict' && (
            <PredictionTab
              currentRowIndex={rowIndex}
              onJumpToRow={(idx) => setRowIndex(idx)}
            />
          )}

          {(activeTab === 'mission_intel' || activeTab === 'fork') && (
            <MissionIntelligenceTab
              currentRowIndex={rowIndex}
              currentState={currentState}
            />
          )}
        </ErrorBoundary>
      </main>

      {/* Operator Authentication Modal */}
      <LoginModal
        isOpen={isLoginModalOpen}
        onClose={() => setIsLoginModalOpen(false)}
        onLoginSuccess={(u) => setCurrentUser(u)}
        initialTab={loginModalTab}
      />

    </div>
  );
}
