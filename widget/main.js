// Floating, always-on-top progress widget. Usage: electron . <path/to/widget.html>
// Remembers where the user leaves it (any display) and the size they give it in widget-bounds.json next to
// the html. The height follows the card up to a cap (the user's chosen height, or a default); past it the
// step list scrolls inside the card.
const { app, BrowserWindow, screen, ipcMain } = require('electron');
const fs = require('fs');
const path = require('path');
const file = process.argv.find((a) => a.endsWith('widget.html'));
const store = path.join(path.dirname(file), 'widget-bounds.json');
const MIN_W = 320, MAX_W = 720, MIN_H = 200, DEFAULT_W = 400, DEFAULT_CAP = 520;

function saved() {
  try { return JSON.parse(fs.readFileSync(store, 'utf8')); } catch { return {}; }
}

function savedPosition(s) {
  const { x, y } = s;
  if (typeof x !== 'number' || typeof y !== 'number') return null;
  // Only reuse it if that point is still on a connected display.
  const on = screen.getAllDisplays().some((d) => x >= d.bounds.x && x < d.bounds.x + d.bounds.width && y >= d.bounds.y && y < d.bounds.y + d.bounds.height);
  return on ? { x, y } : null;
}

app.whenReady().then(() => {
  const { workArea } = screen.getPrimaryDisplay();
  const s = saved();
  let width = Math.min(MAX_W, Math.max(MIN_W, s.width || DEFAULT_W));
  // The tallest the window grows on its own: the height the user last gave it, else the default.
  let cap = Math.max(MIN_H, Math.min(s.height || DEFAULT_CAP, workArea.height - 32));
  let natural = null; // the card's full height, reported by the page after each render
  const pos = savedPosition(s) || { x: workArea.x + workArea.width - width - 16, y: workArea.y + 16 };
  const win = new BrowserWindow({
    width, height: Math.min(380, cap), x: pos.x, y: pos.y,
    frame: false, transparent: true, resizable: false, alwaysOnTop: true, skipTaskbar: true,
    hasShadow: false, fullscreenable: false,
    webPreferences: { sandbox: true, preload: path.join(__dirname, 'preload.js') },
  });
  win.setAlwaysOnTop(true, 'floating');
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  const save = () => {
    const [x, y] = win.getPosition();
    const out = { x, y };
    if (s.width || s.height) { out.width = width; out.height = cap; }
    fs.writeFile(store, JSON.stringify(out), () => {});
  };
  win.on('moved', save);
  // Drag and resize: the page reports mouse down/up; while down, the window follows the cursor.
  let op = null;
  const stop = () => { if (op) { clearInterval(op.timer); op = null; save(); } };
  ipcMain.on('avq-drag', (_e, on) => {
    stop();
    if (!on) return;
    const c = screen.getCursorScreenPoint(); const [x, y] = win.getPosition();
    const dx = c.x - x, dy = c.y - y;
    op = { timer: setInterval(() => {
      const p = screen.getCursorScreenPoint(); win.setPosition(p.x - dx, p.y - dy);
    }, 16) };
  });
  ipcMain.on('avq-resize', (_e, on) => {
    stop();
    if (!on) return;
    const c = screen.getCursorScreenPoint(); const [x, y] = win.getPosition(); const [w0, h0] = win.getSize();
    const maxH = screen.getDisplayNearestPoint(c).workArea.height - 16;
    op = { timer: setInterval(() => {
      const p = screen.getCursorScreenPoint();
      width = Math.round(Math.min(MAX_W, Math.max(MIN_W, w0 + p.x - c.x)));
      cap = Math.round(Math.min(maxH, Math.max(MIN_H, h0 + p.y - c.y)));
      s.width = width; s.height = cap;
      win.setBounds({ x, y, width, height: cap });
    }, 16) };
  });
  ipcMain.on('avq-close', () => win.close());
  win.on('blur', stop);
  // Fit the height to the card after each render (the page puts its full height in the title), up to the
  // cap, keeping the window exactly where it is.
  win.webContents.on('page-title-updated', (_e, t) => {
    const n = parseInt(t, 10);
    if (!(n > 80 && n < 5000)) return;
    natural = n;
    if (op) return;
    const [x, y] = win.getPosition();
    win.setBounds({ x, y, width, height: Math.min(natural, cap) });
  });
  win.loadFile(file);
  win.on('closed', () => app.quit());
});
app.on('window-all-closed', () => app.quit());
if (app.dock) app.dock.hide();
