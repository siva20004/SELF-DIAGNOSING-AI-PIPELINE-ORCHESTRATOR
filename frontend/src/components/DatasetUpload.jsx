import React, { useState, useRef } from 'react';
import { 
  Upload, 
  FileText, 
  CheckCircle2, 
  AlertCircle, 
  Database, 
  Table, 
  X, 
  Layers, 
  FileSpreadsheet, 
  FileCode, 
  FileCheck, 
  Loader2,
  Sparkles,
  Info
} from 'lucide-react';
import { uploadDataset, getDatasetPreview, selectExcelSheet } from '../services/api';

const SUPPORTED_FORMATS = [
  { ext: 'CSV', label: 'CSV', icon: 'csv', color: '#10b981' },
  { ext: 'XLSX/XLS', label: 'Excel', icon: 'excel', color: '#059669' },
  { ext: 'JSON', label: 'JSON', icon: 'json', color: '#f59e0b' },
  { ext: 'PDF', label: 'PDF', icon: 'pdf', color: '#ef4444' },
  { ext: 'TXT', label: 'TXT', icon: 'txt', color: '#6366f1' },
  { ext: 'DOCX', label: 'DOCX', icon: 'docx', color: '#3b82f6' },
  { ext: 'XML', label: 'XML', icon: 'xml', color: '#8b5cf6' },
];

const VALID_EXTENSIONS = ['.csv', '.xlsx', '.xls', '.json', '.pdf', '.txt', '.docx', '.xml', '.parquet', '.pq'];

