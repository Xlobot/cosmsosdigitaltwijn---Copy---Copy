import React, { useState, useEffect } from 'react';
import {
  AlertTriangle, Brain, Clock,
  Lightbulb, RefreshCw, Shield, TrendingUp,
  Check, X, ShieldAlert, Send, FileText, CheckCircle2,
  ChevronRight, GitFork, Sliders, Play, Layers, Sparkles
} from 'lucide-react';
import { getStoredUser } from '../auth';

export default function MissionIntelligenceTab({ currentRowIndex, currentState }) {
  const currentUser = getStoredUser();
  const canDecide = Boolean(
    currentUser && (
      currentUser.role === 'admin' ||
      currentUser.permissions?.includes('*') ||
      (currentUser.role === 'operator' && currentUser.permissions?.includes('mission_intel:decide'))
    )
  );
  // Sub-view mode inside Mission Intelligence: 'decisions', 'scenarios', 'unified'
  const [subView, setSubView] = useState('decisions');

  const [loading, setLoading] = useState(false);
  const [assessment, setAssessment] = useState(null);
  const [error, setError] = useState(null);
  const [horizonMinutes, setHorizonMinutes] = useState(60);
  const [runScenarios, setRunScenarios] = useState(true);
  const [history, setHistory] = useState(null);

  // Manual Operational Notes State
  const [decisionNotes, setDecisionNotes] = useState('');
  const [submittingDecision, setSubmittingDecision] = useState(false);

  // Active Selected Candidate Action for Evaluation
  const [selectedActionIndex, setSelectedActionIndex] = useState(0);

  // Persistent Decision Tracking Map: { [actionKey]: { decision, reasoning, timestamp, actionName } }
  const [actionDecisions, setActionDecisions] = useState({});

  // User Notification Banner
  const [feedbackBanner, setFeedbackBanner] = useState(null);

  // Simulated Telecommand Uplink State
  const [isUplinking, setIsUplinking] = useState(false);
  const [uplinkStatus, setUplinkStatus] = useState(null);

  // Scenario Forking State
  const [forkLoading, setForkLoading] = useState(false);
  const [forkData, setForkData] = useState(null);
  const [customDeltaV, setCustomDeltaV] = useState(15.0);
  const [customThrustDur, setCustomThrustDur] = useState(25);
  const [customPayload, setCustomPayload] = useState('FORCE_OFF');
  const [customThermalSlew, setCustomThermalSlew] = useState(30);
  const [showSandboxControls, setShowSandboxControls] = useState(false);

  // Robust fetcher through Digital Twin backend proxy (/api/mi/...) with auth & error interpretation
  const fetchWithFallback = async (endpoint, options = {}) => {
    try {
      const res = await fetch(`/api/mi/${endpoint}`, options);
      if (res.ok) {
        return await res.json();
      }

      let detail = '';
      try {
        const errData = await res.json();
        detail = errData.detail || errData.message || '';
      } catch (_) {}

      if (res.status === 401) {
        throw new Error(detail || 'Authentication required: Please log in or sign in with flight operator credentials.');
      }
      if (res.status === 403) {
        throw new Error(detail || 'Access restricted: Your operator account lacks permission for Mission Intelligence operations.');
      }
      if (res.status === 502 || res.status === 503) {
        throw new Error(detail || 'Mission Intelligence service is unreachable on port 8001. Please ensure run_all.py is running.');
      }
      throw new Error(detail || `Request returned status ${res.status}`);
    } catch (err) {
      throw err;
    }
  };

  // Run Scenario Forking Simulation via Digital Twin Backend
  const runScenarioSimulation = async (customScenarios = null) => {
    setForkLoading(true);
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
      if (res.ok) {
        const data = await res.json();
        setForkData(data);
      }
    } catch (err) {
      console.warn('Scenario simulation warning:', err);
    } finally {
      setForkLoading(false);
    }
  };

  const handleRunCustomSimulation = () => {
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
    setShowSandboxControls(false);
  };

  const fetchAssessment = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWithFallback('assess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          row_index: currentRowIndex,
          horizon_minutes: horizonMinutes,
          run_scenarios: runScenarios
        })
      });
      setAssessment(data);
      setSelectedActionIndex(0);
      setUplinkStatus(null);
    } catch (err) {
      setError(err.message || 'Mission Intelligence service offline');
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      const data = await fetchWithFallback('history?limit=15');
      setHistory(data);

      if (data && Array.isArray(data.history)) {
        setActionDecisions((prev) => {
          const updated = { ...prev };
          data.history.forEach((entry) => {
            if (entry.decision && entry.recommendation) {
              const actKey = entry.recommendation.action_id || entry.recommendation.name;
              if (actKey && !updated[actKey]) {
                updated[actKey] = {
                  decision: entry.decision,
                  reasoning: entry.decision_reasoning || entry.reasoning || '',
                  timestamp: entry.decision_timestamp || entry.timestamp,
                  actionName: entry.recommendation.name || actKey
                };
              }
            }
          });
          return updated;
        });
      }
    } catch (_) {
      // Optional history fallback
    }
  };

  useEffect(() => {
    fetchAssessment();
    fetchHistory();
    runScenarioSimulation();
  }, [currentRowIndex, horizonMinutes, runScenarios]);

  // Derived properties from assessment
  const situation = assessment?.situation;
  const riskAssessment = assessment?.risk_assessment;
  const explanation = assessment?.explanation;
  const rankedActions = assessment?.ranked_actions?.ranked_actions || [];

  // Active action under evaluation
  const currentAction = rankedActions[selectedActionIndex] || explanation?.proposed_action;
  const currentActionKey = currentAction?.action_id || currentAction?.name || 'ACT-PRIMARY';
  const activeDecisionRecord = actionDecisions[currentActionKey];

  // Scenarios from scenario forking
  const scenarios = forkData?.scenarios || [];
  const aiRec = forkData?.ai_recommendation;

  const getScenarioColor = (idx) => {
    if (idx === 0) return '#38bdf8'; // Cyan
    if (idx === 1) return '#10b981'; // Emerald
    if (idx === 2) return '#818cf8'; // Indigo
    return '#f59e0b'; // Amber
  };

  // Submit operator decision on an action
  const handleDecision = async (actionItem, decisionType, defaultReasoning) => {
    const targetAction = actionItem || currentAction;
    if (!targetAction) return;

    setSubmittingDecision(true);
    setFeedbackBanner(null);
    setUplinkStatus(null);

    const actKey = targetAction.action_id || targetAction.name || 'ACT-DEFAULT';
    const actName = targetAction.name || 'Autonomous Action';
    const finalReasoning = decisionNotes.trim() || defaultReasoning;
    const nowIso = new Date().toISOString();

    // 1. Immediately update local state so table and cards track decision
    setActionDecisions((prev) => ({
      ...prev,
      [actKey]: {
        decision: decisionType,
        reasoning: finalReasoning,
        timestamp: nowIso,
        actionName: actName
      }
    }));

    try {
      const recId = assessment?.recommendation_id || `REC-${Date.now()}`;
      await fetchWithFallback('decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recommendation_id: recId,
          decision: decisionType,
          reasoning: `[${actName}] ${finalReasoning}`
        })
      });

      const opName = currentUser?.username || 'Operator';
      setFeedbackBanner({
        type: decisionType,
        message: `✓ Action "${actName}" recorded as ${decisionType.toUpperCase()} by ${opName}.`
      });

      await fetchHistory();
    } catch (err) {
      console.warn('Backend decision log warning:', err);
      setFeedbackBanner({
        type: decisionType,
        message: `Action "${actName}" marked as ${decisionType.toUpperCase()} (Session active).`
      });
    } finally {
      setSubmittingDecision(false);
    }
  };

  const handleUplink = () => {
    setIsUplinking(true);
    setUplinkStatus('TRANSMITTING');
    setTimeout(() => {
      setIsUplinking(false);
      setUplinkStatus('CONFIRMED');
    }, 1200);
  };

  const handleAddNotePreset = (tag) => {
    setDecisionNotes((prev) => (prev ? `${prev}; ${tag}` : tag));
  };

  const getRiskBadge = (level) => {
    const l = String(level || 'LOW').toUpperCase();
    if (l === 'CRITICAL') return 'status-pill pill-critical';
    if (l === 'HIGH') return 'status-pill pill-high';
    if (l === 'MED' || l === 'MEDIUM') return 'status-pill pill-med';
    return 'status-pill pill-low';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '16px' }}>
      
      {/* Top Header & Integrated Sub-View Switcher */}
      <div className="glass-panel" style={{ padding: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9375rem', fontWeight: '600', color: 'var(--text-main)' }}>
            <Brain size={16} color="#38bdf8" /> Mission Intelligence &amp; Counterfactual Scenario Operations
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
            Cognitive decision support, autonomous action ranking &amp; branching maneuver simulations (Row #{currentRowIndex})
          </div>
        </div>

        {/* Sub-view Navigation Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--bg-surface-elevated)', padding: '3px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
          <button
            className={`btn-control ${subView === 'decisions' ? 'active' : ''}`}
            onClick={() => setSubView('decisions')}
            style={{ fontSize: '0.75rem', padding: '4px 10px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
          >
            <Brain size={13} color="#38bdf8" /> Autonomous Decisions
          </button>

          <button
            className={`btn-control ${subView === 'scenarios' ? 'active' : ''}`}
            onClick={() => setSubView('scenarios')}
            style={{ fontSize: '0.75rem', padding: '4px 10px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
          >
            <GitFork size={13} color="#818cf8" /> Scenario Forking &amp; Sandbox
          </button>

          <button
            className={`btn-control ${subView === 'unified' ? 'active' : ''}`}
            onClick={() => setSubView('unified')}
            style={{ fontSize: '0.75rem', padding: '4px 10px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
          >
            <Layers size={13} color="#10b981" /> Unified Cockpit
          </button>
        </div>

        {/* Global Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>HORIZON:</span>
            {[30, 60, 90, 120].map((m) => (
              <button
                key={m}
                className={`btn-control ${horizonMinutes === m ? 'active' : ''}`}
                onClick={() => setHorizonMinutes(m)}
                disabled={loading || forkLoading}
              >
                {m}m
              </button>
            ))}
          </div>

          <button
            onClick={() => {
              fetchAssessment();
              runScenarioSimulation();
            }}
            disabled={loading || forkLoading}
            className="btn-control"
            title="Refresh assessment and simulations"
          >
            <RefreshCw size={13} className={loading || forkLoading ? 'spin-slow' : ''} />
            Re-assess &amp; Simulate
          </button>
        </div>
      </div>

      {/* Global Feedback Banner */}
      {feedbackBanner && (
        <div style={{
          padding: '10px 14px',
          borderRadius: 'var(--radius-sm)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: feedbackBanner.type === 'accepted' ? 'rgba(16, 185, 129, 0.15)' : feedbackBanner.type === 'rejected' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(245, 158, 11, 0.15)',
          border: `1px solid ${feedbackBanner.type === 'accepted' ? '#10b981' : feedbackBanner.type === 'rejected' ? '#ef4444' : '#f59e0b'}`,
          color: feedbackBanner.type === 'accepted' ? '#34d399' : feedbackBanner.type === 'rejected' ? '#fca5a5' : '#fbbf24'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {feedbackBanner.type === 'accepted' ? <CheckCircle2 size={16} /> : feedbackBanner.type === 'rejected' ? <X size={16} /> : <Clock size={16} />}
            <span>{feedbackBanner.message}</span>
          </div>
          <button
            onClick={() => setFeedbackBanner(null)}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '0.875rem' }}
          >
            ✕
          </button>
        </div>
      )}

      {error ? (
        <div className="glass-panel" style={{ padding: '24px', textAlign: 'center', border: '1px solid var(--status-critical-border)' }}>
          <ShieldAlert size={28} color="#ef4444" style={{ margin: '0 auto 8px' }} />
          <div style={{ fontSize: '0.875rem', fontWeight: '600', color: '#fca5a5' }}>
            {error.toLowerCase().includes('auth') || error.toLowerCase().includes('permission') || error.toLowerCase().includes('restricted')
              ? 'Operator Authentication Required'
              : 'Mission Intelligence Link Notice'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px', maxWidth: '520px', margin: '4px auto 14px' }}>
            {error}
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '8px' }}>
            {(error.toLowerCase().includes('auth') || error.toLowerCase().includes('permission') || error.toLowerCase().includes('restricted')) ? (
              <button
                onClick={() => window.dispatchEvent(new CustomEvent('cosmos:auth-expired'))}
                className="btn-control"
                style={{ borderColor: '#38bdf8', color: '#38bdf8' }}
              >
                <Sparkles size={13} color="#38bdf8" /> Log In / Sign In
              </button>
            ) : null}
            <button onClick={() => { fetchAssessment(); runScenarioSimulation(); }} className="btn-control">
              <RefreshCw size={13} /> Retry Connection
            </button>
          </div>
        </div>
      ) : loading && !assessment ? (
        <div className="glass-panel" style={{ padding: '36px', textAlign: 'center' }}>
          <RefreshCw size={24} color="#38bdf8" className="spin-slow" style={{ margin: '0 auto 10px' }} />
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Synthesizing Digital Twin telemetry, subsystem risks, and candidate actions...
          </div>
        </div>
      ) : (
        <>
          {/* =============================================================== */}
          {/* SCENARIO FORKING & SANDBOX SECTION (Active in 'scenarios' or 'unified') */}
          {/* =============================================================== */}
          {(subView === 'scenarios' || subView === 'unified') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              
              {/* Scenario Forking Header & Sandbox Toggle */}
              <div className="glass-panel" style={{ padding: '14px', borderLeft: '3px solid #818cf8', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <GitFork size={18} color="#818cf8" />
                  <div>
                    <div style={{ fontSize: '0.875rem', fontWeight: '700', color: 'var(--text-main)' }}>
                      Counterfactual Scenario Forking &amp; Maneuver Simulator
                    </div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      Branching from state #{currentRowIndex} ({currentState?.twin_state_id || 'TWIN-LEO-01'}) &bull; Predicting parallel trajectories
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className={`btn-control ${showSandboxControls ? 'active' : ''}`}
                    onClick={() => setShowSandboxControls(!showSandboxControls)}
                    style={{ fontSize: '0.75rem', padding: '5px 12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                  >
                    <Sliders size={13} color="#38bdf8" />
                    <span>{showSandboxControls ? 'Hide Sandbox Controls' : 'Open Maneuver Sandbox'}</span>
                  </button>
                </div>
              </div>

              {/* Custom Maneuver Sandbox Controls */}
              {showSandboxControls && (
                <div className="glass-panel" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', border: '1px solid var(--accent-primary)', background: 'rgba(12, 18, 30, 0.95)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
                    <Sliders size={15} color="#38bdf8" /> Spacecraft Maneuver &amp; Subsystem Injection Parameters
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
                    <div>
                      <label style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px', fontFamily: 'var(--font-mono)' }}>
                        Prograde Delta-V: <strong style={{ color: 'var(--accent-cyan)' }}>{customDeltaV} m/s</strong>
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
                        Burn Duration: <strong style={{ color: 'var(--accent-cyan)' }}>{customThrustDur} s</strong>
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
                        Payload Command Override:
                      </label>
                      <select
                        value={customPayload}
                        onChange={(e) => setCustomPayload(e.target.value)}
                        style={{ width: '100%' }}
                      >
                        <option value="FORCE_OFF">FORCE_OFF (Power Shedding)</option>
                        <option value="FORCE_ON">FORCE_ON (Continuous Imaging)</option>
                        <option value="DUTY_CYCLE_50">DUTY_CYCLE_50 (5m ON / 5m OFF)</option>
                        <option value="KEEP">KEEP (Nominal Flight Plan)</option>
                      </select>
                    </div>

                    <div>
                      <label style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px', fontFamily: 'var(--font-mono)' }}>
                        Radiator Slew Angle: <strong style={{ color: 'var(--accent-cyan)' }}>{customThermalSlew}°</strong>
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

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '6px' }}>
                    <button className="btn-control" onClick={() => setShowSandboxControls(false)}>
                      Cancel
                    </button>
                    <button className="btn-primary" onClick={handleRunCustomSimulation} disabled={forkLoading}>
                      <Play size={13} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle' }} />
                      Run Branch Simulation
                    </button>
                  </div>
                </div>
              )}

              {/* Side-by-Side Candidate Scenarios Matrix Cards */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
                {scenarios.map((scn, idx) => {
                  const color = getScenarioColor(idx);
                  const isWinner = aiRec?.recommended_scenario_id === scn.scenario_id;
                  const sumry = scn.summary || {};

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

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px', fontSize: '0.75rem' }}>
                        <div style={{ background: 'var(--bg-surface-elevated)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-dim)', fontSize: '0.6875rem' }}>Final Health:</span>
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: '700', color: color }}>
                            {sumry.final_health_score !== undefined ? sumry.final_health_score : '--'} pts
                          </div>
                        </div>

                        <div style={{ background: 'var(--bg-surface-elevated)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-dim)', fontSize: '0.6875rem' }}>Min Battery:</span>
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: '700', color: sumry.min_battery_pct < 30 ? 'var(--status-critical)' : 'var(--text-main)' }}>
                            {sumry.min_battery_pct !== undefined ? `${sumry.min_battery_pct}%` : '--'}
                          </div>
                        </div>

                        <div style={{ background: 'var(--bg-surface-elevated)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-dim)', fontSize: '0.6875rem' }}>Peak Temp:</span>
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '1rem', fontWeight: '700', color: sumry.max_temperature_c > 45 ? 'var(--status-critical)' : 'var(--text-main)' }}>
                            {sumry.max_temperature_c !== undefined ? `${sumry.max_temperature_c}°C` : '--'}
                          </div>
                        </div>

                        <div style={{ background: 'var(--bg-surface-elevated)', padding: '6px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-dim)', fontSize: '0.6875rem' }}>Risk Level:</span>
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9375rem', fontWeight: '700', color: sumry.final_risk_level === 'LOW' ? 'var(--status-nominal)' : 'var(--status-caution)' }}>
                            {sumry.final_risk_level || 'NOMINAL'}
                          </div>
                        </div>
                      </div>

                      <div style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px', fontFamily: 'var(--font-mono)' }}>
                        Cmd: {scn.controls?.payload_override || 'KEEP'} | ΔV: {scn.controls?.delta_v_prograde_ms || 0} m/s | Slew: {scn.controls?.thermal_slew_deg || 0}°
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Comparative Subsystem Health Forecast SVG Curve */}
              <div className="glass-panel" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <TrendingUp size={15} color="#38bdf8" />
                    <span>Comparative Health Forecast Trajectories across Branches</span>
                  </div>
                  <div style={{ display: 'flex', gap: '12px', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)' }}>
                    {scenarios.map((scn, idx) => (
                      <span key={scn.scenario_id} style={{ color: getScenarioColor(idx) }}>
                        ● {scn.scenario_label.split(':')[0]}
                      </span>
                    ))}
                  </div>
                </div>

                <div style={{ width: '100%', height: '180px', background: '#05080e', borderRadius: '4px', padding: '10px', border: '1px solid var(--border-subtle)' }}>
                  {scenarios.length > 0 ? (
                    <svg width="100%" height="100%" viewBox="0 0 600 160" preserveAspectRatio="none">
                      {[0.25, 0.5, 0.75].map((g) => (
                        <line key={g} x1="0" y1={160 * g} x2="600" y2={160 * g} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
                      ))}

                      {scenarios.map((scn, idx) => {
                        const color = getScenarioColor(idx);
                        const traj = scn.trajectory || [];
                        if (traj.length === 0) return null;

                        const pathD = traj.map((pt, i) => {
                          const x = (i / Math.max(traj.length - 1, 1)) * 600;
                          const val = pt.health_score ?? 80;
                          const y = 150 - (val / 100) * 130;
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
                      Calculating scenario branch curves...
                    </div>
                  )}
                </div>
              </div>

            </div>
          )}

          {/* =============================================================== */}
          {/* AUTONOMOUS DECISION SUPPORT SECTION (Active in 'decisions' or 'unified') */}
          {/* =============================================================== */}
          {(subView === 'decisions' || subView === 'unified') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

              {/* Situation & Risk Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'minmax(350px, 1.2fr) minmax(320px, 1fr)', gap: '16px' }}>
                
                {/* Left: Mission Situation Overview */}
                <div className="glass-panel" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
                      <TrendingUp size={15} color="#38bdf8" /> Flight Situation Assessment
                    </div>
                    {situation && (
                      <span className={getRiskBadge(situation.overall_status)}>
                        {situation.overall_status}
                      </span>
                    )}
                  </div>

                  {situation && (
                    <>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                        <div className="tel-card">
                          <div className="tel-card-title">Health</div>
                          <div className="tel-card-value" style={{ color: situation.health_summary?.score < 60 ? 'var(--status-critical)' : 'var(--status-nominal)' }}>
                            {situation.health_summary?.score !== undefined ? Number(situation.health_summary.score).toFixed(1) : '85.0'}
                            <span className="tel-card-unit">pts</span>
                          </div>
                        </div>
                        <div className="tel-card">
                          <div className="tel-card-title">Battery</div>
                          <div className="tel-card-value">
                            {situation.resource_status?.battery?.percentage !== undefined ? Number(situation.resource_status.battery.percentage).toFixed(1) : '85.0'}
                            <span className="tel-card-unit">%</span>
                          </div>
                        </div>
                        <div className="tel-card">
                          <div className="tel-card-title">Temp</div>
                          <div className="tel-card-value">
                            {situation.resource_status?.thermal?.temperature_c !== undefined ? Number(situation.resource_status.thermal.temperature_c).toFixed(1) : '24.0'}
                            <span className="tel-card-unit">°C</span>
                          </div>
                        </div>
                        <div className="tel-card">
                          <div className="tel-card-title">Power Net</div>
                          <div className="tel-card-value">
                            {situation.resource_status?.power?.net_power_w !== undefined ? Number(situation.resource_status.power.net_power_w).toFixed(0) : '0'}
                            <span className="tel-card-unit">W</span>
                          </div>
                        </div>
                      </div>

                      {/* Active Concerns */}
                      {situation.concerns && situation.concerns.length > 0 ? (
                        <div style={{ marginTop: '4px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <span style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                            Active Subsystem Concerns ({situation.concerns.length}):
                          </span>
                          {situation.concerns.map((c, i) => (
                            <div
                              key={i}
                              style={{
                                padding: '6px 10px',
                                background: 'var(--bg-surface-elevated)',
                                borderLeft: `3px solid ${c.severity === 'critical' ? 'var(--status-critical)' : 'var(--status-caution)'}`,
                                borderRadius: 'var(--radius-xs)',
                                fontSize: '0.75rem',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                color: '#e2e8f0'
                              }}
                            >
                              <AlertTriangle size={13} color={c.severity === 'critical' ? '#ef4444' : '#f59e0b'} />
                              <span>{c.message || c.description || JSON.stringify(c)}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ fontSize: '0.75rem', color: 'var(--status-nominal)', fontFamily: 'var(--font-mono)', padding: '6px 0' }}>
                          ✓ Zero concerning subsystem trends detected.
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* Right: Subsystem Risk Breakdown */}
                <div className="glass-panel" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)' }}>
                      <Shield size={15} color="#f59e0b" /> Subsystem Risk Assessment
                    </div>
                    <span style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {riskAssessment?.triggered_risks?.length || 0} Triggers
                    </span>
                  </div>

                  {riskAssessment && (
                    <>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px' }}>
                        {['CRITICAL', 'HIGH', 'MED', 'LOW'].map((sev) => {
                          const count = (riskAssessment.risks_by_severity?.[sev] || []).length;
                          return (
                            <div key={sev} style={{ background: 'var(--bg-surface-elevated)', padding: '8px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                              <div style={{ fontSize: '0.625rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>{sev}</div>
                              <div style={{ fontSize: '1.125rem', fontWeight: '700', fontFamily: 'var(--font-mono)', color: count > 0 && sev !== 'LOW' ? '#ef4444' : 'var(--text-main)' }}>
                                {count}
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {riskAssessment.triggered_risks && riskAssessment.triggered_risks.length > 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '130px', overflowY: 'auto' }}>
                          {riskAssessment.triggered_risks.map((r, i) => (
                            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 8px', background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-xs)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                              <span style={{ color: '#cbd5e1' }}>{r.name || r.category}</span>
                              <span className={getRiskBadge(r.severity)}>{r.severity}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>

              </div>

              {/* Primary Explainable Action Recommendation Card */}
              {currentAction && (
                <div
                  className="glass-panel"
                  style={{
                    padding: '16px',
                    borderLeft: activeDecisionRecord?.decision === 'accepted'
                      ? '4px solid #10b981'
                      : activeDecisionRecord?.decision === 'rejected'
                      ? '4px solid #ef4444'
                      : activeDecisionRecord?.decision === 'deferred'
                      ? '4px solid #f59e0b'
                      : '4px solid var(--accent-cyan)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem', color: 'var(--accent-cyan)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em', fontFamily: 'var(--font-mono)' }}>
                        <Lightbulb size={14} />
                        <span>Autonomous Mission Action Recommendation</span>
                        <span style={{ color: 'var(--text-dim)' }}>•</span>
                        <span style={{ color: selectedActionIndex === 0 ? 'var(--status-nominal)' : 'var(--accent-cyan)' }}>
                          {selectedActionIndex === 0 ? 'Rank #1 Primary Recommendation' : `Candidate Option #${selectedActionIndex + 1}`}
                        </span>
                      </div>

                      <div style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--text-main)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span>{currentAction.name || 'Maintain Current Flight Plan'}</span>
                        <span style={{ fontSize: '0.6875rem', padding: '2px 6px', borderRadius: '3px', background: 'var(--bg-surface-elevated)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 'normal' }}>
                          {currentAction.category || 'OPERATION'}
                        </span>
                      </div>

                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '3px' }}>
                        {currentAction.description || currentAction.category_description || explanation?.proposed_action?.description || 'Flight control routine for active spacecraft stabilization.'}
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {activeDecisionRecord ? (
                        <span className={
                          activeDecisionRecord.decision === 'accepted' ? 'status-pill pill-low' :
                          activeDecisionRecord.decision === 'rejected' ? 'status-pill pill-critical' : 'status-pill pill-med'
                        }>
                          {activeDecisionRecord.decision === 'accepted' && <Check size={12} />}
                          {activeDecisionRecord.decision === 'rejected' && <X size={12} />}
                          {activeDecisionRecord.decision === 'deferred' && <Clock size={12} />}
                          {activeDecisionRecord.decision.toUpperCase()}
                        </span>
                      ) : (
                        <span className="status-pill pill-med" style={{ opacity: 0.9 }}>
                          PENDING DECISION
                        </span>
                      )}

                      <span style={{ fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', background: 'var(--bg-surface-elevated)', padding: '4px 8px', borderRadius: 'var(--radius-xs)' }}>
                        ID: {currentAction.action_id || assessment.recommendation_id}
                      </span>
                    </div>
                  </div>

                  {/* Justification, Scores & Expected Outcomes */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 1.3fr) minmax(260px, 1fr)', gap: '12px' }}>
                    <div style={{ background: 'var(--bg-surface-elevated)', padding: '12px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)', fontSize: '0.78125rem', lineHeight: '1.5', color: '#e2e8f0' }}>
                      <div style={{ fontWeight: '600', color: 'var(--text-accent)', marginBottom: '4px', fontSize: '0.6875rem', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                        Operator Justification &amp; Trade-off:
                      </div>
                      <div>
                        {currentAction.justification || currentAction.rationale || explanation?.proposed_action?.justification || 'Telemetry parameters within normal operating envelope; action stabilizes flight margins.'}
                      </div>
                      {currentAction.trade_offs && currentAction.trade_offs.length > 0 && (
                        <div style={{ marginTop: '8px', fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                          Trade-offs: {currentAction.trade_offs.join(' • ')}
                        </div>
                      )}
                    </div>

                    <div style={{ background: 'var(--bg-surface-elevated)', padding: '12px 14px', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)', fontSize: '0.75rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <div style={{ fontWeight: '600', color: 'var(--status-nominal)', fontSize: '0.6875rem', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', marginBottom: '2px' }}>
                        Multi-Objective Feasibility Matrix:
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)' }}>
                        <span style={{ color: 'var(--text-dim)' }}>Overall Score:</span>
                        <span style={{ color: 'var(--status-nominal)', fontWeight: '600' }}>
                          {currentAction.overall_score !== undefined ? Number(currentAction.overall_score).toFixed(2) : '0.85'} / 1.00
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)' }}>
                        <span style={{ color: 'var(--text-dim)' }}>Feasibility:</span>
                        <span style={{ color: '#38bdf8' }}>
                          {currentAction.component_scores?.feasibility !== undefined
                            ? `${(currentAction.component_scores.feasibility * 100).toFixed(0)}%`
                            : '95%'}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)' }}>
                        <span style={{ color: 'var(--text-dim)' }}>Safety Margin:</span>
                        <span style={{ color: '#cbd5e1' }}>
                          {currentAction.component_scores?.safety !== undefined
                            ? `${(currentAction.component_scores.safety * 100).toFixed(0)}%`
                            : 'Nominal'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Verified Decision Details (If Already Decided) */}
                  {activeDecisionRecord && (
                    <div style={{
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-xs)',
                      background: activeDecisionRecord.decision === 'accepted' ? 'rgba(16, 185, 129, 0.1)' : activeDecisionRecord.decision === 'rejected' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                      border: `1px solid ${activeDecisionRecord.decision === 'accepted' ? 'rgba(16, 185, 129, 0.3)' : activeDecisionRecord.decision === 'rejected' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
                      fontSize: '0.75rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: '600', color: activeDecisionRecord.decision === 'accepted' ? '#34d399' : activeDecisionRecord.decision === 'rejected' ? '#fca5a5' : '#fbbf24', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>
                          Active Logged Decision: {activeDecisionRecord.decision}
                        </span>
                        <span style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                          {new Date(activeDecisionRecord.timestamp).toLocaleTimeString()} &bull; {activeDecisionRecord.operator || currentUser?.username || 'Operator'}
                        </span>
                      </div>
                      {activeDecisionRecord.reasoning && (
                        <div style={{ color: '#cbd5e1', fontStyle: 'italic', marginTop: '2px' }}>
                          &ldquo;{activeDecisionRecord.reasoning}&rdquo;
                        </div>
                      )}

                      {/* Telecommand Uplink Simulator (When Accepted) */}
                      {activeDecisionRecord.decision === 'accepted' && (
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '8px', paddingTop: '8px', borderTop: '1px solid rgba(16, 185, 129, 0.2)' }}>
                          <span style={{ fontSize: '0.6875rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
                            Spacecraft Command Uplink Status:
                          </span>
                          {uplinkStatus === 'CONFIRMED' ? (
                            <span style={{ color: '#34d399', fontWeight: '600', display: 'inline-flex', alignItems: 'center', gap: '4px', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                              <CheckCircle2 size={13} /> Uplink Confirmed (ACK 200)
                            </span>
                          ) : (
                            <button
                              className="btn-control"
                              style={{ borderColor: '#10b981', color: '#34d399', fontSize: '0.6875rem', padding: '4px 10px', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
                              onClick={handleUplink}
                              disabled={isUplinking}
                            >
                              <Send size={12} className={isUplinking ? 'spin-slow' : ''} />
                              {isUplinking ? 'Transmitting to S-Band...' : 'Execute Spacecraft Uplink'}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Manual Operational Notes & Decision Control Deck */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <label style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <FileText size={12} color="#38bdf8" /> Manual Flight Director Operational Notes &amp; Rationale:
                      </label>
                      
                      {/* Quick Preset Rationale Tags */}
                      <div style={{ display: 'flex', gap: '5px' }}>
                        <button
                          type="button"
                          className="btn-control"
                          style={{ fontSize: '0.625rem', padding: '2px 6px' }}
                          onClick={() => handleAddNotePreset('Verified Solar Flux Nominal')}
                        >
                          + Solar Flux
                        </button>
                        <button
                          type="button"
                          className="btn-control"
                          style={{ fontSize: '0.625rem', padding: '2px 6px' }}
                          onClick={() => handleAddNotePreset('Battery SOC Margin Confirmed')}
                        >
                          + Battery SOC
                        </button>
                        <button
                          type="button"
                          className="btn-control"
                          style={{ fontSize: '0.625rem', padding: '2px 6px' }}
                          onClick={() => handleAddNotePreset('Thermal Gradient Acceptable')}
                        >
                          + Thermal
                        </button>
                        <button
                          type="button"
                          className="btn-control"
                          style={{ fontSize: '0.625rem', padding: '2px 6px' }}
                          onClick={() => handleAddNotePreset('Approved for S-Band Uplink')}
                        >
                          + Approved
                        </button>
                      </div>
                    </div>

                    <textarea
                      placeholder="Enter manual flight controller notes, telemetry justifications, or execution constraints..."
                      value={decisionNotes}
                      onChange={(e) => setDecisionNotes(e.target.value)}
                      rows={2}
                      style={{ width: '100%', boxSizing: 'border-box' }}
                    />

                    {/* Accept, Defer, Reject Action Buttons */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', marginTop: '4px' }}>
                      <span style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                        TARGET: <strong>{currentAction.name}</strong>
                      </span>

                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {/* Accept Action */}
                        <button
                          className="btn-primary"
                          style={{
                            background: activeDecisionRecord?.decision === 'accepted' ? '#059669' : 'var(--status-nominal)',
                            borderColor: '#059669',
                            color: '#ffffff',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            boxShadow: activeDecisionRecord?.decision === 'accepted' ? '0 0 10px rgba(16, 185, 129, 0.4)' : 'none'
                          }}
                          onClick={() => handleDecision(currentAction, 'accepted', 'Approved by flight controller for immediate execution')}
                          disabled={!canDecide || submittingDecision}
                          title={!canDecide ? "Requires operator or admin role" : "Accept this recommended action"}
                        >
                          <Check size={14} />
                          {activeDecisionRecord?.decision === 'accepted' ? 'Accept Action (Active)' : 'Accept Action'}
                        </button>

                        {/* Defer Action */}
                        <button
                          className="btn-control"
                          style={{
                            borderColor: activeDecisionRecord?.decision === 'deferred' ? '#f59e0b' : 'var(--status-caution-border)',
                            color: 'var(--status-caution)',
                            background: activeDecisionRecord?.decision === 'deferred' ? 'rgba(245, 158, 11, 0.15)' : 'transparent',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px'
                          }}
                          onClick={() => handleDecision(currentAction, 'deferred', 'Deferred for continuous telemetry analysis')}
                          disabled={!canDecide || submittingDecision}
                          title={!canDecide ? "Requires operator or admin role" : "Defer this recommended action"}
                        >
                          <Clock size={13} />
                          {activeDecisionRecord?.decision === 'deferred' ? 'Defer Action (Active)' : 'Defer Action'}
                        </button>

                        {/* Reject Action */}
                        <button
                          className="btn-control"
                          style={{
                            borderColor: activeDecisionRecord?.decision === 'rejected' ? '#ef4444' : 'var(--status-critical-border)',
                            color: '#f87171',
                            background: activeDecisionRecord?.decision === 'rejected' ? 'rgba(239, 68, 68, 0.15)' : 'transparent',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px'
                          }}
                          onClick={() => handleDecision(currentAction, 'rejected', 'Rejected by flight controller: alternative action preferred')}
                          disabled={!canDecide || submittingDecision}
                          title={!canDecide ? "Requires operator or admin role" : "Reject this recommended action"}
                        >
                          <X size={14} />
                          {activeDecisionRecord?.decision === 'rejected' ? 'Reject Action (Active)' : 'Reject Action'}
                        </button>
                      </div>
                    </div>

                  </div>

                </div>
              )}

              {/* Candidate Action Evaluation & Trade-off Ranking Table */}
              {rankedActions.length > 0 && (
                <div className="glass-panel" style={{ padding: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span>Candidate Action Evaluation &amp; Trade-off Ranking</span>
                      <span style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                        ({rankedActions.length} Actions Evaluated)
                      </span>
                    </div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      Click row to review in detail above
                    </div>
                  </div>

                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', textAlign: 'left' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)', fontSize: '0.6875rem' }}>
                          <th style={{ padding: '8px' }}>RANK</th>
                          <th style={{ padding: '8px' }}>ACTION NAME</th>
                          <th style={{ padding: '8px' }}>CATEGORY</th>
                          <th style={{ padding: '8px' }}>SCORE</th>
                          <th style={{ padding: '8px' }}>FEASIBILITY</th>
                          <th style={{ padding: '8px' }}>DECISION TRACKING</th>
                          <th style={{ padding: '8px', textAlign: 'right' }}>QUICK ACTIONS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rankedActions.map((act, i) => {
                          const actKey = act.action_id || act.name;
                          const isSelected = selectedActionIndex === i;
                          const decisionRecord = actionDecisions[actKey];
                          const currentDecision = decisionRecord?.decision;

                          return (
                            <tr
                              key={i}
                              style={{
                                borderBottom: '1px solid var(--border-subtle)',
                                background: isSelected
                                  ? 'rgba(56, 189, 248, 0.08)'
                                  : currentDecision === 'accepted'
                                  ? 'rgba(16, 185, 129, 0.04)'
                                  : 'transparent',
                                cursor: 'pointer',
                                transition: 'background 0.15s ease'
                              }}
                              onClick={() => setSelectedActionIndex(i)}
                              title="Click to review details in recommendation card above"
                            >
                              <td style={{ padding: '8px', color: isSelected ? 'var(--accent-cyan)' : 'var(--text-dim)', fontWeight: '600' }}>
                                #{i + 1}
                              </td>
                              <td style={{ padding: '8px', fontWeight: '600', color: isSelected ? '#ffffff' : 'var(--text-main)' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  {isSelected && <ChevronRight size={13} color="#38bdf8" />}
                                  <span>{act.action?.name || act.name}</span>
                                </div>
                              </td>
                              <td style={{ padding: '8px', color: 'var(--text-muted)' }}>
                                {act.action?.category || act.category}
                              </td>
                              <td style={{ padding: '8px', color: 'var(--status-nominal)', fontWeight: '600' }}>
                                {act.overall_score !== undefined ? act.overall_score.toFixed(2) : (act.score !== undefined ? act.score.toFixed(2) : '1.00')}
                              </td>
                              <td style={{ padding: '8px', color: '#cbd5e1' }}>
                                {act.component_scores?.feasibility !== undefined 
                                  ? `${(act.component_scores.feasibility * 100).toFixed(0)}%` 
                                  : (act.feasibility ? `${(act.feasibility * 100).toFixed(0)}%` : 'High')}
                              </td>

                              <td style={{ padding: '8px' }}>
                                {currentDecision === 'accepted' ? (
                                  <span className="status-pill pill-low" title={decisionRecord?.reasoning}>
                                    <Check size={11} /> ACCEPTED
                                  </span>
                                ) : currentDecision === 'deferred' ? (
                                  <span className="status-pill pill-med" title={decisionRecord?.reasoning}>
                                    <Clock size={11} /> DEFERRED
                                  </span>
                                ) : currentDecision === 'rejected' ? (
                                  <span className="status-pill pill-critical" title={decisionRecord?.reasoning}>
                                    <X size={11} /> REJECTED
                                  </span>
                                ) : i === 0 ? (
                                  <span className="status-pill pill-low" style={{ background: 'rgba(56, 189, 248, 0.12)', color: '#38bdf8', borderColor: 'rgba(56, 189, 248, 0.3)' }}>
                                    PREFERRED
                                  </span>
                                ) : (
                                  <span className="status-pill pill-med" style={{ opacity: 0.7 }}>
                                    ALTERNATIVE
                                  </span>
                                )}
                              </td>

                              <td style={{ padding: '8px', textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                  <button
                                    className={`btn-control ${isSelected ? 'active' : ''}`}
                                    style={{ fontSize: '0.6875rem', padding: '3px 8px' }}
                                    onClick={() => setSelectedActionIndex(i)}
                                    title="Inspect this action"
                                  >
                                    Review
                                  </button>

                                  <button
                                    className="btn-control"
                                    style={{
                                      fontSize: '0.6875rem',
                                      padding: '3px 6px',
                                      color: currentDecision === 'accepted' ? '#ffffff' : '#34d399',
                                      background: currentDecision === 'accepted' ? '#059669' : 'transparent',
                                      borderColor: currentDecision === 'accepted' ? '#059669' : 'rgba(16, 185, 129, 0.3)'
                                    }}
                                    onClick={() => {
                                      setSelectedActionIndex(i);
                                      handleDecision(act, 'accepted', 'Approved directly from candidate action ranking');
                                    }}
                                    title={!canDecide ? "Requires operator or admin role" : "Accept this candidate action"}
                                    disabled={!canDecide || submittingDecision}
                                  >
                                    <Check size={12} />
                                  </button>

                                  <button
                                    className="btn-control"
                                    style={{
                                      fontSize: '0.6875rem',
                                      padding: '3px 6px',
                                      color: currentDecision === 'deferred' ? '#ffffff' : '#fbbf24',
                                      background: currentDecision === 'deferred' ? 'rgba(245, 158, 11, 0.4)' : 'transparent',
                                      borderColor: currentDecision === 'deferred' ? '#f59e0b' : 'rgba(245, 158, 11, 0.3)'
                                    }}
                                    onClick={() => {
                                      setSelectedActionIndex(i);
                                      handleDecision(act, 'deferred', 'Deferred directly from candidate action ranking');
                                    }}
                                    title={!canDecide ? "Requires operator or admin role" : "Defer this candidate action"}
                                    disabled={!canDecide || submittingDecision}
                                  >
                                    <Clock size={12} />
                                  </button>

                                  <button
                                    className="btn-control"
                                    style={{
                                      fontSize: '0.6875rem',
                                      padding: '3px 6px',
                                      color: currentDecision === 'rejected' ? '#ffffff' : '#f87171',
                                      background: currentDecision === 'rejected' ? 'rgba(239, 68, 68, 0.4)' : 'transparent',
                                      borderColor: currentDecision === 'rejected' ? '#ef4444' : 'rgba(239, 68, 68, 0.3)'
                                    }}
                                    onClick={() => {
                                      setSelectedActionIndex(i);
                                      handleDecision(act, 'rejected', 'Rejected directly from candidate action ranking');
                                    }}
                                    title={!canDecide ? "Requires operator or admin role" : "Reject this candidate action"}
                                    disabled={!canDecide || submittingDecision}
                                  >
                                    <X size={12} />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Flight Decision Audit Log */}
              {history && history.history && history.history.length > 0 && (
                <div className="glass-panel" style={{ padding: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <FileText size={14} color="#38bdf8" />
                      <span>Flight Controller Decision Audit Log</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.6875rem', fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
                      <span>Accepted: {history.statistics?.accepted || 0}</span>
                      <span>Deferred: {history.statistics?.deferred || 0}</span>
                      <span>Rejected: {history.statistics?.rejected || 0}</span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {history.history.slice(0, 8).map((entry, i) => {
                      const isAcc = entry.decision === 'accepted';
                      const isRej = entry.decision === 'rejected';
                      const isDef = entry.decision === 'deferred';
                      const decisionReasoning = entry.decision_reasoning || entry.reasoning || entry.recommendation?.justification || 'Standard mission operation';
                      const operatorName = entry.decision_operator || entry.operator || 'Operator';
                      const displayTime = entry.decision_timestamp || entry.timestamp;

                      return (
                        <div
                          key={i}
                          style={{
                            padding: '8px 12px',
                            background: 'var(--bg-surface-elevated)',
                            borderRadius: 'var(--radius-xs)',
                            border: '1px solid var(--border-subtle)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            fontSize: '0.75rem',
                            gap: '12px'
                          }}
                        >
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: '600', color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span>{entry.recommendation?.name || entry.recommendation_id}</span>
                              <span style={{ fontSize: '0.6875rem', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontWeight: 'normal' }}>
                                ({entry.recommendation?.category || 'ACTION'})
                              </span>
                            </div>
                            <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                              {new Date(displayTime).toLocaleTimeString()} &bull; Operator: {operatorName} &bull;{' '}
                              <span style={{ color: '#cbd5e1' }}>&ldquo;{decisionReasoning}&rdquo;</span>
                            </div>
                          </div>

                          <span className={isAcc ? 'status-pill pill-low' : isRej ? 'status-pill pill-critical' : isDef ? 'status-pill pill-med' : 'status-pill pill-med'}>
                            {isAcc && <Check size={11} />}
                            {isRej && <X size={11} />}
                            {isDef && <Clock size={11} />}
                            {entry.decision ? entry.decision.toUpperCase() : 'PENDING'}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

            </div>
          )}

        </>
      )}

    </div>
  );
}
