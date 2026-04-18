import api from './index';
import { AxiosPromise } from 'axios';

interface SessionParams {
  paper_id?: number | null;
  title?: string;
}

export const chatApi = {
  // 会话
  getSessions: (params?: Record<string, any>): AxiosPromise => api.get('/chat/sessions', { params }),
  getSession: (sessionId: number | string): AxiosPromise => api.get(`/chat/sessions/${sessionId}`),
  createSession: (paperId: number | null = null, title: string = '新对话'): AxiosPromise => api.post('/chat/sessions', undefined, {
    params: { paper_id: paperId, title }
  }),
  deleteSession: (sessionId: number | string): AxiosPromise => api.delete(`/chat/sessions/${sessionId}`),
  renameSession: (sessionId: number | string, title: string): AxiosPromise => api.put(`/chat/sessions/${sessionId}`, null, {
    params: { title }
  }),
  getSessionsByPaper: (paperId: number | string): AxiosPromise => api.get(`/chat/sessions/by-paper/${paperId}`),
  
  // 消息
  getMessages: (sessionId: number | string, params: Record<string, any> = {}): AxiosPromise => api.get(`/chat/sessions/${sessionId}/messages`, { params }),
  
  // 跨文档
  createCrossDocSession: (paperIds: number[], title: string = '跨文档对话'): AxiosPromise => api.post('/chat/sessions/cross-doc', paperIds, {
    params: { title }
  }),
};

export default chatApi;