export default function DatasetUpload({ onDatasetUploaded, disabled }) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [datasetInfo, setDatasetInfo] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [switchingSheet, setSwitchingSheet] = useState(false);
  
  // Pipeline stage tracker: 'upload' | 'detect' | 'extract' | 'normalize' | 'ready'
  const [pipelineStage, setPipelineStage] = useState('idle');
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
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleFile = async (file) => {
    setUploadError(null);

    // Validate extension
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!VALID_EXTENSIONS.includes(ext)) {
      setUploadError(
        `Unsupported file type '${ext}'.\nSupported formats: CSV, XLSX, XLS, JSON, PDF, TXT, DOCX, XML`
      );
      return;
    }

    setSelectedFile(file);
    setUploading(true);
    setPipelineStage('upload');

    try {
      setPipelineStage('extract');
      const data = await uploadDataset(file);
      
      setPipelineStage('normalize');
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

      setPipelineStage('ready');
    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.detail || err.message || 'Failed to upload dataset';
      setUploadError(msg);
      setPipelineStage('error');
    } finally {
      setUploading(false);
    }
  };

  const handleSheetChange = async (sheetName) => {
    if (!datasetInfo?.dataset_id || switchingSheet) return;
    setSwitchingSheet(true);
    setUploadError(null);

    try {
      const updated = await selectExcelSheet(datasetInfo.dataset_id, sheetName);
      setDatasetInfo(updated);
      onDatasetUploaded(updated);

      // Refresh preview
      const preview = await getDatasetPreview(updated.dataset_id, 10);
      setPreviewData(preview);
    } catch (err) {
      console.error(err);
      const msg = err.response?.data?.detail || err.message || 'Failed to switch sheet';
      setUploadError(msg);
    } finally {
      setSwitchingSheet(false);
    }
  };

  const handleClear = () => {
    setSelectedFile(null);
    setDatasetInfo(null);
    setPreviewData(null);
    setUploadError(null);
    setPipelineStage('idle');
    if (inputRef.current) inputRef.current.value = '';
    onDatasetUploaded(null);
  };

  return (
    <div className="section-card">
      <div className="section-header">
        <div className="section-title-wrap">
          <span className="section-number">1</span>
          <div>
            <h2 className="section-title">DATASET UPLOAD & INGESTION</h2>
            <p className="section-subtitle">
              Universal multi-format data ingestion engine. Converts raw datasets into a unified internal representation for data contract validation and pipeline execution.
            </p>
          </div>
        </div>
        {datasetInfo && (
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span className="badge badge-success">
              <CheckCircle2 size={14} style={{ marginRight: '4px' }} />
              INGESTED ({datasetInfo.file_type})
            </span>
            <button
              type="button"
              className="btn btn-reset"
              onClick={handleClear}
              title="Clear dataset and upload another file"
              style={{ padding: '3px 8px', fontSize: '11px' }}
            >
              <X size={12} style={{ marginRight: '4px' }} />
              Clear
            </button>
          </div>
        )}
      </div>

      <div className="section-body">
        {/* Supported Formats Pills */}
        <div className="format-badges-bar" style={{
          display: 'flex',
          gap: '6px',
          flexWrap: 'wrap',
          marginBottom: '14px',
          alignItems: 'center'
        }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#64748b', marginRight: '4px' }}>
            SUPPORTED FORMATS:
          </span>
          {SUPPORTED_FORMATS.map((fmt) => (
            <span
              key={fmt.ext}
              style={{
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '4px',
                background: '#f1f5f9',
                border: '1px solid #e2e8f0',
                color: '#334155',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <span style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: fmt.color
              }} />
              {fmt.label}
            </span>
          ))}
        </div>

        {/* Multi-Stage Ingestion Pipeline Progress Indicator */}
        {uploading && (
          <div className="upload-stage-indicator" style={{
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            padding: '12px 16px',
            marginBottom: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Loader2 size={16} className="spinner" style={{ color: '#2563eb' }} />
              <strong style={{ fontSize: '13px', color: '#1e293b' }}>
                Ingesting and Normalizing Dataset...
              </strong>
            </div>
            <div style={{ display: 'flex', gap: '8px', fontSize: '11.5px', color: '#64748b', flexWrap: 'wrap' }}>
              <span style={{ color: pipelineStage === 'upload' ? '#2563eb' : '#10b981', fontWeight: 600 }}>
                {pipelineStage === 'upload' ? '⟳' : '✓'} 1. Upload
              </span>
              <span>→</span>
              <span style={{ color: pipelineStage === 'extract' ? '#2563eb' : (pipelineStage === 'normalize' || pipelineStage === 'ready' ? '#10b981' : '#94a3b8'), fontWeight: 600 }}>
                {pipelineStage === 'extract' ? '⟳' : (pipelineStage === 'normalize' || pipelineStage === 'ready' ? '✓' : '○')} 2. Format Extraction
              </span>
              <span>→</span>
              <span style={{ color: pipelineStage === 'normalize' ? '#2563eb' : (pipelineStage === 'ready' ? '#10b981' : '#94a3b8'), fontWeight: 600 }}>
                {pipelineStage === 'normalize' ? '⟳' : (pipelineStage === 'ready' ? '✓' : '○')} 3. Schema Normalization
              </span>
              <span>→</span>
              <span style={{ color: pipelineStage === 'ready' ? '#10b981' : '#94a3b8', fontWeight: 600 }}>
                {pipelineStage === 'ready' ? '✓' : '○'} 4. Ready for Validation
              </span>
            </div>
          </div>
        )}

        {/* Drop Zone */}
        {!datasetInfo && (
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
              accept=".csv,.xlsx,.xls,.json,.pdf,.txt,.docx,.xml,.parquet,.pq"
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
                  Supports real CSV • Excel (XLSX/XLS) • JSON • PDF • TXT • DOCX • XML • Parquet
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
        )}

        {/* Error Display */}
        {uploadError && (
          <div className="alert alert-danger" style={{ marginTop: '16px', whiteSpace: 'pre-line' }}>
            <AlertCircle size={18} style={{ marginRight: '8px', flexShrink: 0 }} />
            <div>
              <strong>Ingestion Error:</strong>
              <div>{uploadError}</div>
            </div>
          </div>
        )}

        {/* Excel Multi-Sheet Selector */}
        {datasetInfo && datasetInfo.available_sheets && datasetInfo.available_sheets.length > 1 && (
          <div className="excel-sheet-selector-box" style={{
            marginTop: '16px',
            padding: '14px 18px',
            background: '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            flexWrap: 'wrap'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FileSpreadsheet size={20} style={{ color: '#059669', flexShrink: 0 }} />
              <div>
                <strong style={{ color: '#166534', fontSize: '13px' }}>
                  Multi-Sheet Workbook Detected
                </strong>
                <p style={{ color: '#15803d', fontSize: '12px', margin: '2px 0 0 0' }}>
                  Available sheets: {datasetInfo.available_sheets.join(', ')}. Currently active: <strong>{datasetInfo.selected_sheet}</strong>
                </p>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: '#166534', fontWeight: 600 }}>Select Sheet:</span>
              <select
                value={datasetInfo.selected_sheet || ''}
                onChange={(e) => handleSheetChange(e.target.value)}
                disabled={switchingSheet}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: '1px solid #86efac',
                  background: '#ffffff',
                  fontSize: '13px',
                  fontWeight: 600,
                  color: '#166534',
                  cursor: 'pointer'
                }}
              >
                {datasetInfo.available_sheets.map((sheet) => (
                  <option key={sheet} value={sheet}>
                    {sheet}
                  </option>
                ))}
              </select>
              {switchingSheet && <Loader2 size={16} className="spinner" style={{ color: '#059669' }} />}
            </div>
          </div>
        )}

        {/* Extraction Notes Callout */}
        {datasetInfo && datasetInfo.extraction_notes && (
          <div style={{
            marginTop: '12px',
            padding: '8px 14px',
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: '6px',
            fontSize: '12px',
            color: '#475569',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Info size={14} style={{ color: '#64748b', flexShrink: 0 }} />
            <span>{datasetInfo.extraction_notes}</span>
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
                <span className="metadata-label">Original Format</span>
                <span className="metadata-value badge badge-neutral">{datasetInfo.file_type}</span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">File Size</span>
                <span className="metadata-value">{formatBytes(datasetInfo.file_size_bytes)}</span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">Normalized Records</span>
                <span className="metadata-value highlight-num">
                  {datasetInfo.rows.toLocaleString()}
                </span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">Normalized Columns</span>
                <span className="metadata-value highlight-num">{datasetInfo.columns}</span>
              </div>
            </div>

            {/* Preview Section */}
            {previewData && previewData.preview_rows?.length > 0 && (
              <div className="preview-wrap">
                <div className="preview-header">
                  <div className="preview-title">
                    <Table size={16} style={{ marginRight: '6px' }} />
                    Normalized Dataset Preview (Showing first {previewData.preview_rows.length} of {datasetInfo.rows.toLocaleString()} records)
                  </div>
                  <span className="preview-note">Preview is sampled safely from normalized CSV without loading entire dataset into browser</span>
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
