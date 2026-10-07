const { chromium } = require('C:/Users/willi/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const { spawn } = require('node:child_process');
const { randomBytes } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const password = randomBytes(32).toString('hex');
const server = spawn('python', [path.join(__dirname, 'browser_server.py')], {
  env: { ...process.env, STUDIO_ACCESS_TOKEN: password, STUDIO_USER_EMAIL: 'operator@example.test', PYTHONUTF8: '1' },
  stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true
});
const origin = 'http://127.0.0.1:8012';
const results = [];
function check(name, condition) {
  results.push({ name, passed: !!condition });
  if (!condition) throw new Error(name);
}
(async () => {
  let browser;
  try {
    for (let i = 0; i < 100; i++) {
      try { if ((await fetch(origin + '/healthz')).ok) break; } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    browser = await chromium.launch({ channel: 'msedge', headless: true });
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(origin);
    await page.getByRole('button', { name: 'Ingresar al Studio' }).waitFor();
    check('anonymous API rejected in browser', (await page.request.get(origin + '/api/v1/sessions')).status() === 401);
    await page.locator('input[type=email]').fill('operator@example.test');
    await page.locator('input[type=password]').fill(password);
    await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/auth/login') && response.status() === 200),
      page.getByRole('button', { name: 'Ingresar al Studio' }).click()
    ]);
    await page.getByRole('button', { name: 'Ingresar al Studio' }).waitFor({ state: 'detached' });
    check('authenticated API available in browser', (await page.request.get(origin + '/api/v1/sessions')).status() === 200);
    await page.reload();
    await page.getByRole('button', { name: 'Ingresar al Studio' }).waitFor({ state: 'detached' });
    check('cookie session survives reload', (await page.request.get(origin + '/api/v1/auth/session')).status() === 200);
    await page.screenshot({ path: path.join(__dirname, 'browser-authenticated.png'), fullPage: true });
    const logout = page.getByTitle('Cerrar sesión corporativa');
    await logout.click();
    await page.getByRole('button', { name: 'Ingresar al Studio' }).waitFor();
    await page.reload();
    await page.getByRole('button', { name: 'Ingresar al Studio' }).waitFor();
    check('logout persists after reload', (await page.request.get(origin + '/api/v1/sessions')).status() === 401);
    check('no application page errors', errors.length === 0);
    fs.writeFileSync(path.join(__dirname, 'browser.json'), JSON.stringify({ results, errors }, null, 2));
    console.log(results.length + ' real Edge browser checks passed');
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
