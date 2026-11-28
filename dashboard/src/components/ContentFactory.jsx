import { useEffect, useState } from 'react';
import { ArrowRight, Clapperboard, Film, Plus, Settings2, Sparkles, Youtube } from 'lucide-react';
import { apiJson } from '../lib/api';

const types = { gaming_clips: 'Gaming highlights', workplace_skits: 'Workplace skits' };
const statuses = { needs_review: 'Needs review', approved: 'Approved', rejected: 'Rejected' };
const voiceNames = { 'en-US-Neural2-F': 'Voice F', 'en-US-Neural2-D': 'Voice D', 'en-US-Neural2-C': 'Voice C', 'en-US-Neural2-J': 'Voice J' };

function VoiceSettings({ channel, busy, save }) {
  const [provider, setProvider] = useState(channel.voice_settings.provider);
  const [voiceOne, setVoiceOne] = useState(channel.voice_settings.voice_one);
  const [voiceTwo, setVoiceTwo] = useState(channel.voice_settings.voice_two);
  return <form className="space-y-4" onSubmit={e => { e.preventDefault(); save(channel.id, { provider, voice_one: voiceOne, voice_two: voiceTwo }); }}>
    <div><h3 className="text-ink font-semibold">Character voices</h3><p className="text-sm text-muted mt-1">Choose how dialogue is spoken when the next video is rendered.</p></div>
    <label className="block text-sm text-ink" htmlFor={`voice-provider-${channel.id}`}>Voice engine</label>
    <select id={`voice-provider-${channel.id}`} className="input-field w-full" value={provider} onChange={e => setProvider(e.target.value)}>
      <option value="offline">Basic offline voices</option><option value="google">Google Cloud Neural2</option>
    </select>
    {provider === 'google' && <>
      <div className="grid sm:grid-cols-2 gap-4">{[[voiceOne, setVoiceOne, 'First character'], [voiceTwo, setVoiceTwo, 'Second character']].map(([value, setter, label]) => <label key={label} className="text-sm text-ink space-y-2"><span className="block">{label}</span><select className="input-field w-full" value={value} onChange={e => setter(e.target.value)}>{Object.entries(voiceNames).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>)}</div>
      <p className="text-sm text-muted">Requires Google Cloud Text-to-Speech credentials and billing setup. This workspace limits requests to 750,000 characters per UTC month; other Google usage is not included.</p>
    </>}
    <button className="btn-ghost px-4 py-2" disabled={busy}>Save voices</button>
  </form>;
}

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
      <p className="text-sm text-muted">Render an illustrated draft using this project’s voice settings.</p>
      <button type="button" className="btn-ghost px-3 py-2" disabled={busy || changed || idea.render_status === 'processing'} onClick={() => act(idea, 'render')}>Render skit</button>
      {idea.render_status === 'processing' && <p role="status" className="text-sm text-muted">Rendering in the background. You can leave this page.</p>}
      {idea.render_status === 'failed' && <p role="alert" className="text-sm text-danger">{idea.render_error || 'Rendering failed. Try again.'}</p>}
      {idea.video_ready === 1 && <div className="space-y-2">
        <video controls preload="metadata" playsInline className="w-full max-w-[260px] rounded-lg bg-black" src={`/api/factory/ideas/${idea.id}/video?inline=true`} />
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
  const [selectedId, setSelectedId] = useState(null);
  const [view, setView] = useState('drafts');
  const [showCreate, setShowCreate] = useState(false);

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
      const created = await apiJson('/api/factory/channels', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, content_type: type }) });
      setName(''); setSelectedId(created.id); setShowCreate(false); await refresh();
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
  async function saveVoice(channelId, settings) {
    setBusy(true); setError('');
    try {
      await apiJson(`/api/factory/channels/${channelId}/voice`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings) });
      await refresh();
    } catch (e) { setError(e.detail || 'Could not save voices.'); }
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

  const selected = channels?.find(channel => channel.id === selectedId) || channels?.[0];
  const readyCount = selected?.ideas.filter(idea => idea.video_ready === 1).length || 0;
  const connectedCount = selected ? Number(selected.connections.youtube.connected) + Number(selected.connections.instagram.connected) : 0;

  return <section className="max-w-6xl mx-auto px-4 py-8 sm:px-8 sm:py-10 space-y-8">
    <header className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between border-b border-rule pb-7">
      <div><p className="text-xs font-semibold tracking-[0.18em] uppercase text-muted">Your workspace / Create</p>
        <h1 className="font-display text-4xl sm:text-5xl text-ink mt-3">Content factory</h1>
        <p className="text-muted mt-2">Your projects, stories and publishing in one place.</p></div>
      <button type="button" className="btn-primary px-4 py-2 inline-flex items-center justify-center gap-2" onClick={() => setShowCreate(!showCreate)}><Plus size={17} /> New project</button>
    </header>
    {showCreate && <form onSubmit={submitChannel} className="card p-5 sm:p-6 space-y-4">
      <div><h2 className="font-display text-xl text-ink">Start a project</h2><p className="text-sm text-muted mt-1">Give your channel a home for ideas, voices and publishing.</p></div>
      <div className="grid sm:grid-cols-2 gap-4"><label className="text-sm text-ink space-y-2"><span className="block">Project name</span><input className="input-field w-full" value={name} onChange={e => setName(e.target.value)} maxLength={100} placeholder="e.g. Workplace stories" required /></label>
      <label className="text-sm text-ink space-y-2"><span className="block">Content type</span><select className="input-field w-full" value={type} onChange={e => setType(e.target.value)}>{Object.entries(types).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div>
      <div className="flex gap-2"><button className="btn-primary px-4 py-2" disabled={busy}>Create project</button><button type="button" className="btn-quiet px-4 py-2" onClick={() => setShowCreate(false)}>Cancel</button></div>
    </form>}
    {error && <p role="alert" className="text-danger">{error}</p>}
    {channels === null && !error && <p className="text-muted">Loading projects…</p>}
    {channels?.length === 0 && <div className="card p-8 text-center"><Clapperboard className="mx-auto text-muted" size={28}/><h2 className="font-display text-2xl text-ink mt-4">Start with a project</h2><p className="text-muted mt-2">Bring your ideas, voices and channels together.</p><button type="button" className="btn-primary px-4 py-2 mt-5" onClick={() => setShowCreate(true)}>Create a project</button></div>}
    {selected && <div className="grid lg:grid-cols-[220px_minmax(0,1fr)] gap-6 items-start">
      <aside className="space-y-3"><div className="flex justify-between items-center"><h2 className="text-xs uppercase tracking-[0.16em] text-muted font-semibold">Projects</h2><span className="text-xs text-muted">{channels.length}</span></div>
        <div className="flex lg:flex-col gap-2 overflow-x-auto pb-2">{channels.map(channel => <button type="button" key={channel.id} onClick={() => { setSelectedId(channel.id); setView('drafts'); }} aria-pressed={selected.id === channel.id} className={`text-left min-w-[180px] lg:min-w-0 rounded-lg border px-4 py-3 transition-colors ${selected.id === channel.id ? 'border-brass bg-paper2 text-ink' : 'border-rule text-muted hover:text-ink'}`}><span className="block font-semibold truncate">{channel.name}</span><span className="block text-xs mt-1">{types[channel.content_type]}</span></button>)}</div>
      </aside>
      <main className="min-w-0 space-y-5">
        <div className="card p-6 sm:p-7"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs uppercase tracking-[0.16em] font-semibold text-muted">{types[selected.content_type]}</p><h2 className="font-display text-3xl text-ink mt-2">{selected.name}</h2><p className="text-sm text-muted mt-2">{selected.settings.publishing_mode === 'automatic' ? 'Automatic production' : 'Manual review'} · {selected.settings.daily_target} {selected.settings.daily_target === 1 ? 'video' : 'videos'} / day</p></div><span className="rounded-full border border-rule px-3 py-1 text-xs text-muted">{selected.auto_production.status === 'failed' ? 'Needs attention' : selected.auto_production.status === 'idle' ? 'Project ready' : selected.auto_production.status}</span></div>
          <div className="grid grid-cols-3 gap-3 mt-7 pt-5 border-t border-rule"><div><p className="text-2xl font-display text-ink">{selected.ideas.length}</p><p className="text-xs text-muted mt-1">Ideas</p></div><div><p className="text-2xl font-display text-ink">{readyCount}</p><p className="text-xs text-muted mt-1">Videos ready</p></div><div><p className="text-2xl font-display text-ink">{connectedCount}<span className="text-muted text-base"> / 2</span></p><p className="text-xs text-muted mt-1">Accounts connected</p></div></div>
        </div>
        <nav aria-label="Project sections" className="flex gap-1 border-b border-rule overflow-x-auto">{[['drafts', <Film size={16}/>, 'Stories'], ['settings', <Settings2 size={16}/>, 'Settings'], ['voices', <Clapperboard size={16}/>, 'Voices']].map(([id, icon, label]) => <button type="button" key={id} onClick={() => setView(id)} aria-current={view === id ? 'page' : undefined} className={`inline-flex items-center gap-2 px-4 py-3 text-sm whitespace-nowrap border-b-2 ${view === id ? 'border-brass text-ink' : 'border-transparent text-muted hover:text-ink'}`}>{icon}{label}</button>)}</nav>
        {view === 'settings' && <div className="card p-6"><ProjectSettings key={selected.id} channel={selected} busy={busy} save={saveSettings} disconnectAccount={disconnectAccount} retryProduction={retryProduction} /></div>}
        {view === 'voices' && <div className="card p-6"><VoiceSettings key={selected.id} channel={selected} busy={busy} save={saveVoice} /></div>}
        {view === 'drafts' && <div className="space-y-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-display text-2xl text-ink">Stories</h3><p className="text-sm text-muted mt-1">Develop an idea into a video ready to share.</p></div>{selected.content_type === 'workplace_skits' && <button type="button" className="btn-ghost px-4 py-2 inline-flex items-center gap-2" disabled={busy} onClick={() => generateIdeas(selected.id)}><Sparkles size={16}/> Generate 3 ideas</button>}</div>
          <form onSubmit={e => submitIdea(e, selected.id)} className="card p-5 space-y-3"><label htmlFor={`idea-${selected.id}`} className="block text-sm font-semibold text-ink">Have an idea?</label><textarea id={`idea-${selected.id}`} className="input-field w-full" rows={2} maxLength={2000} required value={ideas[selected.id] || ''} onChange={e => setIdeas(old => ({ ...old, [selected.id]: e.target.value }))} placeholder="Describe a moment, topic or story…"/><button className="btn-ghost px-4 py-2 inline-flex gap-2 items-center" disabled={busy}>Add idea <ArrowRight size={15}/></button></form>
          {selected.ideas.length === 0 && <div className="card p-8 text-center text-muted"><Sparkles className="mx-auto mb-3" size={22}/><p>No stories yet. Add an idea or generate a few to get started.</p></div>}
          <div className="space-y-3">{selected.ideas.map((idea, index) => <details key={idea.id} className="card group overflow-hidden"><summary className="cursor-pointer list-none p-5 flex gap-4 items-start"><span className="text-xs text-muted pt-1 font-mono">{String(index + 1).padStart(2, '0')}</span><span className="flex-1 min-w-0"><span className="block text-ink font-medium leading-relaxed">{idea.idea}</span><span className="inline-flex items-center gap-2 text-xs text-muted mt-2">{idea.video_ready === 1 ? 'Video ready' : statuses[idea.status]} {idea.youtube_publication_status === 'published' && <Youtube size={14}/>}</span></span><span className="text-muted text-xl group-open:rotate-45 transition-transform">+</span></summary>
            <div className="border-t border-rule p-5 space-y-3"><div className="flex flex-wrap gap-2">{idea.status !== 'approved' && <button type="button" className="btn-ghost px-3 py-2" disabled={busy} onClick={() => review(idea.id, 'approved')}>Approve idea</button>}{idea.status !== 'rejected' && <button type="button" className="btn-quiet px-3 py-2" disabled={busy} onClick={() => review(idea.id, 'rejected')}>Reject</button>}{idea.status !== 'needs_review' && <button type="button" className="btn-quiet px-3 py-2" disabled={busy} onClick={() => review(idea.id, 'needs_review')}>Move to review</button>}</div>
            {selected.content_type === 'workplace_skits' && <ScriptEditor key={`${idea.id}-${idea.script_revision || 0}`} idea={idea} busy={busy} act={scriptAction} youtubeConnected={selected.connections.youtube.connected} instagramConnected={selected.connections.instagram.connected} />}</div></details>)}</div>
        </div>}
      </main>
    </div>}
  </section>;
}
