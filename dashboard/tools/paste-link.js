/* Paste-a-link widget for the clip tool pages (/platforms/youtube and the
 * rest of seo/clip-tools.js).
 *
 * It does exactly what the homepage hero does with a pasted link
 * (Landing.jsx handleHeroSubmit + main.jsx handleLaunchApp): store the link
 * under os_pending_url, skip the landing from now on, and open the app at
 * #app. MediaInput reads os_pending_url on mount and preloads it; the visitor
 * still ticks the rights attestation and submits, and if they are signed out
 * App.jsx stashes the job (os_pending_job) and resumes it after sign-in. Same
 * origin as the app, so the localStorage is shared.
 *
 * The checks here are only the ones that save a round trip: a link with a
 * scheme, a known video site, and on YouTube one video rather than a channel
 * or a playlist (the server refuses those too, yt_clients.youtube_non_video_reason).
 */
import { $, el, track, setStatus } from './common.js'

const TOOL = 'paste-link'
const form = $('pl-form')
const input = $('pl-url')
const status = $('pl-status')
const page = location.pathname

// Sites the app lists as accepted (MediaInput SUPPORTED_PLATFORMS), plus Kick,
// which the download path handles like Twitch (cloud/metering.py).
const PLATFORMS = [
  ['YouTube', ['youtube.com', 'youtu.be', 'youtube-nocookie.com']],
  ['Vimeo', ['vimeo.com']],
  ['TikTok', ['tiktok.com']],
  ['X / Twitter', ['x.com', 'twitter.com']],
  ['Twitch', ['twitch.tv']],
  ['Kick', ['kick.com']],
  ['Facebook', ['facebook.com', 'fb.watch', 'fb.com']],
  ['Instagram', ['instagram.com']],
  ['Dailymotion', ['dailymotion.com', 'dai.ly']],
  ['Reddit', ['reddit.com', 'redd.it']],
  ['Streamable', ['streamable.com']],
]

const platformOf = (host) => {
  for (const [name, domains] of PLATFORMS) {
    if (domains.some((d) => host === d || host.endsWith(`.${d}`))) return name
  }
  return ''
}

// Mirrors yt_clients.youtube_non_video_reason: an allowlist of single-video
// shapes, everything else on youtube.com is not one video.
const SINGLE_VIDEO = ['shorts', 'live', 'embed', 'v', 'e', 'clip']
function youtubeProblem(u) {
  const host = u.hostname.toLowerCase()
  if (host === 'youtu.be') return u.pathname.replace(/\//g, '') ? '' : 'That youtu.be link has no video in it.'
  if (!(host === 'youtube.com' || host.endsWith('.youtube.com'))) return ''
  const seg = u.pathname.split('/').filter(Boolean)
  if (!seg.length) return 'That is the YouTube home page. Open the video and paste its link.'
  const first = seg[0]
  if (first === 'watch' || first === 'watch_popup') {
    return u.searchParams.get('v') ? '' : 'That watch link has no video id in it.'
  }
  if (SINGLE_VIDEO.includes(first)) return seg.length > 1 ? '' : 'That link has no video id in it.'
  if (first === 'playlist') return 'That is a playlist. Open one video in it and paste that link.'
  if (first === 'results') return 'That is a search page. Open the video and paste its link.'
  if (first.startsWith('@') || ['channel', 'c', 'user'].includes(first)) {
    return 'That is a channel page. Open one video and paste the link of the video itself.'
  }
  return 'That YouTube page is not one video. Open the video and paste its link.'
}

// A Twitch or Kick channel URL is the live channel, not a recording.
function streamProblem(platform, u) {
  const path = u.pathname.toLowerCase()
  if (platform === 'Twitch') {
    if (u.hostname.toLowerCase().startsWith('clips.') || /\/(videos|clip)\//.test(path)) return ''
    return 'That looks like a channel page. Paste the link of a past broadcast (twitch.tv/videos/...) or a clip.'
  }
  if (platform === 'Kick') {
    if (/\/(videos?|clips?)\//.test(path) || u.searchParams.get('clip')) return ''
    return 'That looks like a channel page. Paste the link of a past stream (kick.com/<channel>/videos/...).'
  }
  return ''
}

function parse(raw) {
  let text = raw.trim()
  if (!text) return { error: 'Paste a link to the video first.', code: 'empty' }
  if (!/^[a-z][a-z0-9+.-]*:/i.test(text)) text = `https://${text}`
  let u
  try {
    u = new URL(text)
  } catch (_) {
    return { error: 'That does not look like a link. Copy the address of the video page and paste it here.', code: 'invalid' }
  }
  if (u.protocol !== 'https:' && u.protocol !== 'http:') {
    return { error: 'Only web links (http or https) can be clipped from here.', code: 'scheme' }
  }
  const platform = platformOf(u.hostname.toLowerCase())
  if (!platform) return { url: u.href, platform: '', soft: true }
  const problem = platform === 'YouTube' ? youtubeProblem(u) : streamProblem(platform, u)
  if (problem) return { error: problem, code: 'not_one_video', platform }
  return { url: u.href, platform }
}

function go(url, platform) {
  track('tool_used', { tool: TOOL, ok: true, page, platform: platform || 'other' })
  track('SeoCtaClick', { page, source: TOOL })
  try {
    localStorage.setItem('os_pending_url', url)
    localStorage.setItem('openshorts_skip_landing', '1')
  } catch (_) { /* private mode: the app still opens, without the link */ }
  window.location.href = '/#app'
}

function warnUnknown(url) {
  status.replaceChildren(
    el('p', { text: 'That site is not on the list we test (YouTube, Vimeo, TikTok, X, Twitch, Kick, Facebook, Instagram, Dailymotion, Reddit, Streamable). It may still work, and if it does not, you can upload the file in the app instead.' }),
    el('button', { type: 'button', class: 'btn-primary', text: 'Try this link anyway', onclick: () => go(url, '') }),
  )
  status.dataset.kind = 'warn'
  status.hidden = false
}

form.addEventListener('submit', (e) => {
  e.preventDefault()
  const r = parse(input.value)
  if (r.error) {
    track('tool_used', { tool: TOOL, ok: false, page, code: r.code, platform: r.platform || '' })
    setStatus(status, r.error, 'error')
    input.focus()
    return
  }
  if (r.soft) {
    track('tool_used', { tool: TOOL, ok: false, page, code: 'unknown_site' })
    warnUnknown(r.url)
    return
  }
  setStatus(status, 'Opening the clip generator with your link...', 'busy')
  go(r.url, r.platform)
})

input.addEventListener('input', () => { if (!status.hidden) setStatus(status, '', '') })

// "Upload a file instead" opens the app on the upload tab, nothing stored.
$('pl-upload')?.addEventListener('click', () => {
  track('tool_cta_click', { tool: TOOL, page, kind: 'upload' })
  try { localStorage.setItem('openshorts_skip_landing', '1') } catch (_) { /* private mode */ }
})
