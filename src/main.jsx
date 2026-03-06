import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

class ErrorBoundary extends React.Component {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(error, info) { console.error('App error:', error, info); }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 24, fontFamily: 'system-ui, sans-serif', maxWidth: 480, margin: '40px auto' }}>
          <h1 style={{ color: '#2B2F40', marginBottom: 8 }}>Something went wrong</h1>
          <p style={{ color: '#5E6573', marginBottom: 16 }}>The app failed to load. Try refreshing the page. If it keeps happening, check the browser console (F12) for errors.</p>
          <button onClick={() => window.location.reload()} style={{ padding: '10px 20px', background: '#8A5CF6', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: 'pointer' }}>Reload page</button>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
