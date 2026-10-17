import axios from 'axios';

// When running locally in Vite dev mode, empty string routes through Vite proxy to http://127.0.0.1:8000
// When deployed on Vercel with VITE_API_URL, it uses that remote backend URL
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000, // 10 minutes for large datasets (e.g. 1M records)
});

export const uploadDataset = async (file, sheetName = null) => {
  const formData = new FormData();
  formData.append('file', file);
  if (sheetName) {
    formData.append('sheet_name', sheetName);
  }
  const response = await client.post('/api/datasets/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const selectExcelSheet = async (datasetId, sheetName) => {
  const response = await client.post(`/api/datasets/${datasetId}/select-sheet`, null, {
    params: { sheet_name: sheetName },
  });
  return response.data;
};

export const getDataset = async (datasetId) => {
  const response = await client.get(`/api/datasets/${datasetId}`);
  return response.data;
};

export const getDatasetPreview = async (datasetId, limit = 15) => {
  const response = await client.get(`/api/datasets/${datasetId}/preview`, {
    params: { limit },
  });
  return response.data;
};

export const validateDataset = async (datasetId, contractName = null) => {
  const params = contractName ? { contract_name: contractName } : {};
  const response = await client.post(`/api/datasets/${datasetId}/validate`, null, { params });
  return response.data;
};

export const executePipeline = async (datasetId, contractName = null) => {
  const params = contractName ? { contract_name: contractName } : {};
  const response = await client.post(`/api/datasets/${datasetId}/execute`, null, { params });
  return response.data;
};

export const getContracts = async () => {
  const response = await client.get('/api/contracts');
  return response.data;
};

export const getContract = async (contractName) => {
  const response = await client.get(`/api/contracts/${contractName}`);
  return response.data;
};

export const detectDatasetContract = async (datasetId) => {
  const response = await client.get(`/api/datasets/${datasetId}/detect-contract`);
  return response.data;
};

export const analyzeCorrections = async (datasetId, contractName = null) => {
  const params = contractName ? { contract_name: contractName } : {};
  const response = await client.get(`/api/datasets/${datasetId}/corrections/analyze`, { params });
  return response.data;
};

export const applyCorrections = async (datasetId, approvedFixes) => {
  const response = await client.post(`/api/datasets/${datasetId}/corrections/apply`, {
    approved_fixes: approvedFixes,
  });
  return response.data;
};

export const getDownloadProcessedUrl = (runId) => {
  return `${API_BASE_URL}/api/runs/${runId}/download/processed`;
};

export const getDownloadValidationErrorsUrl = (runId) => {
  return `${API_BASE_URL}/api/runs/${runId}/download/validation-errors`;
};

export const getRun = async (runId) => {
  const response = await client.get(`/api/runs/${runId}`);
  return response.data;
};

export const getValidationErrors = async (runId, skip = 0, limit = 200) => {
  const response = await client.get(`/api/runs/${runId}/validation-errors`, {
    params: { skip, limit },
  });
  return response.data;
};

export const getRunTasks = async (runId) => {
  const response = await client.get(`/api/runs/${runId}/tasks`);
  return response.data;
};

export const getRunResults = async (runId) => {
  const response = await client.get(`/api/runs/${runId}/results`);
  return response.data;
};

export const registerUser = async (userData) => {
  const response = await client.post('/api/auth/register', userData);
  return response.data;
};

export const loginUser = async (credentials) => {
  const response = await client.post('/api/auth/login', credentials);
  return response.data;
};

export const fixDateFormat = async (datasetId) => {
  const response = await client.post(`/api/datasets/${datasetId}/fix-date-format`);
  return response.data;
};

export const alignSchema = async (datasetId, contractName = null) => {
  const params = contractName ? { contract_name: contractName } : {};
  const response = await client.post(`/api/datasets/${datasetId}/align-schema`, null, { params });
  return response.data;
};

export const getCurrentUser = async (userId) => {
  const response = await client.get(`/api/auth/me/${userId}`);
  return response.data;
};

export const recordVisit = async (visitData = {}) => {
  try {
    const response = await client.post('/api/auth/record-visit', visitData);
    return response.data;
  } catch (err) {
    console.warn('Record visit notice:', err);
    return null;
  }
};

export const logOutUser = async (userId = null, email = null, reason = 'MANUAL') => {
  try {
    const response = await client.post('/api/auth/logout', null, {
      params: { user_id: userId, email, reason },
    });
    return response.data;
  } catch (err) {
    console.warn('Logout log notice:', err);
    return null;
  }
};

export const getUserActivities = async (limit = 100) => {
  const response = await client.get('/api/auth/activities', { params: { limit } });
  return response.data;
};

// ==========================================
// PHASES 5-10 API CLIENT METHODS
// ==========================================

export const listRuns = async (limit = 50, offset = 0) => {
  const response = await client.get('/api/runs', { params: { limit, offset } });
  return response.data;
};

export const getRunArtifacts = async (runId) => {
  const response = await client.get(`/api/runs/${runId}/artifacts`);
  return response.data;
};

export const getRunLogs = async (runId) => {
  const response = await client.get(`/api/runs/${runId}/logs`);
  return response.data;
};

export const diagnoseRun = async (runId, useAi = true) => {
  const response = await client.post(`/api/runs/${runId}/diagnose`, null, { params: { use_ai: useAi } });
  return response.data;
};

export const getRunDiagnosis = async (runId) => {
  const response = await client.get(`/api/runs/${runId}/diagnosis`);
  return response.data;
};

export const planBackfill = async (failureId) => {
  const response = await client.post(`/api/failures/${failureId}/plan-backfill`);
  return response.data;
};

export const approveBackfill = async (planId) => {
  const response = await client.post(`/api/backfills/${planId}/approve`);
  return response.data;
};

export const getBackfillPlan = async (planId) => {
  const response = await client.get(`/api/backfills/${planId}`);
  return response.data;
};

export const scheduleBackfill = async (planId, objective = 'minimize_cost', budget = null, deadline = null) => {
  const params = { objective };
  if (budget) params.budget_limit_usd = budget;
  if (deadline) params.deadline_seconds = deadline;
  const response = await client.post(`/api/backfills/${planId}/schedule`, null, { params });
  return response.data;
};

export const approveSchedule = async (scheduleId) => {
  const response = await client.post(`/api/schedules/${scheduleId}/approve`);
  return response.data;
};

export const startRecovery = async (planId, scheduleId = null, maxRetries = 3) => {
  const params = { max_retries: maxRetries };
  if (scheduleId) params.schedule_id = scheduleId;
  const response = await client.post(`/api/backfills/${planId}/recover`, null, { params });
  return response.data;
};

export const getRecoveryStatus = async (recoveryId) => {
  const response = await client.get(`/api/recoveries/${recoveryId}`);
  return response.data;
};

export const getMonitoringDashboard = async () => {
  const response = await client.get('/api/monitoring/dashboard');
  return response.data;
};

export const runExperiment = async (experimentType, config = {}) => {
  const response = await client.post('/api/experiments/run', { experiment_type: experimentType, config });
  return response.data;
};

export const getExperimentCsvUrl = (experimentId) => {
  return `${API_BASE_URL}/api/experiments/${experimentId}/csv`;
};

export default {
  registerUser,
  loginUser,
  getCurrentUser,
  fixDateFormat,
  uploadDataset,
  selectExcelSheet,
  getDataset,
  getDatasetPreview,
  validateDataset,
  executePipeline,
  getRun,
  getValidationErrors,
  getRunTasks,
  getRunResults,
  listRuns,
  getRunArtifacts,
  getRunLogs,
  diagnoseRun,
  getRunDiagnosis,
  planBackfill,
  approveBackfill,
  getBackfillPlan,
  scheduleBackfill,
  approveSchedule,
  startRecovery,
  getRecoveryStatus,
  getMonitoringDashboard,
  runExperiment,
  getExperimentCsvUrl,
  recordVisit,
  logOutUser,
  getUserActivities,
  getContracts,
  getContract,
  detectDatasetContract,
  analyzeCorrections,
  applyCorrections,
  getDownloadProcessedUrl,
  getDownloadValidationErrorsUrl,
};


