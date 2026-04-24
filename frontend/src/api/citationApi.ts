import api from './index';
import { AxiosPromise } from 'axios';

export const citationApi = {
  // 获取单篇论文引用信息
  getCitation: (paperId: number | string): AxiosPromise => 
    api.get(`/citations/${paperId}`),

  // 批量导出引用
  exportCitations: (paperIds: (number | string)[], format: string = 'bibtex'): AxiosPromise => 
    api.post('/citations/export', { paper_ids: paperIds, format }),

  // 同步到 Zotero
  syncToZotero: (paperIds: (number | string)[]): AxiosPromise => 
    api.post('/citations/sync-zotero', { paper_ids: paperIds }),

  // 获取支持的引用格式列表
  getCitationFormats: (): AxiosPromise => 
    api.get('/citations/formats'),

  // 检查 Zotero 连接状态
  getZoteroStatus: (): AxiosPromise => 
    api.get('/citations/zotero/status'),
};

export default citationApi;
