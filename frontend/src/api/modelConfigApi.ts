import api from './index';
import { AxiosPromise } from 'axios';

// 模型配置类型
export interface ModelConfig {
  id: string;
  display_name: string;
  model_name: string;
  api_key_masked: string;
  api_base_url: string;
  is_active: boolean;
  created_at: string;
}

export interface ModelsResponse {
  models: ModelConfig[];
}

export interface AddModelRequest {
  display_name?: string;
  model_name: string;
  api_key: string;
  api_base_url: string;
}

export interface UpdateModelRequest {
  display_name?: string;
  model_name?: string;
  api_key?: string;
  api_base_url?: string;
}

// API 方法
export const modelConfigApi = {
  getModels: (): AxiosPromise<ModelsResponse> =>
    api.get('/models'),

  addModel: (data: AddModelRequest): AxiosPromise<ModelConfig> =>
    api.post('/models', data),

  updateModel: (id: string, data: UpdateModelRequest): AxiosPromise<ModelConfig> =>
    api.put(`/models/${id}`, data),

  deleteModel: (id: string): AxiosPromise<{ success: boolean }> =>
    api.delete(`/models/${id}`),

  activateModel: (id: string): AxiosPromise<ModelConfig> =>
    api.put(`/models/${id}/activate`),
};

export default modelConfigApi;
