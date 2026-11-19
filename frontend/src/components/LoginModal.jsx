import React, { useState, useEffect } from 'react';
import {
  Lock, User, Key, AlertCircle, X, ShieldCheck,
  UserPlus, Users, Trash2, Check, ShieldAlert, Sparkles, CheckSquare, Square
} from 'lucide-react';
import { login, getStoredUser } from '../auth';

const AVAILABLE_PERMISSIONS = [
  { id: 'telemetry:read', label: 'Telemetry Stream & Replay', desc: 'Read live telemetry stream and scrub historical mission timeline' },
  { id: 'predict:run', label: 'Propagation & Forecasting', desc: 'Execute forward orbital predictions and multi-output ML degradation models' },
  { id: 'scenarios:fork', label: 'Scenario Branching & Sandbox', desc: 'Fork counterfactual maneuver branches and run sandbox simulations' },
  { id: 'anomalies:inject', label: 'Fault & Anomaly Injection', desc: 'Inject synthetic telemetry faults into the active generator stream' },
  { id: 'mission_intel:assess', label: 'Mission Intelligence Assessment', desc: 'Synthesize cognitive situation assessments and autonomous action rankings' },
  { id: 'mission_intel:decide', label: 'Decision Telecommand Uplink', desc: 'Authorize or reject critical recommendations for telecommand uplink' }
];

