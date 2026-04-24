import api from './index';

export interface PaperResult {
  paper_id: number;
  paper_title: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  result?: string;
  error?: string;
}

export interface BatchStatusResponse {
  batch_id: string;
  analysis_type: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  total: number;
  completed: number;
  failed: number;
  progress: number;
  paper_results: PaperResult[];
  combined_result?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BatchSubmitResponse {
  batch_id: string;
  message: string;
}

/**
 * 提交批量分析任务
 * @param paperIds 论文 ID 列表
 * @param analysisType 分析类型：summary | compare | review
 */
export async function submitBatchAnalysis(
  paperIds: number[],
  analysisType: 'summary' | 'compare' | 'review',
): Promise<BatchSubmitResponse> {
  const response = await api.post<BatchSubmitResponse>('/analysis/batch', {
    paper_ids: paperIds,
    analysis_type: analysisType,
  });
  return response.data;
}

/**
 * 查询批量分析进度（不含每篇 result 内容）
 * @param batchId 任务 ID
 */
export async function getBatchStatus(batchId: string): Promise<BatchStatusResponse> {
  const response = await api.get<BatchStatusResponse>(`/analysis/batch/${batchId}`);
  return response.data;
}

/**
 * 获取批量分析完整结果
 * @param batchId 任务 ID
 */
export async function getBatchResults(batchId: string): Promise<BatchStatusResponse> {
  const response = await api.get<BatchStatusResponse>(`/analysis/batch/${batchId}/results`);
  return response.data;
}

/**
 * 取消批量分析任务
 * @param batchId 任务 ID
 */
export async function cancelBatch(batchId: string): Promise<{ message: string; batch_id: string }> {
  const response = await api.delete<{ message: string; batch_id: string }>(
    `/analysis/batch/${batchId}`,
  );
  return response.data;
}
