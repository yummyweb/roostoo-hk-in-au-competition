const { app, BrowserWindow, ipcMain, dialog, Menu } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs/promises');
const { existsSync } = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
if (process.env.FLIGHT_USER_DATA) app.setPath('userData', process.env.FLIGHT_USER_DATA);
let window, busy = false;
const allowedDatasets = new Set();
function python(payload) {
  return new Promise((resolve, reject) => {
    let localML;
    for (let dir = root; ; dir = path.dirname(dir)) {
      const candidate = path.join(dir, '.venv-lstm', 'bin', 'python');
      if (existsSync(candidate)) { localML = candidate; break; }
      if (path.dirname(dir) === dir) break;
    }
    const executable = process.env.ROOSTOO_PYTHON || (['lstm_prediction', 'cross_asset'].includes(payload.config?.strategy) ? localML : null) || ['/opt/homebrew/bin/python3', '/usr/local/bin/python3', '/usr/bin/python3'].find(existsSync) || 'python3';
    const child = spawn(executable, ['-m', 'roostoo.cli', 'bridge'], { cwd: root, env: { ...process.env, PYTHONPATH: root }, stdio: ['pipe', 'pipe', 'pipe'] });
    let out = '', err = '', bytes = 0;
    const timeout = ['lstm_prediction', 'cross_asset'].includes(payload.config?.strategy) ? 900000 : 300000;
    const timer = setTimeout(() => { child.kill(); reject(new Error('Backtest exceeded its time limit. Use the CLI for larger datasets.')); }, timeout);
    child.stdout.on('data', d => { bytes += d.length; if (bytes > 150e6) child.kill(); else out += d; });
    child.stderr.on('data', d => { err = (err + d).slice(-10000); });
    child.on('error', e => { clearTimeout(timer); reject(e); });
    child.on('close', code => { clearTimeout(timer); if (code !== 0) return reject(new Error(err || 'Backtest process failed')); try { resolve(JSON.parse(out)); } catch { reject(new Error('Invalid backtest output')); } });
    child.stdin.end(JSON.stringify(payload));
  });
}
function validateRun(run) {
  if (run.schema_version !== 1 || !Array.isArray(run.trades) || !Array.isArray(run.equity_curve) || !run.equity_curve.length || !Array.isArray(run.bars) || !Array.isArray(run.pairs) || !run.metrics || !run.config || !run.manifest) throw new Error('This is not a Flight Deck run.json file.');
  if (run.equity_curve.some(p => !Number.isFinite(p.timestamp) || !Number.isFinite(p.equity))) throw new Error('Run contains invalid chart data.');
  if (!Array.isArray(run.orders) || !Array.isArray(run.warnings) || run.warnings.some(x => typeof x !== 'string')) throw new Error('Run is missing audit fields.');
  if (run.pairs.some(p => typeof p !== 'string' || !/^[A-Z0-9]+\/USD$/.test(p))) throw new Error('Invalid pair names.');
  if (![run.evaluation_start, run.evaluation_end, run.interval_ms].every(Number.isFinite) || run.evaluation_end <= run.evaluation_start) throw new Error('Invalid evaluation range.');
  const ids = new Set();
  for (const t of run.trades) {
    if (!Number.isSafeInteger(t.id) || ids.has(t.id) || !run.pairs.includes(t.pair) || !['LONG', 'SHORT'].includes(t.side) || !['OPEN', 'CLOSED'].includes(t.status)) throw new Error('Invalid trade identity or status.');
    ids.add(t.id);
    if (!['entry_time','entry_price','quantity','net_pnl','return_pct','entry_fee','exit_fee','holding_hours'].every(k => Number.isFinite(t[k]))) throw new Error('Invalid trade accounting data.');
  }
  for (const b of run.bars) if (!run.pairs.includes(b.pair) || !['timestamp','open','high','low','close'].every(k => Number.isFinite(b[k]))) throw new Error('Invalid price data.');

  return run;
}
async function readRun(file) {
  const stat = await fs.stat(file); if (stat.size > 150e6) throw new Error('Run file exceeds 150 MB.');
  return validateRun(JSON.parse(await fs.readFile(file, 'utf8')));
}
app.whenReady().then(() => {
  ipcMain.handle('initial', async () => {
    for (const file of [path.join(app.getPath('userData'), 'last-run.json'), path.join(root, 'desktop/sample-run.json'), path.join(root, 'runs/research/run.json'), path.join(root, 'runs/demo/run.json')]) {
      if (existsSync(file)) { try { return await readRun(file); } catch {} }
    }
    return python({ config: { allow_short: true } });
  });
  ipcMain.handle('open-run', async () => {
    const choice = await dialog.showOpenDialog(window, { title: 'Open backtest run', filters: [{ name: 'Flight Deck run', extensions: ['json'] }], properties: ['openFile'] });
    return choice.canceled ? null : readRun(choice.filePaths[0]);
  });
  ipcMain.handle('choose-data', async () => {
    const choice = await dialog.showOpenDialog(window, { title: 'Choose OHLCV dataset', filters: [{ name: 'OHLCV data', extensions: ['csv'] }], properties: ['openFile'] });
    if (choice.canceled) return null;
    allowedDatasets.add(choice.filePaths[0]); return choice.filePaths[0];
  });
  ipcMain.handle('run', async (_, payload) => {
    if (busy) throw new Error('A backtest is already running.');
    if (payload.data_path && !allowedDatasets.has(payload.data_path)) throw new Error('Choose the dataset with the file picker first.');
    busy = true;
    try {
      const result = await python({ config: payload.config, data_path: payload.data_path || undefined });
      await fs.writeFile(path.join(app.getPath('userData'), 'last-run.json'), JSON.stringify(result));
      return result;
    } finally { busy = false; }
  });
  ipcMain.handle('save', async (_, payload) => {
    if (!['json', 'csv'].includes(payload.type) || typeof payload.content !== 'string' || payload.content.length > 150e6) throw new Error('Invalid export');
    const choice = await dialog.showSaveDialog(window, { defaultPath: payload.type === 'json' ? 'run.json' : 'trades.csv', filters: [{ name: 'Export', extensions: [payload.type] }] });
    if (!choice.canceled) { await fs.writeFile(choice.filePath, payload.content); return true; } return false;
  });
  window = new BrowserWindow({ width: 1512, height: 1000, minWidth: 1100, minHeight: 760, title: 'Flight Deck · Roostoo Research', icon: path.join(__dirname, 'icon.png'), backgroundColor: '#101312', titleBarStyle: 'hiddenInset', trafficLightPosition: { x: 22, y: 22 }, webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true } });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', e => e.preventDefault());
  window.loadFile(path.join(__dirname, 'ui/index.html'));
  Menu.setApplicationMenu(Menu.buildFromTemplate([{ role: 'appMenu' }, { role: 'editMenu' }, { role: 'viewMenu' }, { role: 'windowMenu' }]));
  app.on('activate', () => window.show());
});
app.on('window-all-closed', () => app.quit());
