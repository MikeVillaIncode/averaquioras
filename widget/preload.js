// Bridge for the widget page: start/stop a window drag or resize, and close the window.
// The page cannot move or size its own window, and CSS drag regions (-webkit-app-region) put the close
// button's hit area in the wrong place on macOS (transparent windows can't be resized from their edges
// either), so dragging and resizing are done by the main process instead.
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('avq', {
  dragStart: () => ipcRenderer.send('avq-drag', true),
  dragEnd: () => ipcRenderer.send('avq-drag', false),
  resizeStart: () => ipcRenderer.send('avq-resize', true),
  resizeEnd: () => ipcRenderer.send('avq-resize', false),
  close: () => ipcRenderer.send('avq-close'),
});
