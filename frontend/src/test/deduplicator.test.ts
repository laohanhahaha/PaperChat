/**
 * deduplicator.test.ts
 *
 * 测试 utils/deduplicator.ts 中的去重工具函数：
 * - deduplicate()：并发同 key 共享 Promise
 * - deduplicate()：不同 key 独立执行
 * - deduplicate()：请求完成后自动清理
 * - deduplicate()：错误正常传播给所有等待者
 * - isInFlight()：进行中状态检测
 * - getInFlightCount()：计数
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { deduplicate, isInFlight, getInFlightCount } from '../utils/deduplicator'


// ─────────────────────────────────────────────────────────────────────────────
// 注意：deduplicator 使用模块级 inFlight Map
// 由于 vitest 不重置模块状态，每个测试用不同 key 保证隔离
// ─────────────────────────────────────────────────────────────────────────────


// ══════════════════════════════════════════════════════════════════════════════
// 基础行为
// ══════════════════════════════════════════════════════════════════════════════

describe('deduplicate — 基础行为', () => {
  it('正常请求返回 fn 的结果', async () => {
    const fn = vi.fn().mockResolvedValue('result-basic')
    const result = await deduplicate('basic-key', fn)
    expect(result).toBe('result-basic')
    expect(fn).toHaveBeenCalledTimes(1)
  })

  it('请求完成后 key 从 inFlight 中移除', async () => {
    let resolver: (v: string) => void
    const promise = new Promise<string>(r => { resolver = r })
    const fn = vi.fn().mockReturnValue(promise)

    const p = deduplicate('cleanup-key', fn)
    expect(isInFlight('cleanup-key')).toBe(true)

    resolver!('done')
    await p

    expect(isInFlight('cleanup-key')).toBe(false)
  })

  it('请求失败后 key 也从 inFlight 中移除', async () => {
    const fn = vi.fn().mockRejectedValue(new Error('fetch failed'))
    try {
      await deduplicate('error-cleanup', fn)
    } catch {
      // 预期会抛出
    }
    expect(isInFlight('error-cleanup')).toBe(false)
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// 并发去重
// ══════════════════════════════════════════════════════════════════════════════

describe('deduplicate — 并发同 key 共享 Promise', () => {
  it('并发请求同 key 只执行一次 fn', async () => {
    let resolveP: (v: string) => void
    const lazyPromise = new Promise<string>(r => { resolveP = r })
    const fn = vi.fn().mockReturnValue(lazyPromise)

    const p1 = deduplicate('concurrent-key', fn)
    const p2 = deduplicate('concurrent-key', fn)
    const p3 = deduplicate('concurrent-key', fn)

    expect(fn).toHaveBeenCalledTimes(1)

    resolveP!('shared')
    const [r1, r2, r3] = await Promise.all([p1, p2, p3])
    expect(r1).toBe('shared')
    expect(r2).toBe('shared')
    expect(r3).toBe('shared')
  })

  it('第一个请求完成后，同 key 的新请求会重新发起', async () => {
    const fn = vi.fn()
      .mockResolvedValueOnce('first')
      .mockResolvedValueOnce('second')

    const r1 = await deduplicate('sequential-key', fn)
    const r2 = await deduplicate('sequential-key', fn)

    expect(r1).toBe('first')
    expect(r2).toBe('second')
    expect(fn).toHaveBeenCalledTimes(2)
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// 不同 key 独立
// ══════════════════════════════════════════════════════════════════════════════

describe('deduplicate — 不同 key 独立', () => {
  it('不同 key 各自执行独立的 fn', async () => {
    const fnA = vi.fn().mockResolvedValue('result-A')
    const fnB = vi.fn().mockResolvedValue('result-B')

    let resolveA: (v: string) => void
    let resolveB: (v: string) => void
    const promiseA = new Promise<string>(r => { resolveA = r })
    const promiseB = new Promise<string>(r => { resolveB = r })
    fnA.mockReturnValue(promiseA)
    fnB.mockReturnValue(promiseB)

    deduplicate('key-indep-A', fnA)
    deduplicate('key-indep-B', fnB)

    expect(fnA).toHaveBeenCalledTimes(1)
    expect(fnB).toHaveBeenCalledTimes(1)

    resolveA!('result-A')
    resolveB!('result-B')

    const rA = await deduplicate('key-indep-A-check', vi.fn().mockResolvedValue('new-A'))
    expect(rA).toBe('new-A')
  })

  it('key-A 进行中不影响 key-B 的并发去重计数', async () => {
    let resolveX: (v: number) => void
    const promiseX = new Promise<number>(r => { resolveX = r })
    const fnX = vi.fn().mockReturnValue(promiseX)

    deduplicate('count-key-X', fnX)
    expect(getInFlightCount()).toBeGreaterThanOrEqual(1)

    resolveX!(99)
    await promiseX
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// 错误传播
// ══════════════════════════════════════════════════════════════════════════════

describe('deduplicate — 错误传播', () => {
  it('fn 抛出错误时调用方收到 rejected Promise', async () => {
    const fn = vi.fn().mockRejectedValue(new Error('API Error'))
    await expect(deduplicate('error-key', fn)).rejects.toThrow('API Error')
  })

  it('并发请求共享错误：所有等待者均收到相同错误', async () => {
    let rejectP: (e: Error) => void
    const failingPromise = new Promise<string>((_, r) => { rejectP = r })
    const fn = vi.fn().mockReturnValue(failingPromise)

    const p1 = deduplicate('shared-error-key', fn)
    const p2 = deduplicate('shared-error-key', fn)

    expect(fn).toHaveBeenCalledTimes(1)

    rejectP!(new Error('shared failure'))

    await expect(p1).rejects.toThrow('shared failure')
    await expect(p2).rejects.toThrow('shared failure')
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// isInFlight / getInFlightCount
// ══════════════════════════════════════════════════════════════════════════════

describe('isInFlight / getInFlightCount', () => {
  it('进行中的请求 isInFlight 返回 true', () => {
    let resolve: (v: string) => void
    const lazyP = new Promise<string>(r => { resolve = r })
    const fn = vi.fn().mockReturnValue(lazyP)

    deduplicate('inflight-check', fn)
    expect(isInFlight('inflight-check')).toBe(true)

    resolve!('ok')
  })

  it('未发起的 key isInFlight 返回 false', () => {
    expect(isInFlight('never-started')).toBe(false)
  })

  it('getInFlightCount 反映当前进行中数量', () => {
    const before = getInFlightCount()

    let resolve1: (v: string) => void
    let resolve2: (v: string) => void
    const p1 = new Promise<string>(r => { resolve1 = r })
    const p2 = new Promise<string>(r => { resolve2 = r })

    deduplicate('cnt-key-1', vi.fn().mockReturnValue(p1))
    deduplicate('cnt-key-2', vi.fn().mockReturnValue(p2))

    expect(getInFlightCount()).toBeGreaterThanOrEqual(before + 2)

    resolve1!('r1')
    resolve2!('r2')
  })
})
