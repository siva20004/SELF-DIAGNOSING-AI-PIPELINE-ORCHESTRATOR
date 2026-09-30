import React, { useState } from 'react';
import { Eye, EyeOff, ArrowUpRight, AlertCircle, CheckCircle2, Loader2, Sparkles } from 'lucide-react';
import { registerUser, loginUser } from '../services/api';

const COUNTRIES = [
  'United States',
  'India',
  'United Kingdom',
  'Canada',
  'Germany',
  'Australia',
  'Singapore',
  'France',
  'Japan',
  'Brazil',
  'Netherlands',
  'Switzerland',
  'United Arab Emirates',
  'Other'
];

export default function AuthCard({ onAuthSuccess }) {
  const [mode, setMode] = useState('register'); // 'register' or 'login'
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [country, setCountry] = useState('United States');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const toggleMode = () => {
    setError('');
    setSuccessMsg('');
    setMode(mode === 'register' ? 'login' : 'register');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    if (!email || !password) {
      setError('Please provide both email and password.');
      return;
    }

    if (mode === 'register') {
      if (!firstName.trim() || !lastName.trim()) {
        setError('Please enter your first and last name.');
        return;
      }
      if (password.length < 6) {
        setError('Password must be at least 6 characters.');
        return;
      }
    }

    setLoading(true);

    try {
      if (mode === 'register') {
        const payload = {
          email: email.trim().toLowerCase(),
          password,
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          country
        };
        const res = await registerUser(payload);
        setSuccessMsg('Account created successfully! Logging you in...');
        setTimeout(() => {
          onAuthSuccess(res.user, res.token);
        }, 500);
      } else {
        const payload = {
          email: email.trim().toLowerCase(),
          password
        };
        const res = await loginUser(payload);
        setSuccessMsg('Login successful!');
        setTimeout(() => {
          onAuthSuccess(res.user, res.token);
        }, 500);
      }
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Authentication failed. Please check your details.';
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        {/* Top AGY Pill Badge */}
        <div className="auth-badge-container">
          <div className="agy-pill">
            <span className="agy-pill-text">AGY</span>
          </div>
        </div>

        {/* Title & Subtitle */}
        <h2 className="auth-title">
          {mode === 'register' ? 'Create Your Account' : 'Sign In to Your Account'}
        </h2>
        <p className="auth-subtitle">
          One Account to access all AI pipeline orchestration services.
        </p>

        {/* Mode Switch Link */}
        <div className="auth-mode-switch">
          {mode === 'register' ? (
            <button type="button" className="auth-switch-btn" onClick={toggleMode}>
              Already have an account? <span className="auth-link-highlight">Sign In</span>
              <ArrowUpRight size={14} className="auth-link-icon" />
            </button>
          ) : (
            <button type="button" className="auth-switch-btn" onClick={toggleMode}>
              Don't have an account? <span className="auth-link-highlight">Create Account</span>
              <ArrowUpRight size={14} className="auth-link-icon" />
            </button>
          )}
        </div>

        {/* Error / Success Feedback */}
        {error && (
          <div className="auth-alert auth-alert-error">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}
        {successMsg && (
          <div className="auth-alert auth-alert-success">
            <CheckCircle2 size={16} />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Auth Form */}
        <form onSubmit={handleSubmit} className="auth-form">
          {mode === 'register' && (
            <>
              {/* First & Last Name Two-Column Grid */}
              <div className="auth-row-2col">
                <div className="auth-field">
                  <label className="auth-label">First name</label>
                  <input
                    type="text"
                    className="auth-input"
                    placeholder="First name"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    required
                  />
                </div>
                <div className="auth-field">
                  <label className="auth-label">Last name</label>
                  <input
                    type="text"
                    className="auth-input"
                    placeholder="Last name"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    required
                  />
                </div>
              </div>

              {/* Country / Region Selector */}
              <div className="auth-field">
                <div className="country-select-container">
                  <span className="country-label-tag">COUNTRY / REGION</span>
                  <select
                    className="country-select"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                  >
                    {COUNTRIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </>
          )}

          {/* Email Field */}
          <div className="auth-field">
            <label className="auth-label">Email address</label>
            <input
              type="email"
              className="auth-input"
              placeholder="name@example.com / Gmail"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>

          {/* Password Field with Eye Toggle */}
          <div className="auth-field">
            <label className="auth-label">Password</label>
            <div className="password-input-wrapper">
              <input
                type={showPassword ? 'text' : 'password'}
                className="auth-input auth-password-input"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Submit Action Button */}
          <button
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <span className="btn-loading-flex">
                <Loader2 size={18} className="spinner-icon" />
                {mode === 'register' ? 'Creating Account...' : 'Signing In...'}
              </span>
            ) : (
              <span>{mode === 'register' ? 'Create Account' : 'Sign In'}</span>
            )}
          </button>
        </form>

        {/* Security / Persistence reassurance footer */}
        <div className="auth-card-footer">
          <span>🔒 Secured with Bcrypt & PostgreSQL Cloud Storage</span>
        </div>
      </div>
    </div>
  );
}
