import api from './index';
import { AxiosPromise } from 'axios';

export const citationApi = {
  // 获取单篇论文引用信息
  getCitation: (paperId: number | string): AxiosPromise => 
    api.get(`/citations/${paperId}`),

  // 批量导出引用
  exportCitations: (paperIds: (number | string)[], format: string = 'bibtex'): AxiosPromise => 
    api.post('/citations/export', { paper_ids: paperIds, format }),
};

export default citationApi;
