import api from './index';

export interface SubAgent {
  id: string;
  name: string;
  description: string;
  system_prompt: string;
  tools: string[];
  is_preset: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface SubAgentCreateData {
  name: string;
  description: string;
  system_prompt: string;
  tools: string[];
}

export interface SubAgentUpdateData {
  name?: string;
  description?: string;
  system_prompt?: string;
  tools?: string[];
}

export const subagentApi = {
  list: () => api.get<SubAgent[]>('/subagents'),

  create: (data: SubAgentCreateData) => api.post<SubAgent>('/subagents', data),

  update: (id: string, data: SubAgentUpdateData) =>
    api.put<SubAgent>(`/subagents/${id}`, data),

  delete: (id: string) => api.delete(`/subagents/${id}`),
};

export default subagentApi;
