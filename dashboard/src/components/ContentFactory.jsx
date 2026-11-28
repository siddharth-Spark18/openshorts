import { useEffect, useState } from 'react';
import { apiJson } from '../lib/api';

const types = { gaming_clips: 'Gaming highlights', workplace_skits: 'Workplace skits' };
const statuses = { needs_review: 'Needs review', approved: 'Approved', rejected: 'Rejected' };

function ProjectSettings({ channel, busy, save, disconnectAccount, retryProduction }) {
  const [style, setStyle] = useState(channel.settings.style);
  const [dailyTarget, setDailyTarget] = useState(channel.settings.daily_target);
  const [publishingMode, setPublishingMode] = useState(channel.settings.publishing_mode);
  return <div className="space-y-4 border-t border-rule pt-4">
    <div>
      <h3 className="text-ink font-semibold">Connected accounts</h3>
      <p className="text-sm text-muted mt-1">YouTube: {channel.connections.youtube.connected ? channel.connections.youtube.channel_title : 'Not connected'}</p>
      {channel.connections.youtube.connected
        ? <button type="button" className="btn-quiet px-3 py-2" disabled={busy} onClick={() => disconnectAccount(channel.id, 'youtube')}>Disconnect YouTube</button>
        : channel.connections.youtube.available ? <a className="text-brass underline" href={`/api/factory/channels/${channel.id}/youtube/connect`}>Connect YouTube</a>
          : <p className="text-sm text-muted">YouTube connection needs server credentials.</p>}
      <p className="text-sm text-muted">Instagram: {channel.connections.instagram.connected ? `@${channel.connections.instagram.username}` : 'Not connected'}</p>
      {channel.connections.instagram.connected
        ? <button type="button" className="btn-quiet px-3 py-2" disabled={busy} onClick={() => disconnectAccount(channel.id, 'instagram')}>Disconnect Instagram</button>
        : channel.connections.instagram.available ? <a className="text-brass underline" href={`/api/factory/channels/${channel.id}/instagram/connect`}>Connect Instagram</a>
          : <p className="text-sm text-muted">Instagram connection needs a Meta app and a professional account.</p>}
    </div>
    <form className="space-y-3" onSubmit={e => { e.preventDefault(); save(channel.id, { style, daily_target: Number(dailyTarget), publishing_mode: publishingMode }); }}>
      <h3 className="text-ink font-semibold">Production settings</h3>
      <label className="block text-sm text-ink" htmlFor={`style-${channel.id}`}>Video style and creative direction</label>
      <textarea id={`style-${channel.id}`} className="input-field w-full" rows={3} maxLength={2000} value={style} onChange={e => setStyle(e.target.value)} placeholder="e.g. Short, funny workplace stories with a surprise ending" />
      <p className="text-sm text-muted">Used when generating workplace skit scripts.</p>
      <label className="block text-sm text-ink" htmlFor={`target-${channel.id}`}>Videos per day</label>
      <input id={`target-${channel.id}`} className="input-field w-full" type="number" min="1" max="20" required value={dailyTarget} onChange={e => setDailyTarget(e.target.value)} />
      <label className="block text-sm text-ink" htmlFor={`mode-${channel.id}`}>Publishing preference</label>
      <select id={`mode-${channel.id}`} className="input-field w-full" value={publishingMode} onChange={e => setPublishingMode(e.target.value)}>
        <option value="manual">Manual publishing</option><option value="automatic">Automatic publishing</option>
      </select>
      <p className="text-sm text-muted">Automatic mode creates workplace skits and publishes them to connected accounts without review, spaced according to your daily target. Manual mode lets you review ideas, scripts, and videos.</p>
      <button className="btn-ghost px-4 py-2" disabled={busy}>Save settings</button>
    </form>
    {channel.auto_production.status === 'failed' && <div role="alert" className="text-sm text-danger">
      <p>{channel.auto_production.error || 'Automatic production stopped.'}</p>
      <button type="button" className="btn-ghost px-3 py-2" disabled={busy} onClick={() => retryProduction(channel.id)}>Retry production</button>
    </div>}
    {['generating', 'rendering'].includes(channel.auto_production.status) && <p role="status" className="text-sm text-muted">Automatic production: {channel.auto_production.status}.</p>}
  </div>;
}

