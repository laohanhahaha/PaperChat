import api from './index';

/**
 * 导出指定论文的笔记
 * @param paperId 论文 ID
 * @param format 导出格式: 'md' | 'json'
 */
export async function exportNotes(paperId: number, format: 'md' | 'json' = 'md'): Promise<void> {
  const response = await api.get(`/notes/export`, {
    params: { paper_id: paperId, format },
    responseType: format === 'md' ? 'blob' : 'json',
  });

  if (format === 'md') {
    // 下载 Markdown 文件
    const blob = new Blob([response.data], { type: 'text/markdown' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `notes_paper_${paperId}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } else {
    // JSON 格式也下载为文件
    const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `notes_paper_${paperId}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }
}

/**
 * 批量导出多篇论文的笔记
 * @param paperIds 论文 ID 列表
 * @param format 导出格式: 'md' | 'json'
 */
export async function batchExportNotes(paperIds: number[], format: 'md' | 'json' = 'md'): Promise<void> {
  const response = await api.post(`/notes/export/batch`, {
    paper_ids: paperIds,
    format,
  }, {
    responseType: format === 'md' ? 'blob' : 'json',
  });

  if (format === 'md') {
    const blob = new Blob([response.data], { type: 'text/markdown' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `notes_batch_export.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  } else {
    const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `notes_batch_export.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }
}
