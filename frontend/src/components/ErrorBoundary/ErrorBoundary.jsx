import { Component } from 'react';
import { withTranslation } from 'react-i18next';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    const { t } = this.props;

    if (this.state.hasError) {
      return this.props.fallback || (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '3rem 2rem',
          minHeight: '200px',
          background: 'var(--color-bg-primary)',
          fontFamily: 'var(--sans)',
        }}>
          <div style={{
            fontSize: '48px',
            marginBottom: '16px',
            opacity: 0.5,
          }}>
            ⚠
          </div>
          <h2 style={{
            fontFamily: 'var(--heading)',
            fontSize: '20px',
            fontWeight: 500,
            color: 'var(--color-text-primary)',
            margin: '0 0 8px',
          }}>
            {t('common.error')}
          </h2>
          <p style={{
            color: 'var(--color-text-secondary)',
            margin: '0 0 20px',
            fontSize: '14px',
            maxWidth: '400px',
            textAlign: 'center',
            lineHeight: 1.5,
          }}>
            {this.state.error?.message || t('error.unknownError')}
          </p>
          <button
            onClick={this.handleRetry}
            style={{
              padding: '8px 20px',
              borderRadius: '8px',
              background: 'var(--color-accent)',
              color: '#fff',
              border: 'none',
              cursor: 'pointer',
              fontSize: '14px',
              fontFamily: 'var(--sans)',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.target.style.background = 'var(--color-accent-hover)'}
            onMouseLeave={e => e.target.style.background = 'var(--color-accent)'}
          >
            {t('common.retry')}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default withTranslation()(ErrorBoundary);
