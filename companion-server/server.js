// AL-GHUL companion: static page + a tiny live-sync WebSocket server.
// The presenter (connected with the right key) sets the current stage; every
// other connected phone follows instantly. Late joiners get the current stage
// on connect, and everyone sees a live count of who is here.
const http = require('http');
const fs   = require('fs');
const path = require('path');
const { WebSocketServer } = require('ws');

const PORT = process.env.PORT || 3001;
const KEY  = process.env.PRESENT_KEY || 'changeme';
const HTML = fs.readFileSync(path.join(__dirname, 'public', 'index.html'));
let DECK = null;
try { DECK = fs.readFileSync(path.join(__dirname, 'public', 'deck.html')); } catch (e) {}

let stage = 0;       // the current stage the presenter is on
let status = null;   // last neutralization status pushed by the Watcher/sentinel
let poll = { tallies: [0, 0, 0, 0], revealed: false, epoch: 1 };  // the WPA2 survey

function pollMsg() {
  return { t: 'poll', tallies: poll.tallies,
           total: poll.tallies.reduce((a, b) => a + b, 0),
           revealed: poll.revealed, epoch: poll.epoch };
}

const server = http.createServer((req, res) => {
  const u = new URL(req.url || '/', 'http://x');
  const p = u.pathname;
  if (p === '/' || p === '/index.html') {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache' });
    res.end(HTML);
  } else if (p === '/deck' || p === '/deck.html') {
    if (!DECK) { res.writeHead(404); res.end('no deck'); return; }
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache' });
    res.end(DECK);
  } else if (p === '/healthz') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('ok');
  } else if (p === '/poll' && req.method === 'GET') {
    // The presenter deck reads the live tally from here (CORS-open, read-only).
    res.writeHead(200, { 'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-cache' });
    res.end(JSON.stringify(pollMsg()));
  } else if (p === '/vote' && req.method === 'POST') {
    // Audience votes on the WPA2/WPA3 survey (no key: anyone watching can vote).
    // Once the presenter has revealed/finished, voting is locked.
    const opt = parseInt(u.searchParams.get('option'), 10);
    const ep = parseInt(u.searchParams.get('epoch'), 10);
    if (!poll.revealed && opt >= 0 && opt < poll.tallies.length && (isNaN(ep) || ep === poll.epoch)) {
      poll.tallies[opt]++; broadcast(pollMsg());
    }
    res.writeHead(200, { 'Content-Type': 'text/plain' }); res.end('ok');
  } else if (p === '/poll-reset' && req.method === 'POST') {
    // Clear the survey for a fresh start (key-gated).
    if (u.searchParams.get('key') !== KEY) { res.writeHead(403); res.end('forbidden'); return; }
    poll = { tallies: [0, 0, 0, 0], revealed: false, epoch: poll.epoch + 1 }; broadcast(pollMsg());
    res.writeHead(200, { 'Content-Type': 'text/plain' }); res.end('ok');
  } else if (p === '/reveal' && req.method === 'POST') {
    // The presenter reveals the real statistics (key-gated).
    if (u.searchParams.get('key') !== KEY) { res.writeHead(403); res.end('forbidden'); return; }
    poll.revealed = true; broadcast(pollMsg());
    res.writeHead(200, { 'Content-Type': 'text/plain' }); res.end('ok');
  } else if (p === '/nav' && req.method === 'POST') {
    // The presenter's slide deck pushes its current stage here as she advances;
    // every audience phone jumps to it. Key-gated.
    if (u.searchParams.get('key') !== KEY) {
      res.writeHead(403, { 'Content-Type': 'text/plain' }); res.end('forbidden'); return;
    }
    let body = '';
    req.on('data', (c) => { body += c; if (body.length > 1024) req.destroy(); });
    req.on('end', () => {
      let data; try { data = JSON.parse(body || '{}'); } catch (e) { data = {}; }
      if (Number.isInteger(data.stage)) { stage = data.stage; broadcast({ t: 'stage', i: stage }); }
      res.writeHead(200, { 'Content-Type': 'text/plain' }); res.end('ok');
    });
  } else if (p === '/event' && req.method === 'POST') {
    // The Watcher's sentinel pushes a live neutralization result here; it drives
    // every phone's "TARGET DOWN" badge and latency numbers. Key-gated.
    if (u.searchParams.get('key') !== KEY) {
      res.writeHead(403, { 'Content-Type': 'text/plain' }); res.end('forbidden'); return;
    }
    let body = '';
    req.on('data', (c) => { body += c; if (body.length > 4096) req.destroy(); });
    req.on('end', () => {
      let data; try { data = JSON.parse(body || '{}'); } catch (e) { data = {}; }
      status = { t: 'status', down: data.down !== false,
                 detect: data.detect, neutralize: data.neutralize,
                 total: data.total, target: data.target, ts: Date.now() };
      broadcast(status);
      res.writeHead(200, { 'Content-Type': 'text/plain' }); res.end('ok');
    });
  } else {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('not found');
  }
});

const wss = new WebSocketServer({ server, path: '/ws' });

function broadcast(obj) {
  const s = JSON.stringify(obj);
  for (const c of wss.clients) if (c.readyState === 1) { try { c.send(s); } catch (e) {} }
}
function sendCount() { broadcast({ t: 'count', n: wss.clients.size }); }

wss.on('connection', (ws, req) => {
  let isPresenter = false;
  try {
    const u = new URL(req.url, 'http://x');
    isPresenter = u.searchParams.get('key') === KEY;
  } catch (e) {}
  ws.isPresenter = isPresenter;

  // catch the new arrival up to the current stage (and status), then the count
  try { ws.send(JSON.stringify({ t: 'stage', i: stage })); } catch (e) {}
  if (status) { try { ws.send(JSON.stringify(status)); } catch (e) {} }
  try { ws.send(JSON.stringify(pollMsg())); } catch (e) {}
  sendCount();

  ws.on('message', (data) => {
    let m; try { m = JSON.parse(data.toString()); } catch (e) { return; }
    // only an authenticated presenter may move the room
    if (m && m.t === 'set' && ws.isPresenter && Number.isInteger(m.i)) {
      stage = m.i;
      broadcast({ t: 'stage', i: stage });
    }
  });
  ws.on('close', sendCount);
  ws.on('error', () => {});
});

// keep idle connections alive through the reverse proxy
setInterval(() => {
  for (const c of wss.clients) { if (c.readyState === 1) { try { c.ping(); } catch (e) {} } }
}, 30000);

server.listen(PORT, '0.0.0.0', () => console.log('AL-GHUL companion listening on ' + PORT));