export default function LoginModal({ isOpen, onClose, onLoginSuccess, initialTab = 'login' }) {
  const [activeTab, setActiveTab] = useState(initialTab); // 'login' or 'new_user'

  // Login form state
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  // New user form state (Admin only)
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('operator');
  const [newPermissions, setNewPermissions] = useState([
    'telemetry:read',
    'predict:run',
    'scenarios:fork',
    'mission_intel:assess'
  ]);
  const [newLoading, setNewLoading] = useState(false);
  const [newError, setNewError] = useState('');
  const [newSuccess, setNewSuccess] = useState('');

  // Users registry state
  const [usersList, setUsersList] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);

  const currentUser = getStoredUser();
  const isAdmin = currentUser && currentUser.role === 'admin';

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab || 'login');
      setLoginError('');
      setNewError('');
      setNewSuccess('');
      if (isAdmin) {
        fetchUsers();
      }
    }
  }, [isOpen, initialTab]);

  const fetchUsers = async () => {
    setLoadingUsers(true);
    try {
      const res = await fetch('/api/auth/users');
      if (res.ok) {
        const data = await res.json();
        setUsersList(data.users || []);
      }
    } catch (err) {
      console.warn('Failed to fetch users list:', err);
    } finally {
      setLoadingUsers(false);
    }
  };

  if (!isOpen) return null;

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setLoginError('');
    setLoginLoading(true);

    try {
      const data = await login(loginUsername, loginPassword);
      setLoginLoading(false);
      if (onLoginSuccess) onLoginSuccess(data.user);
      onClose();
    } catch (err) {
      setLoginLoading(false);
      setLoginError(err.message || 'Authentication failed. Please verify credentials.');
    }
  };

  const handleCreateUserSubmit = async (e) => {
    e.preventDefault();
    setNewError('');
    setNewSuccess('');
    setNewLoading(true);

    try {
      const res = await fetch('/api/auth/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: newUsername.trim(),
          password: newPassword,
          role: newRole,
          permissions: newRole === 'admin' ? ['*'] : newPermissions
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to create user account.');
      }

      setNewSuccess(`Operator '${data.user.username}' successfully provisioned with ${newRole} privileges!`);
      setNewUsername('');
      setNewPassword('');
      setNewPermissions(['telemetry:read', 'predict:run', 'scenarios:fork', 'mission_intel:assess']);
      fetchUsers();
    } catch (err) {
      setNewError(err.message || 'Could not provision new user.');
    } finally {
      setNewLoading(false);
    }
  };

  const handleDeleteUser = async (username) => {
    if (!window.confirm(`Are you sure you want to revoke access and delete user '${username}'?`)) return;
    try {
      const res = await fetch(`/api/auth/users/${encodeURIComponent(username)}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        fetchUsers();
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to delete user.');
      }
    } catch (err) {
      alert(`Error deleting user: ${err.message}`);
    }
  };

  const togglePermission = (permId) => {
    setNewPermissions((prev) =>
      prev.includes(permId) ? prev.filter((p) => p !== permId) : [...prev, permId]
    );
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 9999,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'rgba(2, 6, 23, 0.88)',
      backdropFilter: 'blur(10px)',
      padding: '16px'
    }}>
      <div style={{
        width: '100%',
        maxWidth: activeTab === 'new_user' && isAdmin ? '680px' : '480px',
        maxHeight: '90vh',
        backgroundColor: '#0b1329',
        border: '1px solid rgba(56, 189, 248, 0.35)',
        borderRadius: '10px',
        boxShadow: '0 25px 50px rgba(0, 0, 0, 0.75), 0 0 35px rgba(56, 189, 248, 0.2)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        color: '#f8fafc',
        fontFamily: 'var(--font-sans, system-ui, sans-serif)',
        transition: 'max-width 0.2s ease'
      }}>

        {/* Top Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 20px',
          borderBottom: '1px solid rgba(56, 189, 248, 0.2)',
          backgroundColor: '#0f172a'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '34px',
              height: '34px',
              borderRadius: '6px',
              backgroundColor: 'rgba(56, 189, 248, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#38bdf8'
            }}>
              <Lock size={18} />
            </div>
            <div>
              <div style={{ fontWeight: '600', fontSize: '0.9375rem', letterSpacing: '0.02em', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>Welcome to COSMOS</span>
                {currentUser && (
                  <span style={{
                    fontSize: '0.625rem',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    backgroundColor: isAdmin ? 'rgba(239, 68, 68, 0.2)' : 'rgba(56, 189, 248, 0.2)',
                    color: isAdmin ? '#f87171' : '#38bdf8',
                    fontFamily: 'var(--font-mono, monospace)',
                    fontWeight: '700'
                  }}>
                    {currentUser.role.toUpperCase()}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.6875rem', color: '#94a3b8', fontFamily: 'var(--font-mono, monospace)' }}>

              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '4px',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Switcher: Log In / Sign In vs New User / Manage */}
        <div style={{
          display: 'flex',
          backgroundColor: '#0a0f1d',
          borderBottom: '1px solid rgba(56, 189, 248, 0.15)',
          padding: '4px 8px 0'
        }}>
          <button
            onClick={() => setActiveTab('login')}
            style={{
              flex: 1,
              padding: '10px 14px',
              backgroundColor: activeTab === 'login' ? '#0b1329' : 'transparent',
              border: 'none',
              borderBottom: activeTab === 'login' ? '2px solid #38bdf8' : '2px solid transparent',
              color: activeTab === 'login' ? '#38bdf8' : '#94a3b8',
              fontWeight: activeTab === 'login' ? '600' : '400',
              fontSize: '0.8125rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px'
            }}
          >
            <ShieldCheck size={14} />
            <span>LOG IN / SIGN IN</span>
          </button>

          <button
            onClick={() => {
              setActiveTab('new_user');
              if (isAdmin) fetchUsers();
            }}
            style={{
              flex: 1,
              padding: '10px 14px',
              backgroundColor: activeTab === 'new_user' ? '#0b1329' : 'transparent',
              border: 'none',
              borderBottom: activeTab === 'new_user' ? '2px solid #38bdf8' : '2px solid transparent',
              color: activeTab === 'new_user' ? '#38bdf8' : '#94a3b8',
              fontWeight: activeTab === 'new_user' ? '600' : '400',
              fontSize: '0.8125rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px'
            }}
          >
            <UserPlus size={14} />
            <span>{isAdmin ? 'ADMIN: MANAGE & ADD USER' : 'NEW USER PROVISIONING'}</span>
          </button>
        </div>

        {/* Modal Scrollable Content */}
        <div style={{ overflowY: 'auto', padding: '20px' }}>

          {/* =============================================================== */}
          {/* TAB 1: LOG IN / SIGN IN */}
          {/* =============================================================== */}
          {activeTab === 'login' && (
            <form onSubmit={handleLoginSubmit}>
              {loginError && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 12px',
                  marginBottom: '16px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  color: '#f87171',
                  fontSize: '0.8125rem'
                }}>
                  <AlertCircle size={16} style={{ flexShrink: 0 }} />
                  <div>{loginError}</div>
                </div>
              )}

              {/* Username Field */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  fontWeight: '500',
                  color: '#94a3b8',
                  marginBottom: '6px',
                  fontFamily: 'var(--font-mono, monospace)'
                }}>
                  OPERATOR USERNAME / ID
                </label>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  backgroundColor: '#1e293b',
                  border: '1px solid rgba(148, 163, 184, 0.2)',
                  borderRadius: '6px',
                  padding: '0 12px'
                }}>
                  <User size={15} color="#94a3b8" />
                  <input
                    type="text"
                    required
                    value={loginUsername}
                    onChange={(e) => setLoginUsername(e.target.value)}
                    placeholder="username"
                    style={{
                      width: '100%',
                      background: 'transparent',
                      border: 'none',
                      padding: '10px 10px',
                      color: '#f8fafc',
                      outline: 'none',
                      fontSize: '0.875rem'
                    }}
                  />
                </div>
              </div>

              {/* Password Field */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{
                  display: 'block',
                  fontSize: '0.75rem',
                  fontWeight: '500',
                  color: '#94a3b8',
                  marginBottom: '6px',
                  fontFamily: 'var(--font-mono, monospace)'
                }}>
                  PASSWORD
                </label>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  backgroundColor: '#1e293b',
                  border: '1px solid rgba(148, 163, 184, 0.2)',
                  borderRadius: '6px',
                  padding: '0 12px'
                }}>
                  <Key size={15} color="#94a3b8" />
                  <input
                    type="password"
                    required
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="Enter security password"
                    style={{
                      width: '100%',
                      background: 'transparent',
                      border: 'none',
                      padding: '10px 10px',
                      color: '#f8fafc',
                      outline: 'none',
                      fontSize: '0.875rem'
                    }}
                  />
                </div>
              </div>



              {/* Submit Button */}
              <button
                type="submit"
                disabled={loginLoading}
                style={{
                  width: '100%',
                  padding: '12px',
                  backgroundColor: '#0284c7',
                  border: 'none',
                  borderRadius: '6px',
                  color: '#ffffff',
                  fontWeight: '600',
                  fontSize: '0.875rem',
                  cursor: loginLoading ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  opacity: loginLoading ? 0.7 : 1
                }}
              >
                <ShieldCheck size={16} />
                <span>{loginLoading ? 'AUTHENTICATING SESSION...' : 'LOG IN / SIGN IN TO COCKPIT'}</span>
              </button>
            </form>
          )}

          {/* =============================================================== */}
          {/* TAB 2: NEW USER PROVISIONING & RBAC MANAGEMENT */}
          {/* =============================================================== */}
          {activeTab === 'new_user' && (
            <div>
              {!isAdmin ? (
                /* Non-Admin Notice */
                <div style={{ textAlign: 'center', padding: '16px 8px' }}>
                  <ShieldAlert size={40} color="#f59e0b" style={{ margin: '0 auto 12px' }} />
                  <div style={{ fontSize: '1rem', fontWeight: '600', color: '#fcd34d', marginBottom: '8px' }}>
                    Administrator Privilege Required
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: '#94a3b8', lineHeight: '1.5', maxWidth: '400px', margin: '0 auto 18px' }}>
                    In accordance with COSMOS flight security protocol, new user accounts cannot self-register.
                    <strong> Only System Administrators can add new users and decide their operational permissions.</strong>
                  </p>

                  <div style={{
                    padding: '12px',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    border: '1px solid rgba(245, 158, 11, 0.25)',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                    color: '#fef08a',
                    marginBottom: '18px',
                    textAlign: 'left'
                  }}>
                    <strong>To add new operators and configure permissions:</strong>
                    <ol style={{ paddingLeft: '18px', margin: '6px 0 0' }}>
                      <li>Sign in using the Administrator account (<strong>admin</strong>).</li>
                      <li>Open this tab to create new operator credentials and assign specific permissions.</li>
                    </ol>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab('login');
                    }}
                    style={{
                      padding: '10px 18px',
                      backgroundColor: '#0284c7',
                      border: 'none',
                      borderRadius: '6px',
                      color: '#ffffff',
                      fontWeight: '600',
                      fontSize: '0.8125rem',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <Lock size={15} />
                    <span>Go to Log In</span>
                  </button>
                </div>
              ) : (
                /* Authenticated Admin Management Interface */
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

                  {/* Create New User Section */}
                  <div style={{
                    backgroundColor: '#0f172a',
                    border: '1px solid rgba(56, 189, 248, 0.25)',
                    borderRadius: '8px',
                    padding: '16px'
                  }}>
                    <div style={{ fontSize: '0.875rem', fontWeight: '600', color: '#38bdf8', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <UserPlus size={16} /> Add New User &amp; Assign Permissions
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '14px' }}>
                      Administrator exclusive: Provision new credentials and define allowed flight operations.
                    </div>

                    {newError && (
                      <div style={{
                        padding: '8px 12px',
                        borderRadius: '6px',
                        backgroundColor: 'rgba(239, 68, 68, 0.15)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        color: '#f87171',
                        fontSize: '0.75rem',
                        marginBottom: '12px'
                      }}>
                        {newError}
                      </div>
                    )}

                    {newSuccess && (
                      <div style={{
                        padding: '8px 12px',
                        borderRadius: '6px',
                        backgroundColor: 'rgba(16, 185, 129, 0.15)',
                        border: '1px solid rgba(16, 185, 129, 0.3)',
                        color: '#34d399',
                        fontSize: '0.75rem',
                        marginBottom: '12px'
                      }}>
                        {newSuccess}
                      </div>
                    )}

                    <form onSubmit={handleCreateUserSubmit}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '12px' }}>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.6875rem', color: '#94a3b8', marginBottom: '4px', fontFamily: 'var(--font-mono)' }}>
                            USERNAME
                          </label>
                          <input
                            type="text"
                            required
                            value={newUsername}
                            onChange={(e) => setNewUsername(e.target.value)}
                            placeholder="e.g. flight_ops_1"
                            style={{
                              width: '100%',
                              backgroundColor: '#1e293b',
                              border: '1px solid rgba(148, 163, 184, 0.2)',
                              borderRadius: '4px',
                              padding: '8px 10px',
                              color: '#fff',
                              fontSize: '0.8125rem',
                              outline: 'none'
                            }}
                          />
                        </div>

                        <div>
                          <label style={{ display: 'block', fontSize: '0.6875rem', color: '#94a3b8', marginBottom: '4px', fontFamily: 'var(--font-mono)' }}>
                            PASSWORD (MIN 6 CHARS)
                          </label>
                          <input
                            type="password"
                            required
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                            placeholder="Password"
                            style={{
                              width: '100%',
                              backgroundColor: '#1e293b',
                              border: '1px solid rgba(148, 163, 184, 0.2)',
                              borderRadius: '4px',
                              padding: '8px 10px',
                              color: '#fff',
                              fontSize: '0.8125rem',
                              outline: 'none'
                            }}
                          />
                        </div>

                        <div>
                          <label style={{ display: 'block', fontSize: '0.6875rem', color: '#94a3b8', marginBottom: '4px', fontFamily: 'var(--font-mono)' }}>
                            ROLE
                          </label>
                          <select
                            value={newRole}
                            onChange={(e) => setNewRole(e.target.value)}
                            style={{
                              width: '100%',
                              backgroundColor: '#1e293b',
                              border: '1px solid rgba(148, 163, 184, 0.2)',
                              borderRadius: '4px',
                              padding: '8px 10px',
                              color: '#fff',
                              fontSize: '0.8125rem',
                              outline: 'none'
                            }}
                          >
                            <option value="operator">Flight Operator (Granular Perms)</option>
                            <option value="admin">Administrator (Full Access to Everything)</option>
                          </select>
                        </div>
                      </div>

                      {/* Granular Permissions Selection (if role == 'operator') */}
                      {newRole === 'operator' ? (
                        <div style={{ marginBottom: '14px' }}>
                          <label style={{ display: 'block', fontSize: '0.6875rem', color: '#94a3b8', marginBottom: '6px', fontFamily: 'var(--font-mono)' }}>
                            DECIDE OPERATIONAL PERMISSIONS:
                          </label>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '8px' }}>
                            {AVAILABLE_PERMISSIONS.map((p) => {
                              const checked = newPermissions.includes(p.id);
                              return (
                                <div
                                  key={p.id}
                                  onClick={() => togglePermission(p.id)}
                                  style={{
                                    display: 'flex',
                                    alignItems: 'flex-start',
                                    gap: '8px',
                                    padding: '8px 10px',
                                    borderRadius: '6px',
                                    backgroundColor: checked ? 'rgba(56, 189, 248, 0.1)' : 'rgba(30, 41, 59, 0.5)',
                                    border: `1px solid ${checked ? 'rgba(56, 189, 248, 0.4)' : 'rgba(148, 163, 184, 0.15)'}`,
                                    cursor: 'pointer'
                                  }}
                                >
                                  <div style={{ marginTop: '2px', color: checked ? '#38bdf8' : '#64748b' }}>
                                    {checked ? <CheckSquare size={14} /> : <Square size={14} />}
                                  </div>
                                  <div>
                                    <div style={{ fontSize: '0.75rem', fontWeight: '600', color: checked ? '#f8fafc' : '#94a3b8' }}>
                                      {p.label}
                                    </div>
                                    <div style={{ fontSize: '0.625rem', color: '#64748b', marginTop: '1px' }}>
                                      {p.desc}
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ) : (
                        <div style={{
                          padding: '10px 12px',
                          borderRadius: '6px',
                          backgroundColor: 'rgba(239, 68, 68, 0.1)',
                          border: '1px solid rgba(239, 68, 68, 0.25)',
                          marginBottom: '14px',
                          fontSize: '0.75rem',
                          color: '#fca5a5'
                        }}>
                          <strong>Full Administrative Privileges:</strong> Administrators automatically receive wildcard <code>[*]</code> permissions granting unrestricted access to all flight operations and user management.
                        </div>
                      )}

                      <button
                        type="submit"
                        disabled={newLoading}
                        style={{
                          padding: '8px 16px',
                          backgroundColor: '#0284c7',
                          border: 'none',
                          borderRadius: '6px',
                          color: '#ffffff',
                          fontWeight: '600',
                          fontSize: '0.75rem',
                          cursor: newLoading ? 'not-allowed' : 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px'
                        }}
                      >
                        <UserPlus size={14} />
                        <span>{newLoading ? 'CREATING USER...' : '+ PROVISION NEW USER'}</span>
                      </button>
                    </form>
                  </div>

                  {/* Registered Users Table */}
                  <div>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '10px'
                    }}>
                      <div style={{ fontSize: '0.8125rem', fontWeight: '600', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Users size={15} color="#38bdf8" />
                        <span>Registered Users ({usersList.length})</span>
                      </div>
                      <button
                        onClick={fetchUsers}
                        style={{
                          background: 'transparent',
                          border: '1px solid rgba(148, 163, 184, 0.2)',
                          borderRadius: '4px',
                          color: '#94a3b8',
                          padding: '3px 8px',
                          fontSize: '0.6875rem',
                          cursor: 'pointer'
                        }}
                      >
                        Refresh List
                      </button>
                    </div>

                    <div style={{
                      maxHeight: '220px',
                      overflowY: 'auto',
                      borderRadius: '6px',
                      border: '1px solid rgba(148, 163, 184, 0.15)',
                      backgroundColor: '#0a0f1d'
                    }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
                        <thead>
                          <tr style={{ backgroundColor: '#0f172a', borderBottom: '1px solid rgba(148, 163, 184, 0.15)', textAlign: 'left', color: '#94a3b8' }}>
                            <th style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>USERNAME</th>
                            <th style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>ROLE</th>
                            <th style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)' }}>PERMISSIONS</th>
                            <th style={{ padding: '8px 10px', fontFamily: 'var(--font-mono)', textAlign: 'right' }}>ACTION</th>
                          </tr>
                        </thead>
                        <tbody>
                          {usersList.map((u) => {
                            const isRootAdmin = u.username.toLowerCase() === 'admin';
                            const perms = Array.isArray(u.permissions) ? u.permissions : [];
                            return (
                              <tr key={u.id} style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }}>
                                <td style={{ padding: '8px 10px', fontWeight: '600', color: '#f8fafc' }}>
                                  {u.username}
                                  {isRootAdmin && (
                                    <span style={{ marginLeft: '6px', fontSize: '0.625rem', color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>
                                      [ROOT]
                                    </span>
                                  )}
                                </td>
                                <td style={{ padding: '8px 10px' }}>
                                  <span style={{
                                    padding: '2px 6px',
                                    borderRadius: '4px',
                                    fontSize: '0.625rem',
                                    fontFamily: 'var(--font-mono)',
                                    backgroundColor: u.role === 'admin' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                                    color: u.role === 'admin' ? '#f87171' : '#38bdf8'
                                  }}>
                                    {u.role.toUpperCase()}
                                  </span>
                                </td>
                                <td style={{ padding: '8px 10px', color: '#94a3b8', fontSize: '0.6875rem' }}>
                                  {u.role === 'admin' || perms.includes('*') ? (
                                    <span style={{ color: '#34d399', fontWeight: '600' }}>Full Access [*]</span>
                                  ) : perms.length > 0 ? (
                                    <span>{perms.join(', ')}</span>
                                  ) : (
                                    <span style={{ color: '#64748b' }}>None</span>
                                  )}
                                </td>
                                <td style={{ padding: '8px 10px', textAlign: 'right' }}>
                                  {!isRootAdmin && (
                                    <button
                                      onClick={() => handleDeleteUser(u.username)}
                                      title="Revoke and delete user"
                                      style={{
                                        background: 'rgba(239, 68, 68, 0.15)',
                                        border: '1px solid rgba(239, 68, 68, 0.3)',
                                        borderRadius: '4px',
                                        color: '#f87171',
                                        padding: '4px 6px',
                                        cursor: 'pointer'
                                      }}
                                    >
                                      <Trash2 size={12} />
                                    </button>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                </div>
              )}
            </div>
          )}

        </div>

      </div>
    </div>
  );
}
