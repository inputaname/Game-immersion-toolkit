import assert from 'node:assert/strict';
import {spawn, execFileSync} from 'node:child_process';
import {createServer} from 'node:http';
import {once} from 'node:events';
import {mkdirSync, writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {chromium, firefox, webkit} from 'playwright';
import {resolvePython} from './python-runtime.mjs';

mkdirSync('output/checks', {recursive:true});
const baselineIndex = process.argv.indexOf('--baseline');
const baseline = baselineIndex < 0 ? '' : resolve('output/checks/access-baseline-api.py');
if (baseline) writeFileSync(baseline, execFileSync('git', ['show', `${process.argv[baselineIndex + 1]}:backend/api.py`]));
const python = spawn(resolvePython().command, ['scripts/local-access-browser-server.py'], {
  env:{...process.env, ...(baseline ? {TOOLKIT_ACCESS_BASELINE:baseline} : {})}, stdio:['ignore', 'pipe', 'pipe'],
});
let browser;
const servers = [];
let stderr = '';
python.stderr.on('data', value => { stderr += value; });
try {
  const port = await new Promise((resolvePort, reject) => {
    const timer = setTimeout(() => reject(Error(`Synthetic API startup timed out: ${stderr}`)), 30000);
    let text = '';
    python.stdout.on('data', value => {
      text += value;
      if (text.includes('\n')) {
        try { resolvePort(JSON.parse(text.split('\n')[0]).port); clearTimeout(timer); }
        catch (error) { reject(error); clearTimeout(timer); }
      }
    });
    python.once('error', error => {clearTimeout(timer); reject(error);});
    python.once('exit', code => {clearTimeout(timer); reject(Error(`Synthetic API exited ${code}: ${stderr}`));});
  });
  const api = `http://127.0.0.1:${port}`;
  for (let attempt = 0; ; attempt++) {
    try { if ((await fetch(api + '/api/health')).ok) break; } catch {}
    if (attempt > 100) throw Error(`Synthetic API not ready: ${stderr}`);
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  // The untrusted origin has its own server. Trusted fixture documents are
  // fulfilled below so existing companions on 3000/3001 are never contacted.
  // API HTTP and WebSocket requests always reach the real synthetic ASGI app.
  for (const listenPort of [0]) {
    const server = createServer((_req, res) => res.writeHead(200, {'Content-Type':'text/html'}).end('<!doctype html><title>Local access fixture</title><h1>Synthetic browser origin</h1>'));
    servers.push(server);
    server.listen(listenPort, '127.0.0.1');
    await once(server, 'listening');
  }
  const observe = async () => (await fetch(api + '/__test_observations')).json();
  const reset = async () => { assert((await fetch(api + '/__test_reset', {method:'POST'})).ok); };
  for (const [name, engine] of Object.entries({chromium, firefox, webkit})) {
    browser = await engine.launch({headless:true});
    const context = await browser.newContext({serviceWorkers:'block'});
    // Chromium's loopback permission is granted only to this disposable test
    // profile. The server must reject the hostile origin even when the browser
    // permits network access; browser-local network blocking is not our oracle.
    if (name === 'chromium') await context.grantPermissions(['local-network-access']);
    for (const origin of ['http://127.0.0.1:3000', 'http://localhost:3000', 'http://127.0.0.1:3001', 'http://localhost:3001']) {
      await reset();
      const page = await context.newPage();
      page.on('console', message => {if (message.type() === 'error') console.error(`${name}: ${message.text()}`);});
      await page.route(origin + '/__test_origin', route => route.fulfill({contentType:'text/html', body:'<!doctype html><title>Trusted origin fixture</title><h1>Synthetic browser origin</h1>'}));
      await page.goto(origin + '/__test_origin');
      await page.unroute(origin + '/__test_origin');
      const result = await page.evaluate(async api => {
        const statuses = [];
        for (const [path, init] of [
          ['/api/capture/start', {method:'POST'}], ['/api/lines', {}],
          ['/api/lines/1/audio', {}], ['/api/setup', {}],
          ['/api/setup/complete', {method:'POST', headers:{'Content-Type':'application/json','X-Proxy-Transcript':'setup'}, body:JSON.stringify({auto_start:false})}],
        ]) {
          try {statuses.push((await fetch(api + path, init)).status);}
          catch (error) {throw Error(`${path}: ${error.message}`);}
        }
        const snapshot = await new Promise((resolve, reject) => {
          const ws = new WebSocket(api.replace('http:', 'ws:') + '/api/ws');
          const timer = setTimeout(() => {ws.close(); reject(Error('Trusted WebSocket timed out'));}, 5000);
          ws.onmessage = event => {clearTimeout(timer); ws.close(); resolve(JSON.parse(event.data));};
          ws.onerror = () => {clearTimeout(timer); reject(Error('Trusted WebSocket failed'));};
        });
        return {statuses, snapshot};
      }, api);
      assert.deepEqual(result.statuses, [200,200,200,200,200], `${name} trusted desktop/setup/PC transcript HTTP`);
      assert.deepEqual(result.snapshot, {type:'snapshot', snapshot:{synthetic:true}});
      const actual = await observe();
      for (const call of ['start','lines','audio','setup','setup_complete','status']) assert(actual.calls.includes(call), `${name}: ${call} reached synthetic runtime`);
      assert(actual.received.some(item => item.method === 'OPTIONS' && item.path === '/api/setup/complete'), `Real browser preflight reached server: ${JSON.stringify(actual.received)}`);
      // The companion loads voice clips as crossorigin media, which carries
      // Origin even where localhost and 127.0.0.1 are different sites.
      const media = await page.evaluate(api => new Promise(resolve => {
        const audio = new Audio();
        audio.crossOrigin = 'anonymous';
        const timer = setTimeout(() => resolve('timeout'), 5000);
        audio.onloadedmetadata = () => {clearTimeout(timer); resolve('loaded');};
        audio.onerror = () => {clearTimeout(timer); resolve('error');};
        audio.src = api + '/api/lines/1/audio';
      }), api);
      assert.equal(media, 'loaded', `${name}: companion voice clip loads from ${origin}`);
      await page.close();
    }
    await reset();
    const page = await context.newPage();
    const untrusted = `http://127.0.0.1:${servers[0].address().port}`;
    await page.goto(untrusted);
    const rejected = await page.evaluate(async api => {
      const post = await fetch(api + '/api/capture/start', {method:'POST'}).then(response => response.status).catch(() => 'blocked');
      const patch = await fetch(api + '/api/settings', {method:'PATCH', headers:{'Content-Type':'application/json'}, body:'{}'}).then(response => response.status).catch(() => 'blocked');
      const socket = await new Promise(resolve => {
        const ws = new WebSocket(api.replace('http:', 'ws:') + '/api/ws');
        let opened = false, message = false;
        const timer = setTimeout(() => {ws.close(); resolve({opened, message, timeout:true});}, 5000);
        ws.onopen = () => {opened = true;};
        ws.onmessage = () => {message = true; ws.close();};
        ws.onclose = () => {clearTimeout(timer); resolve({opened, message});};
      });
      return {post, patch, socket};
    }, api);
    assert.equal(rejected.post, 'blocked');
    assert.equal(rejected.patch, 'blocked');
    assert.deepEqual(rejected.socket, {opened:false, message:false}, `${name}: no untrusted WebSocket accept or snapshot`);
    // Image and no-cors GETs omit Origin; Sec-Fetch-Site still marks them
    // cross-site. localhost and 127.0.0.1 are different sites on loopback.
    await page.goto(`http://localhost:${servers[0].address().port}`);
    await page.evaluate(async api => {
      await fetch(api + '/api/lines', {mode:'no-cors'}).catch(() => {});
      await new Promise(resolve => {
        const image = new Image();
        image.onload = image.onerror = resolve;
        setTimeout(resolve, 5000);
        image.src = api + '/api/lines/1/audio';
      });
    }, api);
    const actual = await observe();
    assert.deepEqual(actual.calls, [], `${name}: no rejected request side effect`);
    for (const path of ['/api/lines', '/api/lines/1/audio']) {
      assert(actual.received.some(item => item.path === path && item.origin === ''), `${name}: origin-less cross-site ${path} actually reached server`);
    }
    for (const [type,path] of [['http','/api/capture/start'], ['http','/api/settings'], ['websocket','/api/ws']]) {
      assert(actual.received.some(item => item.type === type && item.path === path && item.origin === untrusted), `${name}: rejected ${path} actually reached server`);
    }
    await context.close();
    await browser.close();
    browser = null;
    console.log(`${name}: actual HTTP/preflight/WebSocket origins verified`);
  }
  await reset();
  assert.equal((await fetch(api + '/api/capture/stop', {method:'POST'})).status, 200);
  assert((await observe()).calls.includes('stop'), 'Origin-less trusted updater fallback remains available');
} catch (error) {
  if (stderr.trim()) console.error(stderr.slice(-4000));
  throw error;
} finally {
  await browser?.close();
  for (const server of servers) {server.closeAllConnections(); await new Promise(resolve => server.close(resolve));}
  python.kill();
  await Promise.race([once(python, 'exit').catch(() => {}), new Promise(resolve => setTimeout(resolve, 5000))]);
}
