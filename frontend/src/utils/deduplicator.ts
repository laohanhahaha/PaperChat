/**
 * deduplicator.ts
 * 
 * 请求去重工具：相同 key 的并发请求只发一次真实请求，
 * 其他等待者共享同一个 Promise，避免重复网络开销。
 * 
 * 性能说明：
 * - 仅在请求进行中生效，Promise resolved/rejected 后立即清理
 * - 不缓存结果，只去重并发（结果缓存见 useApiCache）
 * - 无运行时额外开销，Map 操作为 O(1)
 */

type AnyFn = () => Promise<unknown>;

const inFlight = new Map<string, Promise<unknown>>();

/**
 * 对同一 key 的并发请求进行去重。
 * 
 * 若相同 key 的请求正在进行中，则复用同一个 Promise；
 * 否则执行 fn 并记录 Promise，完成后自动清理。
 *
 * @param key   唯一标识（建议使用 URL + 参数序列化）
 * @param fn    实际发起请求的工厂函数
 * @returns     与所有等待者共享的同一 Promise
 */
export function deduplicate<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const existing = inFlight.get(key);
  if (existing !== undefined) {
    return existing as Promise<T>;
  }

  const promise = fn().finally(() => {
    inFlight.delete(key);
  });

  inFlight.set(key, promise);
  return promise;
}

/**
 * 检查指定 key 是否有正在进行中的请求
 */
export function isInFlight(key: string): boolean {
  return inFlight.has(key);
}

/**
 * 获取当前正在进行中的请求数量（用于调试/监控）
 */
export function getInFlightCount(): number {
  return inFlight.size;
}
