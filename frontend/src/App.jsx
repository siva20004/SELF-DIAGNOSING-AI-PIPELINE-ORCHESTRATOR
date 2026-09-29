import React, { useState } from 'react';
import { Database, ShieldCheck, PlayCircle, RefreshCw, Layers, CheckCircle2 } from 'lucide-react';
import DatasetUpload from './components/DatasetUpload';
import ValidationPanel from './components/ValidationPanel';
import PipelineExecution from './components/PipelineExecution';
import './App.css';

export default function App() {
  const [dataset, setDataset] = useState(null);
  const [validationResult, setValidationResult] = useState(null);

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

  const isStep1Complete = !!dataset;
  const isStep2Complete = validationResult && validationResult.status === 'VALID';

  return (
    <div className="app-container">
      {/* Enterprise Platform Header */}
      <header className="app-header">
        <div className="header-inner">
          <div className="brand-block">
            <div className="brand-icon">
              <Layers size={24} />
            </div>
            <div>
              <h1 className="brand-title">SELF-DIAGNOSING AI PIPELINE ORCHESTRATOR</h1>
              <p className="brand-subtitle">
                Enterprise Data Platform — Data Contracts, Quality Validation, Execution & PostgreSQL Persistence
              </p>
            </div>
          </div>

          <div className="header-badges">
            <span className="badge badge-meta">
              <Database size={13} style={{ marginRight: '5px' }} />
              PostgreSQL Connected
            </span>
            <span className="badge badge-meta">
              <ShieldCheck size={13} style={{ marginRight: '5px' }} />
              sales_contract_v1.yaml (v1.0)
            </span>
            {dataset && (
              <button type="button" className="btn btn-reset" onClick={handleReset}>
                <RefreshCw size={13} style={{ marginRight: '4px' }} />
                New Ingestion
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Workflow Body */}
      <main className="main-content">
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
        />

        {/* SECTION 3: PIPELINE EXECUTION & RESULTS */}
        <PipelineExecution
          dataset={dataset}
          validationResult={validationResult}
          disabled={!dataset || validationResult?.status !== 'VALID'}
        />
      </main>

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
