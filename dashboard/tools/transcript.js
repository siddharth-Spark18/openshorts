/* Transcript generator widget: /youtube-transcript-generator and
 * /tools/tiktok-transcript-generator.
 *
 * Asks our API for the captions the video already has (on YouTube, or the ones
 * TikTok's own player shows) and renders them with timestamps, plus copy / TXT
 * / SRT export. Everything past the fetch happens here in the browser. The
 * form's data-platform is the page default; a pasted link picks its own.
 */
import { API_URL, $, el, track, setStatus, copyText, downloadBlob, safeFilename, apiError, openInApp } from './common.js'

const form = $('yt-form')
const input = $('yt-url')
const status = $('yt-status')
const result = $('yt-result')
const out = $('yt-text')
const langSel = $('yt-lang')
const tsBox = $('yt-ts')
const submit = form.querySelector('button[type="submit"]')
const defaultPlatform = form.dataset.platform === 'tiktok' ? 'tiktok' : 'youtube'
const TOOL = `${defaultPlatform}-transcript`
let current = null
let currentUrl = ''
let currentPlatform = defaultPlatform

// Which endpoint a pasted link belongs to. A bare id keeps the page default.
const platformOf = (raw) => {
  const s = raw.trim().toLowerCase()
  if (/(^|\/\/|\.)tiktok\.com(\/|$)/.test(s) || /^\d{15,22}$/.test(s)) return 'tiktok'
  if (/(^|\/\/|\.)(youtube\.com|youtu\.be|youtube-nocookie\.com)(\/|$)/.test(s)) return 'youtube'
  return defaultPlatform
}
const KIND_LABEL = {
  auto: 'YouTube auto-generated captions',
  manual: 'captions uploaded by the creator',
  tiktok: 'TikTok captions',
}

const clock = (s, srt) => {
  const ms = Math.round(s * 1000)
  const h = Math.floor(ms / 3600000)
  const m = Math.floor((ms % 3600000) / 60000)
  const sec = Math.floor((ms % 60000) / 1000)
  const pad = (n, w = 2) => String(n).padStart(w, '0')
  if (srt) return `${pad(h)}:${pad(m)}:${pad(sec)},${pad(ms % 1000, 3)}`
  return h ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`
}

const asText = (segs, withTs) =>
  segs.map((s) => (withTs ? `[${clock(s.start)}] ${s.text}` : s.text)).join(withTs ? '\n' : ' ')
    .replace(/ {2,}/g, ' ')

const asSrt = (segs) =>
  segs.map((s, i) => {
    const end = s.start + Math.max(s.dur || 0, 0.5)
    return `${i + 1}\n${clock(s.start, true)} --> ${clock(end, true)}\n${s.text}\n`
  }).join('\n')

function render() {
  if (!current) return
  const withTs = tsBox.checked
  out.replaceChildren()
  if (!withTs) {
    out.append(el('p', { text: asText(current.segments, false) }))
    return
  }
  const frag = document.createDocumentFragment()
  // YouTube links each timestamp to that second; TikTok has no time parameter.
  const yt = current.platform !== 'tiktok'
  for (const s of current.segments) {
    frag.append(el('p', {},
      yt
        ? el('a', {
          class: 'ts',
          href: `https://www.youtube.com/watch?v=${current.video_id}&t=${Math.floor(s.start)}s`,
          target: '_blank', rel: 'noopener',
          text: clock(s.start),
        })
        : el('span', { class: 'ts', text: clock(s.start) }),
      ' ', s.text))
  }
  out.append(frag)
}

