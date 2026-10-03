const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('flight', Object.freeze({
  initial: () => ipcRenderer.invoke('initial'),
  openRun: () => ipcRenderer.invoke('open-run'),
  chooseData: () => ipcRenderer.invoke('choose-data'),
  run: payload => ipcRenderer.invoke('run', payload),
  save: payload => ipcRenderer.invoke('save', payload)
}));
