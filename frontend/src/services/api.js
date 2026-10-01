import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 2 minutes for processing large 1M records
});

export const uploadDataset = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await client.post('/api/datasets/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
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

export const validateDataset = async (datasetId) => {
  const response = await client.post(`/api/datasets/${datasetId}/validate`);
  return response.data;
};

export const executePipeline = async (datasetId) => {
  const response = await client.post(`/api/datasets/${datasetId}/execute`);
  return response.data;
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

export const getCurrentUser = async (userId) => {
  const response = await client.get(`/api/auth/me/${userId}`);
  return response.data;
};

export default {
  registerUser,
  loginUser,
  getCurrentUser,
  fixDateFormat,
  uploadDataset,
  getDataset,
  getDatasetPreview,
  validateDataset,
  executePipeline,
  getRun,
  getValidationErrors,
  getRunTasks,
  getRunResults,
};

