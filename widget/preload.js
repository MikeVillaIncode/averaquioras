// Bridge for the widget page: start/stop a window drag and close the window.
// The page cannot move its own window, and CSS drag regions (-webkit-app-region) put the close
// button's hit area in the wrong place on macOS, so dragging is done by the main process instead.
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('avq', {
  dragStart: () => ipcRenderer.send('avq-drag', true),
  dragEnd: () => ipcRenderer.send('avq-drag', false),
  close: () => ipcRenderer.send('avq-close'),
});
