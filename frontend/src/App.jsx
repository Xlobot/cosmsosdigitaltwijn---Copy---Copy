import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Activity, AlertTriangle, ChevronLeft, ChevronRight, Cpu, 
  FastForward, GitFork, Globe, Pause, Play, RotateCcw, 
  RotateCw, ShieldAlert, Sparkles, Zap, Orbit, Keyboard
} from 'lucide-react';
import RealTimeTab from './components/RealTimeTab';
import PredictionTab from './components/PredictionTab';
import ExperimentTab from './components/ExperimentTab';
import ModelInfoTab from './components/ModelInfoTab';
import ErrorBoundary from './components/ErrorBoundary';

export default function App() {
  const [activeTab, setActiveTab] = useState('realtime'); // 'realtime', 'predict', 'fork', 'ml_info'
  const [rowIndex, setRowIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playSpeed, setPlaySpeed] = useState(1); // 1x, 2x, 5x, 10x, 30x, 60x

  // In-Memory Preloaded Dataset for 100% Zero-Latency 60 FPS Playback
  const datasetCacheRef = useRef([]);
  const [datasetLoaded, setDatasetLoaded] = useState(false);
  const [currentState, setCurrentState] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [orbitPoints, setOrbitPoints] = useState([]);
  const totalRows = 4320;

  const playIntervalRef = useRef(null);

  // 1. Preload Full Dataset & Anomalies Registry on startup
  useEffect(() => {
    // Load Anomalies
    fetch('/api/anomalies')
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setAnomalies(data);
      })
      .catch((err) => console.error('Error fetching anomalies:', err));

    // Load initial 1-orbit track points
    fetch('/api/timeline?start=0&count=95&step=1')
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setOrbitPoints(data);
      })
      .catch((err) => console.error('Error fetching orbit points:', err));

    // Load initial state
    fetch('/api/state?index=0')
      .then((res) => res.json())
      .then((data) => {
        if (data && typeof data === 'object' && !Array.isArray(data) && data.timestamp) {
          setCurrentState(data);
        }
      })
      .catch((err) => console.error('Error fetching initial state:', err));

    // Preload all 4,320 rows for instantaneous client replay
    fetch('/api/dataset/all')
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          datasetCacheRef.current = data;
          setDatasetLoaded(true);
          // Set initial timeline slice
          setTimeline(data.slice(0, 90));
          setCurrentState((prev) => prev || data[0]);
        }
      })
      .catch((err) => console.error('Dataset preload error:', err));
  }, []);

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
        .then((res) => res.json())
        .then((data) => setCurrentState(data))
        .catch((err) => console.error('Error fetching state:', err));

      const startIdx = Math.max(0, rowIndex - 60);
      fetch(`/api/timeline?start=${startIdx}&count=90&step=1`)
        .then((res) => res.json())
        .then((data) => setTimeline(data))
        .catch((err) => console.error('Error fetching timeline:', err));
    }
  }, [rowIndex]);

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
  }, [totalRows]);

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

  return (
    <div className="app-container">
      
      {/* Top Aerospace Navbar */}
      <header className="top-navbar">
        <div className="brand-section">
          <div className="brand-logo">
            <Orbit size={24} color="#040711" />
          </div>
          <div>
            <div className="brand-title">COSMOS DIGITAL TWIN</div>
            <div className="brand-subtitle">
              Mission Control • Telemetry Replay • XGBoost Health Engine {datasetLoaded && '• Real-Time Synced'}
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="nav-tabs">
          <button
            className={`nav-tab-btn ${activeTab === 'realtime' ? 'active' : ''}`}
            onClick={() => setActiveTab('realtime')}
          >
            <Activity size={15} /> Real-Time Replay
          </button>
          <button
            className={`nav-tab-btn ${activeTab === 'predict' ? 'active' : ''}`}
            onClick={() => setActiveTab('predict')}
          >
            <Sparkles size={15} /> Prediction & Validation
          </button>
          <button
            className={`nav-tab-btn ${activeTab === 'fork' ? 'active' : ''}`}
            onClick={() => setActiveTab('fork')}
          >
            <GitFork size={15} /> Experiment (Fork)
          </button>
          <button
            className={`nav-tab-btn ${activeTab === 'ml_info' ? 'active' : ''}`}
            onClick={() => setActiveTab('ml_info')}
          >
            <Cpu size={15} /> Health Engine Models
          </button>
        </div>

        {/* Live Satellite Info & Risk Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
            <div style={{ fontSize: '0.85rem', color: '#ffffff', fontWeight: 'bold' }}>ISS-25544</div>
            <div style={{ fontSize: '0.72rem', color: '#00f0ff' }}>{currentTs}</div>
          </div>
          <span className={`status-pill pill-${riskLevel.toLowerCase()}`}>
            {riskLevel}
          </span>
        </div>
      </header>

      {/* Master Replay & Scrubber Control Deck */}
      <section className="playback-bar">
        {/* Play / Step Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button className="btn-control" onClick={() => handleStep(-10)} title="Step -10m (Shift+Left)">
            -10m
          </button>
          <button className="btn-control" onClick={() => handleStep(-1)} title="Step -1m (Left Arrow)">
            <ChevronLeft size={16} />
          </button>
          <button
            className={`btn-control ${isPlaying ? 'active' : ''}`}
            onClick={() => setIsPlaying(!isPlaying)}
            style={{ width: '40px', justifyContent: 'center' }}
            title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
          >
            {isPlaying ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <button className="btn-control" onClick={() => handleStep(1)} title="Step +1m (Right Arrow)">
            <ChevronRight size={16} />
          </button>
          <button className="btn-control" onClick={() => handleStep(10)} title="Step +10m (Shift+Right)">
            +10m
          </button>
          <button className="btn-control" onClick={() => { setIsPlaying(false); setRowIndex(0); }} title="Rewind to Start">
            <RotateCcw size={14} />
          </button>
        </div>

        {/* Speed Multiplier Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {[1, 2, 5, 10, 30, 60].map((spd) => (
            <button
              key={spd}
              className={`btn-control ${playSpeed === spd ? 'active' : ''}`}
              style={{ padding: '4px 8px', fontSize: '0.72rem' }}
              onClick={() => setPlaySpeed(spd)}
            >
              {spd}x
            </button>
          ))}
        </div>

        {/* Interactive Scrubber with Anomaly Markers */}
        <div className="scrubber-container">
          <div className="scrubber-track-wrap" onClick={handleScrubberClick}>
            <div className="scrubber-track">
              <div
                className="scrubber-progress"
                style={{ width: `${(rowIndex / (totalRows - 1)) * 100}%` }}
              />
            </div>
            <div
              className="scrubber-thumb"
              style={{ left: `${(rowIndex / (totalRows - 1)) * 100}%` }}
            />

            {/* Render Anomaly Ticks */}
            {Array.isArray(anomalies) && anomalies.map((anom, i) => {
              const leftPct = (Number(anom.row_index) / (totalRows - 1)) * 100;
              return (
                <div
                  key={`anom-${anom.row_index}-${i}`}
                  className="anomaly-marker"
                  style={{ left: `${leftPct}%` }}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleJumpToAnomaly(Number(anom.row_index));
                  }}
                  title={`Jump to ${anom.description || 'anomaly'} (Row #${anom.row_index})`}
                />
              );
            })}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
            <span>T=0 (2019-12-09T00:00)</span>
            <span style={{ color: '#00f0ff' }}>
              Row {rowIndex + 1} / {totalRows} ({((rowIndex / (totalRows - 1)) * 100).toFixed(1)}%)
            </span>
            <span>T+72h (2019-12-11T23:59)</span>
          </div>
        </div>

        {/* Jump-To-Anomaly Event Dropdown */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Jump To:</span>
          <select
            style={{ maxWidth: '240px', fontSize: '0.75rem', padding: '4px 8px' }}
            onChange={(e) => {
              if (e.target.value !== '') {
                handleJumpToAnomaly(parseInt(e.target.value));
              }
            }}
            value=""
          >
            <option value="">Select Anomaly Event...</option>
            {Array.isArray(anomalies) && anomalies.map((a, i) => (
              <option key={`opt-${a.row_index}-${i}`} value={a.row_index}>
                Row {a.row_index}: {String(a.parameter || 'unknown').toUpperCase()} ({String(a.timestamp || '').slice(11, 16) || '??:??'})
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
            />
          )}

          {activeTab === 'predict' && (
            <PredictionTab
              currentRowIndex={rowIndex}
              onJumpToRow={(idx) => setRowIndex(idx)}
            />
          )}

          {activeTab === 'fork' && (
            <ExperimentTab
              currentRowIndex={rowIndex}
              currentState={currentState}
            />
          )}

          {activeTab === 'ml_info' && (
            <ModelInfoTab />
          )}
        </ErrorBoundary>
      </main>

    </div>
  );
}
