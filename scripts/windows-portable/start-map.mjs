import { spawn } from 'node:child_process';
import { createConnection, createServer } from 'node:net';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const bundleRoot = fileURLToPath(new URL('.', import.meta.url));
const serverFile = path.join(bundleRoot, 'frontend', 'src', 'features', 'scenic', 'three-preview', 'serve.mjs');
const host = '127.0.0.1';

function freePort() {
  return new Promise((resolve, reject) => {
    const probe = createServer();
    probe.once('error', reject);
    probe.listen(0, host, () => {
      const { port } = probe.address();
      probe.close(() => resolve(port));
    });
  });
}

function waitForServer(port, child) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + 10_000;
    function attempt() {
      if (child.exitCode !== null) return reject(new Error('地图服务未能启动。'));
      const socket = createConnection({ host, port });
      socket.once('connect', () => {
        socket.end();
        resolve();
      });
      socket.once('error', () => {
        socket.destroy();
        if (Date.now() >= deadline) reject(new Error('等待地图服务超时。'));
        else setTimeout(attempt, 120);
      });
    }
    attempt();
  });
}

let child;
try {
  const port = await freePort();
  const url = `http://${host}:${port}/`;
  child = spawn(process.execPath, [serverFile], {
    cwd: path.dirname(serverFile),
    env: { ...process.env, PORT: String(port), SCENIC_AUTHORING: '0' },
    stdio: 'inherit',
  });
  await waitForServer(port, child);
  console.log(`\n地图已启动：${url}`);
  console.log('关闭此窗口即可停止地图。');

  if (process.env.NKU_SKIP_BROWSER !== '1') {
    const opener = spawn('cmd.exe', ['/d', '/s', '/c', `start "" "${url}"`], {
      windowsHide: true,
      stdio: 'ignore',
    });
    opener.once('error', error => console.error(`无法自动打开浏览器，请手动访问 ${url}: ${error.message}`));
    opener.unref();
  }
  child.once('exit', code => { process.exitCode = code ?? 0; });
} catch (error) {
  if (child && child.exitCode === null) child.kill();
  console.error(error.message);
  process.exitCode = 1;
}
