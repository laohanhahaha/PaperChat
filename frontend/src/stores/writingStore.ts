import { create } from 'zustand';
import { writingApi } from '../api/writingApi';

interface WritingState {
  outline: string;
  draft: string;
  polishedText: string;
  citations: any[];
  isGenerating: boolean;
  error: string | null;
  streamingContent: string;

  setOutline: (outline: string) => void;
  setDraft: (draft: string) => void;
  setPolishedText: (polishedText: string) => void;
  setCitations: (citations: any[]) => void;
  setIsGenerating: (isGenerating: boolean) => void;
  setError: (error: string | null) => void;
  setStreamingContent: (streamingContent: string) => void;
  reset: () => void;
  generateOutline: (topic: string, paperIds?: number[], requirements?: string, onChunk?: ((chunk: string) => void) | null) => Promise<string>;
  generateDraft: (outlineSection: string, context?: string, style?: string, onChunk?: ((chunk: string) => void) | null) => Promise<string>;
  polishText: (text: string, polishType?: string, onChunk?: ((chunk: string) => void) | null) => Promise<string>;
  generateCitations: (paperIds: number[], format?: string) => Promise<any[]>;
  getFormats: () => Promise<any>;
}

const useWritingStore = create<WritingState>((set) => ({
  // 状态
  outline: '',
  draft: '',
  polishedText: '',
  citations: [],
  isGenerating: false,
  error: null,

  // 流式生成中的临时内容
  streamingContent: '',
  
  // 设置状态
  setOutline: (outline) => set({ outline }),
  setDraft: (draft) => set({ draft }),
  setPolishedText: (polishedText) => set({ polishedText }),
  setCitations: (citations) => set({ citations }),
  setIsGenerating: (isGenerating) => set({ isGenerating }),
  setError: (error) => set({ error }),
  setStreamingContent: (streamingContent) => set({ streamingContent }),
  
  // 清空状态
  reset: () => set({
    outline: '',
    draft: '',
    polishedText: '',
    citations: [],
    isGenerating: false,
    error: null,
    streamingContent: '',
  }),
  
  // 生成论文大纲（流式）
  generateOutline: async (topic, paperIds = [], requirements = '', onChunk = undefined) => {
    set({ isGenerating: true, error: null, streamingContent: '' });
    
    try {
      const response = await writingApi.generateOutline(topic, paperIds, requirements);
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '生成大纲失败');
      }
      
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.content) {
                fullContent += data.content;
                set({ streamingContent: fullContent });
                if (onChunk) onChunk(data.content);
              } else if (data.done) {
                set({ outline: fullContent, isGenerating: false });
                return fullContent;
              } else if (data.error) {
                throw new Error(data.error);
              }
            } catch {
              // 忽略解析错误
            }
          }
        }
      }
      
      set({ outline: fullContent, isGenerating: false });
      return fullContent;
    } catch (error: any) {
      set({ error: error.message, isGenerating: false });
      throw error;
    }
  },
  
  // 生成段落初稿（流式）
  generateDraft: async (outlineSection, context = '', style = 'academic', onChunk = undefined) => {
    set({ isGenerating: true, error: null, streamingContent: '' });
    
    try {
      const response = await writingApi.generateDraft(outlineSection, context, style);
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '生成段落失败');
      }
      
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.content) {
                fullContent += data.content;
                set({ streamingContent: fullContent });
                if (onChunk) onChunk(data.content);
              } else if (data.done) {
                set({ draft: fullContent, isGenerating: false });
                return fullContent;
              } else if (data.error) {
                throw new Error(data.error);
              }
            } catch {
              // 忽略解析错误
            }
          }
        }
      }
      
      set({ draft: fullContent, isGenerating: false });
      return fullContent;
    } catch (error: any) {
      set({ error: error.message, isGenerating: false });
      throw error;
    }
  },
  
  // 学术润色（流式）
  polishText: async (text, polishType = 'academic', onChunk = undefined) => {
    set({ isGenerating: true, error: null, streamingContent: '' });
    
    try {
      const response = await writingApi.polishText(text, polishType);
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '润色失败');
      }
      
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.content) {
                fullContent += data.content;
                set({ streamingContent: fullContent });
                if (onChunk) onChunk(data.content);
              } else if (data.done) {
                set({ polishedText: fullContent, isGenerating: false });
                return fullContent;
              } else if (data.error) {
                throw new Error(data.error);
              }
            } catch {
              // 忽略解析错误
            }
          }
        }
      }
      
      set({ polishedText: fullContent, isGenerating: false });
      return fullContent;
    } catch (error: any) {
      set({ error: error.message, isGenerating: false });
      throw error;
    }
  },
  
  // 生成引用格式（非流式）
  generateCitations: async (paperIds, format = 'apa') => {
    set({ isGenerating: true, error: null });
    
    try {
      const response = await writingApi.generateCitations(paperIds, format);
      
      const citations = response.data.citations || [];
      set({ citations, isGenerating: false });
      return citations;
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || '生成引用失败';
      set({ error: errorMsg, isGenerating: false });
      throw new Error(errorMsg);
    }
  },
  
  // 获取支持的格式列表
  getFormats: async () => {
    try {
      const response = await writingApi.getFormats();
      return response.data;
    } catch (error) {
      console.error('获取格式列表失败:', error);
      return {
        formats: [
          { id: 'apa', name: 'APA', description: '美国心理学会格式' },
          { id: 'mla', name: 'MLA', description: '现代语言协会格式' },
          { id: 'chicago', name: 'Chicago', description: '芝加哥格式' },
          { id: 'gbt7714', name: 'GB/T 7714', description: '中国国家标准' },
        ],
        polish_types: [
          { id: 'academic', name: '学术表达', description: '提升学术性' },
          { id: 'grammar', name: '语法修正', description: '修正语法错误' },
          { id: 'fluency', name: '流畅性', description: '优化流畅度' },
          { id: 'concise', name: '精简表达', description: '删除冗余' },
        ],
        writing_styles: [
          { id: 'academic', name: '学术风格', description: '严谨、专业' },
          { id: 'formal', name: '正式风格', description: '规范、礼貌' },
          { id: 'concise', name: '简洁风格', description: '精炼、直接' },
        ],
      };
    }
  },
}));

export default useWritingStore;
