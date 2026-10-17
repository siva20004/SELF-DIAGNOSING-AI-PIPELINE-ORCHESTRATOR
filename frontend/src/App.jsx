import React, { useState, useEffect } from 'react';
import { Database, ShieldCheck, PlayCircle, RefreshCw, Layers, CheckCircle2, User, LogOut, Globe, History, AlertOctagon, BarChart3, Users, Clock } from 'lucide-react';
import DatasetUpload from './components/DatasetUpload';
import ValidationPanel from './components/ValidationPanel';
import PipelineExecution from './components/PipelineExecution';
import RunHistory from './components/RunHistory';
import FailureDiagnosis from './components/FailureDiagnosis';
import BackfillAndRecovery from './components/BackfillAndRecovery';
import MonitoringAndExperiments from './components/MonitoringAndExperiments';
import AuthCard from './components/AuthCard';
import UserAuditModal from './components/UserAuditModal';
import { recordVisit, logOutUser } from './services/api';
import { formatIST } from './utils/dateUtils';
import './App.css';

// 30 minutes in milliseconds
const SESSION_TIMEOUT_MS = 30 * 60 * 1000;

export default function App() {
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('pipeline_auth_user');
      const loginTime = localStorage.getItem('pipeline_login_timestamp');
      if (saved && loginTime) {
        const elapsed = Date.now() - parseInt(loginTime, 10);
        if (elapsed > SESSION_TIMEOUT_MS) {
          // Session expired after 30 minutes
          localStorage.removeItem('pipeline_auth_user');
          localStorage.removeItem('pipeline_auth_token');
          localStorage.removeItem('pipeline_login_timestamp');
          return null;
        }
      }
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [activeTab, setActiveTab] = useState('pipeline'); // 'pipeline' | 'history' | 'diagnosis' | 'backfill' | 'monitoring'
  const [selectedRunIdForDiagnosis, setSelectedRunIdForDiagnosis] = useState(null);
  const [selectedFailureIdForBackfill, setSelectedFailureIdForBackfill] = useState(null);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);
  const [sessionExpiryWarning, setSessionExpiryWarning] = useState(null);

  const [dataset, setDataset] = useState(null);
  const [validationResult, setValidationResult] = useState(null);
  const [shouldAutoExecute, setShouldAutoExecute] = useState(false);

  // 1. Record Website Visit in Neon/PostgreSQL when website opens
  useEffect(() => {
    recordVisit({
      user_id: currentUser ? currentUser.id : null,
      email: currentUser ? currentUser.email : null,
      page_url: window.location.pathname || '/',
      details: {
        screen: `${window.innerWidth}x${window.innerHeight}`,
        referrer: document.referrer || 'Direct Visit',
        time: formatIST(new Date().toISOString())
      }
    });
  }, [currentUser?.id]);

  // 2. Continuous 30-Minute Session Expiration Timer
  useEffect(() => {
    if (!currentUser) return;

    const interval = setInterval(() => {
      const loginTime = localStorage.getItem('pipeline_login_timestamp');
      if (loginTime) {
        const elapsed = Date.now() - parseInt(loginTime, 10);
        const remaining = SESSION_TIMEOUT_MS - elapsed;

        if (remaining <= 0) {
          // Session expired! Log to Neon database and log out user
          logOutUser(currentUser.id, currentUser.email, 'SESSION_EXPIRED');
          localStorage.removeItem('pipeline_auth_user');
          localStorage.removeItem('pipeline_auth_token');
          localStorage.removeItem('pipeline_login_timestamp');
          setCurrentUser(null);
          setSessionExpiryWarning('Your 30-minute session has expired. For enterprise security, please log in again.');
        } else if (remaining < 3 * 60 * 1000) {
          // Warning in the last 3 minutes
          const mins = Math.ceil(remaining / 60000);
          setSessionExpiryWarning(`Session expires in ${mins} minute(s).`);
        } else {
          setSessionExpiryWarning(null);
        }
      }
    }, 15000); // Check every 15 seconds

    return () => clearInterval(interval);
  }, [currentUser]);

  const handleAuthSuccess = (user, token) => {
    const now = Date.now().toString();
    localStorage.setItem('pipeline_auth_user', JSON.stringify(user));
    localStorage.setItem('pipeline_login_timestamp', now);
    if (token) {
      localStorage.setItem('pipeline_auth_token', token);
    }
    setSessionExpiryWarning(null);
    setCurrentUser(user);
  };

  const handleSignOut = () => {
    if (currentUser) {
      logOutUser(currentUser.id, currentUser.email, 'MANUAL');
    }
    localStorage.removeItem('pipeline_auth_user');
    localStorage.removeItem('pipeline_auth_token');
    localStorage.removeItem('pipeline_login_timestamp');
    setCurrentUser(null);
    setDataset(null);
    setValidationResult(null);
    setSessionExpiryWarning(null);
  };

  const handleDatasetUploaded = (uploadedData) => {
    setDataset(uploadedData);
    setValidationResult(null); // Reset validation when new dataset uploaded
  };

  const handleValidationComplete = (summary) => {
    setValidationResult(summary);
  };

  const handleReset = () => {
    setDataset(null);
    setValidationResult(null);
  };

  const handleSelectRunForDiagnosis = (runId) => {
    setSelectedRunIdForDiagnosis(runId);
    setActiveTab('diagnosis');
  };

  const handleProceedToBackfill = (failureId) => {
    setSelectedFailureIdForBackfill(failureId);
    setActiveTab('backfill');
  };

  const handleNavigateToHistory = () => {
    setActiveTab('history');
  };

  const isStep1Complete = !!dataset;
  const isStep2Complete = validationResult && (
    validationResult.status === 'VALID' || 
    validationResult.status === 'VALID_WITH_WARNINGS'
  );

  // If not logged in, show AuthCard
  if (!currentUser) {
    return (
      <div className="app-container auth-page-container">
        <header className="app-header">
          <div className="header-inner">
            <div className="brand-block">
              <div className="brand-icon">
                <img src="/pipeline-icon.png" alt="Pipeline Logo" className="brand-logo-img" />
              </div>
              <div>
                <h1 className="brand-title">SELF-DIAGNOSING AI PIPELINE ORCHESTRATOR</h1>
                <p className="brand-subtitle">
                  Enterprise Data Platform — Secure Account & Pipeline Orchestration
                </p>
              </div>
            </div>
            <div className="header-badges">
              <span className="badge badge-meta">
                <Database size={13} style={{ marginRight: '5px' }} />
                PostgreSQL Cloud DB
              </span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setIsAuditModalOpen(true)}
                title="View Live User Visits & Logins from Neon Database"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '5px 10px', fontSize: '12px' }}
              >
                <Users size={13} />
                Neon User Audit
              </button>
            </div>
          </div>
        </header>

        {sessionExpiryWarning && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid #ef4444',
            color: '#fca5a5',
            padding: '10px 20px',
            textAlign: 'center',
            fontSize: '13px',
            fontWeight: '600'
          }}>
            <Clock size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: '-2px' }} />
            {sessionExpiryWarning}
          </div>
        )}

        <main className="auth-main-wrapper">
          <AuthCard onAuthSuccess={handleAuthSuccess} />
        </main>

        <UserAuditModal isOpen={isAuditModalOpen} onClose={() => setIsAuditModalOpen(false)} />

        <footer className="app-footer">
          <div>
            Self-Diagnosing AI Pipeline Orchestrator — Real Ingestion & Execution Pipeline
          </div>
          <div className="footer-meta">
            Polars High-Speed Engine • FastAPI Backend • PostgreSQL Cloud Persistence
          </div>
        </footer>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Enterprise Platform Header */}
      <header className="app-header">
        <div className="header-inner">
          <div className="brand-block">
            <div className="brand-icon">
              <img src="/pipeline-icon.png" alt="Pipeline Logo" className="brand-logo-img" />
            </div>
            <div>
              <h1 className="brand-title">SELF-DIAGNOSING AI PIPELINE ORCHESTRATOR</h1>
              <p className="brand-subtitle">
                Enterprise Data Platform — Data Contracts, Quality Validation, Execution & PostgreSQL Persistence
              </p>
            </div>
          </div>

          <div className="header-badges">
            <span className="badge badge-user-profile">
              <User size={13} style={{ marginRight: '5px' }} />
              {currentUser.first_name} {currentUser.last_name}
              {currentUser.country && (
                <span className="user-country-tag">({currentUser.country})</span>
              )}
            </span>
            <span className="badge badge-meta">
              <Database size={13} style={{ marginRight: '5px' }} />
              PostgreSQL Connected
            </span>
            <span className="badge badge-meta">
              <ShieldCheck size={13} style={{ marginRight: '5px' }} />
              {validationResult?.contract_name ? `${validationResult.contract_name} (v1.0)` : dataset?.suggested_contract ? `${typeof dataset.suggested_contract === 'object' ? (dataset.suggested_contract.suggested_contract || 'sales') : dataset.suggested_contract}_contract.yaml` : 'Multi-Contract Engine (v1.0)'}
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setIsAuditModalOpen(true)}
              title="View Neon Database User Visits & Logins"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '5px 10px', fontSize: '12px' }}
            >
              <Users size={13} />
              Neon User Audit
            </button>
            {dataset && (
              <button type="button" className="btn btn-reset" onClick={handleReset}>
                <RefreshCw size={13} style={{ marginRight: '4px' }} />
                New Ingestion
              </button>
            )}
            <button
              type="button"
              className="btn btn-signout"
              onClick={handleSignOut}
              title="Sign Out"
            >
              <LogOut size={13} style={{ marginRight: '4px' }} />
              Sign Out
            </button>
          </div>
        </div>
      </header>

      {sessionExpiryWarning && (
        <div style={{
          background: 'rgba(245, 158, 11, 0.15)',
          border: '1px solid #f59e0b',
          color: '#fbbf24',
          padding: '8px 20px',
          textAlign: 'center',
          fontSize: '13px',
          fontWeight: '600'
        }}>
          <Clock size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: '-2px' }} />
          {sessionExpiryWarning}
        </div>
      )}

      {/* Platform Navigation Tabs (Phases 1-10) */}
      <nav className="main-nav-bar">
        <div className="main-nav-container">
          <button
            type="button"
            className={`main-nav-tab ${activeTab === 'pipeline' ? 'active' : ''}`}
            onClick={() => setActiveTab('pipeline')}
          >
            <PlayCircle size={15} />
            Pipeline Ingestion (Steps 1–3)
          </button>

          <button
            type="button"
            className={`main-nav-tab ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            <History size={15} />
            Run History
            <span className="nav-tab-badge">Phase 5</span>
          </button>

          <button
            type="button"
            className={`main-nav-tab ${activeTab === 'diagnosis' ? 'active' : ''}`}
            onClick={() => setActiveTab('diagnosis')}
          >
            <AlertOctagon size={15} />
            AI Root Cause Diagnosis
            <span className="nav-tab-badge">Phase 6</span>
          </button>

          <button
            type="button"
            className={`main-nav-tab ${activeTab === 'backfill' ? 'active' : ''}`}
            onClick={() => setActiveTab('backfill')}
          >
            <Layers size={15} />
            Backfill & Recovery
            <span className="nav-tab-badge">Phases 7–9</span>
          </button>

          <button
            type="button"
            className={`main-nav-tab ${activeTab === 'monitoring' ? 'active' : ''}`}
            onClick={() => setActiveTab('monitoring')}
          >
            <BarChart3 size={15} />
            Monitoring & Experiments
            <span className="nav-tab-badge">Phase 10</span>
          </button>
        </div>
      </nav>

      {/* Main Workflow Body */}
      <main className="main-content">
        {/* TAB 1: PIPELINE INGESTION & EXECUTION (PHASES 1-4) */}
        {activeTab === 'pipeline' && (
          <>
            {/* Step Indicator Progress Bar */}
            <div className="stepper-bar">
              <div className={`step-node ${isStep1Complete ? 'step-done' : 'step-active'}`}>
                <div className="step-circle">
                  {isStep1Complete ? <CheckCircle2 size={16} /> : '1'}
                </div>
                <div className="step-meta">
                  <span className="step-caption">Step 1</span>
                  <span className="step-heading">Dataset Upload</span>
                </div>
              </div>

              <div className={`step-connector ${isStep1Complete ? 'connector-done' : ''}`} />

              <div className={`step-node ${!dataset ? 'step-locked' : isStep2Complete ? 'step-done' : 'step-active'}`}>
                <div className="step-circle">
                  {isStep2Complete ? <CheckCircle2 size={16} /> : '2'}
                </div>
                <div className="step-meta">
                  <span className="step-caption">Step 2</span>
                  <span className="step-heading">Contract Validation</span>
                </div>
              </div>

              <div className={`step-connector ${isStep2Complete ? 'connector-done' : ''}`} />

              <div className={`step-node ${!isStep2Complete ? 'step-locked' : 'step-active'}`}>
                <div className="step-circle">3</div>
                <div className="step-meta">
                  <span className="step-caption">Step 3</span>
                  <span className="step-heading">Execution & Results</span>
                </div>
              </div>
            </div>

            {/* SECTION 1: DATASET UPLOAD */}
            <DatasetUpload
              onDatasetUploaded={handleDatasetUploaded}
              disabled={false}
            />

            {/* SECTION 2: DATA CONTRACT VALIDATION */}
            <ValidationPanel
              dataset={dataset}
              onValidationComplete={handleValidationComplete}
              disabled={!dataset}
              onNavigateToDiagnosis={handleSelectRunForDiagnosis}
              onAutoResumeExecution={() => {
                setShouldAutoExecute(true);
              }}
            />

            {/* SECTION 3: PIPELINE EXECUTION & RESULTS */}
            <PipelineExecution
              dataset={dataset}
              validationResult={validationResult}
              disabled={!dataset || !(validationResult?.status === 'VALID' || validationResult?.status === 'VALID_WITH_WARNINGS')}
              onNavigateToDiagnosis={handleSelectRunForDiagnosis}
              onNavigateToHistory={handleNavigateToHistory}
              autoExecute={shouldAutoExecute}
              onAutoExecuteDone={() => setShouldAutoExecute(false)}
            />
          </>
        )}

        {/* TAB 2: RUN HISTORY (PHASE 5) */}
        {activeTab === 'history' && (
          <RunHistory onSelectRunForDiagnosis={handleSelectRunForDiagnosis} />
        )}

        {/* TAB 3: FAILURE DETECTION & AI DIAGNOSIS (PHASE 6) */}
        {activeTab === 'diagnosis' && (
          <FailureDiagnosis
            runId={selectedRunIdForDiagnosis}
            onProceedToBackfill={handleProceedToBackfill}
          />
        )}

        {/* TAB 4: BACKFILL PLANNING & RECOVERY (PHASES 7-9) */}
        {activeTab === 'backfill' && (
          <BackfillAndRecovery
            failureId={selectedFailureIdForBackfill}
            onCompleteRecovery={() => setActiveTab('history')}
          />
        )}

        {/* TAB 5: MONITORING & EXPERIMENTS (PHASE 10) */}
        {activeTab === 'monitoring' && (
          <MonitoringAndExperiments />
        )}
      </main>

      {/* User Access & Activity Audit Modal */}
      <UserAuditModal isOpen={isAuditModalOpen} onClose={() => setIsAuditModalOpen(false)} />

      {/* Enterprise Footer */}
      <footer className="app-footer">
        <div>
          Self-Diagnosing AI Pipeline Orchestrator — Real Ingestion & Execution Pipeline
        </div>
        <div className="footer-meta">
          Polars High-Speed Engine • FastAPI Backend • PostgreSQL 18 Auditing
        </div>
      </footer>
    </div>
  );
}
