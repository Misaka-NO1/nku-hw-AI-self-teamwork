// Loopback-only, fixed file allowlist; never receives or logs credentials.
const http = require('node:http');
const fs = require('node:fs/promises');
const path = require('node:path');
const files = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/style.css', ['style.css', 'text/css; charset=utf-8']],
  ['/credential.mjs', ['credential.mjs', 'text/javascript; charset=utf-8']],
  ['/core.mjs', ['core.mjs', 'text/javascript; charset=utf-8']],
]);
const server = http.createServer(async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'none'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'");
  const item = files.get(req.url);
  if (req.method !== 'GET' || !item || req.headers.host !== '127.0.0.1:8023') {
    res.writeHead(404); res.end(); return;
  }
  try {
    res.setHeader('Content-Type', item[1]);
    res.end(await fs.readFile(path.join(__dirname, item[0])));
  } catch { res.writeHead(500); res.end('Local helper unavailable'); }
});
server.listen(8023, '127.0.0.1', () => process.stdout.write('Local-only credential helper: http://127.0.0.1:8023/\n'));
