/**
 * apiCache.test.ts
 *
 * 测试 useApiCache.ts 中的缓存工具函数：
 * - readCache / writeCache：基本读写
 * - TTL 过期：写入后超过 TTL 读取返回 null
 * - fetchWithCache：缓存命中、缓存未命中、并发请求去重
 * - invalidate / invalidateAll / invalidateByPrefix
 * - getCacheStatus：empty / loading / fresh / stale
 * - getCacheSize / getInFlightCount 诊断函数
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import {
  readCache,
  writeCache,
  fetchWithCache,
  invalidate,
  invalidateAll,
  invalidateByPrefix,
  getCacheStatus,
  getCacheSize,
  getInFlightCount,
  type CacheStatus,
} from '../hooks/useApiCache'


// ── 每次测试前清空缓存，保证隔离 ─────────────────────────────────────────────
beforeEach(() => {
  invalidateAll()
})

afterEach(() => {
  vi.restoreAllMocks()
})


// ══════════════════════════════════════════════════════════════════════════════
// readCache / writeCache
// ══════════════════════════════════════════════════════════════════════════════

describe('readCache / writeCache', () => {
  it('写入后能立即读取', () => {
    writeCache('key1', { value: 42 })
    const result = readCache<{ value: number }>('key1')
    expect(result).toEqual({ value: 42 })
  })

  it('不存在的 key 返回 null', () => {
    expect(readCache('nonexistent')).toBeNull()
  })

  it('TTL 过期后读取返回 null', () => {
    const now = Date.now()
    // 写入时 TTL=100ms，将时间伪造成 200ms 后
    writeCache('expire-key', 'data', 100)
    vi.spyOn(Date, 'now').mockReturnValue(now + 200)
    expect(readCache('expire-key')).toBeNull()
  })

  it('TTL 内读取正常返回数据', () => {
    writeCache('fresh-key', 'fresh-data', 60_000)
    expect(readCache('fresh-key')).toBe('fresh-data')
  })

  it('覆盖写入更新缓存', () => {
    writeCache('overwrite', 'v1')
    writeCache('overwrite', 'v2')
    expect(readCache('overwrite')).toBe('v2')
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// invalidate / invalidateAll / invalidateByPrefix
// ══════════════════════════════════════════════════════════════════════════════

describe('invalidate', () => {
  it('invalidate 删除指定 key', () => {
    writeCache('to-delete', 123)
    invalidate('to-delete')
    expect(readCache('to-delete')).toBeNull()
  })

  it('invalidate 不影响其他 key', () => {
    writeCache('a', 1)
    writeCache('b', 2)
    invalidate('a')
    expect(readCache('b')).toBe(2)
  })

  it('invalidateAll 清空所有缓存', () => {
    writeCache('x', 1)
    writeCache('y', 2)
    invalidateAll()
    expect(getCacheSize()).toBe(0)
  })

  it('invalidateByPrefix 只删除匹配前缀的 key', () => {
    writeCache('papers:1', 'p1')
    writeCache('papers:2', 'p2')
    writeCache('sessions:1', 's1')
    invalidateByPrefix('papers:')
    expect(readCache('papers:1')).toBeNull()
    expect(readCache('papers:2')).toBeNull()
    expect(readCache('sessions:1')).toBe('s1')
  })

  it('invalidateByPrefix 无匹配时不报错', () => {
    writeCache('unrelated', 'data')
    expect(() => invalidateByPrefix('no-match:')).not.toThrow()
    expect(readCache('unrelated')).toBe('data')
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// getCacheStatus
// ══════════════════════════════════════════════════════════════════════════════

describe('getCacheStatus', () => {
  it('未写入时状态为 empty', () => {
    const status: CacheStatus = getCacheStatus('no-key')
    expect(status).toBe('empty')
  })

  it('写入有效缓存后状态为 fresh', () => {
    writeCache('fresh-status', 'data', 60_000)
    expect(getCacheStatus('fresh-status')).toBe('fresh')
  })

  it('TTL 过期后状态为 stale', () => {
    const now = Date.now()
    writeCache('stale-key', 'old', 100)
    vi.spyOn(Date, 'now').mockReturnValue(now + 200)
    expect(getCacheStatus('stale-key')).toBe('stale')
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// fetchWithCache
// ══════════════════════════════════════════════════════════════════════════════

describe('fetchWithCache', () => {
  it('缓存未命中时调用 fetcher', async () => {
    const fetcher = vi.fn().mockResolvedValue('fetched-data')
    const result = await fetchWithCache('fetch-key', fetcher)
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(result).toBe('fetched-data')
  })

  it('缓存命中时不调用 fetcher', async () => {
    writeCache('cached-key', 'cached-data', 60_000)
    const fetcher = vi.fn().mockResolvedValue('new-data')
    const result = await fetchWithCache('cached-key', fetcher)
    expect(fetcher).not.toHaveBeenCalled()
    expect(result).toBe('cached-data')
  })

  it('请求成功后数据写入缓存', async () => {
    const fetcher = vi.fn().mockResolvedValue({ id: 1 })
    await fetchWithCache('write-after-fetch', fetcher)
    expect(readCache('write-after-fetch')).toEqual({ id: 1 })
  })

  it('并发同 key 只发一次真实请求（请求去重）', async () => {
    let resolvePromise: (v: string) => void
    const lazyPromise = new Promise<string>(r => { resolvePromise = r })
    const fetcher = vi.fn().mockReturnValue(lazyPromise)

    // 并发发起 3 个相同 key 的请求
    const p1 = fetchWithCache('dedup-key', fetcher)
    const p2 = fetchWithCache('dedup-key', fetcher)
    const p3 = fetchWithCache('dedup-key', fetcher)

    // fetcher 只应被调用一次
    expect(fetcher).toHaveBeenCalledTimes(1)

    resolvePromise!('shared-result')
    const [r1, r2, r3] = await Promise.all([p1, p2, p3])

    expect(r1).toBe('shared-result')
    expect(r2).toBe('shared-result')
    expect(r3).toBe('shared-result')
  })

  it('请求完成后 inFlightCount 归零', async () => {
    const fetcher = vi.fn().mockResolvedValue('done')
    await fetchWithCache('inflight-check', fetcher)
    expect(getInFlightCount()).toBe(0)
  })

  it('支持自定义 TTL', async () => {
    const now = Date.now()
    const fetcher = vi.fn().mockResolvedValue('short-lived')
    await fetchWithCache('short-ttl', fetcher, { ttl: 100 })

    // TTL 内命中
    expect(readCache('short-ttl')).toBe('short-lived')

    // TTL 过期后读取 null
    vi.spyOn(Date, 'now').mockReturnValue(now + 200)
    expect(readCache('short-ttl')).toBeNull()
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// 诊断函数
// ══════════════════════════════════════════════════════════════════════════════

describe('诊断函数', () => {
  it('getCacheSize 返回当前缓存条目数', () => {
    writeCache('d1', 1)
    writeCache('d2', 2)
    expect(getCacheSize()).toBe(2)
  })

  it('invalidateAll 后 getCacheSize 为 0', () => {
    writeCache('d1', 1)
    invalidateAll()
    expect(getCacheSize()).toBe(0)
  })
})
