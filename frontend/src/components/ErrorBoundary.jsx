import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="card" style={{ padding: '20px', border: '1px solid var(--color-critical, #d32f2f)', margin: '15px 0' }}>
          <h3 style={{ color: 'var(--color-critical, #d32f2f)', marginBottom: '10px' }}>⚠️ Component Render Error</h3>
          <p style={{ fontSize: '0.88rem', color: 'var(--text-main, #333)', marginBottom: '15px', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
            {this.state.error?.stack || this.state.error?.toString() || "An unexpected error occurred while rendering this section."}
          </p>
          <button 
            className="btn btn-outline" 
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{ fontSize: '0.8rem', padding: '6px 15px' }}
          >
            Retry Render
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
