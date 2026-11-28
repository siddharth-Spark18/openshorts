/* The free tools (/tools) and the two automation pages built around
 * Autopilot (/auto-clip, /youtube-automation).
 *
 * Tool pages carry `tool: { entry, html }`. The html is the tool's real form,
 * rendered straight into the static document right under the H1, so it is in
 * the raw HTML a crawler reads and it is the first thing a visitor sees; the
 * entry (dashboard/tools/*.js, built by Vite) only wires it up.
 *
 * House rules that apply to every line here (seo-work REGLAS.md): nothing
 * invented, every number dated and sourced, no em dashes, no filler copy.
 */

import { SITE } from './data.js'
import { esc } from './render.js'

const PUBLISHED = '2026-09-23'

const faqBlock = (faq) =>
  `<h2>Common questions</h2><dl class="faq">${faq
    .map((f) => `<dt>${esc(f.q)}</dt><dd>${esc(f.a)}</dd>`)
    .join('')}</dl>`

const sources = (items) =>
  `<h2>Sources</h2><ul class="sources">${items.map((s) => `<li>${s}</li>`).join('')}</ul>`

const webApp = (path, name, description, category = 'MultimediaApplication') => ({
  '@type': 'WebApplication',
  '@id': `${SITE.url}${path}#app`,
  name,
  description,
  url: `${SITE.url}${path}`,
  applicationCategory: category,
  operatingSystem: 'Any (runs in the browser)',
  browserRequirements: 'Requires JavaScript',
  isAccessibleForFree: true,
  offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
  publisher: { '@id': `${SITE.url}/#organization` },
})

/* ------------------------------------------------------------------------ */
/* /tools                                                                    */
/* ------------------------------------------------------------------------ */

export const TOOLS = [
  {
    path: '/youtube-transcript-generator',
    name: 'YouTube transcript generator',
    blurb: 'Paste a link, get the transcript with timestamps. Copy it or download TXT and SRT.',
  },
  {
    path: '/tools/tiktok-transcript-generator',
    name: 'TikTok transcript generator',
    blurb: 'Paste a TikTok link, get the captions as text. Copy or download TXT and SRT.',
  },
  {
    path: '/youtube-tag-generator',
    name: 'YouTube tag, title and description generator',
    blurb: 'Describe the video in a few lines, get tags, 10 title options or a description.',
  },
  {
    path: '/video-aspect-ratio-converter',
    name: 'Video to 9:16 converter',
    blurb: 'Turn a 16:9 video vertical with a blurred background, a crop or black bars. Runs in your browser.',
  },
]

/* The clip tool pages (clip-tools.js, pages.js) and the how-to guide, listed on
 * the hub so every one of them is a described link from /tools. */
const CLIP_MAKERS = [
  { path: '/platforms/youtube', name: 'YouTube clip maker', blurb: 'Paste a YouTube link, get vertical clips with captions and hooks.' },
  { path: '/platforms/youtube-shorts', name: 'YouTube Shorts maker', blurb: 'Shorts from long videos: length, hooks, captions and posting to your channel.' },
  { path: '/platforms/tiktok', name: 'TikTok clip maker', blurb: 'A long video cut into TikToks, sent to TikTok as drafts.' },
  { path: '/platforms/instagram-reels', name: 'AI reels maker', blurb: 'Instagram Reels from a long video, posted straight to Instagram.' },
  { path: '/platforms/twitch', name: 'Twitch clip maker', blurb: 'Twitch VODs clipped in parts, with the facecam kept.' },
  { path: '/platforms/kick', name: 'Kick clip maker', blurb: 'Kick VOD and clip links, with IRL and facecam layouts.' },
  { path: '/podcast-to-shorts', name: 'Podcast clip maker', blurb: 'Podcast clips with both speakers kept in frame.' },
  { path: '/use-cases/sermons', name: 'Sermon clip maker', blurb: 'Clip only the sermon from a service, with the preacher followed.' },
  { path: '/auto-reframe', name: 'Auto reframe', blurb: '16:9 to 9:16 by tracking the speaker, stacking two, or keeping the screen.' },
  { path: '/how-to/clip-a-youtube-video', name: 'How to clip a YouTube video', blurb: 'A guide: the Clip button, YouTube Studio, ffmpeg, or AI-cut Shorts.' },
]

const toolsHub = () => ({
  path: '/tools',
  title: 'Free Tools for YouTube and Short-Form Video | OpenShorts',
  description:
    'Free YouTube tools with no sign-up: transcript generator, tag, title and description generator, and a video to 9:16 converter that runs in your browser.',
  h1: 'Free tools for YouTube and short-form video',
  lede: 'Small tools that do one job each, free and without an account. They come from the same team as the OpenShorts clip generator.',
  breadcrumb: [{ name: 'Free tools' }],
  published: PUBLISHED,
  updated: PUBLISHED,
  cta: false,
  relatedTitle: 'Also on this site',
  related: ['/auto-clip', '/youtube-automation', '/free-ai-clip-generator'],
  body: `
<div class="tools-grid">
${TOOLS.map((t) => `<a href="${t.path}"><strong>${esc(t.name)}</strong><span>${esc(t.blurb)}</span></a>`).join('\n')}
</div>

<h2>What each tool does, and what it does not</h2>
<p><a href="/youtube-transcript-generator">The transcript generator</a> reads the
captions a video already has on YouTube, either the ones the creator uploaded or
YouTube's automatic ones. It does not run speech recognition itself, so a video
with no captions at all gets an honest "no captions" instead of a guess.</p>
<p><a href="/youtube-tag-generator">The tag, title and description generator</a>
writes from a short brief you type, using Google Gemini. It follows the limits
YouTube documents: titles up to 100 characters, descriptions up to 5,000, tags up
to 500 characters in total.</p>
<p><a href="/video-aspect-ratio-converter">The 9:16 converter</a> works on your
device. The video is never uploaded, which is why it has no queue and no daily
cap. It keeps the whole frame over a blurred copy, crops to fill, or adds black
bars. It does not follow faces: that is what the clip generator is for.</p>

<h2>AI clip makers by platform</h2>
<p>When the job is a long video cut into several vertical clips rather than one
transcript or one converted file, these pages explain how the clip generator
handles each kind of source and destination.</p>
<div class="cluster">
${CLIP_MAKERS.map((t) => `<a href="${t.path}"><strong>${esc(t.name)}</strong><span>${esc(t.blurb)}</span></a>`).join('\n')}
</div>

<h2>Where the paid product starts</h2>
<p>If what you want is not one transcript or one converted file but a long video
cut into several vertical clips with subtitles and the speaker kept in frame,
that is <a href="/free-ai-clip-generator">the free AI clip generator</a>: 20 free
minutes a month on OpenShorts Cloud, or unlimited if you self-host the MIT
licensed code. To have every new upload on your channel clipped without opening
anything, see <a href="/auto-clip">auto clip with Autopilot</a>.</p>
`,
  faq: [],
})

