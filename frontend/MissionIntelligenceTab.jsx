import React, { useState, useEffect } from 'react';
import {
  AlertTriangle, Brain, CheckCircle2, Clock, FileText,
  Lightbulb, Play, RefreshCw, Shield, TrendingUp, XCircle
} from 'lucide-react';

export default function MissionIntelligenceTab({ currentRowIndex }) {
  const [loading, setLoading] = useState(false);
  const [assessment, setAssessment] = useState(null);
  const [error, setError] = useState(null);
  const [horizonMinutes, setHorizonMinutes] = useState(60);
  const [runScenarios, setRunScenarios] = useState(true);
  const [history, setHistory] = useState(null);

  const fetchAssessment = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://127.0.0.1:8001/api/assess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          row_index: currentRowIndex,
          horizon_minutes: horizonMinutes,
          run_scenarios: runScenarios
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Assessment failed');
      setAssessment(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8001/api/history?limit=5');
      const data = await response.json();
      setHistory(data);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  };

  const submitDecision = async (recommendationId, decision, reasoning) => {
    try {
      const response = await fetch('http://127.0.0.1:8001/api/decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recommendation_id: recommendationId,
          decision,
          reasoning,
          operator: 'operator'
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Decision failed');
      // Refresh assessment and history
      fetchAssessment();
      fetchHistory();
    } catch (err) {
      alert(`Failed to submit decision: ${err.message}`);
    }
  };

  useEffect(() => {
    fetchAssessment();
    fetchHistory();
  }, [currentRowIndex]);

  const getRiskColor = (level) => {
    switch (level?.toUpperCase()) {
      case 'CRITICAL': return '#ef4444';
      case 'HIGH': return '#f97316';
      case 'MEDIUM': case 'MED': return '#f59e0b';
      case 'LOW': return '#10b981';
      default: return '#6b7280';
    }
  };

  const getHealthColor = (score) => {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#f59e0b';
    if (score >= 40) return '#f97316';
    return '#ef4444';
  };

  if (loading && !assessment) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <RefreshCw size={32} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
        <p style={{ marginTop: '16px', color: '#9ca3af' }}>Loading Mission Intelligence...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '40px', textAlign: 'center' }}>
        <XCircle size={32} style={{ color: '#ef4444' }} />
        <p style={{ marginTop: '16px', color: '#ef4444' }}>{error}</p>
        <button
          onClick={fetchAssessment}
          style={{
            marginTop: '16px',
            padding: '8px 16px',
            background: '#040711',
            color: '#00f0ff',
            border: '1px solid #00f0ff',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  const situation = assessment?.situation;
  const riskAssessment = assessment?.risk_assessment;
  const explanation = assessment?.explanation;
  const rankedActions = assessment?.ranked_actions;

  return (
    <div style={{ padding: '24px', color: '#e5e7eb' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '24px',
        paddingBottom: '16px',
        borderBottom: '1px solid rgba(255,255,255,0.1)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Brain size={28} style={{ color: '#00f0ff' }} />
          <div>
            <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 'bold' }}>
              Mission Intelligence
            </h2>
            <p style={{ margin: 0, fontSize: '0.85rem', color: '#9ca3af' }}>
              Cognitive Decision Support System
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <label style={{ fontSize: '0.85rem', color: '#9ca3af' }}>
            Horizon: {horizonMinutes}min
          </label>
          <input
            type="range"
            min="30"
            max="120"
            step="30"
            value={horizonMinutes}
            onChange={(e) => setHorizonMinutes(parseInt(e.target.value))}
            style={{ width: '100px' }}
          />
          <label style={{ fontSize: '0.85rem', color: '#9ca3af', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <input
              type="checkbox"
              checked={runScenarios}
              onChange={(e) => setRunScenarios(e.target.checked)}
            />
            Run Scenarios
          </label>
          <button
            onClick={fetchAssessment}
            disabled={loading}
            style={{
              padding: '8px 16px',
              background: loading ? '#1f2937' : '#040711',
              color: '#00f0ff',
              border: '1px solid #00f0ff',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Mission Situation */}
      {situation && (
        <div style={{
          background: 'rgba(15, 23, 42, 0.8)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '20px'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TrendingUp size={20} style={{ color: '#00f0ff' }} />
            Mission Situation
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '4px' }}>Overall Status</div>
              <div style={{
                fontSize: '1rem',
                fontWeight: 'bold',
                color: getRiskColor(situation.overall_status)
              }}>
                {situation.overall_status}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '4px' }}>Health Score</div>
              <div style={{
                fontSize: '1rem',
                fontWeight: 'bold',
                color: getHealthColor(situation.health_summary?.score)
              }}>
                {situation.health_summary?.score?.toFixed(1)}%
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '4px' }}>Battery</div>
              <div style={{ fontSize: '1rem', fontWeight: 'bold' }}>
                {situation.resource_status?.battery?.percentage?.toFixed(1)}%
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '4px' }}>Temperature</div>
              <div style={{ fontSize: '1rem', fontWeight: 'bold' }}>
                {situation.resource_status?.thermal?.temperature_c?.toFixed(1)}°C
              </div>
            </div>
          </div>
          {situation.concerns && situation.concerns.length > 0 && (
            <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
              <div style={{ fontSize: '0.85rem', color: '#9ca3af', marginBottom: '8px' }}>Concerns:</div>
              {situation.concerns.map((concern, i) => (
                <div key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '0.85rem',
                  marginBottom: '4px',
                  color: concern.severity === 'critical' ? '#ef4444' : '#f59e0b'
                }}>
                  <AlertTriangle size={14} />
                  {concern.message}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Risk Assessment */}
      {riskAssessment && (
        <div style={{
          background: 'rgba(15, 23, 42, 0.8)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '20px'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Shield size={20} style={{ color: '#f59e0b' }} />
            Risk Assessment
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', marginBottom: '16px' }}>
            {Object.entries(riskAssessment.risks_by_severity || {}).map(([severity, risks]) => (
              risks.length > 0 && (
                <div key={severity} style={{
                  background: 'rgba(255,255,255,0.05)',
                  padding: '12px',
                  borderRadius: '4px',
                  borderLeft: `3px solid ${getRiskColor(severity)}`
                }}>
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '4px' }}>
                    {severity}
                  </div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>
                    {risks.length}
                  </div>
                </div>
              )
            ))}
          </div>
          {riskAssessment.triggered_risks && riskAssessment.triggered_risks.length > 0 && (
            <div style={{ maxHeight: '150px', overflowY: 'auto' }}>
              {riskAssessment.triggered_risks.slice(0, 5).map((risk, i) => (
                <div key={i} style={{
                  padding: '8px',
                  background: 'rgba(255,255,255,0.03)',
                  marginBottom: '4px',
                  borderRadius: '4px',
                  fontSize: '0.85rem',
                  display: 'flex',
                  justifyContent: 'space-between'
                }}>
                  <span>{risk.name}</span>
                  <span style={{ color: getRiskColor(risk.severity) }}>{risk.severity}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Recommendation */}
      {explanation && (
        <div style={{
          background: 'rgba(15, 23, 42, 0.8)',
          border: '2px solid #00f0ff',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '20px'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Lightbulb size={20} style={{ color: '#00f0ff' }} />
            Recommended Action
          </h3>
          <div style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '1.25rem', fontWeight: 'bold', marginBottom: '8px' }}>
              {explanation.proposed_action?.name}
            </div>
            <div style={{ fontSize: '0.9rem', color: '#9ca3af', marginBottom: '12px' }}>
              {explanation.proposed_action?.description}
            </div>
            <div style={{ fontSize: '0.85rem', color: '#d1d5db', marginBottom: '8px' }}>
              <strong>Justification:</strong> {explanation.proposed_action?.justification}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              onClick={() => submitDecision(
                assessment.recommendation_id,
                'accepted',
                'Accepted based on MI recommendation'
              )}
              style={{
                padding: '8px 16px',
                background: '#10b981',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <CheckCircle2 size={16} />
              Accept
            </button>
            <button
              onClick={() => submitDecision(
                assessment.recommendation_id,
                'rejected',
                'Rejected by operator'
              )}
              style={{
                padding: '8px 16px',
                background: '#ef4444',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <XCircle size={16} />
              Reject
            </button>
            <button
              onClick={() => submitDecision(
                assessment.recommendation_id,
                'deferred',
                'Deferred for further review'
              )}
              style={{
                padding: '8px 16px',
                background: '#f59e0b',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <Clock size={16} />
              Defer
            </button>
          </div>
        </div>
      )}

      {/* Decision History */}
      {history && history.history && history.history.length > 0 && (
        <div style={{
          background: 'rgba(15, 23, 42, 0.8)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: '8px',
          padding: '20px'
        }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={20} style={{ color: '#9ca3af' }} />
            Recent Decisions
          </h3>
          <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
            {history.history.map((entry, i) => (
              <div key={i} style={{
                padding: '12px',
                background: 'rgba(255,255,255,0.03)',
                marginBottom: '8px',
                borderRadius: '4px',
                fontSize: '0.85rem'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 'bold' }}>
                    {entry.recommendation?.name}
                  </span>
                  <span style={{
                    color: entry.decision === 'accepted' ? '#10b981' :
                           entry.decision === 'rejected' ? '#ef4444' : '#f59e0b'
                  }}>
                    {entry.decision?.toUpperCase()}
                  </span>
                </div>
                <div style={{ color: '#9ca3af', fontSize: '0.75rem' }}>
                  {new Date(entry.timestamp).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
