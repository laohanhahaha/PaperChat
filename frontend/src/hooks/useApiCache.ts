/**
 * useApiCache.ts
 * 
 * 通用 API 缓存 Hook（非 React hook，纯 TS 工具函数）
 * 
 * 功能：
 * 1. TTL 过期控制（默认 5 分钟）
 * 2. 请求去重：相同 key 的并发请求只发一次，共享同一 Promise
 * 3. 手动失效：invalidate(key) / invalidateAll()
 * 4. 缓存状态枚举：loading / fresh / stale / empty
 * 
 * 性能说明：
 * - 内存开销极低，每条缓存只存 {data, timestamp, promise?} 三字段
 * - TTL 校验为 O(1)，Map 操作 O(1)
 * - 不引入任何外部依赖（无 React Query / SWR）
 * - 请求去重通过内嵌 inFlight Map 实现，与 deduplicator 原理相同
 *   但此处与缓存层合并，避免双重 Map 查找开销
 */

const DEFAULT_TTL = 5 * 60 * 1000; // 5 分钟

export type CacheStatus = 'empty' | 'loading' | 'fresh' | 'stale';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

interface ApiCacheOptions {
  /** TTL 毫秒数，默认 300_000（5 分钟） */
  ttl?: number;
}

// 全局缓存存储
const cache = new Map<string, CacheEntry<unknown>>();
// 全局 in-flight 存储（请求去重）
const inFlight = new Map<string, Promise<unknown>>();

// ────────────────────────────────────────────
// 核心读写操作（泛型，类型安全）
// ────────────────────────────────────────────

/**
 * 从缓存读取数据。返回 null 表示无有效缓存。
 */
export function readCache<T>(key: string): T | null {
  const entry = cache.get(key) as CacheEntry<T> | undefined;
  if (!entry) return null;
  if (Date.now() - entry.timestamp > entry.ttl) {
    cache.delete(key);
    return null;
  }
  return entry.data;
}

/**
 * 写入缓存
 */
export function writeCache<T>(key: string, data: T, ttl = DEFAULT_TTL): void {
  cache.set(key, { data, timestamp: Date.now(), ttl });
}

/**
 * 获取指定 key 的缓存状态
 */
export function getCacheStatus(key: string): CacheStatus {
  if (inFlight.has(key)) return 'loading';
  const entry = cache.get(key);
  if (!entry) return 'empty';
  if (Date.now() - entry.timestamp > entry.ttl) return 'stale';
  return 'fresh';
}

// ────────────────────────────────────────────
// 失效操作
// ────────────────────────────────────────────

/**
 * 使指定 key 的缓存失效（立即删除）
 */
export function invalidate(key: string): void {
  cache.delete(key);
}

/**
 * 使所有缓存失效
 */
export function invalidateAll(): void {
  cache.clear();
}

/**
 * 使所有符合前缀的缓存失效
 */
export function invalidateByPrefix(prefix: string): void {
  for (const key of cache.keys()) {
    if (key.startsWith(prefix)) {
      cache.delete(key);
    }
  }
}

// ────────────────────────────────────────────
// 主函数：带缓存 + 去重的请求包装器
// ────────────────────────────────────────────

/**
 * 通用缓存请求函数。
 * 
 * - 缓存命中（fresh）：直接返回缓存数据，零网络开销
 * - 并发请求（in-flight）：共享同一 Promise，零重复请求
 * - 缓存未命中：发起真实请求并缓存结果
 * 
 * @param key      唯一缓存键（建议：`资源类型:参数`，如 `papers:page=1`）
 * @param fetcher  实际请求函数
 * @param options  { ttl?: number }
 */
export async function fetchWithCache<T>(
  key: string,
  fetcher: () => Promise<T>,
  options: ApiCacheOptions = {},
): Promise<T> {
  const ttl = options.ttl ?? DEFAULT_TTL;

  // 1. 检查 fresh 缓存
  const cached = cache.get(key) as CacheEntry<T> | undefined;
  if (cached && Date.now() - cached.timestamp <= cached.ttl) {
    return cached.data;
  }

  // 2. 检查 in-flight（请求去重）
  const existing = inFlight.get(key);
  if (existing !== undefined) {
    return existing as Promise<T>;
  }

  // 3. 发起真实请求
  const promise: Promise<T> = fetcher()
    .then((data) => {
      writeCache(key, data, ttl);
      return data;
    })
    .finally(() => {
      inFlight.delete(key);
    });

  inFlight.set(key, promise);
  return promise;
}

// ────────────────────────────────────────────
// 诊断（调试/监控用）
// ────────────────────────────────────────────

export function getCacheSize(): number {
  return cache.size;
}

export function getInFlightCount(): number {
  return inFlight.size;
}