/* ------------------------------------------------------------------------ */
/* /youtube-transcript-generator and /tools/tiktok-transcript-generator       */
/* ------------------------------------------------------------------------ */
/* Both pages mount the same widget (dashboard/tools/transcript.js). The form's
 * data-platform picks the endpoint for a bare id; a pasted link picks its own,
 * so a TikTok link on the YouTube page (or the reverse) still works.
 *
 * Every claim about behaviour below is read off free_tools.py: per-network
 * limits (LIMITS), the 24 h cache, the track order (choose_track), machine
 * translations never offered, and the "no captions" / "unavailable" verdicts.
 * Change the copy if that code changes. */

const TRANSCRIPT_UPDATED = '2026-10-29'

const transcriptForm = ({ platform, label, placeholder, hint }) => `
<section class="tool" id="tool" aria-label="${esc(label)}">
  <form id="yt-form" class="tool-row" autocomplete="off" data-platform="${platform}">
    <label for="yt-url" class="sr">${esc(platform === 'tiktok' ? 'TikTok video link' : 'YouTube video link')}</label>
    <input id="yt-url" name="url" type="url" inputmode="url" required
      placeholder="${esc(placeholder)}">
    <button type="submit" class="btn-primary">Get transcript</button>
  </form>
  <p class="tool-hint">${hint}</p>
  <div id="yt-status" class="tool-status" role="status" aria-live="polite" hidden></div>
  <div id="yt-result" hidden>
    <div class="tool-meta"><strong id="yt-title"></strong><span id="yt-sub"></span></div>
    <div class="tool-actions">
      <select id="yt-lang" aria-label="Caption track"></select>
      <label><input type="checkbox" id="yt-ts" checked> timestamps</label>
      <button type="button" id="yt-copy">Copy</button>
      <button type="button" id="yt-txt">Download TXT</button>
      <button type="button" id="yt-srt">Download SRT</button>
    </div>
    <div id="yt-text" class="transcript" tabindex="0" aria-label="Transcript"></div>
    <div class="cta-inline">
      <p>${platform === 'tiktok'
    ? 'Have the long video this TikTok came from? OpenShorts cuts it into 3 to 15 vertical clips with subtitles. 20 free minutes a month.'
    : 'Want the best moments of this video as vertical clips with subtitles? OpenShorts cuts it into 3 to 15 shorts. 20 free minutes a month.'}</p>
      <button type="button" id="yt-clip" class="btn-primary">${platform === 'tiktok' ? 'Clip a long video' : 'Turn this video into clips'}</button>
    </div>
  </div>
</section>`

const transcriptTool = transcriptForm({
  platform: 'youtube',
  label: 'YouTube transcript generator',
  placeholder: 'https://www.youtube.com/watch?v=...',
  hint: 'Free, no sign-up. Works on any public video with captions, including YouTube\'s auto-generated ones. Watch, youtu.be, Shorts and live links. Copy the text or download TXT or SRT, with or without timestamps.',
})

const tiktokTool = transcriptForm({
  platform: 'tiktok',
  label: 'TikTok transcript generator',
  placeholder: 'https://www.tiktok.com/@user/video/...',
  hint: 'Free, no sign-up. Paste a TikTok video link or a share link from the app (vm.tiktok.com). Works when TikTok shows captions on the video. Copy the text or download TXT or SRT.',
})

const exampleList = (items, urlOf) => `<ul>
${items.map(([id, label, note]) => `<li><button type="button" class="btn-ghost" data-example-url="${esc(urlOf(id))}">Run</button> ${esc(label)}. ${esc(note)}</li>`).join('\n')}
</ul>`

const EXAMPLES = [
  ['arj7oStGLkU', 'Tim Urban, "Inside the Mind of a Master Procrastinator" (TED, 14 min)',
    '315 caption lines from the English track TED uploaded; the menu offers 50 tracks.'],
  ['UF8uR6Z6KLc', 'Steve Jobs, 2005 Stanford commencement address (15 min)',
    '244 caption lines; 9 tracks in the menu.'],
  ['8S0FDjFBj8o', 'Will Stephen, "How to sound smart in your TEDx Talk" (6 min)',
    '128 caption lines, a good short test.'],
]

const howToNode = (path, name, steps) => ({
  '@type': 'HowTo',
  '@id': `${SITE.url}${path}#howto`,
  name,
  totalTime: 'PT1M',
  tool: [{ '@type': 'HowToTool', name: 'A web browser' }],
  step: steps.map(([stepName, text], i) => ({
    '@type': 'HowToStep',
    position: i + 1,
    name: stepName,
    text,
    url: `${SITE.url}${path}#tool`,
  })),
})

const YT_STEPS = [
  ['Copy the video link', 'On YouTube, click Share under the video and copy the link, or copy the address bar. Watch, youtu.be, Shorts and live links all work.'],
  ['Paste it and click Get transcript', 'Paste the link into the box at the top of this page and click Get transcript. The text appears in a second or two.'],
  ['Pick the caption track', 'If the video has captions in more than one language, choose the one you want from the menu above the transcript.'],
  ['Choose timestamps or plain text', 'Tick or untick timestamps. With them, every line starts with the time it is said; without them you get one block of text.'],
  ['Copy or download', 'Click Copy, Download TXT for a text file, or Download SRT for a subtitle file you can load into a video editor or YouTube Studio.'],
]

