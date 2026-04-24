import api from './index';
import { AxiosPromise } from 'axios';

// 服务状态类型
export interface ServiceStatus {
  status: 'healthy' | 'unhealthy' | 'not_configured' | 'unknown';
  display_name: string;
}

export interface ServicesStatusResponse {
  statuses: Record<string, ServiceStatus>;
}

export interface ServiceInfo {
  name: string;
  display_name: string;
  description: string;
  requires_api_key: boolean;
  optional_api_key?: boolean;
  is_configured: boolean;
}

export interface ServicesListResponse {
  services: ServiceInfo[];
  total: number;
}

export interface ConfigureResult {
  service: string;
  status: string;
  message: string;
  env_updated?: string[];
}

export interface AutoSetupResult {
  configured: string[];
  failed: string[];
}

export interface ValidateResult {
  service: string;
  valid: boolean;
  message: string;
  latency_ms?: number;
}

// API 方法
export const configApi = {
  // 获取所有服务状态
  getServiceStatus: (): AxiosPromise<ServicesStatusResponse> =>
    api.get('/config/services/status'),

  // 配置指定服务
  configureService: (name: string, config: { api_key?: string; settings?: Record<string, any> }): AxiosPromise<ConfigureResult> =>
    api.post('/config/services/configure', {
      service_name: name,
      api_key: config.api_key || '',
      settings: config.settings || {},
    }),

  // 一键配置免费服务
  autoSetup: (): AxiosPromise<AutoSetupResult> =>
    api.post('/config/services/auto-setup'),

  // 验证服务连通性
  validateService: (name: string): AxiosPromise<ValidateResult> =>
    api.post('/config/services/validate', { service_name: name }),
};

export default configApi;
