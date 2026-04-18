import axios, { AxiosInstance } from 'axios';
import useToastStore from '../stores/toastStore';

// 创建 axios 实例
const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// 响应拦截器：统一处理网络错误
api.interceptors.response.use(
  response => response,
  error => {
    // 跳过被主动 catch 的请求（如 fire-and-forget）
    // 只对未被业务代码处理的错误弹出 Toast
    const message = error.response?.data?.detail || error.message || '请求失败';
    useToastStore.getState().error(message);
    return Promise.reject(error);
  }
);

export default api;