const YT_FAQ = [
  {
    q: 'How do I get the transcript of a YouTube video?',
    a: 'Copy the video link, paste it into the box on this page and click Get transcript. You get the full text with timestamps, which you can copy or download as TXT or SRT. On YouTube itself, open the description and click Show transcript, which shows the text in a panel but has no download button.',
  },
  {
    q: 'How do I convert a YouTube video to text?',
    a: 'Paste the link above, untick timestamps and click Copy or Download TXT: you get YouTube to text as one block of prose, built from the video\'s own captions. Keep timestamps on if you want each line to point back to its moment. It works for any public video that has captions, including auto-generated ones.',
  },
  {
    q: 'Is this YouTube transcript generator free?',
    a: 'Yes. There is no account, no payment and no sign-up. To keep it fast for everyone it allows 10 transcripts per 10 minutes and 60 per day from the same network, and the whole tool has a shared daily cap that resets at midnight UTC.',
  },
  {
    q: 'Can I get a YouTube transcript with timestamps?',
    a: 'Yes. Timestamps are on by default and each one links to that moment of the video. Untick timestamps to get plain text in one block. Copy and TXT follow the checkbox; the SRT file always carries start and end times.',
  },
  {
    q: 'Can I download a YouTube transcript as a text file or SRT?',
    a: 'Yes. Download TXT saves the text as shown, with or without timestamps. Download SRT saves a subtitle file with one numbered cue per caption line, which Premiere Pro, DaVinci Resolve, CapCut and YouTube Studio can import.',
  },
  {
    q: 'Does it work on videos with only auto-generated captions?',
    a: 'Yes. When the creator has not uploaded subtitles, the tool returns YouTube\'s automatic captions in the language spoken in the video and labels them as auto-generated. They are speech recognition, so expect misspelled names and, on older videos, little punctuation.',
  },
  {
    q: 'Why does it say a video has no captions?',
    a: 'Because YouTube has none for it: no uploaded subtitles and no automatic track. That happens with music, with very recent uploads YouTube has not processed yet, and when a channel turns automatic captions off. The tool does not guess text it cannot read.',
  },
  {
    q: 'Can I get the transcript of a YouTube Short or a live stream?',
    a: 'Yes, paste the Shorts or live link as it is. A Short with speech usually has an automatic track like any other video. A live stream has captions once it has finished and YouTube has processed it; a stream in progress or a premiere that has not aired cannot be read.',
  },
  {
    q: 'Which languages does it support?',
    a: 'Every language YouTube has a real caption track for. The menu lists the tracks uploaded by the creator and YouTube\'s automatic track in the spoken language. YouTube\'s machine translations of the automatic track are left out, because they are not what was said.',
  },
  {
    q: 'Can I translate a YouTube transcript?',
    a: 'If the creator uploaded subtitles in other languages, pick one from the menu: those are human translations. Otherwise download the TXT or SRT and run it through a translation tool; an SRT keeps its timing, so the translated file still works as subtitles.',
  },
  {
    q: 'Does it work on private, members-only or age-restricted videos?',
    a: 'No. The tool reads only what YouTube shows to anyone without signing in. Private, members-only, age-restricted and removed videos get a message saying their captions cannot be read.',
  },
  {
    q: 'Can I get a transcript from TikTok or other sites?',
    a: 'TikTok, yes: paste a TikTok link here or use the TikTok transcript generator, which reads the captions TikTok shows on the video. Vimeo, Instagram and other sites are not supported.',
  },
  {
    q: 'Do you store the transcripts or the links I paste?',
    a: 'The server keeps each result in memory for up to 24 hours so the same video is not fetched from YouTube twice, and nothing is tied to you because there is no account. Analytics record that the tool was used and whether it worked, not which video.',
  },
]

