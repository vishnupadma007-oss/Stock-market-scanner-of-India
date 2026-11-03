// Persistent headless Chromium for the DGFT portal.
// Start:  node browser_server.js <work_dir>   (listens on localhost:9555)
// Use:    curl -s --max-time 120 localhost:9555 --data-binary @snippet.js
// The POST body is the body of an async function with `page` (first tab),
// `ctx` (browser context), `WORK` (work dir) and `fs` in scope; its return
// value is sent back (strings as-is, everything else as JSON).
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');
const http = require('http');

let playwright;
try { playwright = require('playwright'); }
catch (e) { playwright = require(path.join(execSync('npm root -g').toString().trim(), 'playwright')); }

const WORK = path.resolve(process.argv[2] || '.');
fs.mkdirSync(WORK, { recursive: true });

(async () => {
  const browser = await playwright.chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 }, acceptDownloads: true });
  await ctx.newPage();
  http.createServer((req, res) => {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', async () => {
      try {
        const page = ctx.pages()[0];
        const fn = new Function('page', 'ctx', 'WORK', 'fs', 'return (async () => {' + body + '})()');
        const out = await fn(page, ctx, WORK, fs);
        res.end(typeof out === 'string' ? out : JSON.stringify(out, null, 1));
      } catch (e) { res.statusCode = 500; res.end(String(e.stack || e)); }
    });
  }).listen(9555, '127.0.0.1', () => console.log('ready'));
})();
