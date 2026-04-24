/**
 * 前端 Store 单元测试
 *
 * 测试：
 * - sessionStore: 创建会话、切换会话、删除会话
 * - messageStore: 添加消息、加载消息
 *
 * 所有 API 调用均 mock，不依赖真实网络请求。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// ── mock chatApi ─────────────────────────────────────────────────────────────

vi.mock('../api/chatApi', () => ({
  chatApi: {
    getSessions: vi.fn(),
    createSession: vi.fn(),
    deleteSession: vi.fn(),
    renameSession: vi.fn(),
    getSessionsByPaper: vi.fn(),
    createCrossDocSession: vi.fn(),
    getMessages: vi.fn(),
  },
}))

import { chatApi } from '../api/chatApi'
import { useSessionStore } from '../stores/sessionStore'
import { useMessageStore } from '../stores/messageStore'


// ── helpers ───────────────────────────────────────────────────────────────────

/** 每次测试前重置所有 store 状态 */
function resetStores() {
  useSessionStore.getState().reset()
  useMessageStore.getState().reset()
}


// ══════════════════════════════════════════════════════════════════════════════
// sessionStore 测试
// ══════════════════════════════════════════════════════════════════════════════

describe('sessionStore', () => {
  beforeEach(() => {
    resetStores()
    vi.clearAllMocks()
  })

  // ── 创建会话 ────────────────────────────────────────────────────────────────

  describe('createSession', () => {
    it('成功创建会话后，会话出现在列表中', async () => {
      const newSession = { id: 1, title: '新对话', paper_id: null }
      vi.mocked(chatApi.createSession).mockResolvedValueOnce({ data: newSession } as any)

      const result = await useSessionStore.getState().createSession(null, '新对话')

      expect(result).toEqual(newSession)
      const { sessions } = useSessionStore.getState()
      expect(sessions).toHaveLength(1)
      expect(sessions[0].id).toBe(1)
    })

    it('成功创建会话后，currentSessionId 更新为新会话 ID', async () => {
      const newSession = { id: 42, title: '测试会话', paper_id: null }
      vi.mocked(chatApi.createSession).mockResolvedValueOnce({ data: newSession } as any)

      await useSessionStore.getState().createSession()

      expect(useSessionStore.getState().currentSessionId).toBe(42)
    })

    it('创建会话时指定 paperId，新会话在列表最前面', async () => {
      // 预置一个旧会话
      useSessionStore.setState({
        sessions: [{ id: 10, title: '旧会话', paper_id: 1 }],
      })
      const newSession = { id: 20, title: '新论文会话', paper_id: 1 }
      vi.mocked(chatApi.createSession).mockResolvedValueOnce({ data: newSession } as any)

      await useSessionStore.getState().createSession(1, '新论文会话')

      const { sessions } = useSessionStore.getState()
      expect(sessions[0].id).toBe(20)
      expect(sessions).toHaveLength(2)
    })

    it('API 失败时，error 字段被设置', async () => {
      const apiError = { response: { data: { detail: '服务器错误' } } }
      vi.mocked(chatApi.createSession).mockRejectedValueOnce(apiError)

      await expect(useSessionStore.getState().createSession()).rejects.toBeTruthy()
      expect(useSessionStore.getState().error).toBe('服务器错误')
    })
  })

  // ── 切换会话 ────────────────────────────────────────────────────────────────

  describe('setCurrentSession', () => {
    it('setCurrentSession 更新 currentSessionId', () => {
      useSessionStore.getState().setCurrentSession(99)
      expect(useSessionStore.getState().currentSessionId).toBe(99)
    })

    it('setCurrentSession 可以设置为 null（取消选中）', () => {
      useSessionStore.setState({ currentSessionId: 5 })
      useSessionStore.getState().setCurrentSession(null)
      expect(useSessionStore.getState().currentSessionId).toBeNull()
    })
  })

  // ── 删除会话 ────────────────────────────────────────────────────────────────

  describe('deleteSession', () => {
    it('删除会话后，会话从列表中移除', async () => {
      useSessionStore.setState({
        sessions: [
          { id: 1, title: '会话1' },
          { id: 2, title: '会话2' },
        ],
        currentSessionId: 3,
      })
      vi.mocked(chatApi.deleteSession).mockResolvedValueOnce({} as any)

      const result = await useSessionStore.getState().deleteSession(1)

      expect(result).toBe(true)
      const { sessions } = useSessionStore.getState()
      expect(sessions).toHaveLength(1)
      expect(sessions[0].id).toBe(2)
    })

    it('删除当前会话时，currentSessionId 切换到列表中第一个', async () => {
      useSessionStore.setState({
        sessions: [
          { id: 1, title: '当前会话' },
          { id: 2, title: '下一个会话' },
        ],
        currentSessionId: 1,
      })
      vi.mocked(chatApi.deleteSession).mockResolvedValueOnce({} as any)

      await useSessionStore.getState().deleteSession(1)

      expect(useSessionStore.getState().currentSessionId).toBe(2)
    })

    it('删除最后一个会话后，currentSessionId 变为 null', async () => {
      useSessionStore.setState({
        sessions: [{ id: 5, title: '唯一会话' }],
        currentSessionId: 5,
      })
      vi.mocked(chatApi.deleteSession).mockResolvedValueOnce({} as any)

      await useSessionStore.getState().deleteSession(5)

      expect(useSessionStore.getState().currentSessionId).toBeNull()
      expect(useSessionStore.getState().sessions).toHaveLength(0)
    })

    it('API 失败时返回 false', async () => {
      vi.mocked(chatApi.deleteSession).mockRejectedValueOnce(new Error('网络错误'))

      const result = await useSessionStore.getState().deleteSession(99)

      expect(result).toBe(false)
    })
  })

  // ── 其他功能 ─────────────────────────────────────────────────────────────────

  describe('clearSessionCache', () => {
    it('clearSessionCache 清空会话缓存', () => {
      useSessionStore.setState({
        sessionCache: {
          all: { data: [], timestamp: Date.now() },
        },
      })
      useSessionStore.getState().clearSessionCache()
      expect(useSessionStore.getState().sessionCache).toEqual({})
    })
  })

  describe('reset', () => {
    it('reset 将所有状态恢复初始值', () => {
      useSessionStore.setState({
        sessions: [{ id: 1, title: 'x' }],
        currentSessionId: 1,
        error: '一些错误',
      })
      useSessionStore.getState().reset()

      const state = useSessionStore.getState()
      expect(state.sessions).toHaveLength(0)
      expect(state.currentSessionId).toBeNull()
      expect(state.error).toBeNull()
    })
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// messageStore 测试
// ══════════════════════════════════════════════════════════════════════════════

describe('messageStore', () => {
  beforeEach(() => {
    resetStores()
    vi.clearAllMocks()
  })

  // ── 添加消息 ────────────────────────────────────────────────────────────────

  describe('addMessage', () => {
    it('addMessage 将消息追加到列表末尾', () => {
      const msg = { id: 1, role: 'user', content: '你好' }
      useMessageStore.getState().addMessage(msg)
      expect(useMessageStore.getState().messages).toHaveLength(1)
      expect(useMessageStore.getState().messages[0]).toEqual(msg)
    })

    it('多次 addMessage 保持顺序', () => {
      const msgs = [
        { id: 1, role: 'user', content: '问题' },
        { id: 2, role: 'assistant', content: '回答' },
      ]
      msgs.forEach(m => useMessageStore.getState().addMessage(m))

      const { messages } = useMessageStore.getState()
      expect(messages).toHaveLength(2)
      expect(messages[0].role).toBe('user')
      expect(messages[1].role).toBe('assistant')
    })
  })

  // ── 加载消息 ────────────────────────────────────────────────────────────────

  describe('fetchMessages', () => {
    it('成功加载消息后，messages 更新', async () => {
      vi.mocked(chatApi.getMessages).mockResolvedValueOnce({
        data: {
          messages: [
            { id: 2, role: 'assistant', content: '回答', sources: null },
            { id: 1, role: 'user', content: '问题', sources: null },
          ],
          total: 2,
        },
      } as any)

      await useMessageStore.getState().fetchMessages(10)

      const { messages } = useMessageStore.getState()
      expect(messages).toHaveLength(2)
      // 后端返回倒序（最新在前），fetchMessages 会 reverse 成正序
      expect(messages[0].id).toBe(1)
      expect(messages[1].id).toBe(2)
    })

    it('sessionId 为空时返回空数组', async () => {
      const result = await useMessageStore.getState().fetchMessages('')
      expect(result).toEqual([])
      expect(chatApi.getMessages).not.toHaveBeenCalled()
    })

    it('API 失败时 error 字段被设置，返回空数组', async () => {
      vi.mocked(chatApi.getMessages).mockRejectedValueOnce({
        response: { data: { detail: '获取失败' } },
      })

      const result = await useMessageStore.getState().fetchMessages(5)

      expect(result).toEqual([])
      expect(useMessageStore.getState().error).toBe('获取失败')
    })
  })

  // ── updateLastMessage ───────────────────────────────────────────────────────

  describe('updateLastMessage', () => {
    it('updateLastMessage 更新最后一条消息的内容', () => {
      useMessageStore.setState({
        messages: [
          { id: 1, role: 'user', content: '原始内容' },
        ],
      })
      useMessageStore.getState().updateLastMessage('更新后内容')
      expect(useMessageStore.getState().messages[0].content).toBe('更新后内容')
    })

    it('消息列表为空时不报错', () => {
      expect(() => {
        useMessageStore.getState().updateLastMessage('内容')
      }).not.toThrow()
    })
  })

  // ── 流式状态 ─────────────────────────────────────────────────────────────────

  describe('streaming state', () => {
    it('setIsStreaming 更新 isStreaming 状态', () => {
      useMessageStore.getState().setIsStreaming(true)
      expect(useMessageStore.getState().isStreaming).toBe(true)
      useMessageStore.getState().setIsStreaming(false)
      expect(useMessageStore.getState().isStreaming).toBe(false)
    })

    it('updateStreamingMessage 更新 streamingMessage', () => {
      useMessageStore.getState().updateStreamingMessage('正在生成...')
      expect(useMessageStore.getState().streamingMessage).toBe('正在生成...')
    })
  })

  // ── clearMessages ────────────────────────────────────────────────────────────

  describe('clearMessages', () => {
    it('clearMessages 清空消息列表和来源', () => {
      useMessageStore.setState({
        messages: [{ id: 1, role: 'user', content: 'x' }],
        sources: [{ text: 'ref' }],
        streamingMessage: '正在流式...',
      })
      useMessageStore.getState().clearMessages()

      const state = useMessageStore.getState()
      expect(state.messages).toHaveLength(0)
      expect(state.sources).toHaveLength(0)
      expect(state.streamingMessage).toBe('')
    })
  })

  // ── 消息缓存 ─────────────────────────────────────────────────────────────────

  describe('message cache', () => {
    it('invalidateMessageCache 不报错并可多次调用', () => {
      // 缓存现在由 useApiCache 管理，Store 本身不再持有 messageCache
      expect(() => {
        useMessageStore.getState().invalidateMessageCache('1')
        useMessageStore.getState().invalidateMessageCache('2')
      }).not.toThrow()
    })

    it('clearMessageCache 不报错', () => {
      expect(() => {
        useMessageStore.getState().clearMessageCache()
      }).not.toThrow()
    })
  })
})