const transcriptPage = () => ({
  path: '/youtube-transcript-generator',
  title: 'YouTube Transcript Generator: Free, TXT & SRT | OpenShorts',
  description:
    'Get the transcript of any YouTube video free: paste the link, copy the text with or without timestamps, or download TXT or SRT. No sign-up, any language.',
  h1: 'YouTube transcript generator: free, with timestamps, TXT or SRT',
  lede: 'Paste a YouTube link and get the full transcript in a couple of seconds, every line timestamped. Copy it or download a TXT or SRT file. <strong>Free, no account, no sign-up.</strong>',
  breadcrumb: [{ name: 'Free tools', path: '/tools' }, { name: 'YouTube transcript generator' }],
  published: PUBLISHED,
  updated: TRANSCRIPT_UPDATED,
  cta: false,
  tool: { entry: 'tool-transcript', html: transcriptTool },
  relatedTitle: 'More free tools',
  related: ['/tools/tiktok-transcript-generator', '/youtube-tag-generator', '/video-aspect-ratio-converter'],
  body: `
<h2>How to get the transcript of a YouTube video</h2>
<ol>
${YT_STEPS.map(([name, text]) => `<li><strong>${esc(name)}.</strong> ${esc(text)}</li>`).join('\n')}
</ol>
<p>The tool reads the captions the video already has on YouTube. It does not
download the video and does not run speech recognition of its own, which is why
a YouTube video transcript comes back in about the time a page takes to load. Above the text you
see the video title, the channel, the length, the word count and where the words
came from: captions uploaded by the creator, or YouTube's auto-generated ones.</p>

<h2>Try it with a real video</h2>
<p>These were checked on 23 September 2026. Click one to run it:</p>
${exampleList(EXAMPLES, (id) => `https://www.youtube.com/watch?v=${id}`)}

<h2>Getting the transcript on YouTube itself</h2>
<p>YouTube has its own transcript viewer, and for reading along with a video it
works well. Where it falls short is getting the text out: there is no copy or
download button, and selecting the panel by hand picks up the timestamps line by
line. The steps below describe YouTube's layout as of October 2026; YouTube moves
these controls from time to time.</p>
<p><strong>On a computer.</strong> Open the video and click the description
under it (the "...more" link) to expand it. Near the end of the description
there is a Transcript section with a <strong>Show transcript</strong> button.
The transcript opens in a panel next to the video, each line with its time.
Clicking a line jumps to that moment, and the panel can hide the timestamps
and switch language when there is more than one track.</p>
<p><strong>On the phone app.</strong> Tap the title or description under the
video, scroll down and tap <strong>Show transcript</strong>. The text scrolls with
the video. Copying from the app is awkward, so on a phone this page is the
quicker route to text you can paste somewhere else.</p>
<p>If you do not see Show transcript at all, the video almost always has no
captions, and this tool will tell you the same thing.</p>

<h2>With timestamps or as plain text</h2>
<p>Keep the timestamps when the times matter: quoting someone with the moment as
the citation, writing chapters, checking a fact against the video, or handing
the text to an AI model and asking it to point to where something is said. Each
timestamp here is a link to that second of the video, and copied or downloaded
text keeps them as <code>[12:34]</code> at the start of each line.</p>
<p>Untick timestamps when you want prose, the plain YouTube to text version: a
blog draft, notes, a translation, or search. Without timestamps the caption lines are joined into one block, which
reads far better than line-by-line fragments, because YouTube splits captions
for the screen, not at the end of sentences.</p>

<h2>SRT: the transcript as a subtitle file</h2>
<p>SRT is the plain-text subtitle format almost every editor and platform
accepts. Each cue is a number, a start and end time down to the millisecond, and
the line of text. Download SRT gives you one cue per caption line of the video,
ready to import into Premiere Pro, DaVinci Resolve, CapCut or back into YouTube
Studio for a re-upload or a second channel.</p>
<p>Two details are handled for you. YouTube's automatic captions roll: each line
stays on screen until the next one finishes, so raw cues overlap. The export
trims every cue to end where the next begins, so lines do not pile up on top of
each other, and a caption that would only flash by gets at least half a second
on screen.</p>
<p>An SRT made from captions is only as good as the captions. Uploaded subtitles
are usually clean; automatic ones carry the recognizer's mistakes. If you are
subtitling a clip for publishing, read it through once.</p>

<h2>Languages, auto-generated captions and translations</h2>
<p>A YouTube video can have several caption tracks. The tool picks one in this
order: subtitles a person uploaded in the language spoken in the video; then
YouTube's automatic track in that language; then any uploaded track, English
first; then any automatic track. When there is more than one real track, a menu
above the transcript switches between them without leaving the page.</p>
<p>YouTube can also machine-translate its automatic captions into dozens of
languages on the fly. Those are left out of the menu on purpose: they are a
translation of a transcription, two layers of guessing away from what was said.
Translations the creator uploaded are real tracks and are offered.</p>
<p>Automatic captions deserve a word of caution. They are speech recognition, so
names, brands and jargon come out spelled the way they sound, overlapping
speakers get merged, and on older videos there is little or no punctuation. For
a quote you will publish, check the moment in the video: that is what the
timestamp link is for.</p>

<h2>When there is no transcript</h2>
<p>Some videos have no captions at all: music and videos without speech, uploads
so recent that YouTube has not processed them yet, and channels that turned
automatic captions off. Private, members-only, age-restricted and removed videos
cannot be read either, and a premiere or a live stream only has captions after it
has aired and been processed. In each case the tool says so, rather than inventing
text.</p>
<p>Occasionally YouTube does not answer at all, and the tool asks you to try
again in a minute. That is about the connection, not the video: a retry usually
works, and Show transcript under the description is the fallback.</p>
<p>If you need the words of a video without captions, the
<a href="/free-ai-clip-generator">OpenShorts clip generator</a> runs its own
speech recognition with word-level timing and uses it to cut the video into
subtitled vertical clips. That is the paid product, with a free allowance of 20
minutes a month on OpenShorts Cloud and paid plans from $12 a month on
<a href="/pricing">the pricing table</a>, or free with no cap when you self-host
the open source code.</p>

<h2>What people use a YouTube transcript for</h2>
<ul>
<li><strong>Notes and studying.</strong> Read a lecture or a tutorial at your own
speed, search it for the part you need, and keep the timestamps to jump back.</li>
<li><strong>Quotes with a source.</strong> Copy the exact words of a talk or an
interview, with the timestamp as the citation and the link to that second.</li>
<li><strong>Blog posts, newsletters and show notes.</strong> Plain text is a
first draft for an article version of the video, or the raw material for show
notes and a description.</li>
<li><strong>Translation.</strong> Download the SRT, translate it, and you have
subtitles in another language that keep the original timing.</li>
<li><strong>Feeding an AI model.</strong> Paste the transcript into ChatGPT,
Claude or Gemini to summarise it, ask questions about it or draft chapters. Keep
the timestamps so the answer can point to the moment it comes from. Our
<a href="/youtube-tag-generator">title, description and tag generator</a> works
from a short brief, and a few lines of the transcript make a good one.</li>
<li><strong>Finding the moment to clip.</strong> Skim the text for the line
worth a Short, then cut it. If you would rather have the whole video cut into
vertical clips for you, see how OpenShorts handles
<a href="/platforms/youtube">long YouTube videos</a> and
<a href="/platforms/youtube-shorts">YouTube Shorts</a>, or paste the link into the
<a href="/youtube-to-shorts-converter">YouTube to Shorts converter</a>.</li>
<li><strong>Accessibility and editing.</strong> An SRT lines the words up with
the timeline in any editor, which is the start of burned-in captions or a
cleaned-up subtitle track.</li>
</ul>

<h2>TikTok, Vimeo and other sites</h2>
<p>TikTok links work in the box above, and there is a page for them: the
<a href="/tools/tiktok-transcript-generator">TikTok transcript generator</a>
reads the captions TikTok shows on a video and exports them the same way. Vimeo,
Instagram, X and other sites are not supported by this tool.</p>

<h2>Limits</h2>
<ul>
<li>One video per request. Playlists, channels and search pages are refused; a
watch link that also names a playlist reads just the video.</li>
<li>10 transcripts every 10 minutes and 60 a day from the same network, plus a
shared daily cap for the whole tool that resets at midnight UTC. A video that
was read in the last 24 hours comes from the cache and does not count.</li>
<li>Only public videos, only captions that already exist, and no machine
translations.</li>
<li>If YouTube takes longer than 45 seconds to answer, the request stops and you
can try again.</li>
</ul>

<h2>Privacy</h2>
<p>There is no account, so nothing you look up is tied to you. The server keeps
each result in memory for up to 24 hours so a popular video is fetched from
YouTube once, then forgets it. The transcript is laid out in your browser, and
Copy, TXT and SRT are produced there too: the files never pass through our
servers. Analytics record that the tool was used, whether it worked and how long
it took, not which video you asked for.</p>

${faqBlock(YT_FAQ)}
`,
  faq: YT_FAQ,
  extraNodes: [
    webApp('/youtube-transcript-generator', 'YouTube transcript generator',
      'Get the transcript of a YouTube video with timestamps from its existing captions. Copy it or download TXT and SRT. Free, no sign-up.'),
    howToNode('/youtube-transcript-generator', 'How to get the transcript of a YouTube video', YT_STEPS),
  ],
})

/* /tools/tiktok-transcript-generator. Checked against TikTok on 29-oct-2026
 * from a residential connection (see tests/test_free_tools.py for the parsing
 * and route rules; the examples below are those checks). */

const TIKTOK_EXAMPLES = [
  ['https://www.tiktok.com/@hankgreen1/video/7699685948937784590',
    'Hank Green on how the internet skews our view of people (83 s)', '45 caption lines.'],
  ['https://www.tiktok.com/@garyvee/video/7701056731048201486',
    'GaryVee on making content without AI (41 s)', '22 caption lines.'],
]

const TT_STEPS = [
  ['Copy the TikTok link', 'In the TikTok app tap Share, then Copy link. On the website, copy the address of the video page.'],
  ['Paste it and click Get transcript', 'Paste the link into the box at the top of this page and click Get transcript.'],
  ['Choose timestamps or plain text', 'Tick timestamps to start each line with its time, or untick them for one block of text.'],
  ['Copy or download', 'Click Copy, Download TXT for a text file, or Download SRT for a subtitle file with the original timing.'],
]

const TT_FAQ = [
  {
    q: 'How do I get the transcript of a TikTok video?',
    a: 'Copy the video link (Share, then Copy link in the app), paste it into the box on this page and click Get transcript. You get the text TikTok shows as captions, with timestamps, ready to copy or download as TXT or SRT.',
  },
  {
    q: 'How do I convert a TikTok to text?',
    a: 'Paste the TikTok link, untick timestamps and click Copy or Download TXT: the captions come back as one block of text. Keep timestamps on to start each line with its second, or download SRT for a subtitle file.',
  },
  {
    q: 'Is the TikTok transcript generator free?',
    a: 'Yes. There is no account, no payment and no sign-up. It allows 10 transcripts per 10 minutes and 60 per day from the same network, with a shared daily cap that resets at midnight UTC.',
  },
  {
    q: 'Why does it say a TikTok has no captions?',
    a: 'Because TikTok has none for it. TikTok generates captions for many videos with speech, but not for videos without talking or with only music, and creators can turn captions off. The tool does not guess text it cannot read.',
  },
  {
    q: 'Does it work with vm.tiktok.com share links?',
    a: 'Yes. Share links from the app (vm.tiktok.com, vt.tiktok.com and tiktok.com/t/ links) are followed to the video. A share link that has expired or points to a deleted video gets a message saying so.',
  },
  {
    q: 'Can I download a TikTok transcript as SRT?',
    a: 'Yes. Download SRT saves one cue per caption line with the timing TikTok uses, which CapCut, Premiere Pro, DaVinci Resolve and YouTube Studio can import.',
  },
  {
    q: 'Does it work on photo posts, LIVE or private videos?',
    a: 'No. Photo posts have no speech to caption, LIVE streams are not videos the tool can read, and private, friends-only, removed or region-blocked videos are not visible to it.',
  },
  {
    q: 'Can I get the transcript of a TikTok in another language?',
    a: 'The tool returns the caption tracks TikTok lists for the video, usually one in the spoken language; when there are more, a menu switches between them. For another language, download the SRT and run it through a translation tool.',
  },
  {
    q: 'Do you store the TikTok links I paste?',
    a: 'The server keeps each result in memory for up to 24 hours so the same video is not fetched twice, and nothing is tied to you. Analytics record that the tool was used and whether it worked, not which video.',
  },
]

const tiktokTranscriptPage = () => ({
  path: '/tools/tiktok-transcript-generator',
  title: 'TikTok Transcript Generator: Free, TXT & SRT | OpenShorts',
  description:
    'Get the transcript of a TikTok video free: paste the link or a vm.tiktok.com share link, then copy the text or download TXT or SRT. No sign-up needed.',
  h1: 'TikTok transcript generator: copy or download what was said',
  lede: 'Paste a TikTok link and get the captions as text, every line timestamped. Copy it or download a TXT or SRT file. <strong>Free, no account, no sign-up.</strong>',
  breadcrumb: [{ name: 'Free tools', path: '/tools' }, { name: 'TikTok transcript generator' }],
  published: TRANSCRIPT_UPDATED,
  updated: TRANSCRIPT_UPDATED,
  cta: false,
  tool: { entry: 'tool-transcript', html: tiktokTool },
  relatedTitle: 'More free tools',
  related: ['/youtube-transcript-generator', '/platforms/tiktok', '/video-aspect-ratio-converter'],
  body: `
<h2>How to get a TikTok video transcript</h2>
<ol>
${TT_STEPS.map(([name, text]) => `<li><strong>${esc(name)}.</strong> ${esc(text)}</li>`).join('\n')}
</ol>
<p>Going from TikTok to transcript takes one paste. The tool reads the captions
TikTok already serves with the video, the same lines you see on screen when
captions are on. It does not download the video and
does not run speech recognition of its own. Above the text you see the caption
of the post, the creator, the length and the word count.</p>

<h2>Try it with a real TikTok</h2>
<p>These were checked on 29 October 2026. Click one to run it:</p>
${exampleList(TIKTOK_EXAMPLES, (url) => url)}

<h2>Where TikTok's captions come from</h2>
<p>TikTok runs speech recognition on many videos with talking and shows the
result as captions, and creators can edit those captions or turn them off when
they post. Whatever TikTok's player has for a video is what this tool reads. So
the text is usually good for clear speech in one voice, and weaker for music,
crowd noise, slang or several people talking at once. Names come out spelled the
way they sound.</p>
<p>The TikTok app shows captions over the video one line at a time, which is fine
for watching and awkward for copying. Turning those lines into one block of text,
or into a subtitle file with the original timing, is the job this page does.</p>

<h2>Which links work</h2>
<ul>
<li>Video pages: <code>tiktok.com/@creator/video/1234...</code>, with or without
the tracking parameters the app adds.</li>
<li>Share links from the app: <code>vm.tiktok.com/...</code>,
<code>vt.tiktok.com/...</code> and <code>tiktok.com/t/...</code>. They are
followed to the video they point to; an expired one gets a clear message.</li>
<li>Embed links and a bare video id.</li>
</ul>
<p>Not supported: profiles, hashtags, sounds and collections (one video at a
time), photo posts and slideshows (nothing spoken to caption), LIVE, and private,
friends-only, removed or region-blocked videos.</p>

<h2>Timestamps, plain text and SRT</h2>
<p>With timestamps on, every line starts with the second it is said. TikTok links
cannot jump to a moment the way YouTube links can, so here the times are plain
text rather than links. Untick timestamps for one block of prose: the easiest
form to paste into a document, a caption or an AI model.</p>
<p>Download SRT gives you a subtitle file with one cue per caption line and
TikTok's own start and end times, overlaps trimmed. That is the useful format
when the same video is going somewhere else: import it into CapCut or Premiere,
restyle the captions, and post the video to Reels or Shorts without retyping a
word.</p>

<h2>What people use a TikTok transcript for</h2>
<ul>
<li><strong>Reposting to other platforms.</strong> The SRT carries the captions
to Instagram Reels, YouTube Shorts or Facebook with the timing intact.</li>
<li><strong>Studying what works.</strong> Read the first lines of the videos that
did well in your niche: the hook is usually in the first sentence, and it is
easier to compare written down.</li>
<li><strong>Scripts and captions.</strong> Turn a video into the post caption, a
thread, a newsletter paragraph or the script for a longer version.</li>
<li><strong>Quoting accurately.</strong> Copy exactly what a creator said, with
the time it was said.</li>
<li><strong>Translation and language learning.</strong> Run the text through a
translator, or read along slowly with a creator who speaks the language you are
learning.</li>
<li><strong>Feeding an AI model.</strong> Paste a few transcripts into ChatGPT,
Claude or Gemini and ask what the openings have in common, or for a summary.</li>
</ul>

<h2>When there is no transcript</h2>
<p>If TikTok has no captions for a video, the tool says so instead of guessing:
that happens with music, with videos without speech, and when a creator turned
captions off. If TikTok does not answer, try again in a minute.</p>
<p>When you have the video file, the <a href="/free-ai-clip-generator">OpenShorts
clip generator</a> runs its own speech recognition with word-level timing and
burns the subtitles in. It is built for the other direction too: a long video
cut into vertical clips, which is what the
<a href="/platforms/tiktok">TikTok clip maker</a> page covers. The free plan is
20 minutes a month on OpenShorts Cloud; paid plans start at $12 a month on
<a href="/pricing">the pricing table</a>, and the open source version is free
when you self-host it.</p>

<h2>YouTube videos too</h2>
<p>The same box reads YouTube links, and the
<a href="/youtube-transcript-generator">YouTube transcript generator</a> explains
the YouTube side: caption tracks in several languages, timestamps that link to
the moment, and what to do when a video has none.</p>

<h2>Limits and privacy</h2>
<p>10 transcripts every 10 minutes and 60 a day from the same network, with a
shared daily cap that resets at midnight UTC; a video read in the last 24 hours
comes from the cache and does not count. There is no account. The server keeps
each result in memory for up to 24 hours and then forgets it, the text and the
files are produced in your browser, and analytics record that the tool was used,
not which video.</p>

${faqBlock(TT_FAQ)}
`,
  faq: TT_FAQ,
  extraNodes: [
    webApp('/tools/tiktok-transcript-generator', 'TikTok transcript generator',
      'Get the transcript of a TikTok video from the captions TikTok shows. Copy it or download TXT and SRT. Free, no sign-up.'),
    howToNode('/tools/tiktok-transcript-generator', 'How to get the transcript of a TikTok video', TT_STEPS),
  ],
})

/* ------------------------------------------------------------------------ */
/* /youtube-tag-generator                                                    */
/* ------------------------------------------------------------------------ */

const metadataTool = `
<section class="tool" id="tool" aria-label="YouTube tag, title and description generator">
  <form id="md-form">
    <fieldset class="modes">
      <legend class="sr">What to generate</legend>
      <label><input type="radio" name="mode" value="tags" checked> Tags</label>
      <label><input type="radio" name="mode" value="titles"> Titles</label>
      <label><input type="radio" name="mode" value="description"> Description</label>
    </fieldset>
    <label class="field" for="md-topic"><span>What is the video about? Who is it for? Paste timestamps if you want chapters.</span>
      <textarea id="md-topic" rows="4" maxlength="2000" required
        placeholder="Example: I bake sourdough at home with no stand mixer. I show the stretch and folds, the overnight proof in the fridge and how to tell when the loaf is done."></textarea>
    </label>
    <label class="field" for="md-keyword"><span>Main keyword (optional)</span>
      <input id="md-keyword" type="text" maxlength="80" placeholder="sourdough bread">
    </label>
    <button type="submit" id="md-go" class="btn-primary">Generate tags</button>
  </form>
  <div id="md-status" class="tool-status" role="status" aria-live="polite" hidden></div>
  <div id="md-out" class="out" hidden></div>
  <div id="md-cta" class="cta-inline" hidden>
    <p>Got the long video done? OpenShorts cuts it into vertical Shorts with subtitles, and its YouTube Studio writes titles from the video itself.</p>
    <a id="md-cta-btn" class="btn-primary" href="${SITE.url}/">Clip the video</a>
  </div>
</section>`

const SAMPLE_TAGS = ['procrastination', 'Tim Urban', 'TED talk', 'instant gratification monkey', 'panic monster',
  'why we procrastinate', 'Tim Urban TED talk', 'procrastination TED talk', 'long term goals', 'no deadline',
  'procrastinating', 'how to stop procrastinating', 'gratification monkey', 'Tim Urban procrastination',
  'Tim Urbin', 'procrastionation', 'psychology', 'productivity', 'TED']

const SAMPLE_TITLES = [
  'Why Procrastination Destroys Goals Without Deadlines',
  'How Procrastination Works Inside Your Brain',
  'Deadlines Actually Protect You From Procrastination',
  'The Kind of Procrastination Panic Cannot Fix',
  'Tim Urban on Procrastination',
]

const metadataPage = () => ({
  path: '/youtube-tag-generator',
  title: 'YouTube Tag, Title and Description Generator | OpenShorts',
  description:
    'Free YouTube tag generator that also writes titles and descriptions from a short brief. Stays inside YouTube\'s limits: 100-character titles, 500 for tags.',
  h1: 'YouTube tag, title and description generator',
  lede: 'Describe your video in a few lines and get tags, 10 title options or a full description. Free, no account.',
  breadcrumb: [{ name: 'Free tools', path: '/tools' }, { name: 'YouTube tag, title and description generator' }],
  published: PUBLISHED,
  updated: PUBLISHED,
  cta: false,
  tool: { entry: 'tool-metadata', html: metadataTool },
  relatedTitle: 'More free tools',
  related: ['/youtube-transcript-generator', '/video-aspect-ratio-converter', '/youtube-automation'],
  body: `
<h2>How to use it</h2>
<ol>
<li>Pick <strong>Tags</strong>, <strong>Titles</strong> or <strong>Description</strong>.</li>
<li>Write two or three sentences about the video: what happens in it, who it is for, anything specific (names, tools, places). Specific briefs get specific output.</li>
<li>Add the keyword you want to rank for, if you have one.</li>
<li>Click a tag to copy it, or copy all of them at once and paste them into the Tags field in YouTube Studio. Titles copy with one click; the description is editable before you copy it.</li>
</ol>
<p>Need the brief? Paste the video into the <a href="/youtube-transcript-generator">transcript generator</a> first and summarise from that.</p>

<h2>A real example</h2>
<p>This is unedited output from the generator on 23 September 2026, for the brief
<em>"A TED talk by Tim Urban about procrastination: the instant gratification
monkey, the panic monster, and why long-term goals with no deadline never get
done"</em> with the keyword <em>procrastination</em>.</p>
<p><strong>Tags</strong> (${SAMPLE_TAGS.join(', ').length} characters, note the two deliberate misspellings):</p>
<p><code>${esc(SAMPLE_TAGS.join(', '))}</code></p>
<p><strong>Five of the ten titles:</strong></p>
<ul>${SAMPLE_TITLES.map((t) => `<li>${esc(t)} <span class="sources">(${t.length} characters)</span></li>`).join('')}</ul>
<p><button type="button" class="btn-ghost" data-example-topic="A TED talk by Tim Urban about procrastination: the instant gratification monkey, the panic monster, and why long-term goals with no deadline never get done." data-example-keyword="procrastination">Load this brief</button></p>

<h2>What it follows, and why</h2>
<ul>
<li><strong>Tags matter less than you think.</strong> YouTube's own help page says tags "play a minimal role in your video's discovery" and are mainly useful when your topic is commonly misspelled. So the generator includes likely misspellings of the names in your brief, and the title and description deserve more of your time.</li>
<li><strong>Length limits.</strong> Titles can be up to 100 characters and descriptions up to 5,000. The tags field takes 500 characters in total, and the tool keeps the list under that and shows the count.</li>
<li><strong>The first lines of a description do the work.</strong> They are what shows before "more", so the generator puts the payoff and the keyword there.</li>
<li><strong>Three hashtags.</strong> YouTube shows up to three hashtags from the description next to the title and ignores every hashtag on a video that has more than 60.</li>
<li><strong>Nothing invented.</strong> The model is told to use only facts from your brief: no made-up numbers, guests or results, and no chapters unless you gave timestamps.</li>
</ul>

${faqBlock([
  {
    q: 'Is this YouTube tag generator free?',
    a: 'Yes, with no account. Each click is one call to Google Gemini on our side, so it allows 12 generations per 10 minutes and 50 a day from the same network.',
  },
  {
    q: 'Do YouTube tags still help SEO?',
    a: 'A little. YouTube says tags play a minimal role in discovery and are most useful for commonly misspelled topics. Your title, thumbnail and description matter more.',
  },
  {
    q: 'How long should a YouTube title be?',
    a: 'YouTube allows 100 characters. Search results and phones cut long titles, so the generator aims for about 60 and puts the main point first.',
  },
  {
    q: 'Which AI writes the titles and descriptions?',
    a: 'Google Gemini, the same model family OpenShorts uses to pick clips and write titles in its YouTube Studio.',
  },
  {
    q: 'Does it work in other languages?',
    a: 'Yes. Write the brief in your language and the output comes back in the same language.',
  },
])}

${sources([
  '<a href="https://support.google.com/youtube/answer/146402" rel="noopener">YouTube Help: Add tags to your videos</a> (tags play a minimal role; useful for misspellings), checked 23 September 2026.',
  '<a href="https://support.google.com/youtube/answer/57404" rel="noopener">YouTube Help: Edit video settings</a> (100-character titles, 5,000-character descriptions), checked 23 September 2026.',
  '<a href="https://developers.google.com/youtube/v3/docs/videos" rel="noopener">YouTube Data API: videos resource</a> (tags up to 500 characters), checked 23 September 2026.',
  '<a href="https://support.google.com/youtube/answer/6390658" rel="noopener">YouTube Help: Use hashtags for YouTube search</a> (up to three shown by the title, more than 60 ignored), checked 23 September 2026.',
])}
`,
  faq: [
    { q: 'Is this YouTube tag generator free?', a: 'Yes, with no account. It allows 12 generations per 10 minutes and 50 a day from the same network.' },
    { q: 'Do YouTube tags still help SEO?', a: 'A little. YouTube says tags play a minimal role in discovery and are most useful for commonly misspelled topics.' },
    { q: 'How long should a YouTube title be?', a: 'YouTube allows 100 characters. The generator aims for about 60 and puts the main point first.' },
    { q: 'Which AI writes the titles and descriptions?', a: 'Google Gemini.' },
  ],
  extraNodes: [
    webApp('/youtube-tag-generator', 'YouTube tag, title and description generator',
      'Generate YouTube tags, title options and a description from a short brief, within YouTube\'s length limits.', 'UtilitiesApplication'),
  ],
})

/* ------------------------------------------------------------------------ */
/* /video-aspect-ratio-converter                                             */
/* ------------------------------------------------------------------------ */

const verticalTool = `
<section class="tool" id="tool" aria-label="Video to 9:16 converter">
  <label class="drop" id="vc-drop" for="vc-file">
    <strong>Choose a video or drop it here</strong>
    <small id="vc-name">MP4, MOV or WebM. Up to 5 minutes are converted. The file stays on your device.</small>
    <input id="vc-file" type="file" accept="video/*,.mp4,.mov,.m4v,.webm,.mkv" class="sr">
  </label>
  <div class="opts">
    <fieldset>
      <legend>Fill the vertical frame with</legend>
      <div class="modes">
        <label><input type="radio" name="vc-fit" value="blur" checked> Blurred background</label>
        <label><input type="radio" name="vc-fit" value="crop"> Crop to fill</label>
        <label><input type="radio" name="vc-fit" value="bars"> Black bars</label>
      </div>
      <label class="field" id="vc-pos-wrap" for="vc-pos"><span>Crop position (left to right)</span>
        <input id="vc-pos" type="range" min="0" max="100" value="50">
      </label>
    </fieldset>
    <fieldset>
      <legend>Output size</legend>
      <div class="modes">
        <label><input type="radio" name="vc-size" value="1080" checked> 1080x1920</label>
        <label><input type="radio" name="vc-size" value="720"> 720x1280</label>
      </div>
    </fieldset>
  </div>
  <button type="button" id="vc-go" class="btn-primary" disabled>Convert to 9:16</button>
  <div id="vc-progress" class="progress" hidden><span></span></div>
  <div id="vc-status" class="tool-status" role="status" aria-live="polite" hidden></div>
  <div id="vc-result" class="vc-result" hidden>
    <video id="vc-preview" controls playsinline muted></video>
    <div>
      <p id="vc-info" class="tool-hint"></p>
      <p><button type="button" id="vc-download" class="btn-primary">Download</button></p>
      <div class="cta-inline">
        <p>Is someone talking in it? OpenShorts reframes with face tracking so the speaker stays in the frame, and cuts the long video into clips with subtitles.</p>
        <a id="vc-cta-btn" class="btn-primary" href="${SITE.url}/">Try the clip generator</a>
      </div>
    </div>
  </div>
</section>`

const verticalPage = () => ({
  path: '/video-aspect-ratio-converter',
  title: 'Video Aspect Ratio Converter (16:9 to 9:16) | OpenShorts',
  description:
    'Convert a video to 9:16 for TikTok, Reels and Shorts in your browser: blurred background, crop or black bars. Free, no upload, no watermark.',
  h1: 'Video aspect ratio converter: 16:9 to 9:16 in your browser',
  lede: 'Turn a horizontal video into a vertical 9:16 one for TikTok, Instagram Reels and YouTube Shorts. The conversion runs on your device, so nothing is uploaded.',
  breadcrumb: [{ name: 'Free tools', path: '/tools' }, { name: 'Video to 9:16 converter' }],
  published: PUBLISHED,
  updated: PUBLISHED,
  cta: false,
  tool: { entry: 'tool-vertical', html: verticalTool },
  relatedTitle: 'More free tools',
  related: ['/youtube-transcript-generator', '/youtube-tag-generator', '/youtube-to-shorts-converter'],
  body: `
<h2>The three ways to fill a vertical frame</h2>
<p>A 16:9 video is 1.78 times wider than it is tall; a 9:16 frame is 0.56. Something
has to give, and each option trades a different thing:</p>
<ul>
<li><strong>Blurred background</strong> keeps the whole picture, centred, over a
blurred and darkened copy of itself. Nothing is cut off, but the video only
fills about a third of the screen height. Good for screen recordings, slides and
wide shots.</li>
<li><strong>Crop to fill</strong> uses the full screen and keeps a vertical
slice of the frame, which you can slide left or right. It cuts away about two
thirds of the width, so it only works when the subject stays in one place.</li>
<li><strong>Black bars</strong> is the plain letterbox: the whole picture, with
the rest of the screen left black.</li>
</ul>
<p>The output is 1080x1920 or 720x1280, as MP4 (H.264) in Chrome, Edge and
Safari, or WebM in browsers that cannot encode H.264. Audio is kept.</p>

<h2>Why it runs in your browser</h2>
<p>Your browser already has a hardware video encoder, and the WebCodecs API lets
a page use it. So the file is read, re-framed and encoded on your machine and
never uploaded: no queue, no watermark, no account. The limits are the ones that
keep a browser tab stable: the first 5 minutes of the video and files up to
2 GB. Keep the tab open while it runs.</p>

<h2>When a fixed crop is not enough</h2>
<p>A fixed crop cannot follow a person who moves, and it cannot show two people
talking at the same time. That is what the
<a href="/youtube-to-shorts-converter">OpenShorts YouTube to Shorts converter</a>
does: it tracks faces with MediaPipe so the speaker stays in the frame, can stack
two people talking in a split screen, and cuts the long video into 3 to 15 clips
with subtitles.</p>


${faqBlock([
  {
    q: 'How do I convert a video to 9:16 for free?',
    a: 'Choose the file above, pick blurred background, crop or black bars, and click Convert. The video is processed in your browser and you download a 1080x1920 or 720x1280 file. There is no sign-up and no watermark.',
  },
  {
    q: 'Is my video uploaded anywhere?',
    a: 'No. The conversion runs on your device with your browser\'s own video encoder. The file never leaves your computer or phone.',
  },
  {
    q: 'Why is there a 5 minute limit?',
    a: 'The finished video is held in the browser\'s memory until you download it, and long 1080p videos can exhaust a tab. Short-form platforms rarely take more than a few minutes anyway.',
  },
  {
    q: 'Which browsers work?',
    a: 'Current versions of Chrome, Edge, Safari and Firefox. The tool needs the WebCodecs API; a browser without it shows a message instead of failing silently.',
  },
])}

${sources([
  '<a href="https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API" rel="noopener">MDN: WebCodecs API</a>, the browser encoder this tool uses.',
  `<a href="https://github.com/Vanilagy/mediabunny" rel="noopener">Mediabunny</a>, the open source library that reads and writes the video files. Face tracking in the clip generator: the project source at <a href="${SITE.repo}" rel="noopener">github.com/mutonby/openshorts</a>.`,
])}
`,
  faq: [
    { q: 'How do I convert a video to 9:16 for free?', a: 'Choose the file, pick blurred background, crop or black bars, and click Convert. It runs in your browser with no sign-up and no watermark.' },
    { q: 'Is my video uploaded anywhere?', a: 'No. The conversion runs on your device with your browser\'s own video encoder.' },
    { q: 'Why is there a 5 minute limit?', a: 'The finished video is held in the browser\'s memory until you download it, and long 1080p videos can exhaust a tab.' },
    { q: 'Which browsers work?', a: 'Current versions of Chrome, Edge, Safari and Firefox. The tool needs the WebCodecs API.' },
  ],
  extraNodes: [
    webApp('/video-aspect-ratio-converter', 'Video to 9:16 converter',
      'Convert a horizontal video to vertical 9:16 in the browser with a blurred background, a crop or black bars.'),
  ],
})

export function toolPages() {
  return [toolsHub(), transcriptPage(), tiktokTranscriptPage(), metadataPage(), verticalPage()]
}
