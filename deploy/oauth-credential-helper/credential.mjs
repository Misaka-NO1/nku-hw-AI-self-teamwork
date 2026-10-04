import {freshSecret, secretDigest, validSecret} from './core.mjs';
const secret = document.querySelector('#secret');
const digest = document.querySelector('#digest');
const status = document.querySelector('#status');
const copySecret = document.querySelector('#copy-secret');
const copyDigest = document.querySelector('#copy-digest');
let revision = 0;
async function refresh() {
  const current = ++revision;
  digest.value = '';
  copySecret.disabled = true;
  copyDigest.disabled = true;
  if (!validSecret(secret.value)) {
    status.textContent = secret.value ? '需要 40–256 位无空格 ASCII 随机密钥。' : '尚未生成或输入密钥。';
    return;
  }
  try {
    const result = await secretDigest(secret.value);
    if (current !== revision) return;
    digest.value = result;
    copySecret.disabled = false;
    copyDigest.disabled = false;
    status.textContent = '已在本机计算摘要。请自行复制、填写和提交；不要把密钥发送到聊天。';
  } catch {
    if (current === revision) status.textContent = '本机加密组件不可用；没有生成可用摘要，请勿提交配置。';
  }
}
document.querySelector('#generate').addEventListener('click', () => {
  secret.value = freshSecret();
  void refresh();
});
secret.addEventListener('input', () => void refresh());
document.querySelector('#clear').addEventListener('click', () => {
  secret.value = '';
  void refresh();
});
async function copy(value, label) {
  try {
    await navigator.clipboard.writeText(value);
    status.textContent = `${label}已复制到剪贴板；请粘贴到对应表单，随后清理剪贴板。`;
  } catch {
    status.textContent = '浏览器不允许复制。可在对应字段手动选择并复制；不要把密钥发到聊天。';
  }
}
copySecret.addEventListener('click', () => void copy(secret.value, '客户端密钥'));
copyDigest.addEventListener('click', () => void copy(digest.value, '摘要'));
window.addEventListener('pagehide', () => { revision++; secret.value = ''; digest.value = ''; });