function showNoCaptions(message) {
  result.hidden = true
  const tt = currentPlatform === 'tiktok'
  status.replaceChildren(
    el('p', {}, el('strong', { text: 'No captions to read. ' }), message || ''),
    el('p', {
      text: tt
        ? 'OpenShorts runs its own speech recognition on the audio, word by word. Upload the video file in the app to get it transcribed and subtitled. 20 free minutes a month, no credit card.'
        : 'OpenShorts runs its own speech recognition on the audio, word by word, so it can transcribe this video and cut it into vertical clips with subtitles. 20 free minutes a month, no credit card.',
    }),
    el('button', {
      type: 'button', class: 'btn-primary',
      onclick: () => openInApp(tt ? '' : currentUrl, TOOL),
      text: tt ? 'Transcribe it with OpenShorts' : 'Transcribe and clip it with OpenShorts',
    }),
  )
  status.dataset.kind = 'warn'
  status.hidden = false
}

async function load(url, lang) {
  currentUrl = url
  currentPlatform = platformOf(url)
  const site = currentPlatform === 'tiktok' ? 'TikTok' : 'YouTube'
  submit.disabled = true
  setStatus(status, `Reading the captions from ${site}...`, 'busy')
  const t0 = performance.now()
  try {
    const q = new URLSearchParams({ url })
    if (lang) q.set('lang', lang)
    const res = await fetch(`${API_URL}/api/tools/${currentPlatform}-transcript?${q}`)
    if (!res.ok) {
      const err = await apiError(res)
      track('tool_used', { tool: TOOL, platform: currentPlatform, ok: false, code: err.code })
      if (err.code === 'no_captions') return showNoCaptions(err.message)
      setStatus(status, err.message, 'error')
      return
    }
    current = await res.json()
    track('tool_used', { tool: TOOL, platform: currentPlatform, ok: true, kind: current.kind, cached: !!current.cached,
      ms: Math.round(performance.now() - t0) })
    $('yt-title').textContent = current.title
    const mins = Math.round((current.duration || 0) / 60)
    const words = current.segments.reduce((n, s) => n + s.text.split(/\s+/).length, 0)
    $('yt-sub').textContent = [
      current.channel,
      mins ? `${mins} min` : '',
      `${words.toLocaleString('en-US')} words`,
      KIND_LABEL[current.kind] || '',
    ].filter(Boolean).join(' · ')
    langSel.replaceChildren(...current.languages.map((l) => el('option', {
      value: l.request,
      selected: l.code === current.language && l.kind === current.kind,
      text: l.name,
    })))
    langSel.hidden = current.languages.length < 2
    render()
    setStatus(status, '', '')
    result.hidden = false
  } catch (_) {
    track('tool_used', { tool: TOOL, platform: currentPlatform, ok: false, code: 'network' })
    setStatus(status, 'Could not reach the transcript service. Check your connection and try again.', 'error')
  } finally {
    submit.disabled = false
  }
}

form.addEventListener('submit', (e) => {
  e.preventDefault()
  const url = input.value.trim()
  if (!url) return
  load(url)
})
langSel.addEventListener('change', () => load(currentUrl, langSel.value))
tsBox.addEventListener('change', render)
$('yt-copy').addEventListener('click', (e) => current && copyText(asText(current.segments, tsBox.checked), e.currentTarget))
$('yt-txt').addEventListener('click', () => {
  if (!current) return
  downloadBlob(new Blob([asText(current.segments, tsBox.checked)], { type: 'text/plain;charset=utf-8' }),
    `${safeFilename(current.title, current.video_id)}.txt`)
})
$('yt-srt').addEventListener('click', () => {
  if (!current) return
  downloadBlob(new Blob([asSrt(current.segments)], { type: 'application/x-subrip;charset=utf-8' }),
    `${safeFilename(current.title, current.video_id)}.srt`)
})
$('yt-clip').addEventListener('click', () => openInApp(currentPlatform === 'tiktok' ? '' : currentUrl, TOOL))

// Example buttons in the page copy fill the form and run it.
document.querySelectorAll('[data-example-url]').forEach((b) => b.addEventListener('click', () => {
  input.value = b.dataset.exampleUrl
  window.scrollTo({ top: 0, behavior: 'smooth' })
  load(input.value)
}))