function ScriptEditor({ idea, busy, act, youtubeConnected, instagramConnected }) {
  const [draft, setDraft] = useState(idea.script || '');
  const changed = draft.trim() !== (idea.script || '');
  return <div className="space-y-2 pt-2">
    <p className="text-sm text-ink font-semibold">Script {idea.script_status && `· ${statuses[idea.script_status]}`}</p>
    {idea.script ? <>
      <label htmlFor={`script-${idea.id}`} className="block text-sm text-muted">Edit script</label>
      <textarea id={`script-${idea.id}`} className="input-field w-full" rows={10} maxLength={12000}
        value={draft} onChange={e => setDraft(e.target.value)} />
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-ghost px-3 py-2" disabled={busy || !changed || !draft.trim()}
          onClick={() => act(idea, 'save', draft)}>Save script</button>
        {idea.script_status !== 'approved' && <button type="button" className="btn-ghost px-3 py-2" disabled={busy || changed || idea.status !== 'approved'}
          onClick={() => act(idea, 'approved')}>Approve script</button>}
        {idea.script_status !== 'rejected' && <button type="button" className="btn-quiet px-3 py-2" disabled={busy || changed || idea.status !== 'approved'}
          onClick={() => act(idea, 'rejected')}>Reject script</button>}
      </div>
      <p className="text-sm text-muted">Saving edits sends the script back for review.</p>
    </> : <p className="text-sm text-muted">Approve the idea, then generate a script using your saved Gemini key.</p>}
    <button type="button" className="btn-quiet px-3 py-2" disabled={busy || idea.status !== 'approved' || changed}
      onClick={() => { if (!idea.script || window.confirm('Replace this script with a new draft?')) act(idea, 'generate'); }}>
      {idea.script ? 'Generate a new draft' : 'Generate script'}
    </button>
    {idea.script_status === 'approved' && idea.status === 'approved' && <div className="space-y-2 pt-2">
      <p className="text-sm text-muted">Render a simple illustrated draft with offline voices. Rendering may take several minutes.</p>
      <button type="button" className="btn-ghost px-3 py-2" disabled={busy || changed || idea.render_status === 'processing'} onClick={() => act(idea, 'render')}>Render skit</button>
      {idea.render_status === 'processing' && <p role="status" className="text-sm text-muted">Rendering in the background. You can leave this page.</p>}
      {idea.render_status === 'failed' && <p role="alert" className="text-sm text-danger">{idea.render_error || 'Rendering failed. Try again.'}</p>}
      {idea.video_ready === 1 && <div className="space-y-2">
        <p><a className="text-brass underline" href={`/api/factory/ideas/${idea.id}/video`} download>Download skit</a></p>
        <p className="text-sm text-muted">Video review: {statuses[idea.queue_status] || 'Needs review'}</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-ghost px-3 py-2" disabled={busy || idea.queue_status === 'approved'} onClick={() => act(idea, 'video-approved')}>Approve video</button>
          <button type="button" className="btn-quiet px-3 py-2" disabled={busy || idea.queue_status === 'rejected'} onClick={() => act(idea, 'video-rejected')}>Reject video</button>
        </div>
        <p className="text-sm text-muted">{idea.schedule_status === 'pending' ? `Scheduled for YouTube: ${new Date(idea.scheduled_at).toLocaleString()}` : idea.schedule_status === 'failed' ? 'Scheduled upload failed. Check YouTube Studio before retrying.' : 'In automatic mode, approving a video schedules it for YouTube.'}</p>
        {idea.instagram_schedule_status === 'pending' && <p className="text-sm text-muted">Scheduled for Instagram: {new Date(idea.instagram_scheduled_at).toLocaleString()}</p>}
        {idea.instagram_schedule_status === 'failed' && <p className="text-sm text-muted">Scheduled Instagram upload failed. Check Instagram before retrying.</p>}
        {idea.youtube_publication_status === 'published' && <p><a className="text-brass underline" href={`https://www.youtube.com/watch?v=${encodeURIComponent(idea.youtube_video_id)}`} target="_blank" rel="noreferrer">View published YouTube video</a></p>}
        {['preparing', 'uploading', 'uncertain'].includes(idea.youtube_publication_status) && <p role="status" className="text-sm text-muted">Upload is in progress or its outcome is uncertain. Check YouTube Studio before attempting another upload.</p>}
        {idea.queue_status === 'approved' && youtubeConnected && !['published', 'preparing', 'uploading', 'uncertain'].includes(idea.youtube_publication_status) &&
          <button type="button" className="btn-primary px-3 py-2" disabled={busy} onClick={() => act(idea, 'publish-youtube')}>Publish to YouTube</button>}
        {idea.instagram_publication_status === 'published' && <p className="text-sm text-muted">Published to Instagram.</p>}
        {['preparing', 'uploading', 'uncertain'].includes(idea.instagram_publication_status) && <p role="status" className="text-sm text-muted">Instagram upload is in progress or uncertain. Check Instagram before trying again.</p>}
        {idea.queue_status === 'approved' && instagramConnected && !['published', 'preparing', 'uploading', 'uncertain'].includes(idea.instagram_publication_status) &&
          <button type="button" className="btn-primary px-3 py-2" disabled={busy} onClick={() => act(idea, 'publish-instagram')}>Publish to Instagram</button>}
      </div>}
    </div>}
  </div>;
}

