import { useEffect, useState } from 'react';
import { apiFetch, apiJson } from '../lib/api';

function loadPicker() {
  return new Promise((resolve, reject) => {
    if (window.google?.picker) { resolve(); return; }
    const script = document.createElement('script');
    script.src = 'https://apis.google.com/js/api.js';
    script.onerror = () => reject(new Error('Could not load Google Picker.'));
    script.onload = () => window.gapi.load('picker', { callback: resolve, onerror: reject });
    document.head.appendChild(script);
  });
}

export default function DriveConnection() {
  const [status, setStatus] = useState(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const refresh = () => apiJson('/api/drive/status').then(setStatus);
  useEffect(() => { refresh().catch(() => setMessage('Could not check Google Drive.')); }, []);

  async function chooseFolder() {
    setBusy(true);
    setMessage('');
    try {
      const config = await apiJson('/api/drive/picker');
      await loadPicker();
      const view = new window.google.picker.DocsView(window.google.picker.ViewId.FOLDERS)
        .setIncludeFolders(true).setSelectFolderEnabled(true);
      new window.google.picker.PickerBuilder().addView(view)
        .setOAuthToken(config.token).setDeveloperKey(config.api_key).setAppId(config.app_id)
        .setCallback(async data => {
          if (data.action !== window.google.picker.Action.PICKED) return;
          try {
            await apiJson('/api/drive/folder', { method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ id: data.docs[0].id }) });
            await refresh();
            setMessage('Folder selected.');
          } catch (error) { setMessage(error.detail || 'Could not select this folder.'); }
        }).build().setVisible(true);
    } catch (error) { setMessage(error.detail || error.message); }
    finally { setBusy(false); }
  }

  async function disconnect() {
    if (!window.confirm('Disconnect Google Drive from this workspace?')) return;
    setBusy(true);
    try {
      const response = await apiFetch('/api/drive/connection', { method: 'DELETE' });
      if (!response.ok) throw new Error();
      await refresh();
      setMessage('Google Drive disconnected.');
    } catch { setMessage('Could not disconnect Google Drive.'); }
    finally { setBusy(false); }
  }

  return <section className="card p-4 sm:p-6 mb-8 space-y-3">
    <h2 className="font-display text-lg text-ink">Google Drive</h2>
    {!status ? <p>Checking connection…</p> : !status.available
      ? <p className="text-sm text-muted">Configure the Google Drive credentials on the server to connect.</p>
      : <>
        <p className="text-sm">{status.folder_name ? `Selected folder: ${status.folder_name}` : status.connected ? 'Connected. Choose a folder.' : 'Connect your Google account to choose a folder.'}</p>
        <div className="flex flex-wrap gap-3">
          <a className="btn-ghost px-4 py-2" href="/api/drive/connect">{status.connected ? 'Reconnect Google' : 'Connect Google'}</a>
          {status.connected && <button className="btn-ghost px-4 py-2" disabled={busy} onClick={chooseFolder}>Choose folder</button>}
          {status.connected && <button className="btn-quiet px-4 py-2" disabled={busy} onClick={disconnect}>Disconnect</button>}
        </div>
        <p className="text-sm text-muted">The connection selects a folder. Clip uploads to Drive are not yet enabled.</p>
      </>}
    {message && <p role="status" className="text-sm">{message}</p>}
  </section>;
}
