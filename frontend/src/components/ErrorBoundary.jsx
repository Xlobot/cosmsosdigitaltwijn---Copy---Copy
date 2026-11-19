import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('UI crashed:', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          padding: '32px',
          margin: '20px',
          background: 'rgba(239,68,68,0.12)',
          border: '1px solid #ef4444',
          borderRadius: '12px',
          color: '#fecaca',
          fontFamily: 'ui-monospace, monospace'
        }}>
          <div style={{ fontSize: '1.1rem', fontWeight: 'bold', color: '#f87171', marginBottom: '8px' }}>
            UI Error — tab crashed
          </div>
          <div style={{ fontSize: '0.85rem', marginBottom: '12px' }}>
            {String(this.state.error?.message || this.state.error)}
          </div>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            style={{
              padding: '8px 14px',
              background: '#ef4444',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer'
            }}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
