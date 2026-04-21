import api from './index';
import { AxiosPromise } from 'axios';

export const metricsApi = {
  getDashboard: (): AxiosPromise => api.get('/metrics/dashboard'),
  getRuns: (limit = 50, offset = 0): AxiosPromise => api.get(`/metrics/runs?limit=${limit}&offset=${offset}`),
  getToolStats: (days = 7): AxiosPromise => api.get(`/metrics/tools?days=${days}`),
};

export default metricsApi;
