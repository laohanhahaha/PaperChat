import api from './index';
import { AxiosPromise } from 'axios';

export const writingApi = {
  // 生成论文大纲（流式）- 使用原生 fetch
  generateOutline: (topic: string, paperIds: number[] = [], requirements: string = ''): Promise<Response> => 
    fetch('/api/v1/writing/outline', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify({ topic, paper_ids: paperIds, requirements }),
    }),

  // 生成段落初稿（流式）- 使用原生 fetch
  generateDraft: (outlineSection: string, context: string = '', style: string = 'academic'): Promise<Response> => 
    fetch('/api/v1/writing/draft', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify({ outline_section: outlineSection, context, style }),
    }),

  // 学术润色（流式）- 使用原生 fetch
  polishText: (text: string, polishType: string = 'academic'): Promise<Response> => 
    fetch('/api/v1/writing/polish', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify({ text, polish_type: polishType }),
    }),

  // 生成引用格式（非流式）
  generateCitations: (paperIds: number[], format: string = 'apa'): AxiosPromise => 
    api.post('/writing/citations', { paper_ids: paperIds, format }),

  // 获取支持的格式列表
  getFormats: (): AxiosPromise => api.get('/writing/formats'),
};

export default writingApi;