export default function ContentFactory() {
  const [channels, setChannels] = useState(null);
  const [name, setName] = useState('');
  const [type, setType] = useState('workplace_skits');
  const [ideas, setIdeas] = useState({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const data = await apiJson('/api/factory/channels');
    setChannels(data.channels);
  }
  useEffect(() => {
    const load = () => refresh().catch(() => setError('Could not load channels.'));
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, []);

  async function scriptAction(idea, action, text) {
    setBusy(true); setError('');
    try {
      const base = `/api/factory/ideas/${idea.id}/script`;
      const options = action === 'generate' ? { method: 'POST' }
        : { method: action === 'save' ? 'PUT' : 'PATCH', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(action === 'save' ? { script: text, revision: idea.script_revision }
              : { status: action, revision: idea.script_revision }) };
      const ideaBase = base.replace(/\/script$/, '');
      if (action === 'publish-youtube' || action === 'publish-instagram') {
        await apiJson(`${ideaBase}/${action.slice(8)}/publish`, { method: 'POST' });
      } else if (action.startsWith('video-')) {
        await apiJson(`${ideaBase}/video/review`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: action.slice(6), revision: idea.script_revision }) });
      } else {
        await apiJson(action === 'render' ? `${ideaBase}/render` : action === 'generate' || action === 'save' ? base : `${base}/review`, action === 'render' ? { method: 'POST' } : options);
      }
      await refresh();
    } catch (e) { setError(e.detail || 'Could not update the script.'); }
    finally { setBusy(false); }
  }

  async function submitChannel(event) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await apiJson('/api/factory/channels', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, content_type: type }) });
      setName(''); await refresh();
    } catch (e) { setError(e.detail || 'Could not create channel.'); }
    finally { setBusy(false); }
  }
  async function submitIdea(event, channelId) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      await apiJson(`/api/factory/channels/${channelId}/ideas`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ idea: ideas[channelId] || '' }) });
      setIdeas(old => ({ ...old, [channelId]: '' })); await refresh();
    } catch (e) { setError(e.detail || 'Could not save idea.'); }
    finally { setBusy(false); }
  }
  async function generateIdeas(channelId) {
    setBusy(true); setError('');
    try {
      await apiJson(`/api/factory/channels/${channelId}/ideas/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ count: 3 }) });
      await refresh();
    } catch (e) { setError(e.detail || 'Could not generate ideas.'); }
    finally { setBusy(false); }
  }
  async function saveSettings(channelId, settings) {
    setBusy(true); setError('');
    try {
      await apiJson(`/api/factory/channels/${channelId}/settings`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings) });
      await refresh();
    } catch (e) { setError(e.detail || 'Could not save project settings.'); }
    finally { setBusy(false); }
  }
  async function disconnectAccount(channelId, platform) {
    setBusy(true); setError('');
    try {
      await apiJson(`/api/factory/channels/${channelId}/${platform}/connection`, { method: 'DELETE' });
      await refresh();
    } catch (e) { setError(e.detail || 'Could not disconnect the account.'); }
    finally { setBusy(false); }
  }
  async function retryProduction(channelId) {
    setBusy(true); setError('');
    try {
      await apiJson(`/api/factory/channels/${channelId}/production/retry`, { method: 'POST' });
      await refresh();
    } catch (e) { setError(e.detail || 'Could not retry production.'); }
    finally { setBusy(false); }
  }
  async function review(id, status) {
    setBusy(true); setError('');
    try {
      await apiJson(`/api/factory/ideas/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }) });
      await refresh();
    } catch (e) { setError(e.detail || 'Could not update idea.'); }
    finally { setBusy(false); }
  }

  return <section className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
    <header><p className="text-sm text-muted">Your workspace</p>
      <h1 className="font-display text-3xl text-ink">Content factory</h1>
      <p className="text-sm text-muted mt-2">Create a project for each channel and plan its videos.</p></header>
    <div className="card p-4 text-sm text-muted">Create workplace skit drafts with basic illustrations and offline voices. Approved videos can be published to a connected YouTube channel.</div>
    <form onSubmit={submitChannel} className="card p-4 space-y-3">
      <h2 className="font-display text-xl text-ink">Create a project</h2>
      <label htmlFor="factory-name" className="block text-sm text-ink">Project name</label>
      <input id="factory-name" className="input-field w-full" value={name} onChange={e => setName(e.target.value)} maxLength={100} placeholder="e.g. Workplace stories" required />
      <label htmlFor="factory-type" className="block text-sm text-ink">Content type</label>
      <select id="factory-type" className="input-field w-full" value={type} onChange={e => setType(e.target.value)}>
        {Object.entries(types).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      <button className="btn-primary px-4 py-2" disabled={busy}>Create project</button>
    </form>
    {error && <p role="alert" className="text-danger">{error}</p>}
    {channels === null && !error && <p>Loading channels…</p>}
    {channels?.length === 0 && <p className="text-sm text-muted">Create your first project to start collecting ideas.</p>}
    {channels?.map(channel => <article key={channel.id} className="card p-4 space-y-4">
      <div><h2 className="font-display text-xl text-ink">{channel.name}</h2><p className="text-sm text-muted">{types[channel.content_type]}</p></div>
      <ProjectSettings channel={channel} busy={busy} save={saveSettings} disconnectAccount={disconnectAccount} retryProduction={retryProduction} />
      <form onSubmit={e => submitIdea(e, channel.id)} className="space-y-2">
        <label htmlFor={`idea-${channel.id}`} className="block text-sm text-ink">New idea</label>
        <textarea id={`idea-${channel.id}`} className="input-field w-full" rows={3} maxLength={2000} required
          value={ideas[channel.id] || ''} onChange={e => setIdeas(old => ({ ...old, [channel.id]: e.target.value }))}
          placeholder="A manager tries to ban lunch breaks…" />
        <button className="btn-ghost px-4 py-2" disabled={busy}>Save idea</button>
      </form>
      <h3 className="text-ink font-semibold">Ideas</h3>
      {channel.content_type === 'workplace_skits' && <button type="button" className="btn-ghost px-4 py-2" disabled={busy} onClick={() => generateIdeas(channel.id)}>Generate 3 ideas</button>}
      {channel.ideas.length === 0 && <p className="text-sm text-muted">No ideas yet.</p>}
      <div className="space-y-3">{channel.ideas.map(idea => <div key={idea.id} className="border-t border-rule pt-3 space-y-2">
        <p className="text-ink whitespace-pre-wrap">{idea.idea}</p><p className="text-sm text-muted">{statuses[idea.status]}</p>
        <div className="flex flex-wrap gap-2">
          {idea.status !== 'approved' && <button className="btn-ghost px-3 py-2" disabled={busy} onClick={() => review(idea.id, 'approved')}>Approve</button>}
          {idea.status !== 'rejected' && <button className="btn-quiet px-3 py-2" disabled={busy} onClick={() => review(idea.id, 'rejected')}>Reject</button>}
          {idea.status !== 'needs_review' && <button className="btn-quiet px-3 py-2" disabled={busy} onClick={() => review(idea.id, 'needs_review')}>Move to review</button>}
        </div>
        {channel.content_type === 'workplace_skits' && <ScriptEditor key={`${idea.id}-${idea.script_revision || 0}`} idea={idea} busy={busy} act={scriptAction} youtubeConnected={channel.connections.youtube.connected} instagramConnected={channel.connections.instagram.connected} />}
      </div>)}</div>
    </article>)}
  </section>;
}
