/**
 * 字段名转换：后端 snake_case → 前端内部 camelCase。
 * 只在 API client 边界调用；线上字段名保持不变。
 */

const snakeToCamelKey = (key: string): string =>
  key.replace(/_([a-z0-9])/g, (_, ch: string) => ch.toUpperCase());

export function snakeToCamel<T>(value: T): T {
  if (Array.isArray(value)) {
    return value.map((item) => snakeToCamel(item)) as T;
  }
  if (value !== null && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(value as Record<string, unknown>)) {
      out[snakeToCamelKey(key)] = snakeToCamel(val);
    }
    return out as T;
  }
  return value;
}
