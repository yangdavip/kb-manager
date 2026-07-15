import axios from 'axios';

const API_BASE = '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
});

// ─── Stats ───
export const getStats = () => api.get('/stats');

// ─── Files ───
export const getFiles = (params?: { skip?: number; limit?: number; status?: string }) =>
  api.get('/files', { params });

export const getFile = (fileId: string) => api.get(`/files/${fileId}`);

export const deleteFile = (fileId: string) => api.delete(`/files/${fileId}`);

export const reprocessFile = (fileId: string) => api.post(`/files/${fileId}/reprocess`);

export const getChunks = (fileId: string, params?: { skip?: number; limit?: number }) =>
  api.get(`/files/${fileId}/chunks`, { params });

export const uploadFile = (file: File, onProgress?: (percent: number) => void) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/files/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) {
        onProgress(Math.round((e.loaded * 100) / e.total));
      }
    },
  });
};

// ─── Retrieve ───
export const retrieve = (data: {
  query: string;
  top_k?: number;
  distance_metric?: string;
  score_threshold?: number;
}) => api.post('/retrieve', data);

// ─── Config ───
export const getConfig = () => api.get('/config');

export const updateConfig = (key: string, value: string | number) =>
  api.put('/config', { key, value });

export default api;
