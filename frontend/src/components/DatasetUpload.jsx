import React, { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle2, AlertCircle, Database, Table, ArrowRight } from 'lucide-react';
import { uploadDataset, getDatasetPreview } from '../services/api';

export default function DatasetUpload({ onDatasetUploaded, disabled }) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [datasetInfo, setDatasetInfo] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const inputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleFile = async (file) => {
    setSelectedFile(file);
    setUploadError(null);
    setUploading(true);

    try {
      const data = await uploadDataset(file);
      setDatasetInfo(data);
      onDatasetUploaded(data);

      // Fetch preview
      setLoadingPreview(true);
      try {
        const preview = await getDatasetPreview(data.dataset_id, 10);
        setPreviewData(preview);
      } catch (pErr) {
        console.error('Failed to load preview:', pErr);
      } finally {
        setLoadingPreview(false);
      }
    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.detail || err.message || 'Failed to upload dataset';
      setUploadError(msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="section-card">
      <div className="section-header">
        <div className="section-title-wrap">
          <span className="section-number">1</span>
          <div>
            <h2 className="section-title">DATASET UPLOAD & INGESTION</h2>
            <p className="section-subtitle">
              Upload raw source data (CSV, JSON, Parquet). The orchestrator reads actual records, verifies file integrity, and prepares for contract validation.
            </p>
          </div>
        </div>
        {datasetInfo && (
          <span className="badge badge-success">
            <CheckCircle2 size={14} style={{ marginRight: '4px' }} />
            INGESTED
          </span>
        )}
      </div>

      <div className="section-body">
        {/* Drop Zone */}
        <div
          className={`dropzone ${dragActive ? 'active' : ''} ${disabled ? 'disabled' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => !disabled && inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.json,.parquet,.pq"
            style={{ display: 'none' }}
            onChange={handleChange}
            disabled={disabled}
          />
          <div className="dropzone-content">
            <div className="dropzone-icon">
              <Upload size={32} />
            </div>
            <div className="dropzone-text">
              <span className="dropzone-primary-text">
                {uploading ? 'Reading and ingesting dataset into engine...' : 'Click to browse or drag & drop dataset file here'}
              </span>
              <span className="dropzone-secondary-text">
                Supports real CSV, Parquet, and JSON datasets (tested up to 1,000,000+ rows)
              </span>
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={disabled || uploading}
              onClick={(e) => {
                e.stopPropagation();
                inputRef.current?.click();
              }}
            >
              Browse Files
            </button>
          </div>
        </div>

        {uploadError && (
          <div className="alert alert-danger" style={{ marginTop: '16px' }}>
            <AlertCircle size={18} style={{ marginRight: '8px', flexShrink: 0 }} />
            <div>
              <strong>Upload Error:</strong> {uploadError}
            </div>
          </div>
        )}

        {/* Dataset Metadata Display */}
        {datasetInfo && (
          <div className="dataset-metadata-box">
            <div className="metadata-grid">
              <div className="metadata-item">
                <span className="metadata-label">Dataset ID</span>
                <span className="metadata-value font-mono">{datasetInfo.dataset_id}</span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">Filename</span>
                <span className="metadata-value" title={datasetInfo.filename}>{datasetInfo.filename}</span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">File Type</span>
                <span className="metadata-value badge badge-neutral">{datasetInfo.file_type}</span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">File Size</span>
                <span className="metadata-value">{formatBytes(datasetInfo.file_size_bytes)}</span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">Actual Rows</span>
                <span className="metadata-value highlight-num">
                  {datasetInfo.rows.toLocaleString()}
                </span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">Actual Columns</span>
                <span className="metadata-value highlight-num">{datasetInfo.columns}</span>
              </div>
            </div>

            {/* Preview Section */}
            {previewData && previewData.preview_rows?.length > 0 && (
              <div className="preview-wrap">
                <div className="preview-header">
                  <div className="preview-title">
                    <Table size={16} style={{ marginRight: '6px' }} />
                    Dataset Preview (Showing first {previewData.preview_rows.length} of {datasetInfo.rows.toLocaleString()} records)
                  </div>
                  <span className="preview-note">Preview is sampled safely from disk without loading complete dataset into browser</span>
                </div>
                <div className="table-responsive">
                  <table className="enterprise-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        {previewData.columns.map((col) => (
                          <th key={col}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {previewData.preview_rows.map((row, idx) => (
                        <tr key={idx}>
                          <td className="row-num">{idx + 1}</td>
                          {previewData.columns.map((col) => (
                            <td key={col} className="cell-data">
                              {row[col] !== null && row[col] !== undefined ? String(row[col]) : <span className="null-tag">NULL</span>}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
