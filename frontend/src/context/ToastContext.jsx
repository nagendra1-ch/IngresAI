import React, { createContext, useContext, useState, useCallback } from 'react';

const ToastContext = createContext(null);

/**
 * ToastProvider — Wrap your app with this to enable toast notifications anywhere.
 * Usage: const { showToast } = useToast();
 *        showToast('Copied to clipboard!', 'success');
 */
export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, type = 'info', duration = 3000) => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, duration);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {/* Toast container — rendered at the edge of the viewport */}
      <div
        style={{
          position: 'fixed',
          bottom: '30px',
          right: '30px',
          zIndex: 99999,
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          pointerEvents: 'none',
        }}
      >
        {toasts.map(toast => (
          <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
};

const TOAST_STYLES = {
  success: {
    background: '#166534',
    borderColor: '#22c55e',
    icon: '✅',
  },
  error: {
    background: '#991b1b',
    borderColor: '#ef4444',
    icon: '❌',
  },
  info: {
    background: '#1b6ca8',
    borderColor: '#4a9ed6',
    icon: 'ℹ️',
  },
  warning: {
    background: '#92400e',
    borderColor: '#f59e0b',
    icon: '⚠️',
  },
};

const ToastItem = ({ toast, onRemove }) => {
  const style = TOAST_STYLES[toast.type] || TOAST_STYLES.info;

  return (
    <div
      onClick={() => onRemove(toast.id)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        padding: '12px 20px',
        borderRadius: '10px',
        background: style.background,
        borderLeft: `4px solid ${style.borderColor}`,
        color: 'white',
        fontSize: '0.9rem',
        fontWeight: 500,
        boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
        cursor: 'pointer',
        pointerEvents: 'all',
        animation: 'slideInRight 0.3s ease',
        maxWidth: '340px',
        userSelect: 'none',
        fontFamily: 'var(--font-family, Inter, system-ui, sans-serif)',
      }}
      title="Click to dismiss"
    >
      <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>{style.icon}</span>
      <span style={{ flex: 1 }}>{toast.message}</span>
    </div>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

export default ToastContext;
