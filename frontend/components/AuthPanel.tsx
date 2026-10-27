import React, { useState } from 'react';
import { login, register } from '../lib/api';
import { BrainCircuit } from 'lucide-react';

interface AuthPanelProps {
  onLoginSuccess: () => void;
}

export default function AuthPanel({ onLoginSuccess }: AuthPanelProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      if (isLogin) {
        const data = await login(email, password);
        if (data.access_token) {
          localStorage.setItem('auth_token', data.access_token);
          onLoginSuccess();
        } else {
          setError('Invalid response from server');
        }
      } else {
        await register(email, password, displayName);
        // Automatically log in upon successful registration
        const data = await login(email, password);
        if (data.access_token) {
          localStorage.setItem('auth_token', data.access_token);
          onLoginSuccess();
        } else {
          setSuccess('Registration successful. Please log in.');
          setIsLogin(true);
        }
      }
    } catch (err: any) {
      setError(err.message || (isLogin ? 'Login failed' : 'Registration failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-panel-container glass-card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      <div style={{ marginBottom: '1rem' }}>
        <BrainCircuit size={48} color="var(--accent-color)" />
      </div>
      <h2 className="auth-title" style={{ textAlign: 'center' }}>
        Knowledge Workspace
      </h2>
      <p className="subtitle" style={{ textAlign: 'center', marginBottom: '1rem', color: 'var(--text-secondary)' }}>
        Your personal AI-powered knowledge assistant
      </p>
      
      {error && (
        <div className="auth-error-box" role="alert">
          {error}
        </div>
      )}
      {success && (
        <div className="auth-success-box" role="status">
          {success}
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="auth-form">
        {!isLogin && (
          <div>
            <label htmlFor="displayName" className="form-label">Display Name</label>
            <input
              id="displayName"
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="auth-input"
            />
          </div>
        )}
        
        <div>
          <label htmlFor="email" className="form-label">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="auth-input"
          />
        </div>
        
        <div>
          <label htmlFor="password" className="form-label">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="auth-input"
          />
        </div>
        
        <button
          type="submit"
          disabled={loading}
          aria-disabled={loading}
          aria-label={isLogin ? 'Log In' : 'Register'}
          className="btn btn-primary auth-submit-btn"
        >
          {loading ? (isLogin ? 'Logging in...' : 'Registering...') : (isLogin ? 'Log In' : 'Register')}
        </button>
      </form>
      
      <div className="auth-footer">
        {isLogin ? (
          <p>
            Don't have an account?{' '}
            <button
              type="button"
              onClick={() => { setIsLogin(false); setError(''); setSuccess(''); }}
              className="auth-link-btn"
            >
              Register here
            </button>
          </p>
        ) : (
          <p>
            Already have an account?{' '}
            <button
              type="button"
              onClick={() => { setIsLogin(true); setError(''); setSuccess(''); }}
              className="auth-link-btn"
            >
              Log in
            </button>
          </p>
        )}
      </div>
    </div>
  );
}
