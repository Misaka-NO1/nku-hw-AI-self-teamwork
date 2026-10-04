export function validSecret(value) {
  return typeof value === 'string' && /^[\x21-\x7e]{40,256}$/.test(value);
}
export async function secretDigest(value, cryptoApi = globalThis.crypto) {
  if (!validSecret(value)) throw new Error('需要 40–256 位无空格 ASCII 随机密钥。');
  const bytes = await cryptoApi.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('');
}
export function freshSecret(cryptoApi = globalThis.crypto) {
  const bytes = cryptoApi.getRandomValues(new Uint8Array(48));
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
}
