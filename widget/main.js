// Floating, always-on-top progress widget. Usage: electron . <path/to/widget.html>
// Remembers where the user leaves it (any display) in widget-bounds.json next to the html.
const { app, BrowserWindow, screen, ipcMain } = require('electron');
const fs = require('fs');
const path = require('path');
const file = process.argv.find((a) => a.endsWith('widget.html'));
const store = path.join(path.dirname(file), 'widget-bounds.json');
const W = 400, H = 380;

function savedPosition() {
  try {
    const { x, y } = JSON.parse(fs.readFileSync(store, 'utf8'));
    // Only reuse it if that point is still on a connected display.
    const on = screen.getAllDisplays().some((d) => x >= d.bounds.x && x < d.bounds.x + d.bounds.width && y >= d.bounds.y && y < d.bounds.y + d.bounds.height);
    return on ? { x, y } : null;
  } catch { return null; }
}

app.whenReady().then(() => {
  const { workArea } = screen.getPrimaryDisplay();
  const pos = savedPosition() || { x: workArea.x + workArea.width - W - 16, y: workArea.y + 16 };
  const win = new BrowserWindow({
    width: W, height: H, x: pos.x, y: pos.y,
    frame: false, transparent: true, resizable: false, alwaysOnTop: true, skipTaskbar: true,
    hasShadow: false, fullscreenable: false,
    webPreferences: { sandbox: true, preload: path.join(__dirname, 'preload.js') },
  });
  win.setAlwaysOnTop(true, 'floating');
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  const save = () => { const [x, y] = win.getPosition(); fs.writeFile(store, JSON.stringify({ x, y }), () => {}); };
  win.on('moved', save);
  // Drag: the page reports mouse down/up; while down, the window follows the cursor.
  let drag = null;
  ipcMain.on('avq-drag', (_e, on) => {
    if (drag) { clearInterval(drag.timer); drag = null; save(); }
    if (!on) return;
    const c = screen.getCursorScreenPoint(); const [x, y] = win.getPosition();
    const dx = c.x - x, dy = c.y - y;
    drag = { timer: setInterval(() => {
      const p = screen.getCursorScreenPoint(); win.setPosition(p.x - dx, p.y - dy);
    }, 16) };
  });
  ipcMain.on('avq-close', () => win.close());
  win.on('blur', () => { if (drag) { clearInterval(drag.timer); drag = null; save(); } });
  // Fit the height to the card after each reload (the page puts its height in the title),
  // keeping the window exactly where it is.
  win.webContents.on('page-title-updated', (_e, t) => {
    const n = parseInt(t, 10);
    if (!(n > 80 && n < 1200)) return;
    const [x, y] = win.getPosition();
    win.setBounds({ x, y, width: W, height: n });
  });
  win.loadFile(file);
  win.on('closed', () => app.quit());
});
app.on('window-all-closed', () => app.quit());
if (app.dock) app.dock.hide();
