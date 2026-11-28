/* Guide pages: self-hosting, the free-plan comparison, the "how to clip a
 * YouTube video" guide and the platform how-to guides (Reel and Shorts specs,
 * Facebook Reels, making Shorts, when to post). Pricing links go to the
 * standalone /pricing page (seo/pricing-page.js).
 *
 * Every price, minute and limit on these pages is read from data.js. Where a
 * fact had to be transcribed into a structured field (the free-plan table), the
 * transcription is checked against the data.js wording at build time, so a
 * change in data.js that the table no longer matches fails the build instead of
 * shipping a stale number.
 */

import { SITE, COMPETITORS, EDITIONS, PRICE_MODELS, PIPELINE_STEPS } from './data.js'
import { costCalculator, priceFor } from './components.js'
import { esc } from './render.js'

const PUBLISHED = '2026-10-28'

const faqBlock = (faq) =>
  `<h2>Common questions</h2><dl class="faq">${faq
    .map((f) => `<dt>${esc(f.q)}</dt><dd>${esc(f.a)}</dd>`)
    .join('')}</dl>`

const sources = (items) =>
  `<h2>Sources</h2><ul class="sources">${items.map((s) => `<li>${s}</li>`).join('')}</ul>`

/* Build-time guard: a transcribed fact must still appear in its data.js text. */
function assertIn(text, needle, where) {
  if (!String(text).toLowerCase().includes(String(needle).toLowerCase())) {
    throw new Error(`[guide-pages] ${where}: data.js no longer says "${needle}". Update guide-pages.js.`)
  }
}

const money = (n) => (n === 0 ? '$0' : `$${n % 1 ? n.toFixed(2) : n}`)
const monthName = (iso) =>
  new Date(`${iso}T12:00:00Z`).toLocaleString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' })

/* ---------------------------------------------------------------- pricing data */

const OS = PRICE_MODELS.openshorts
const osPlan = (name) => {
  const p = OS.plans.find((x) => x.name === name)
  if (!p) throw new Error(`[guide-pages] PRICE_MODELS.openshorts has no "${name}" plan`)
  return p
}
const FREE = osPlan('Free')
// Plan ids are the ones PricingSection.jsx and the Stripe lookup keys use.
const PAID = [
  ['starter', 'Starter', 'For getting started'],
  ['creator', 'Creator', 'For regular creators'],
  ['pro', 'Pro', 'For power users and teams'],
].map(([id, name, blurb]) => {
  const p = osPlan(name)
  return {
    id,
    name,
    blurb,
    minutes: p.monthly.minutes,
    monthly: p.monthly.price,
    yearlyPerMonth: p.yearly.price,
    yearlyTotal: Math.round(p.yearly.price * 12),
    perMinuteCents: Math.round((p.monthly.price / p.monthly.minutes) * 1000) / 10,
  }
})
const [STARTER, , PRO] = PAID
const FIRST_VIDEO_MINUTES = 60
assertIn(EDITIONS.cloud.summary, `up to ${FIRST_VIDEO_MINUTES} minutes`, 'EDITIONS.cloud first video')
assertIn(EDITIONS.cloud.summary, 'about 50 seconds', 'EDITIONS.cloud GPU speed')
assertIn(EDITIONS.selfHosted.summary, '5 to 8 minutes', 'EDITIONS.selfHosted CPU speed')
if (FREE.monthly.minutes !== EDITIONS.cloud.freeMinutes) throw new Error('[guide-pages] free minutes disagree in data.js')
if (STARTER.monthly !== EDITIONS.cloud.lowPrice || PRO.monthly !== EDITIONS.cloud.highPrice) {
  throw new Error('[guide-pages] EDITIONS.cloud low/high price disagree with PRICE_MODELS')
}

/* ---------------------------------------------------- /self-hosted-ai-clip-maker */

const SELF_FAQ = [
  {
    q: 'Is there an open source version of Opus Clip?',
    a: 'Opus Clip itself is closed source and cloud only. OpenShorts is the open source alternative: MIT-licensed, self-hosted with Docker, and covering the same job of finding the best moments in a long video, reframing them to 9:16 with face tracking and burning in word-level subtitles.',
  },
  {
    q: 'What hardware do I need to self-host OpenShorts?',
    a: 'Docker and Docker Compose, 8 GB of RAM or more and a modern multi-core CPU. On CPU an 8-minute video takes 5 to 8 minutes. An NVIDIA GPU with NVENC is optional and brings that to about a minute; 8 GB of VRAM is enough for the large-v3-turbo transcription model in fp16 plus the detection models.',
  },
  {
    q: 'Does self-hosted OpenShorts have a watermark or a usage limit?',
    a: 'No. The self-hosted edition has no watermark code and no metering code. The only limits are your hardware and the quotas of the API keys you bring.',
  },
  {
    q: 'Which API keys do I need?',
    a: 'Only a Google Gemini key for the AI features, and its free tier covers individual use. You can replace it with a local LLM through LLM_BASE_URL. ElevenLabs (dubbing), fal.ai (AI Shorts) and Upload-Post (auto-posting) are optional and only needed for those features.',
  },
  {
    q: 'Does my video leave my machine?',
    a: 'The video file stays local: transcription, scene detection, reframing and encoding run on your machine. With Gemini, the moment picker receives the transcript text, the automatic layout picker receives a few still frames, and videos with no speech are sent to Gemini to be clipped by what is on screen. With a local LLM and no Gemini key, nothing leaves the machine at all.',
  },
  {
    q: 'Is there an open source AI clipping API?',
    a: 'Yes. A self-hosted OpenShorts serves the same REST API and MCP endpoint as the hosted service, with no metering: POST a video, get a signed webhook with the clips. It runs only while your machine is on; the hosted endpoint is always on and draws from your plan minutes.',
  },
  {
    q: 'Can I use self-hosted OpenShorts commercially?',
    a: 'Yes. The core application is MIT-licensed, which allows commercial use, modification and redistribution. The cloud/ directory (billing and hosted-service code) is under a separate licence and is not needed to self-host.',
  },
  {
    q: 'How much does self-hosting really cost compared to Opus Clip or Vizard?',
    a: `The software is $0. What you pay is the machine, its electricity and your time, plus Gemini usage, which is typically under a cent per 10-minute video on paid tiers and free within the free tier. Opus Clip and Vizard bill one credit per source minute: at 300 minutes a month that is ${money(priceFor('opus-clip', 300, 'monthly').price)}/month on Opus Clip and ${money(priceFor('vizard', 300, 'monthly').price)}/month on Vizard, billed monthly.`,
  },
]

const selfHosted = () => {
  const podcast = 260 // a weekly 60-minute show, ~4.3 episodes a month
  const opus = priceFor('opus-clip', podcast, 'monthly')
  const vizard = priceFor('vizard', podcast, 'monthly')
  const cloud = priceFor('openshorts', podcast, 'monthly')
  const heavy = 1200
  const opusHeavy = priceFor('opus-clip', heavy, 'monthly')
  const quso = priceFor('vidyo-ai', heavy, 'yearly')
  return {
    path: '/self-hosted-ai-clip-maker',
    title: 'Self-Hosted AI Clip Maker (Docker, MIT) | OpenShorts',
    description:
      'Self-host OpenShorts, the open source Opus Clip alternative: requirements, Docker quick start, your own keys, privacy, and the real cost vs per-minute credits.',
    h1: 'A self-hosted AI clip maker: requirements, setup and what it really costs',
    breadcrumb: [
      { name: 'Open source video clipper', path: '/open-source-video-clipper' },
      { name: 'Self-hosting guide' },
    ],
    published: PUBLISHED,
    updated: '2026-10-30',
    lede: `OpenShorts is the open source AI clip maker you can self-host: MIT-licensed, free with no watermark and no cap on your own machine with Docker, or hosted from ${money(STARTER.monthly)}/month for ${STARTER.minutes} minutes if you would rather not run it.`,
    cta: {
      label: 'Self-host or try it hosted',
      title: 'Clone it, or test the output first',
      body: `The repo is MIT and free to run. If you want to see the clips before installing anything, the hosted free plan clips your first video up to ${FIRST_VIDEO_MINUTES} minutes; paid plans from ${money(STARTER.monthly)}/month.`,
      button: 'Source on GitHub',
      href: SITE.repo,
    },
    tldr: [
      'OpenShorts is an open source AI clip maker you can self-host: MIT-licensed, started with one <code>docker compose up</code>, and running the same pipeline as the hosted service. It finds the strongest moments in a long video, reframes them to 9:16 with face tracking and burns in word-level subtitles.',
      'You need Docker, 8 GB+ of RAM and a Google Gemini key (free tier, or a local LLM instead). An optional NVIDIA GPU cuts an 8-minute video from 5 to 8 minutes of processing to about one.',
      `Self-hosted has no watermark, no cap and no per-minute meter. The hosted edition, OpenShorts Cloud, exists for people who would rather not run it: free plan with a watermark, paid from ${money(STARTER.monthly)}/month.`,
    ],
    facts: [
      { k: 'Licence', v: 'MIT', s: 'Commercial use allowed' },
      { k: 'Software cost', v: '$0', s: 'No watermark, no cap' },
      { k: '8-min video', v: '5-8 min', s: 'On CPU; about 1 min with an NVIDIA GPU' },
      { k: 'Your video', v: 'Local', s: 'Transcribed and rendered on your machine' },
    ],
    body: `
<p>This page is the practical half of self-hosting: what you need, the commands,
what it costs to run and what you give up. For the licence and the case for
open source clipping in general, see <a href="/open-source-video-clipper">the open
source video clipper</a>; if you are not sure a clipper is what you want rather
than a text-to-video model, start with <a href="/open-source-ai-video-generator">the
open source AI video generator</a> page.</p>

<h2>What do you get when you self-host?</h2>
<p>The same software as the hosted service, not a cut-down community edition.
The pipeline is identical, stage by stage:</p>
<ol>${PIPELINE_STEPS.map((s) => `<li><strong>${esc(s.title)}.</strong> ${esc(s.body.split('. ')[0])}.</li>`).join('')}</ol>
<p>On top of the clip generator you get the layouts that make podcasts and screen
recordings work in 9:16 (two speakers stacked, a screen above the presenter, a
webcam inset enlarged), the hook overlay, the clip editor, the YouTube Studio for
titles, thumbnails and descriptions, AI Shorts with your fal.ai key, dubbing with
your ElevenLabs key, and the REST API and MCP server for agents. The stage-by-stage
detail is in <a href="/how-openshorts-works">how OpenShorts works</a>.</p>

<h2>What are the requirements?</h2>
<ul>
<li><strong>Docker and Docker Compose.</strong> Linux, macOS, or Windows with Docker Desktop on the WSL2 backend.</li>
<li><strong>8 GB of RAM or more</strong> and a modern multi-core CPU. The first start downloads the transcription and detection models.</li>
<li><strong>A Google Gemini API key</strong> for the AI features. The free tier is enough for individual use, or you can point the moment picker at a local LLM instead.</li>
<li><strong>Optional: an NVIDIA GPU with NVENC</strong> (an RTX 4060 class card is plenty). 8 GB of VRAM fits the large-v3-turbo transcription model in fp16 plus the detection models. The GPU build adds about 2 GB to the image.</li>
</ul>
<p>The default image is CPU-only, and that is a perfectly good way to start. On a
typical CPU an 8-minute video takes 5 to 8 minutes; with the GPU build it takes
about a minute. If you clip a weekly podcast overnight, CPU is fine. If you clip
every day and want results while you wait, the GPU is worth it.</p>

<h2>Quick start</h2>
<pre><code>git clone https://github.com/mutonby/openshorts.git
cd openshorts
cp .env.example .env        # optional: S3 backup and other settings
docker compose up --build</code></pre>
<p>Open <code>http://localhost:5175</code>, go to <strong>Settings</strong> and
paste your Gemini key (plus fal.ai, ElevenLabs and Upload-Post keys if you want
those features). Then paste a YouTube link or upload a file in the Clip Generator.
The backend API listens on port 8000.</p>

<h3>Turning on the GPU</h3>
<p>Install the NVIDIA driver and the NVIDIA Container Toolkit on the host
(<code>nvidia-smi</code> must work), then create a
<code>docker-compose.override.yml</code> next to the compose file:</p>
<pre><code>services:
  backend:
    build:
      context: .
      args:
        GPU: "1"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu, video]</code></pre>
<p>and set these in <code>.env</code>:</p>
<pre><code>WHISPER_MODEL=large-v3-turbo
WHISPER_DEVICE=cuda
WHISPER_COMPUTE=float16
FFMPEG_ENCODER=auto</code></pre>
<p><code>FFMPEG_ENCODER=auto</code> probes the NVENC encoder at startup and falls
back to x264 if it is missing, and a CUDA error during transcription retries once
on CPU, so a misconfigured GPU degrades to slow rather than broken. The README
has the verification commands.</p>

<h2>Bring your own keys: what each one is for</h2>
<table>
<thead><tr><th>Key</th><th>Needed for</th><th>Cost</th></tr></thead>
<tbody>
<tr><td class="os">Google Gemini</td><td>Picking the moments, titles, the layout picker</td><td>Free tier for individual use; under a cent per 10-minute video on paid tiers</td></tr>
<tr><td class="os">Local LLM (optional)</td><td>Replaces Gemini for moment picking: Ollama, LM Studio, vLLM, llama.cpp</td><td>$0, your hardware</td></tr>
<tr><td class="os">ElevenLabs (optional)</td><td>Dubbing into 30+ languages, voice-over</td><td>Billed by ElevenLabs; free tier available</td></tr>
<tr><td class="os">fal.ai (optional)</td><td>AI Shorts: AI actors, lip-sync, B-roll</td><td>Pay per video, billed by fal.ai</td></tr>
<tr><td class="os">Upload-Post (optional)</td><td>Posting to TikTok, Instagram and YouTube</td><td>Free tier available</td></tr>
</tbody>
</table>
<p>To run without any Google key, set <code>LLM_BASE_URL</code> and
<code>LLM_MODEL</code> in <code>.env</code> to any OpenAI-compatible server. Give
it a context of 16k tokens (Ollama defaults to 4k and truncates silently) and a
7-8B model or larger; 3B models do not return valid JSON reliably. Without
Gemini, the features that need to look at frames fall back: the automatic layout
picker uses the plain face-tracking crop, and a video with no speech cannot be
clipped.</p>

<h2>Privacy: what leaves your machine</h2>
<p>The video file stays where it is. Downloading, transcription, scene detection,
face tracking, reframing and encoding all run locally, and the clips are written
to your disk. What goes out depends on the keys you configure:</p>
<ul>
<li><strong>With Gemini:</strong> the moment picker sends the transcript text, never the video. The automatic layout picker sends a handful of still frames. A video with no speech (gameplay, B-roll) is sent to Gemini so it can be clipped by what is on screen.</li>
<li><strong>With a local LLM and no Gemini key:</strong> nothing leaves the machine.</li>
<li><strong>Optional features</strong> call their providers only when you use them: dubbing sends audio to ElevenLabs, AI Shorts sends prompts to fal.ai, posting sends the finished clip to Upload-Post.</li>
</ul>
<p>That is the real reason teams self-host a clipper: unreleased episodes, client
work and internal recordings never touch a third-party upload form, and there is
no retention policy to read because there is no retention.</p>

<h2>What does it cost compared to per-minute credits?</h2>
<p>Opus Clip and Vizard bill one credit per minute of video you import; Quso
bills roughly one credit per minute. That meter is what makes long-form clipping
expensive. A weekly 60-minute podcast is about ${podcast} minutes a month. On
monthly billing that is ${opus ? `${money(opus.price)}/month on Opus Clip (${esc(opus.plan)})` : 'past every published Opus Clip plan'},
${vizard ? `${money(vizard.price)}/month on Vizard (${esc(vizard.plan)})` : 'past every published Vizard plan'}
and ${money(cloud.price)}/month on OpenShorts Cloud (${esc(cloud.plan)}). Self-hosted,
it is $0 in software. At ${heavy} minutes a month (a daily 40-minute stream),
${opusHeavy ? `Opus Clip costs ${money(opusHeavy.price)}/month` : 'Opus Clip has no published plan and moves you to custom Business pricing'}${quso ? `, and Quso costs ${money(quso.price)}/month on its yearly plan` : ''}.</p>
${costCalculator(['opus-clip', 'vizard', 'vidyo-ai'], { minutes: 600 })}
<p>The self-hosted bar is not literally free. What you actually pay:</p>
<ul>
<li><strong>The machine.</strong> If you already own a desktop with 8 GB+ of RAM, nothing extra. A GPU is a one-off purchase that pays for itself only at high volume.</li>
<li><strong>Electricity</strong> for the minutes it spends processing.</li>
<li><strong>API usage.</strong> Gemini is free within its free tier and under a cent per 10-minute video beyond it. Dubbing and AI Shorts are billed by ElevenLabs and fal.ai if you use them.</li>
<li><strong>Your time</strong> to install it, update it (<code>git pull</code> and rebuild) and keep the machine on.</li>
</ul>
<p>Rule of thumb: below a couple of hours of source a month, a hosted plan is
cheaper than your time. Above that, and especially for long recordings, the
per-minute meter is the whole bill, and self-hosting removes it.</p>

<h2>Using it from agents: API and MCP</h2>
<p>A self-hosted instance serves the same REST API and MCP server as the hosted
one, unmetered. An agent in Claude, ChatGPT or n8n can submit a video, wait for
the signed webhook and publish the clips, with no per-call price. There is also
a stdio MCP transport for local clients. The catch is availability: the endpoint
is up only while your machine is. Setup and the tool list are on
<a href="/mcp">the MCP page</a>; the one-POST, one-webhook flow is on
<a href="/automate-shorts-api">automate shorts with the API</a>.</p>

<h2>What you give up compared to Cloud</h2>
<ul>
<li><strong>Speed without a GPU.</strong> Cloud renders on an NVIDIA GPU, about 50 seconds per 8-minute video. A CPU-only box takes 5 to 8 minutes.</li>
<li><strong>Zero setup.</strong> Cloud has the Gemini key included and auto-posting already connected. Self-hosted, you create and manage the keys.</li>
<li><strong>An always-on endpoint.</strong> Cloud's MCP server and webhooks work while your laptop sleeps.</li>
<li><strong>Storage and backup.</strong> Cloud keeps your clips and serves them from any browser. Self-hosted, they live on your disk unless you configure S3 backup.</li>
<li><strong>Maintenance.</strong> Updates, YouTube download changes and model downloads are yours to handle.</li>
</ul>
<p>Nothing is feature-locked: the hosted plans pay for hardware and keys, not
for features. If those trade-offs are not worth it to you, the
<a href="/pricing">Cloud plans</a> start with a free tier and go from
${money(STARTER.monthly)} to ${money(PRO.monthly)} a month.</p>

<h2>Self-hosted or Cloud: a quick decision</h2>
<ul>
<li><strong>Self-host</strong> if the footage is private, your volume is high or your sources are long, you are comfortable with Docker, or you want to change how the pipeline cuts and reframes.</li>
<li><strong>Use Cloud</strong> if you want results in under a minute on any laptop, you do not want to manage keys, or you need an endpoint that is always on for an agent.</li>
<li><strong>Do both:</strong> test the output on the hosted free plan, then self-host once you know it fits your footage. It is the same pipeline, so the clips match.</li>
</ul>

${faqBlock(SELF_FAQ)}

${sources([
  `Requirements, commands and environment variables from the project README at <a href="${SITE.repo}" rel="noopener">github.com/mutonby/openshorts</a>.`,
  `Competitor plans in the calculator checked ${esc(PRICE_MODELS['opus-clip'].checked)} on each vendor's public pricing page; the full plan breakdowns are in <a href="/alternatives">the alternatives hub</a>.`,
])}
`,
    faq: SELF_FAQ,
    extraNodes: [
      {
        '@type': 'SoftwareSourceCode',
        '@id': `${SITE.url}/self-hosted-ai-clip-maker#code`,
        name: 'OpenShorts',
        description:
          'Open source AI clip maker: turns long videos into vertical 9:16 clips with AI moment detection, face-tracked reframing and word-level subtitles. Self-hosted with Docker.',
        codeRepository: SITE.repo,
        license: 'https://opensource.org/licenses/MIT',
        programmingLanguage: ['Python', 'JavaScript'],
        runtimePlatform: 'Docker',
        author: { '@id': `${SITE.url}/#organization` },
      },
      {
        '@type': 'SoftwareApplication',
        '@id': `${SITE.url}/self-hosted-ai-clip-maker#app`,
        name: EDITIONS.selfHosted.name,
        applicationCategory: 'MultimediaApplication',
        operatingSystem: 'Linux, macOS, Windows (Docker)',
        description: EDITIONS.selfHosted.summary,
        license: 'https://opensource.org/licenses/MIT',
        downloadUrl: SITE.repo,
        offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
      },
    ],
    related: ['/open-source-video-clipper', '/how-to', '/mcp'],
  }
}

/* ------------------------------------------------ /free-ai-clipping-tools-compared */

/* One row per tool. `must` lists the phrases the row relies on; each has to
 * appear in that vendor's free-tier text in data.js (tiers[0] plus tierNote),
 * or the build fails. "Not stated" means the vendor's pricing page did not say
 * on the checked date, not that the answer is no. */
const FREE_ROWS = [
  {
    slug: '2short',
    ongoing: true,
    allowance: '30 min of analysis a month',
    resolution: '1080p',
    watermark: 'No',
    card: 'Not stated',
    limits: 'YouTube links only',
    must: ['30 minutes', 'no watermark', '1080p', 'YouTube links only'],
  },
  {
    slug: 'opus-clip',
    ongoing: true,
    allowance: '60 min of source a month',
    resolution: '1080p',
    watermark: 'Yes',
    card: 'Not stated (the 7-day Pro trial needs none)',
    limits: 'No editing; export within 3 days',
    must: ['60 credits', '1080p', 'watermark', 'no editing', '3 days', 'no credit card'],
  },
  {
    slug: 'vizard',
    ongoing: true,
    allowance: '60 min of uploads a month',
    resolution: '720p',
    watermark: 'Yes',
    card: 'Not stated',
    limits: 'Uploads up to 60 min, exports up to 10 min, 3-day storage',
    must: ['60 credits', '720p', 'watermark', 'up to 60 minutes', 'up to 10 minutes', '3-day storage'],
  },
  {
    slug: 'vidyo-ai',
    ongoing: true,
    allowance: '75 min a month (about 1 credit per min)',
    resolution: '720p',
    watermark: 'Not stated',
    card: 'Not stated',
    limits: 'Data kept 7 days, no scheduling',
    must: ['75 credits', '720p', '7 days', 'no scheduling'],
  },
  {
    slug: 'klap',
    ongoing: false,
    allowance: 'One video, once',
    resolution: 'Not stated',
    watermark: 'Not stated',
    card: 'No',
    limits: 'No ongoing free plan',
    must: ['one video', 'no credit card', 'no ongoing free plan'],
  },
  {
    slug: 'submagic',
    ongoing: false,
    allowance: 'None; a trial instead',
    resolution: 'n/a',
    watermark: 'n/a',
    card: 'No (for the trial)',
    limits: 'No free plan',
    must: ['no free plan', 'no credit card'],
  },
  {
    slug: 'sendshort',
    ongoing: false,
    allowance: 'None; 3 free videos at sign-up',
    resolution: 'n/a',
    watermark: 'n/a',
    card: 'Not stated',
    limits: 'No free plan; long-video clipping from the $29 plan',
    must: ['no free plan', '3 free videos'],
  },
]

for (const r of FREE_ROWS) {
  const c = COMPETITORS[r.slug]
  if (!c) throw new Error(`[guide-pages] no competitor "${r.slug}" in data.js`)
  const text = `${c.tiers[0][1]} ${c.tierNote || ''} ${c.tiers[0][0]}`
  for (const m of r.must) assertIn(text, m, `${r.slug} free tier`)
}
assertIn(COMPETITORS.sendshort.gotcha, '$29', 'sendshort clipping price')

const freeCompared = () => {
  const vendorRows = FREE_ROWS.map((r) => ({ ...r, name: COMPETITORS[r.slug].name, paid: COMPETITORS[r.slug].entryPrice, checked: COMPETITORS[r.slug].checked, link: `/alternatives/${r.slug}` }))
  const osCloud = {
    name: 'OpenShorts Cloud',
    ongoing: true,
    allowance: `First video whole up to ${FIRST_VIDEO_MINUTES} min, then ${FREE.monthly.minutes} min a month`,
    resolution: 'Same as paid plans',
    watermark: 'Yes',
    card: 'No (Google sign-in)',
    limits: 'Clips kept 7 days',
    paid: `${money(STARTER.monthly)}/month`,
    checked: OS.checked,
    link: '/pricing',
    us: true,
  }
  const osSelf = {
    name: 'OpenShorts self-hosted',
    ongoing: true,
    allowance: 'No cap (your hardware)',
    resolution: 'Same as your source',
    watermark: 'No',
    card: 'No (no account at all)',
    limits: 'Needs Docker and your own Gemini key or a local LLM',
    paid: 'Free, MIT',
    checked: OS.checked,
    link: '/self-hosted-ai-clip-maker',
    us: true,
  }
  const all = [osSelf, ...vendorRows.filter((r) => r.ongoing), osCloud, ...vendorRows.filter((r) => !r.ongoing)]
  const latest = all.map((r) => r.checked).sort().at(-1)
  const asOf = monthName(latest)
  const listNames = (rows) =>
    rows.map((r) => r.name).reduce((s, n, i, a) => (i === 0 ? n : i === a.length - 1 ? `${s} and ${n}` : `${s}, ${n}`), '')
  const noMark = all.filter((r) => r.ongoing && r.watermark === 'No')
  const marked = all.filter((r) => r.ongoing && r.watermark === 'Yes')
  const unknown = all.filter((r) => r.ongoing && r.watermark === 'Not stated')
  const noFree = all.filter((r) => !r.ongoing)
  const answer = `As of ${asOf}, the free plans in this comparison that export without a watermark are ${listNames(noMark)}. ${listNames(marked)} watermark their free exports${unknown.length ? `; ${listNames(unknown)} does not say on its pricing page` : ''}. ${listNames(noFree)} have no ongoing free plan.`

  const cell = (v) => {
    const cls = v === 'No' ? ' class="yes"' : ''
    return `<td${cls}>${esc(v)}</td>`
  }
  const table = `<table>
<thead><tr><th>Tool</th><th>Free allowance</th><th>Max resolution</th><th>Watermark</th><th>Card needed</th><th>Limits</th><th>Paid from</th><th>Checked</th></tr></thead>
<tbody>${all
    .map(
      (r) =>
        `<tr><td class="os"><a href="${esc(r.link)}">${esc(r.name)}</a></td><td>${esc(r.allowance)}</td><td>${esc(r.resolution)}</td>${cell(r.watermark)}<td>${esc(r.card)}</td><td>${esc(r.limits)}</td><td>${esc(r.paid)}</td><td>${esc(r.checked)}</td></tr>`
    )
    .join('')}</tbody>
</table>`

  const minutesFree = vendorRows.filter((r) => r.ongoing).map((r) => ({ name: r.name, min: PRICE_MODELS[r.slug]?.plans.find((p) => p.monthly.price === 0)?.monthly.minutes })).filter((x) => x.min)
  const biggest = minutesFree.sort((a, b) => b.min - a.min)[0]
  biggest.resolution = vendorRows.find((r) => r.name === biggest.name).resolution

  const faq = [
    {
      q: 'Which free AI clip generator has no watermark?',
      a: `${answer} Watermark status is taken from each vendor's pricing page on the checked date.`,
    },
    {
      q: 'What is the best free AI clip generator?',
      a: `It depends on what you need from free. For the most free minutes on a hosted plan, ${biggest.name} gives ${biggest.min} a month at ${biggest.resolution}. For clips you can post without a watermark, 2short.ai's free plan (30 minutes, YouTube links only) or self-hosted OpenShorts (no cap, your own machine). To try a tool on one long video, the OpenShorts Cloud free plan clips the first video whole up to ${FIRST_VIDEO_MINUTES} minutes, watermarked.`,
    },
    {
      q: 'Is the OpenShorts free plan watermarked?',
      a: `Yes. The OpenShorts Cloud free plan watermarks its clips and keeps them 7 days; paid plans from ${money(STARTER.monthly)}/month do not, and upgrading removes the mark from clips already made. The self-hosted edition, free under MIT, has no watermark at all.`,
    },
    {
      q: 'Do free AI clipping tools need a credit card?',
      a: 'Among the plans we checked, OpenShorts Cloud (Google sign-in), Klap\'s one free video and the Opus Clip and Submagic trials state that no card is needed. Most other vendors do not say on their pricing pages either way; self-hosted OpenShorts has no account at all.',
    },
    {
      q: 'Why do free AI clipping tools add a watermark?',
      a: 'Because the GPU time and AI calls behind every clip cost the vendor money, and the watermark is what turns a free user into a paying one. Software you run yourself has no such cost to recover, which is why self-hosted OpenShorts can be free without one.',
    },
  ]

  return {
    path: '/free-ai-clipping-tools-compared',
    // The verdict first: "best free AI clipping tool" is answered in one
    // paragraph before the table, from the same numbers the table shows.
    lede: `The best free AI clipping tool depends on what "free" means. Most free minutes on a hosted plan: ${esc(biggest.name)} (${biggest.min} a month at ${esc(biggest.resolution)}), then ${minutesFree.slice(1, 3).map((x) => `${esc(x.name)} (${x.min})`).join(' and ')}. No watermark and no cap: OpenShorts self-hosted (MIT), if you can run Docker. Hosted with no card: OpenShorts clips your first video free up to ${FIRST_VIDEO_MINUTES} minutes (watermarked), and removes the watermark from ${money(STARTER.monthly)}/month.`,
    title: 'Free AI Clipping Tools Compared: Who Has No Watermark?',
    description: `The free plans of ${vendorRows.length + 1} AI clipping tools side by side, checked ${asOf}: free minutes, resolution, watermark, card required, limits and paid price.`,
    h1: 'Free AI clipping tools compared: minutes, watermark and limits',
    breadcrumb: [{ name: 'Alternatives', path: '/alternatives' }, { name: 'Free plans compared' }],
    published: PUBLISHED,
    updated: '2026-10-30',
    cta: {
      label: 'Free, two ways',
      title: 'Self-host with no watermark, or try it hosted',
      body: `Hosted: first video free up to ${FIRST_VIDEO_MINUTES} minutes, then ${FREE.monthly.minutes} minutes a month, watermarked, no card. Self-hosted: MIT, no watermark, no cap.`,
      button: 'Get free clips',
    },
    tldr: [
      answer,
      `The free plans differ more than the headline "free" suggests: from no ongoing plan at all to ${biggest.min} minutes a month, from 720p to 1080p, and from 3 days to 7 days before your clips are gone.`,
    ],
    body: `
<h2>Free AI clip generators, side by side</h2>
<p class="checked">Each vendor's figures checked on the date in its row, on its public pricing page. "Not stated" means the page did not say, not that the answer is no.</p>
${table}
<p>Paid prices are the cheapest entry plan; where a vendor discounts yearly
billing, the price shown is the one it advertises, and the
<a href="/alternatives">alternatives hub</a> has each plan in full.</p>

<h2>How we built this table</h2>
<p>Every figure for a third-party tool comes from that vendor's own public
pricing and help pages, read on the date shown in the "Checked" column. We list
only what the vendor states. When a pricing page is silent on a point (whether
the free plan needs a card, whether Quso's free exports are watermarked), the
cell says "Not stated" instead of guessing. The figures for OpenShorts come from
our own plans. Vendors change free tiers without notice, so check the vendor's
page before you rely on a number, and tell us if one has moved.</p>
<p>"Free allowance" is what you can process each month for $0. Tools meter in
different units: Opus Clip, Vizard and Quso count minutes of video imported,
2short.ai counts minutes analysed, and Klap, Submagic and SendShort count clips
or videos. A one-off trial is not counted as a free plan.</p>

<h2>Which free plan fits which use?</h2>
<ul>
<li><strong>You need clips you can post today, without a watermark:</strong> 2short.ai's free plan if your sources are already on YouTube and 30 minutes a month is enough; self-hosted OpenShorts if you can run Docker and want no cap.</li>
<li><strong>You want the most free minutes on a hosted tool:</strong> ${esc(biggest.name)} (${biggest.min} minutes at ${esc(biggest.resolution)}), then ${minutesFree.slice(1).map((x) => `${esc(x.name)} (${x.min})`).join(', ')}.</li>
<li><strong>You want to judge quality on a full-length episode:</strong> the OpenShorts Cloud free plan clips your first video whole up to ${FIRST_VIDEO_MINUTES} minutes, so a complete podcast or webinar fits.</li>
<li><strong>You want 1080p on free:</strong> Opus Clip (watermarked) or 2short.ai (no watermark). Vizard and Quso cap free exports at 720p.</li>
<li><strong>Your footage is private:</strong> only self-hosting keeps the video on your own machine. Every hosted free plan, ours included, means uploading it.</li>
<li><strong>You only want to try a tool once:</strong> Klap's one free video and the Submagic and SendShort trials work for a single test, not for ongoing use.</li>
</ul>

<h2>Why the watermark column matters</h2>
<p>A watermark on a free export is not a bug or a trick: it is the vendor's way of
covering GPU time and AI calls for people who are not paying. That is also why a
watermark-free hosted free plan is rare, and why the generous ones tend to cap
something else instead: links only, minutes analysed, a short storage window. The
structural exception is software you run yourself, where there is no vendor
cost to recover. The reasoning is laid out on
<a href="/free-ai-clip-generator">the free AI clip generator page</a>.</p>
<p>The OpenShorts Cloud free plan follows the hosted rule and says so: its clips
are watermarked, and paid plans from ${money(STARTER.monthly)}/month are not. The
<a href="/pricing">pricing table on the homepage</a> has every plan.</p>

<h2>What happens when the free plan runs out?</h2>
<ul>
${vendorRows.filter((r) => r.ongoing).map((r) => `<li><strong>${esc(r.name)}:</strong> paid plans from ${esc(r.paid)}.</li>`).join('\n')}
<li><strong>OpenShorts Cloud:</strong> ${STARTER.name} at ${money(STARTER.monthly)}/month for ${STARTER.minutes} minutes, or self-host for $0.</li>
</ul>
<p>To price your own monthly volume across the tools that meter minutes, use the
calculator on <a href="/alternatives">the alternatives hub</a> or the
<a href="/opus-clip-pricing">Opus Clip pricing breakdown</a>.</p>

${faqBlock(faq)}

${sources([
  ...vendorRows.map((r) => `${esc(r.name)}: free tier and entry price checked ${esc(r.checked)}; details on <a href="${esc(r.link)}">our ${esc(r.name)} comparison</a>.`),
  `OpenShorts: <a href="/pricing">plans</a> and <a href="${SITE.repo}" rel="noopener">source on GitHub</a>.`,
])}
`,
    faq,
    related: ['/free-ai-clip-generator', '/alternatives', '/self-hosted-ai-clip-maker'],
  }
}

/* -------------------------------------------------- /how-to/clip-a-youtube-video */

const HOWTO_FAQ = [
  {
    q: 'How do you clip a YouTube video?',
    a: 'Note the start and end time of the part you want, then use one of four routes: YouTube Studio\'s editor or Video Clips tool for your own uploads, a free trimmer or ffmpeg on a copy of a video you have the rights to, or an AI clipper such as OpenShorts that finds the best moments and cuts them into vertical Shorts. YouTube\'s viewer Clip button, where it still appears, only makes a shareable link.',
  },
  {
    q: 'How do I cut a clip from a YouTube video?',
    a: 'Get a copy of the video you own or are licensed to use (YouTube Studio lets you download your own uploads), then cut it: ffmpeg -ss 00:01:30 -to 00:02:15 -i input.mp4 -c copy clip.mp4 keeps the part between 1:30 and 2:15 without re-encoding. Any free trimmer such as QuickTime, the Windows Photos app or your phone\'s gallery does the same with a slider.',
  },
  {
    q: 'How do I copy a video clip from YouTube?',
    a: 'To share a moment, use Share and tick "Start at" to copy a link that opens the video at that second. To get an actual file, you need a video you own or have permission to use: download your own upload from YouTube Studio, or use the creator\'s licence (for example Creative Commons), then trim it.',
  },
  {
    q: 'How do I take a clip from a YouTube video for TikTok or Shorts?',
    a: 'Cut the segment, then reframe it from 16:9 to 9:16 and add captions. You can do it by hand with an editor or ffmpeg, or paste the link into an AI clipper like OpenShorts, which picks 3 to 15 moments of 15 to 60 seconds, reframes them with face tracking and burns in word-level subtitles.',
  },
  {
    q: 'How do I save a clip of a YouTube video?',
    a: 'A YouTube Clip or a timestamp link is not a file; it plays the original video on YouTube and disappears if the video is removed. To keep a clip, save a trimmed copy of a video you have the rights to on your own device, with Studio\'s download plus a trimmer, or with ffmpeg.',
  },
  {
    q: 'Is YouTube Clips gone?',
    a: 'In April 2026 YouTube announced it was discontinuing the viewer Clips feature and making Share at timestamp, now on mobile too, the main way to share a moment. Creators keep the Video Clips tool in YouTube Studio for republishing parts of their own longer videos and archived streams. Availability can differ by account and region.',
  },
  {
    q: 'Can I clip someone else\'s YouTube video?',
    a: 'Sharing a link or timestamp is fine. Downloading, re-uploading or monetising a cut of someone else\'s video needs their permission or a licence that allows it, such as Creative Commons Attribution; YouTube\'s Terms of Service restrict downloading, and fair use is a narrow defence decided case by case, not a rule you can count on.',
  },
  {
    q: 'Can I clip a YouTube video on my phone?',
    a: 'Yes. Share at timestamp works in the mobile apps. For your own videos, the YouTube Studio app and the YouTube app\'s Shorts tools let you reuse parts of your uploads. For a file you have the rights to, the trim tool in the iPhone Photos app or Google Photos cuts it in seconds.',
  },
]

const howToClip = () => ({
  path: '/how-to/clip-a-youtube-video',
  title: 'How to Clip a YouTube Video in 2026 (4 Ways, Free)',
  description:
    'Four free ways to clip a YouTube video: share a moment, edit your own in YouTube Studio, cut it with ffmpeg or a free trimmer, or let AI cut it into Shorts.',
  h1: 'How to clip a YouTube video: 4 free ways, from a link to a vertical Short',
  breadcrumb: [{ name: 'Guides', path: '/how-to' }, { name: 'How to clip a YouTube video' }],
  published: PUBLISHED,
  updated: PUBLISHED,
  cta: {
    label: 'The fast way',
    title: 'Paste a YouTube link, get vertical clips',
    body: `OpenShorts finds the best moments and cuts them into 9:16 Shorts with captions. First video free up to ${FIRST_VIDEO_MINUTES} minutes, no credit card; self-hosted it is free under MIT.`,
    button: 'Clip a video',
  },
  tldr: [
    'There are four ways to clip a YouTube video, and which one you want depends on whether you need a <strong>link</strong>, a <strong>file</strong> or a <strong>vertical Short</strong>.',
    '<strong>1.</strong> Share a moment: the Clip button where you still see it, or Share at timestamp. <strong>2.</strong> YouTube Studio, for videos on your own channel. <strong>3.</strong> Cut the segment yourself with a free trimmer or one ffmpeg command. <strong>4.</strong> Let AI find the best moments and cut them into 9:16 Shorts with captions, with OpenShorts.',
    'Only clip content you own or have the rights to use. A link to someone else\'s video is fine; a downloaded and re-uploaded cut of it usually is not.',
  ],
  body: `
<h2>Which method should you use?</h2>
<table>
<thead><tr><th>You want</th><th>Method</th><th>Gives you</th><th>Works on</th></tr></thead>
<tbody>
<tr><td class="os">To send a friend one moment</td><td>1. Clip button or Share at timestamp</td><td>A link</td><td>Any public video</td></tr>
<tr><td class="os">To shorten or reuse your own upload</td><td>2. YouTube Studio</td><td>An edited video or a republished clip on YouTube</td><td>Your own channel</td></tr>
<tr><td class="os">An exact segment as a file</td><td>3. Free trimmer or ffmpeg</td><td>An MP4 on your device</td><td>Videos you own or are licensed to use</td></tr>
<tr><td class="os">Several Shorts from a long video</td><td>4. AI clipping (OpenShorts)</td><td>Vertical 9:16 clips with captions</td><td>Videos you own or are licensed to use</td></tr>
</tbody>
</table>
<p>Before any of them, find the exact moment. Scrub the timeline, or open the
transcript (the "Show transcript" button in the description) and search for a
phrase you remember: every line has a timestamp. Write down the start and end
time, to the second.</p>

<h2>Method 1: share a moment with the Clip button or a timestamp</h2>
<p>For years YouTube had a <strong>Clip</strong> button (the scissors icon under
the player) that let a viewer select a short stretch of a video, give it a
title and share it as a link. In April 2026 YouTube announced it was
discontinuing viewer Clips and making <strong>Share at timestamp</strong> the
main way to share a moment, now in the mobile apps as well as on desktop.
Rollouts are gradual, so what you see depends on your account and region.</p>
<p>If you still see the Clip button under a video:</p>
<ol>
<li>Click or tap <strong>Clip</strong>.</li>
<li>Drag the selection to the stretch you want and add a title.</li>
<li>Click <strong>Share clip</strong> and copy the link.</li>
</ol>
<p>If you do not, use a timestamp link, which does the same job for most people:</p>
<ol>
<li>Pause the video at the moment you want.</li>
<li>Click <strong>Share</strong>, tick <strong>Start at</strong> (it fills in the current time) and copy the link. On a phone, use the same option in the Share sheet where it is available.</li>
<li>Or add it by hand: append <code>&amp;t=95</code> (seconds) to a youtube.com/watch link, or <code>?t=95</code> to a youtu.be link.</li>
</ol>
<p>Both give you a <strong>link, not a file</strong>. The viewer watches the
original video on YouTube, the creator keeps the view, and if the video is
removed or made private the link stops working. That makes it the right method
for sharing and the wrong one for making your own content.</p>

<h2>Method 2: YouTube Studio, for videos on your own channel</h2>
<p>If the video is yours, YouTube Studio has three tools that cover most needs.</p>
<h3>Trim your upload in the Studio editor</h3>
<ol>
<li>Open YouTube Studio, go to <strong>Content</strong> and click the video.</li>
<li>Choose <strong>Editor</strong> in the left menu, then <strong>Trim &amp; cut</strong>.</li>
<li>Drag the edges to keep the part you want, or add cuts to remove stretches in the middle, then <strong>Save</strong>.</li>
</ol>
<p>This edits the published video itself; it does not create a second one. The
change takes a while to process, the URL and views stay the same, and some
videos cannot be edited (Studio tells you when). Keep a copy of the original
first if you might want it back.</p>
<h3>Republish part of a video with Video Clips</h3>
<p>YouTube Studio also has a <strong>Video Clips</strong> tool for creators,
which YouTube describes as letting you republish clips from your longer videos
and archived live streams. YouTube has said it will extend it to Shorts. Where
it is available on your channel, it is the most direct way to turn one segment
of your own video into its own upload without downloading anything.</p>
<h3>Download your own video to edit elsewhere</h3>
<p>In <strong>Content</strong>, open the three-dot menu on a video and choose
<strong>Download</strong>. You get an MP4 of your own upload, which you can then
cut with method 3 or clip with method 4. This is the clean, permitted way to get
a file of a YouTube video: it is your video, and Studio hands it to you.</p>

<h2>Method 3: cut the segment yourself, free</h2>
<p>Once you have a file you have the rights to (your own Studio download, your
original recording, or a video under a licence such as Creative Commons
Attribution), cutting a segment out takes seconds.</p>
<h3>With a free trimmer</h3>
<ul>
<li><strong>Mac:</strong> open the file in QuickTime Player, choose Edit, Trim, drag the yellow handles and save.</li>
<li><strong>Windows:</strong> open it in the Photos app or Clipchamp, which ship with Windows 11, and use Trim.</li>
<li><strong>iPhone:</strong> in Photos, tap Edit and drag the ends of the timeline; save as a new clip to keep the original.</li>
<li><strong>Android:</strong> in Google Photos, tap Edit and drag the trim handles, then Save copy.</li>
</ul>
<h3>With ffmpeg, to the exact second</h3>
<p>ffmpeg is free, runs on every operating system and is the tool most video
software uses underneath. This keeps the part from 1:30 to 2:15 without
re-encoding, so it is instant and lossless:</p>
<pre><code>ffmpeg -ss 00:01:30 -to 00:02:15 -i input.mp4 -c copy clip.mp4</code></pre>
<p>With <code>-c copy</code> the cut snaps to the nearest keyframe, so it can start
a fraction of a second early. For a frame-exact cut, re-encode instead:</p>
<pre><code>ffmpeg -ss 00:01:30 -to 00:02:15 -i input.mp4 -c:v libx264 -crf 18 -preset veryfast -c:a aac -b:a 160k clip.mp4</code></pre>
<p>And to turn a 16:9 segment into a centred 9:16 vertical clip for Shorts, TikTok
or Reels:</p>
<pre><code>ffmpeg -ss 00:01:30 -to 00:02:15 -i input.mp4 -vf "crop=ih*9/16:ih,scale=1080:1920" -c:v libx264 -crf 18 -c:a aac clip_vertical.mp4</code></pre>
<p>A fixed centre crop works when the speaker stays in the middle. When they
move, or there are two people on screen, a static crop cuts someone off, and
that is the point where doing it by hand stops scaling. If you only need the
format change, the free <a href="/video-aspect-ratio-converter">16:9 to 9:16
converter</a> does it in your browser.</p>
<p>For a Creative Commons video or your own upload, yt-dlp can download just the
part you need instead of the whole file:
<code>yt-dlp --download-sections "*00:01:30-00:02:15" &lt;video-url&gt;</code>. Use it
only where you have the rights; YouTube's Terms of Service restrict downloading
other people's videos.</p>

<h2>Method 4: let AI find the best moments and cut them into Shorts</h2>
<p>Methods 1 to 3 assume you already know which 30 seconds you want. With a
45-minute podcast or a two-hour stream, finding them is the real work. An AI
clipper does that part: it reads the whole video and returns the strongest
moments already cut, reframed and captioned.</p>
<p>With OpenShorts:</p>
<ol>
<li>Paste the YouTube link (or upload the file) at openshorts.app, or in your own self-hosted copy.</li>
<li>The video is transcribed with a timestamp for every word and scanned for scene cuts.</li>
<li>Google Gemini scores the transcript and picks the 3 to 15 strongest moments, each 15 to 60 seconds, that make sense on their own.</li>
<li>Each moment is cut and reframed to 9:16: face tracking for one speaker, both people stacked for a two-person podcast, the screen above the presenter for a tutorial.</li>
<li>Subtitles are burned in from the word-level transcript, with a hook line on the first seconds. Download the clips, or post them to YouTube Shorts, TikTok and Instagram Reels.</li>
</ol>
<p>The same rights rule applies: use it on your own videos, on channels you
manage, or on footage you are licensed to clip. The details for YouTube sources
are on <a href="/platforms/youtube">the YouTube clip maker</a> page, and for
turning a channel's long videos into Shorts, see
<a href="/platforms/youtube-shorts">the YouTube Shorts maker</a> and
<a href="/youtube-to-shorts-converter">the YouTube to Shorts converter</a>.</p>
<p>What it costs: OpenShorts self-hosted is free and open source under MIT, with
no watermark and no cap. OpenShorts Cloud clips your first video free up to
${FIRST_VIDEO_MINUTES} minutes, then ${FREE.monthly.minutes} minutes a month with a
watermark, and paid plans start at ${money(STARTER.monthly)}/month without one
(<a href="/pricing">all plans</a>).</p>

<h2>Copyright: what you are allowed to clip</h2>
<p>The method is the easy part. Whether you may use the clip is the one that gets
channels struck.</p>
<ul>
<li><strong>Sharing a link or timestamp</strong> to any public video is fine: it plays the original, on YouTube, credited to the creator.</li>
<li><strong>Your own videos</strong> are yours to cut, download from Studio and repost anywhere.</li>
<li><strong>Licensed videos</strong>, such as those marked Creative Commons Attribution (CC BY) in YouTube's description panel, can be reused if you credit the creator as the licence requires.</li>
<li><strong>Someone else's video</strong> needs their permission to download, re-upload or monetise. Many creators run clipping programmes and say so in their description; ask if not.</li>
<li><strong>Fair use</strong> (commentary, criticism, news) is a legal defence judged case by case, not a licence. Do not build a channel on the assumption that it covers you.</li>
</ul>
<p>Re-uploading other people's clips without permission also tends to trip
YouTube's reused-content rules for monetisation, independent of copyright.</p>

<h2>Clipping on mobile vs desktop</h2>
<p><strong>On a phone</strong>, sharing is the strong suit: Share at timestamp
from the Share sheet, and the YouTube and YouTube Studio apps for reusing parts
of your own uploads in Shorts. For a file you already have, the trim tools in
Photos and Google Photos are the quickest way to cut it.</p>
<p><strong>On a desktop</strong>, you get the full Studio editor, frame-exact
cuts with ffmpeg and a mouse for precise trimming. Long videos are also easier
to scrub on a big timeline. An AI clipper works the same on both, since the
processing happens on the server (or on your own machine when self-hosted).</p>

<h2>Common mistakes when clipping YouTube videos</h2>
<ul>
<li><strong>Cutting mid-sentence.</strong> Start a beat before the first word and end after the last one. A transcript with word timestamps makes this exact.</li>
<li><strong>Keeping 16:9 for Shorts.</strong> A horizontal clip in a vertical feed is a small box between black bars. Reframe to 9:16.</li>
<li><strong>No captions.</strong> Most short-form video is watched on mute. Burn subtitles in.</li>
<li><strong>Clips that need context.</strong> A moment that only makes sense after the previous ten minutes will not hold a stranger. Pick moments that stand alone.</li>
</ul>

${faqBlock(HOWTO_FAQ)}

${sources([
  'YouTube discontinuing viewer Clips in favour of Share at timestamp, and the Studio Video Clips tool: <a href="https://9to5google.com/2026/04/17/youtube-clips-share-at-time-changes/" rel="noopener">9to5Google, 17 April 2026</a>; <a href="https://www.tubefilter.com/2026/04/17/youtube-clipping-tool-viewer-clips-shorts/" rel="noopener">Tubefilter, 17 April 2026</a>.',
  'ffmpeg options <code>-ss</code>, <code>-to</code> and <code>-c copy</code>: <a href="https://ffmpeg.org/ffmpeg.html" rel="noopener">ffmpeg documentation</a>.',
  `OpenShorts pipeline: <a href="/how-openshorts-works">how OpenShorts works</a> and the <a href="${SITE.repo}" rel="noopener">source on GitHub</a>.`,
])}
`,
  faq: HOWTO_FAQ,
  extraNodes: [
    {
      '@type': 'HowTo',
      '@id': `${SITE.url}/how-to/clip-a-youtube-video#howto`,
      name: 'How to clip a YouTube video',
      description:
        'Cut a segment out of a YouTube video you own or are licensed to use, and turn it into a vertical clip for Shorts, TikTok or Reels.',
      totalTime: 'PT10M',
      supply: [{ '@type': 'HowToSupply', name: 'A YouTube video you own or have the rights to clip' }],
      tool: [
        { '@type': 'HowToTool', name: 'YouTube Studio' },
        { '@type': 'HowToTool', name: 'ffmpeg or a free video trimmer' },
        { '@type': 'HowToTool', name: 'OpenShorts (optional, for AI clipping)' },
      ],
      step: [
        {
          '@type': 'HowToStep',
          name: 'Find the moment',
          text: 'Scrub the timeline or search the video transcript for a phrase, and note the start and end time to the second.',
        },
        {
          '@type': 'HowToStep',
          name: 'Share it, or get a copy you have the rights to',
          text: 'To share, use Share with Start at for a timestamp link. To make a clip, download your own upload from YouTube Studio (Content, three-dot menu, Download), or use footage you are licensed to reuse.',
        },
        {
          '@type': 'HowToStep',
          name: 'Cut the segment',
          text: 'Trim it in QuickTime, the Windows Photos app or your phone gallery, or run: ffmpeg -ss 00:01:30 -to 00:02:15 -i input.mp4 -c copy clip.mp4',
        },
        {
          '@type': 'HowToStep',
          name: 'Make it vertical and add captions',
          text: 'For Shorts, TikTok or Reels, reframe the clip from 16:9 to 9:16 and burn in subtitles, by hand or with an AI clipper such as OpenShorts that also picks the moments.',
        },
        {
          '@type': 'HowToStep',
          name: 'Export and post',
          text: 'Save the clip as MP4 and upload it, crediting the original creator where the licence requires.',
        },
      ],
    },
  ],
  related: ['/platforms/youtube', '/platforms/youtube-shorts', '/youtube-to-shorts-converter'],
})

/* ------------------------------------------------- platform how-to guides */

/* Five informational guides under /how-to that answer a platform question
 * (specs, steps, timing) first and then point at the product. Platform facts
 * are dated: they are the ones the platforms' own help pages and announcements
 * gave as of the date below, and a number nobody publishes is described as a
 * rule of thumb, never as an official figure. Wording about OpenShorts
 * (posting targets, caption margin, scheduling) matches clip-tools.js and
 * autopilot-pages.js. */
const GUIDES_PUBLISHED = '2026-10-29'
const AS_OF = 'October 2026'
const APP_URL = `${SITE.url}/#app`

const PLAN_SHORT = `Cloud free plan with a watermark, paid plans from ${money(STARTER.monthly)}/month, self-hosted $0 under MIT.`
const PLAN_LINE =
  `OpenShorts Cloud has a free plan: your first video is clipped whole up to ${FIRST_VIDEO_MINUTES} minutes, then ` +
  `${FREE.monthly.minutes} minutes a month, with a watermark and no credit card. Paid plans start at ` +
  `${money(STARTER.monthly)}/month with no watermark, and the self-hosted edition is $0 under the MIT licence ` +
  '(<a href="/pricing">all plans</a>).'

/* The above-the-fold aside, rendered by render.js right after the summary. */
const guideCta = (title, body) => ({ label: 'Next step', title, body: `${body} ${PLAN_SHORT}`, button: 'Paste a link' })

/* The closing "try it" block: same markup as render.js's CTA box, reported with
 * its position so the end block can be told apart from the top one. */
const nextStep = (path, { heading, html, title, body }) => `
<h2>${esc(heading)}</h2>
${html}
<p>${PLAN_LINE}</p>
<div class="cta-box">
  <div class="copy">
    <span class="label">Next step</span>
    <strong>${esc(title)}</strong>
    <p>${esc(body)}</p>
  </div>
  <a class="btn" href="${esc(APP_URL)}" onclick="window.op&amp;&amp;window.op('track','SeoCtaClick',{page:'${esc(path)}',position:'end'})">Paste a link</a>
</div>`

const howToSteps = (path, name, description, steps, extra = {}) => ({
  '@type': 'HowTo',
  '@id': `${SITE.url}${path}#howto`,
  name,
  description,
  ...extra,
  step: steps.map(([n, text]) => ({ '@type': 'HowToStep', name: n, text })),
})

const guide = (path, crumb, page) => ({
  path,
  breadcrumb: [{ name: 'Guides', path: '/how-to' }, { name: crumb }],
  published: GUIDES_PUBLISHED,
  updated: GUIDES_PUBLISHED,
  ...page,
})

const SRC_IG_3MIN =
  'Instagram Reels up to 3 minutes: announced by Instagram in January 2025, reported by <a href="https://www.socialmediatoday.com/news/instagram-officially-expands-reels-length-3-minutes/737766/" rel="noopener">Social Media Today</a>.'
const SRC_YT_UPLOAD =
  '<a href="https://support.google.com/youtube/answer/12779649" rel="noopener">YouTube Help: Upload YouTube Shorts</a> (up to 3 minutes, square or vertical).'
const SRC_YT_3MIN =
  '<a href="https://support.google.com/youtube/answer/15424877" rel="noopener">YouTube Help: Understand three-minute YouTube Shorts</a> (uploads from 15 October 2024; Shorts over one minute with an active Content ID claim are blocked).'
const SRC_FB_REELS =
  'Facebook treating new videos as Reels with no length or format limits: <a href="https://creators.facebook.com/blog/making-it-easier-to-create-videos-on-facebook" rel="noopener">Meta for Creators, 17 June 2025</a>; <a href="https://techcrunch.com/2025/06/17/facebook-announces-that-all-videos-on-its-platform-will-soon-be-shared-as-reels" rel="noopener">TechCrunch, 17 June 2025</a>.'
const SRC_CAPTIONS = `Caption placement (about 15% of the frame height above the bottom edge) is <code>SAFE_MARGIN_V</code> in <code>subtitles.py</code> at <a href="${SITE.repo}" rel="noopener">github.com/mutonby/openshorts</a>.`

/* ------------------------------------------- /how-to/instagram-reel-dimensions */

const REEL_DIM_FAQ = [
  {
    q: 'What are the dimensions of an Instagram Reel?',
    a: '1080 x 1920 pixels, which is a 9:16 vertical frame that fills a phone screen. That is the size to export at. Instagram accepts other sizes, but anything that is not 9:16 is shown with empty space around it or cropped.',
  },
  {
    q: 'What is the Instagram Reel size in pixels?',
    a: '1080 pixels wide by 1920 pixels tall. 720 x 1280 is the same shape and still uploads, but it looks softer once Instagram compresses it. Going above 1080 x 1920 rarely shows on a phone, because the file is recompressed for playback anyway.',
  },
  {
    q: 'What aspect ratio is an Instagram Reel?',
    a: '9:16, vertical. A 16:9 horizontal video uploaded as a Reel plays as a narrow band in the middle of the screen, so convert it to 9:16 first with a blurred background, a crop or an AI reframe that follows the speaker.',
  },
  {
    q: 'How long can an Instagram Reel be?',
    a: 'Up to 3 minutes. Instagram raised the limit from 90 seconds in January 2025. Most Reels that hold attention are far shorter: pick the length that fits the moment rather than filling the limit.',
  },
  {
    q: 'What is the Instagram Reel safe zone?',
    a: 'Instagram does not publish one for organic Reels. As a rule of thumb, keep text and faces out of the bottom strip (roughly the lowest 15% of the frame, more when the description is long), the right edge where the buttons sit and the very top. Meta\'s guidance for Reels ads, as widely quoted, is stricter: about 14% clear at the top, 35% at the bottom and 6% on each side.',
  },
  {
    q: 'What size should an Instagram Reel cover be?',
    a: '1080 x 1920, the same as the Reel. As of October 2026 the profile grid shows a 3:4 crop from the middle of it, roughly the centre 1080 x 1440, so put the title and the face in that band.',
  },
  {
    q: 'Can I post a horizontal video as a Reel?',
    a: 'You can, but it will not fill the screen and most viewers scroll past a small box. Convert it to 9:16 first. The free OpenShorts converter does it in your browser; the clip generator reframes it by tracking the speaker.',
  },
  {
    q: 'What is the best file format for a Reel?',
    a: 'MP4 with H.264 video, 8-bit 4:2:0 colour (yuv420p), 30 frames per second, and AAC audio at 48 kHz. That combination uploads everywhere and is what most editors export by default.',
  },
]

const reelDimensions = () => {
  const path = '/how-to/instagram-reel-dimensions'
  return guide(path, 'Instagram Reel dimensions', {
    title: 'Instagram Reel Dimensions, Size and Safe Zone (2026)',
    description:
      'Instagram Reel dimensions as of October 2026: 1080 x 1920 at 9:16, up to 3 minutes, how the cover is cropped on the grid, safe zones and export settings.',
    h1: 'Instagram Reel dimensions: size, aspect ratio, cover and safe zones',
    cta: guideCta('Turn a long video into Reels with AI', 'Paste a link and get 1080 x 1920 Reels with captions placed clear of Instagram\'s buttons.'),
    tldr: [
      'An Instagram Reel is <strong>1080 x 1920 pixels</strong>, a <strong>9:16</strong> vertical frame, and can run <strong>up to 3 minutes</strong> (Instagram raised the limit from 90 seconds in January 2025). Export an MP4 with H.264 video and AAC audio at 30 frames per second and you will not hit a format problem.',
      `The whole 9:16 frame plays in the Reels feed, but the cover is cropped elsewhere: as of ${AS_OF} the profile grid shows a 3:4 slice from the middle. Keep faces and cover text in the centre, captions out of the bottom strip where Instagram draws the username, description and audio line, and nothing important under the buttons on the right.`,
      'Got a horizontal 16:9 video? Convert it to 9:16 with a blurred background, a crop or bars in the free converter, or let an AI reframe keep the speaker in shot.',
    ],
    facts: [
      { k: 'Size', v: '1080 x 1920', s: 'Pixels, width by height' },
      { k: 'Aspect ratio', v: '9:16', s: 'Vertical, full screen' },
      { k: 'Max length', v: '3 min', s: 'Since January 2025' },
      { k: 'Grid crop', v: '3:4', s: `Cover on the profile, as of ${AS_OF}` },
    ],
    body: `
<h2>Instagram Reel size at a glance</h2>
<table>
<thead><tr><th>Spec</th><th>Use this</th><th>Why</th></tr></thead>
<tbody>
<tr><td class="os">Resolution</td><td>1080 x 1920 px</td><td>Fills a phone screen sharply; 720 x 1280 works but looks softer after compression</td></tr>
<tr><td class="os">Aspect ratio</td><td>9:16</td><td>Any other shape is shown with empty space around it or cropped</td></tr>
<tr><td class="os">Length</td><td>Up to 3 minutes</td><td>The limit since January 2025; most good Reels are much shorter</td></tr>
<tr><td class="os">File</td><td>MP4, H.264, yuv420p</td><td>The most compatible combination; MOV and HEVC from a phone usually work too</td></tr>
<tr><td class="os">Frame rate</td><td>30 fps</td><td>Keep the source rate between 24 and 60; do not convert 25 to 30 for no reason</td></tr>
<tr><td class="os">Audio</td><td>AAC, 48 kHz, stereo</td><td>What every editor exports by default</td></tr>
<tr><td class="os">Cover</td><td>1080 x 1920 image or a frame</td><td>The grid shows the middle 3:4 (about 1080 x 1440)</td></tr>
<tr><td class="os">Text safe area</td><td>Centre of the frame</td><td>The bottom strip, the right edge and the top are covered by Instagram's interface</td></tr>
</tbody>
</table>
<p class="checked">Platform details as of ${AS_OF}. Instagram changes its interface often and rolls changes out gradually, so what you see in your app can differ slightly.</p>

<h2>Why 1080 x 1920 and 9:16</h2>
<p>A Reel is made to be watched full screen on a phone held upright, and 9:16 is
the shape of that screen: nine units wide for every sixteen tall. 1080 pixels
wide is the width Instagram is built around for full-screen video, so
1080 x 1920 is the size that fills the screen without being scaled up.</p>
<p>Two things follow from that. First, a smaller file of the same shape, such as
720 x 1280, uploads fine but is enlarged on the way to the screen, and after
Instagram's own compression the softness shows in faces and text. Second, a
larger file, such as a 2160 x 3840 export from a 4K camera, rarely looks better
to the viewer, because Instagram recompresses every upload for playback and a
phone screen shows only so much detail. Upload at 1080 x 1920 unless your source
is genuinely sharper and you have checked the result.</p>
<p>What happens with other shapes: Instagram accepts them, but a Reel that is
not 9:16 does not fill the screen. A horizontal 16:9 video plays as a band
across the middle with empty space above and below, and a square video leaves
less of a gap but still does not fill the frame. In a feed people scroll with
one thumb, a small picture loses to a full one.</p>

<h2>How long can an Instagram Reel be?</h2>
<p>Up to <strong>3 minutes</strong>. Instagram raised the limit from 90 seconds
in January 2025. The limit is a ceiling, not a target. A Reel is judged in its
first second or two, and the moments that hold a stranger's attention usually
run between about 15 seconds and a minute: a single idea, a single story, a
single answer. Use the extra length when the moment needs it, for a tutorial
step or a story that only lands at the end, and not to fit more in.</p>
<p>A video longer than the Reels limit is not cut for you. Trim it first, or
split a long recording into several Reels that each stand on their own.</p>

<h2>The Reel cover: what shows where (as of ${AS_OF})</h2>
<p>The cover is the still image people see before the Reel plays. It appears in
three places, and only one of them shows the whole frame:</p>
<ul>
<li><strong>The Reels tab and full screen</strong> show the full 9:16 cover.</li>
<li><strong>Your profile grid</strong> shows a crop. Instagram moved the grid from square tiles to taller 3:4 rectangles in early 2025, so the grid shows roughly the middle 1080 x 1440 of a 1080 x 1920 cover: about 240 pixels are cut from the top and the same from the bottom.</li>
<li><strong>The main feed and shares</strong> can show a shorter crop than full screen, depending on where the Reel appears and the app version.</li>
</ul>
<p>The safe way to design a cover is to put everything that matters, the face
and the title text, in the middle band and treat the top and bottom as
background. When you pick the cover, Instagram lets you choose a frame from the
video or upload an image from your camera roll, and shows how the profile grid
will crop it so you can adjust it. Upload a cover image at 1080 x 1920, keep the
title short and large enough to read at grid size, and check the grid preview
before you share.</p>

<h2>Instagram Reel safe zones</h2>
<p>Instagram draws its interface on top of your video. Anything under it is
still in the file, but the viewer cannot read it. The parts that cover the
frame, as of ${AS_OF}:</p>
<ul>
<li><strong>The bottom strip:</strong> your username and follow button, the description (which grows when it is long or tapped open) and the audio line.</li>
<li><strong>The right edge:</strong> the like, comment, share and more buttons, stacked vertically, with the audio thumbnail below them.</li>
<li><strong>The top:</strong> the Reels header and camera icon.</li>
</ul>
<p>Instagram does not publish an official safe zone for organic Reels, so treat
any number you read as a rule of thumb. A practical working area on a
1080 x 1920 frame: keep captions and key text above the lowest 15% or so of the
frame (more if your descriptions are long), clear of the right-hand 10 to 15%,
and a little below the top edge. Faces sit comfortably in the centre third.</p>
<p>Ads are stricter. Meta's guidance for Reels ads, as widely quoted, asks you to
keep roughly 14% of the top, 35% of the bottom and 6% of each side free of text
and logos, which on a 1080 x 1920 frame is about 270, 670 and 65 pixels. If a
Reel may be boosted or reused as an ad, design for those margins from the start.</p>
<p>For reference, OpenShorts burns its captions about 15% of the frame height
above the bottom edge, which keeps them clear of the username and description
Instagram draws on an organic Reel.</p>

<h2>How to convert a 16:9 video to 9:16 for a Reel</h2>
<p>Most recordings are horizontal: a webinar, a podcast camera, a screen
recording, a YouTube video. There are three ways to make them vertical, and the
right one depends on what is in the picture.</p>
<h3>1. Keep the whole frame over a blurred background</h3>
<p>The original 16:9 picture sits in the middle at full width, and a blurred,
enlarged copy fills the space above and below. Nothing is cut off, which suits
slides, wide shots and anything with text across the frame. The picture is
small, though: a 1920 x 1080 frame scaled to 1080 wide is only about 608 pixels
tall. In ffmpeg:</p>
<pre><code>ffmpeg -i input.mp4 -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20[bg];[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2" -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a aac reel.mp4</code></pre>
<h3>2. Crop to fill</h3>
<p>A 9:16 window is cut out of the 16:9 frame and enlarged to fill the screen.
It looks native, but it keeps only about a third of the original width, so it
works when the subject stays in the middle and fails when they move or when two
people sit side by side. A centred crop in ffmpeg:</p>
<pre><code>ffmpeg -i input.mp4 -vf "crop=ih*9/16:ih,scale=1080:1920" -c:v libx264 -crf 20 -pix_fmt yuv420p -c:a aac reel.mp4</code></pre>
<h3>3. Black bars</h3>
<p>The frame is placed in the middle with black above and below. It is the
simplest and the least attractive; use it only when you need the exact picture
untouched.</p>
<p>All three run in your browser, with no upload and no account, in the free
<a href="/video-aspect-ratio-converter">16:9 to 9:16 converter</a>. What none of
them does is follow a person. When the speaker walks across the frame, or two
people talk in turn, a fixed crop cuts someone off. That is what an AI reframe
is for: it tracks the face that is speaking, stacks two speakers one above the
other, or keeps a shared screen readable with the presenter beside it. The
modes are explained on <a href="/auto-reframe">the auto reframe page</a>.</p>

<h2>Export settings that upload cleanly</h2>
<p>Instagram recompresses everything, so the goal is a clean, high-quality file
in a standard format, not the smallest one. These settings work in any editor,
and as an ffmpeg command:</p>
<pre><code>ffmpeg -i edit.mov -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -movflags +faststart reel.mp4</code></pre>
<ul>
<li><strong>H.264 in an MP4</strong> is the most compatible pairing. HEVC (H.265) from a recent phone usually uploads fine too.</li>
<li><strong>yuv420p (8-bit 4:2:0)</strong> matters more than it looks. Some cameras record 10-bit or 4:2:2 colour, which can upload with shifted colours or fail outright.</li>
<li><strong>Keep the source frame rate.</strong> 24, 25, 30 or 60 are all fine; converting between them adds judder.</li>
<li><strong>HDR footage</strong> from recent phones is sometimes shown with different brightness than you expect. If colours matter, export in standard dynamic range and check it on your own phone.</li>
<li><strong>Upload over Wi-Fi</strong> and, in the app's settings, turn on the option to upload at the highest quality if your app shows it.</li>
</ul>

<h2>Common mistakes</h2>
<ul>
<li><strong>Text at the very bottom.</strong> Captions placed where a TV subtitle would go end up under the username and description.</li>
<li><strong>A cover designed for the full frame.</strong> The title at the top of the cover disappears in the 3:4 grid crop.</li>
<li><strong>Uploading horizontal and hoping.</strong> A small 16:9 band in a vertical feed is easy to scroll past.</li>
<li><strong>Exporting below 1080 wide.</strong> It saves nothing and costs sharpness after compression.</li>
<li><strong>Using all 3 minutes because you can.</strong> Length should come from the moment, not the limit.</li>
</ul>

${nextStep(path, {
  heading: 'Next step: turn a long video into Reels with AI',
  html: `<p>If your Reels come from longer recordings (a podcast, a webinar, a class,
a YouTube video), the slow part is not the size: it is watching the whole thing
to find the moments that stand alone, then cutting, reframing and captioning
each one. OpenShorts does that part. Paste a link or upload the file, and it
returns 1080 x 1920 Reels with word-level captions placed clear of Instagram's
interface and a hook over the opening seconds. It can publish them to Instagram
as Reels or schedule a week of them; for Facebook Reels you download the MP4.
The details are on <a href="/platforms/instagram-reels">the AI reel generator</a>
page.</p>`,
  title: 'Paste a link, get 9:16 Reels with captions',
  body: 'The AI picks the moments, reframes them to 1080 x 1920 and burns in captions.',
})}

${faqBlock(REEL_DIM_FAQ)}

${sources([
  SRC_IG_3MIN,
  'Instagram\'s 3:4 profile grid (early 2025) and the Reels interface are described as of October 2026 from the Instagram app; Instagram does not publish an official safe zone for organic Reels.',
  'Reels ad margins (about 14% top, 35% bottom, 6% sides) as quoted from Meta\'s ad guidance by advertising guides; check Meta\'s current ad specs before relying on them for a campaign.',
  'ffmpeg filters <code>scale</code>, <code>crop</code>, <code>boxblur</code> and <code>overlay</code>: <a href="https://ffmpeg.org/ffmpeg-filters.html" rel="noopener">ffmpeg filters documentation</a>.',
  SRC_CAPTIONS,
])}
`,
    faq: REEL_DIM_FAQ,
    extraNodes: [
      howToSteps(path, 'How to size a video for an Instagram Reel',
        'Make a video 1080 x 1920 at 9:16, keep its text inside the safe area and export it in a format Instagram accepts.', [
          ['Start vertical, or convert', 'Record in 9:16, or convert a 16:9 video with a blurred background, a crop or an AI reframe that follows the speaker.'],
          ['Set the size to 1080 x 1920', 'Export at 1080 pixels wide by 1920 tall, the size that fills a phone screen without being enlarged.'],
          ['Keep text in the safe area', 'Place captions above the lowest 15% or so of the frame, away from the buttons on the right edge and below the top edge.'],
          ['Export a standard file', 'MP4 with H.264 video in yuv420p, the source frame rate (30 fps is typical) and AAC audio at 48 kHz.'],
          ['Pick the cover and check the grid', 'Choose a frame or upload a 1080 x 1920 image, and keep the face and title in the middle 3:4 that the profile grid shows.'],
        ], { totalTime: 'PT10M' }),
    ],
    related: ['/platforms/instagram-reels', '/video-aspect-ratio-converter', '/auto-reframe'],
  })
}

/* ------------------------------------------- /how-to/youtube-shorts-aspect-ratio */

const SHORTS_AR_FAQ = [
  {
    q: 'What is the aspect ratio of YouTube Shorts?',
    a: '9:16 vertical is the standard, and square (1:1) is also accepted. YouTube\'s help pages say a Short must have a square or vertical aspect ratio and run up to 3 minutes. A horizontal video is uploaded as a regular video, not a Short.',
  },
  {
    q: 'What size is a YouTube Short?',
    a: '1080 x 1920 pixels for a 9:16 Short, or 1080 x 1080 for a square one. Those are the sizes to export at. Higher resolutions are accepted, but on a phone the difference is small.',
  },
  {
    q: 'What resolution should a YouTube Short be?',
    a: '1080 x 1920 (1080p vertical) is the practical standard. 720 x 1280 uploads and plays, but looks softer. If you shoot in 4K vertical you can upload it, and YouTube will offer the higher quality where the viewer\'s screen and connection allow.',
  },
  {
    q: 'How long can a YouTube Short be?',
    a: 'Up to 3 minutes, for videos uploaded from 15 October 2024. Before that the limit was 60 seconds, and longer vertical videos uploaded before that date stay regular videos.',
  },
  {
    q: 'Do I need #Shorts in the title?',
    a: 'No. YouTube decides that an upload is a Short from its shape and length: square or vertical, up to 3 minutes. A hashtag does not turn a horizontal video into a Short.',
  },
  {
    q: 'What is the YouTube Shorts safe zone?',
    a: 'YouTube does not publish exact pixel margins. As a rule of thumb, keep text and faces out of the bottom strip where the title, channel name and subscribe button appear (roughly the lowest 15%, more when a title runs to two lines), away from the column of buttons on the right edge, and a little below the top.',
  },
  {
    q: 'Can I upload a horizontal video as a Short?',
    a: 'Not as a Short: a 16:9 video is treated as a regular upload. Convert it to 9:16 first with a crop, a blurred background or an AI reframe that follows the speaker, then upload it.',
  },
  {
    q: 'Why is my Short over one minute blocked?',
    a: 'YouTube blocks a Short longer than one minute worldwide while it has an active Content ID claim of any type, for example from music added outside YouTube. It becomes viewable again once the claim is resolved. Shorts under one minute are not affected by this rule.',
  },
]

const shortsAspectRatio = () => {
  const path = '/how-to/youtube-shorts-aspect-ratio'
  return guide(path, 'YouTube Shorts aspect ratio', {
    title: 'YouTube Shorts Aspect Ratio, Size and Resolution (2026)',
    description:
      'YouTube Shorts aspect ratio and size as of October 2026: 9:16 at 1080 x 1920, square allowed, up to 3 minutes, safe zones, and how to make 16:9 vertical.',
    h1: 'YouTube Shorts aspect ratio, size and resolution',
    cta: guideCta('Turn a long video into Shorts with AI', 'Paste a YouTube link and get 1080 x 1920 Shorts with captions and a hook.'),
    tldr: [
      'A YouTube Short is <strong>9:16 vertical at 1080 x 1920 pixels</strong>. YouTube also accepts <strong>square</strong> (1:1, 1080 x 1080). It must run <strong>up to 3 minutes</strong>. Square or vertical and up to 3 minutes is what makes an upload a Short; no hashtag is needed.',
      'A horizontal 16:9 video is uploaded as a regular video, however short it is. To make it a Short, convert it to 9:16 with a crop, a blurred background or an AI reframe that keeps the speaker in shot.',
      `Keep text out of the bottom strip, where the Shorts player shows the title, channel name and subscribe button, and away from the buttons down the right edge (as of ${AS_OF}).`,
    ],
    facts: [
      { k: 'Aspect ratio', v: '9:16', s: 'Square 1:1 also accepted' },
      { k: 'Size', v: '1080 x 1920', s: 'Pixels, width by height' },
      { k: 'Max length', v: '3 min', s: 'Uploads from 15 Oct 2024' },
      { k: 'Horizontal', v: 'Not a Short', s: 'Uploaded as a regular video' },
    ],
    body: `
<h2>YouTube Shorts specs at a glance</h2>
<table>
<thead><tr><th>Spec</th><th>Use this</th><th>Notes</th></tr></thead>
<tbody>
<tr><td class="os">Aspect ratio</td><td>9:16 vertical</td><td>Square (1:1) is accepted too; horizontal is not a Short</td></tr>
<tr><td class="os">Size</td><td>1080 x 1920 px</td><td>1080 x 1080 for a square Short</td></tr>
<tr><td class="os">Resolution</td><td>1080p vertical</td><td>720p uploads but looks softer; 4K vertical is accepted</td></tr>
<tr><td class="os">Length</td><td>Up to 3 minutes</td><td>For uploads from 15 October 2024; 60 seconds before</td></tr>
<tr><td class="os">File</td><td>MP4, H.264, AAC</td><td>The safest upload; YouTube accepts most common formats</td></tr>
<tr><td class="os">Frame rate</td><td>Same as the source</td><td>24, 25, 30, 50 and 60 fps all work</td></tr>
<tr><td class="os">Text safe area</td><td>Centre of the frame</td><td>The bottom strip and the right edge are covered by the player</td></tr>
</tbody>
</table>
<p class="checked">Length and aspect ratio from YouTube's help pages; the player layout as of ${AS_OF}. YouTube tests interface changes gradually, so your app may differ slightly.</p>

<h2>9:16, square, and why horizontal is not a Short</h2>
<p>YouTube's help pages describe a Short by two properties: a <strong>square or
vertical</strong> aspect ratio and a length of <strong>up to 3 minutes</strong>.
An upload that has both is a Short and appears on the Shorts shelf and in the
Shorts feed. One that is horizontal is a regular video, even at 30 seconds, and
one that is vertical but longer than 3 minutes is a regular video too.</p>
<p>9:16 is the shape to aim for because the Shorts player is full screen on a
phone held upright. A square Short is allowed, but in the player it sits in the
middle with space above and below, so it fills only part of the screen. Square
makes sense when the same file must also work in a square placement elsewhere;
for Shorts alone, vertical uses the whole screen.</p>
<p>Uploading the same video as a Short and as a regular video is a matter of the
file, not a setting: export a 9:16 version for Shorts and keep the 16:9 one for
the main channel.</p>

<h2>YouTube Shorts size and resolution</h2>
<p><strong>1080 x 1920</strong> is the size to export a vertical Short at, and
<strong>1080 x 1080</strong> a square one. It is the width that fills a phone
screen sharply without being enlarged. A 720 x 1280 file has the same shape and
uploads fine, but after YouTube's compression it looks noticeably softer on
faces and text. If you shoot vertical 4K (2160 x 3840), YouTube accepts it and
can serve a higher-quality stream where the screen and connection allow; whether
viewers see the difference on a phone is another matter, and the file takes much
longer to upload.</p>
<p>Export settings that work: MP4 with H.264 video in 8-bit 4:2:0 colour
(yuv420p), the source frame rate, and AAC audio at 48 kHz. In ffmpeg:</p>
<pre><code>ffmpeg -i edit.mov -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -movflags +faststart short.mp4</code></pre>

<h2>How long can a YouTube Short be?</h2>
<p>Up to <strong>3 minutes</strong>. YouTube raised the limit from 60 seconds
for videos uploaded from 15 October 2024; a vertical video longer than a minute
uploaded before that date stays a regular video. The help page on three-minute
Shorts adds one rule worth knowing: a Short <strong>longer than one minute with
an active Content ID claim</strong> of any type is blocked worldwide until the
claim is resolved. If you add a commercial song outside YouTube, keep the Short
under a minute or use music you are sure is cleared.</p>
<p>As with any short-form format, the limit is a ceiling. A Short is decided in
the first second or two of the feed, and most moments that hold a stranger run
well under a minute.</p>

<h2>YouTube Shorts safe zones</h2>
<p>The Shorts player draws its controls on top of the video. As of ${AS_OF}:</p>
<ul>
<li><strong>The bottom strip</strong> carries the title, the channel name and avatar, the subscribe button and, when present, the sound and a related-video link. It grows when the title runs to two lines.</li>
<li><strong>The right edge</strong> carries a column of buttons: like, dislike, comments, share, remix and the sound thumbnail.</li>
<li><strong>The top</strong> carries the search and menu icons.</li>
</ul>
<p>YouTube does not publish exact pixel margins, so treat numbers as rules of
thumb. A practical working area on a 1080 x 1920 frame: keep captions and key
text above the lowest 15% or so of the frame, clear of the right-hand 10 to 15%,
and a little below the top edge. Faces and the main action belong in the centre
of the frame. Check a draft on your own phone before you publish a batch.</p>
<p>OpenShorts places burned-in captions about 15% of the frame height above the
bottom edge, so the title, channel name and buttons of the Shorts player do not
sit on top of them.</p>

<h2>How to turn a 16:9 video into a 9:16 Short</h2>
<p>A horizontal video has to change shape before it can be a Short. There are
three common ways, and one smart one.</p>
<ul>
<li><strong>Crop to fill.</strong> Cut a 9:16 window out of the middle and enlarge it. It looks native, but keeps only about a third of the width, so a subject who moves, or a second person, ends up out of frame.</li>
<li><strong>Blurred background.</strong> Keep the whole 16:9 picture across the middle and fill above and below with a blurred copy. Nothing is lost, but the picture is small: about 608 pixels tall in a 1920-pixel frame.</li>
<li><strong>Black bars.</strong> The same, with black instead of blur. The simplest and the least attractive.</li>
<li><strong>Reframe that follows the speaker.</strong> A crop that moves with the face that is talking, two speakers stacked one above the other, or a screen recording kept readable with the presenter beside it.</li>
</ul>
<p>The first three run in your browser, with no upload and no account, in the
free <a href="/video-aspect-ratio-converter">16:9 to 9:16 converter</a>. A
centred crop in ffmpeg is one line:</p>
<pre><code>ffmpeg -i input.mp4 -vf "crop=ih*9/16:ih,scale=1080:1920" -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac short.mp4</code></pre>
<p>The fourth is what an AI reframe does, and why a fixed crop is fine for a
single speaker sitting still but not for a podcast, an interview or a talk. The
modes are explained on <a href="/auto-reframe">the auto reframe page</a>.</p>

<h2>Common mistakes</h2>
<ul>
<li><strong>Uploading a short horizontal clip and expecting a Short.</strong> Shape decides it, not length alone.</li>
<li><strong>Captions in the TV position.</strong> Low captions end up under the title and channel name.</li>
<li><strong>Text under the right-hand buttons.</strong> Long captions that run edge to edge get partly covered.</li>
<li><strong>Exporting at 720p to save time.</strong> The softness shows after compression.</li>
<li><strong>A claimed song on a two-minute Short.</strong> Over one minute, an active Content ID claim blocks the Short.</li>
</ul>

${nextStep(path, {
  heading: 'Next step: make Shorts from your long videos',
  html: `<p>Getting the aspect ratio right is the easy part. The work behind a
steady flow of Shorts is finding the moments in your long videos that stand
alone and cutting each one: reframed to 9:16, captioned, with a hook in the
first seconds. OpenShorts reads the whole video, picks those moments and
returns them as 1080 x 1920 Shorts, 15 to 60 seconds by default and up to 3
minutes if you raise the maximum. It can publish them to your channel or
schedule a week of them. See <a href="/platforms/youtube-shorts">the YouTube
Shorts maker</a> for the details.</p>`,
  title: 'Paste a YouTube link, get 9:16 Shorts',
  body: 'Moments picked from the whole video, reframed to follow the speaker, captioned word by word.',
})}

${faqBlock(SHORTS_AR_FAQ)}

${sources([
  SRC_YT_UPLOAD,
  SRC_YT_3MIN,
  'The Shorts player layout is described as of October 2026 from the YouTube app; YouTube does not publish pixel safe-zone margins.',
  SRC_CAPTIONS,
])}
`,
    faq: SHORTS_AR_FAQ,
    extraNodes: [
      howToSteps(path, 'How to format a video for YouTube Shorts',
        'Make a video 9:16 at 1080 x 1920 and up to 3 minutes long so YouTube treats it as a Short.', [
          ['Make it vertical', 'Record in 9:16, or convert a 16:9 video with a crop, a blurred background or an AI reframe that follows the speaker. Square 1:1 is also accepted.'],
          ['Export at 1080 x 1920', 'Export MP4 with H.264 video in yuv420p, the source frame rate and AAC audio.'],
          ['Keep it to 3 minutes or less', 'Shorts can run up to 3 minutes. Over one minute, avoid music that may carry a Content ID claim.'],
          ['Keep text in the safe area', 'Place captions above the bottom strip where the title and channel name appear, and away from the buttons on the right edge.'],
          ['Upload it', 'Upload from the YouTube app or YouTube Studio. A square or vertical video up to 3 minutes becomes a Short automatically.'],
        ], { totalTime: 'PT10M' }),
    ],
    related: ['/platforms/youtube-shorts', '/auto-reframe', '/video-aspect-ratio-converter'],
  })
}

/* --------------------------------------------- /how-to/make-a-reel-on-facebook */

const FB_REEL_FAQ = [
  {
    q: 'How do I make a Reel on Facebook?',
    a: 'In the Facebook app, tap Create (or the plus button) and choose Reel. Record or pick a video from your gallery, edit it with audio, text and effects, tap Next, write a description, choose the audience and share it. Labels move around between app versions, but the flow is the same.',
  },
  {
    q: 'How do I post a Reel on Facebook from a computer?',
    a: 'For a Page, use Meta Business Suite: choose Create reel, upload a vertical video, add a description and share it now or schedule it. Since 2025 Facebook also treats new video uploads as Reels, so a vertical video posted from a Page on the web generally becomes a Reel as well.',
  },
  {
    q: 'How long can a Facebook Reel be?',
    a: 'In June 2025 Meta announced that all new Facebook videos would be shared as Reels, with no length or format limit, rolled out gradually. Before that, Reels were capped at 90 seconds. The Reels feed is still made for short vertical clips.',
  },
  {
    q: 'What size is a Facebook Reel?',
    a: '1080 x 1920 pixels, 9:16 vertical. Export an MP4 with H.264 video and AAC audio. Keep captions clear of the bottom strip where Facebook shows your name and description, and of the buttons on the right edge.',
  },
  {
    q: 'Can I share my Instagram Reels to Facebook automatically?',
    a: 'Yes, if both accounts are in the same Accounts Center. Turn on the Facebook option on Instagram\'s share screen for one Reel, or set it to always share in Accounts Center under sharing across profiles. Some music licensed on Instagram may not be available on Facebook.',
  },
  {
    q: 'Can I schedule a Facebook Reel?',
    a: 'For a Page, yes: Meta Business Suite lets you schedule a Reel for a date and time. Scheduling options for personal profiles depend on whether professional mode is on and on the app version.',
  },
  {
    q: 'Why can\'t I see the Reel option on Facebook?',
    a: 'Update the app first: Reels tools roll out by region and account type, and the Create menu changes between versions. On the web, personal profiles have fewer creation tools than Pages; Meta Business Suite is the reliable desktop route for a Page.',
  },
  {
    q: 'Can I make Facebook Reels from a long video?',
    a: 'Yes. Cut the strongest moments out of the long video, reframe them to 9:16 and caption them, by hand in an editor or with an AI clipper such as OpenShorts, then upload each one as a Reel. OpenShorts makes the files; you post them to Facebook yourself.',
  },
]

const facebookReel = () => {
  const path = '/how-to/make-a-reel-on-facebook'
  return guide(path, 'How to make a Reel on Facebook', {
    title: 'How to Make a Reel on Facebook (Phone and Desktop, 2026)',
    description:
      'How to make and post Reels on Facebook as of October 2026: the app on your phone, Meta Business Suite on desktop, specs, sharing from Instagram, long videos.',
    h1: 'How to make a Reel on Facebook, on your phone or a computer',
    cta: guideCta('Turn a long video into Reels with AI', 'Paste a link and download 9:16 Reels with captions, ready to post on Facebook.'),
    tldr: [
      '<strong>On your phone:</strong> open the Facebook app, tap <strong>Create</strong> (or the plus button) and choose <strong>Reel</strong>, record or pick a video, edit it, tap <strong>Next</strong>, write a description, choose who can see it and <strong>Share</strong>.',
      '<strong>On a computer:</strong> for a Page, open <strong>Meta Business Suite</strong>, choose <strong>Create reel</strong>, upload a vertical video, add a description and share it or schedule it. Since 2025 Facebook also treats new video uploads as Reels.',
      `Make it <strong>1080 x 1920, 9:16</strong>, and keep text in the centre. If you already post Reels on Instagram, you can share them to Facebook automatically. Steps and labels as of ${AS_OF}; Meta changes the menus often.`,
    ],
    facts: [
      { k: 'Size', v: '1080 x 1920', s: '9:16 vertical' },
      { k: 'Length', v: 'No fixed cap', s: 'Since Meta\'s June 2025 change' },
      { k: 'Desktop', v: 'Business Suite', s: 'Create reel, for Pages' },
      { k: 'From Instagram', v: 'Auto-share', s: 'Via Accounts Center' },
    ],
    body: `
<h2>How to make a Reel in the Facebook app</h2>
<p>The Facebook app on iPhone and Android is the main place to create Reels,
and the only one with the full set of editing tools. As of ${AS_OF} the flow
is:</p>
<ol>
<li><strong>Open Create.</strong> Tap the plus button or the <strong>Create</strong> area at the top of your feed and choose <strong>Reel</strong>. You can also start from the Reels tab (which replaced the old Video tab in 2025) by tapping the create or camera icon.</li>
<li><strong>Record or choose a video.</strong> Hold or tap the record button to film with the Reels camera, in one take or several clips, or pick one or more videos from your gallery. A video already shot vertically is the easiest starting point.</li>
<li><strong>Edit it.</strong> Trim the clips, add music from Facebook's audio library or keep the original sound, and add text, stickers, effects, a voice-over or automatic captions where your app offers them. Place any text in the centre of the frame (see the safe-zone section below).</li>
<li><strong>Tap Next.</strong> Write a description: one line that says what the Reel is about, plus a few relevant hashtags if you use them. Tag people or a location if it helps.</li>
<li><strong>Choose the audience.</strong> Public lets the Reel be recommended to people who do not follow you; Friends keeps it to them. Pages and profiles in professional mode have more options here, including scheduling on some versions.</li>
<li><strong>Share.</strong> Tap <strong>Share now</strong> (or <strong>Share reel</strong>). It appears in your followers' feeds and in the Reels tab.</li>
</ol>
<p>If you do not see the Reel option, update the app first. Reels tools roll
out by region and account type, and the position of the Create menu changes
between versions.</p>

<h2>How to post a Reel on Facebook from a computer</h2>
<p>Facebook on the web has fewer creation tools than the app, so there are two
routes depending on what you are posting from.</p>
<h3>For a Page: Meta Business Suite</h3>
<ol>
<li>Open Meta Business Suite and select the Page.</li>
<li>Choose <strong>Create reel</strong> (from the home screen, or from the Content or Planner section).</li>
<li>Upload a vertical video. It is checked for size and length as it uploads.</li>
<li>Add a description, a cover if you want one, and any options Business Suite offers for that Page, such as collaborators or a location.</li>
<li>Choose <strong>Share now</strong> or <strong>Schedule</strong>, pick the date and time, and confirm.</li>
</ol>
<p>Business Suite is also where a Page's scheduled Reels are listed and can be
moved or deleted, which makes it the better route for a team that plans posts
a week ahead.</p>
<h3>From facebook.com</h3>
<p>In June 2025 Meta announced that new videos uploaded to Facebook would be
shared as Reels, with the change rolled out gradually to profiles and Pages. In
practice that means a vertical video posted from a Page, or from a profile in
professional mode, on facebook.com generally becomes a Reel. What you get on
the web is the upload, the description and the audience; for music, effects
and the Reels camera, use the app.</p>

<h2>Facebook Reel specs</h2>
<table>
<thead><tr><th>Spec</th><th>Use this</th><th>Notes</th></tr></thead>
<tbody>
<tr><td class="os">Aspect ratio</td><td>9:16 vertical</td><td>Other shapes are accepted since 2025, but vertical is what fills the Reels feed</td></tr>
<tr><td class="os">Size</td><td>1080 x 1920 px</td><td>Smaller files look soft after compression</td></tr>
<tr><td class="os">Length</td><td>As long as the moment needs</td><td>Meta removed the length limit in its June 2025 change; Reels were capped at 90 seconds before</td></tr>
<tr><td class="os">File</td><td>MP4, H.264, AAC</td><td>MOV from a phone works too</td></tr>
<tr><td class="os">Frame rate</td><td>Same as the source</td><td>30 fps is typical</td></tr>
<tr><td class="os">Text safe area</td><td>Centre of the frame</td><td>The bottom strip and right edge are covered by the interface</td></tr>
</tbody>
</table>
<p>The Facebook Reels player, like Instagram's, puts your name, the description
and the audio line across the bottom and a column of buttons (like, comment,
share) down the right edge. Facebook does not publish an official safe zone for
organic Reels; as a rule of thumb keep captions above the lowest 15% or so of
the frame, clear of the right-hand 10 to 15%, and faces in the centre. Meta's
guidance for Reels <em>ads</em>, as widely quoted, is stricter: about 14% of the
top, 35% of the bottom and 6% of each side kept free of text. The full size
guide, written for Instagram but true for Facebook Reels too, is
<a href="/how-to/instagram-reel-dimensions">Instagram Reel dimensions</a>.</p>
<p>No length limit does not mean long is better. A Reel is judged in its first
second or two, and the Reels feed is still built for short vertical video. A
long horizontal episode posted as a Reel competes with clips made for the
format.</p>

<h2>Cross-posting Reels from Instagram to Facebook</h2>
<p>If you already make Reels for Instagram, the cheapest way to have Facebook
Reels is to share the same ones. Both accounts need to be in the same Meta
Accounts Center.</p>
<ul>
<li><strong>One Reel at a time:</strong> on Instagram's final share screen, turn on the Facebook option (it may read <strong>Share to Facebook</strong> or <strong>Recommend on Facebook</strong>) before you share.</li>
<li><strong>Every Reel:</strong> in Instagram, open Accounts Center, go to <strong>Sharing across profiles</strong>, choose the Instagram account and the Facebook profile or Page, and turn on automatic sharing for Reels.</li>
</ul>
<p>Two things to know. Music licensed for your Reel on Instagram is not always
available on Facebook, so a Reel with a popular track can be shared without its
sound or not shared at all. And the audiences are different: a description
written for Instagram (hashtags, an @ handle) may read oddly on Facebook, so
check the first few that go across.</p>

<h2>Making Facebook Reels from long videos</h2>
<p>Many Pages already have hours of video that never become Reels: Facebook Live
replays, webinars, sermons, interviews, podcast recordings. Each one usually
holds several moments that would stand on their own. Turning them into Reels
by hand means four jobs for every clip:</p>
<ol>
<li><strong>Find the moment.</strong> Watch or skim the recording, or search its transcript, and note where a complete idea starts and ends.</li>
<li><strong>Cut it.</strong> Trim it in an editor, starting a beat before the first word and ending after the last.</li>
<li><strong>Make it vertical.</strong> Crop the 16:9 frame to 9:16 so the speaker fills the screen, or keep the whole frame over a blurred background.</li>
<li><strong>Caption it.</strong> Most Reels are watched on mute, so burn subtitles in, clear of the bottom strip.</li>
</ol>
<p>The steps are simple; the time goes into finding the moments and keeping the
speaker in frame when they move. That is the part an AI clipper automates.</p>

${nextStep(path, {
  heading: 'Next step: let AI cut the Reels for you',
  html: `<p>OpenShorts reads the whole recording, picks the passages that make sense
on their own and returns each one as a 9:16 Reel with word-level captions, a
hook over the opening seconds and a description. You can paste the link of a
public Facebook video or Live replay, a YouTube video, or upload the file. It
publishes to Instagram as Reels; it does not post to Facebook, so for Facebook
Reels you download the MP4 and post it from the Facebook app or Meta Business
Suite, as above. More on <a href="/platforms/instagram-reels">the AI reel
generator</a> page.</p>`,
  title: 'Paste a link, get Reels ready for Facebook',
  body: 'Moments picked from the whole video, reframed to 9:16, captioned, ready to download.',
})}

${faqBlock(FB_REEL_FAQ)}

${sources([
  SRC_FB_REELS,
  'Facebook app, Meta Business Suite and Accounts Center steps described as of October 2026; Meta tests and renames menus gradually, so labels can differ by account and region.',
  'Reels ad margins (about 14% top, 35% bottom, 6% sides) as quoted from Meta\'s ad guidance by advertising guides; check Meta\'s current ad specs before relying on them.',
  SRC_CAPTIONS,
])}
`,
    faq: FB_REEL_FAQ,
    extraNodes: [
      howToSteps(path, 'How to make a Reel on Facebook',
        'Create and post a Facebook Reel from the Facebook app, or from Meta Business Suite on a computer for a Page.', [
          ['Open Create and choose Reel', 'In the Facebook app, tap Create or the plus button and choose Reel. On a computer, for a Page, open Meta Business Suite and choose Create reel.'],
          ['Record or upload a vertical video', 'Film with the Reels camera or pick a 9:16 video, ideally 1080 x 1920, from your gallery or computer.'],
          ['Edit it', 'Trim it, add music or keep the original sound, and add text or captions in the centre of the frame, clear of the bottom strip and the right-hand buttons.'],
          ['Write the description and choose the audience', 'Add a one-line description and any hashtags, then choose Public or Friends.'],
          ['Share or schedule', 'Tap Share now, or schedule the Reel for a date and time in Meta Business Suite.'],
        ], { totalTime: 'PT10M' }),
    ],
    related: ['/platforms/instagram-reels', '/how-to/instagram-reel-dimensions', '/auto-reframe'],
  })
}

/* ---------------------------------------------------- /how-to/make-youtube-shorts */

const MAKE_SHORTS_FAQ = [
  {
    q: 'How do you make a YouTube Short?',
    a: 'In the YouTube app, tap the plus button and choose Create a Short, record or pick a vertical video, add sound and text, tap Next, add a title and upload. Or upload any square or vertical video up to 3 minutes from YouTube Studio: it becomes a Short automatically.',
  },
  {
    q: 'How do I make a YouTube Short from a long video?',
    a: 'For your own videos, the YouTube app can turn part of an upload into a Short (Remix, then Edit into a Short, where available). Or cut the segment yourself, reframe it to 9:16 and caption it, or let an AI clipper such as OpenShorts pick the moments and cut several Shorts at once.',
  },
  {
    q: 'How long can a YouTube Short be?',
    a: 'Up to 3 minutes for videos uploaded from 15 October 2024. A Short longer than one minute with an active Content ID claim is blocked worldwide until the claim is resolved.',
  },
  {
    q: 'Can I make YouTube Shorts on a computer?',
    a: 'Yes, by uploading. In YouTube Studio choose Create, then Upload videos, and pick a square or vertical video up to 3 minutes. The Shorts camera, the music library and the Shorts effects are in the mobile app only.',
  },
  {
    q: 'Do I need #Shorts for a video to be a Short?',
    a: 'No. YouTube classifies a video as a Short from its shape and length: square or vertical and up to 3 minutes. The hashtag does not make a horizontal video a Short.',
  },
  {
    q: 'What size should a YouTube Short be?',
    a: '1080 x 1920 pixels, 9:16 vertical. Square 1080 x 1080 is also accepted. Keep text out of the bottom strip and away from the buttons on the right edge.',
  },
  {
    q: 'Can I add music to a YouTube Short?',
    a: 'Yes, from the sound library in the YouTube app\'s Shorts editor. Music added outside YouTube can bring a Content ID claim, and a claimed Short over one minute is blocked, so use cleared or royalty-free music for longer Shorts.',
  },
  {
    q: 'Can I link a Short to my long video?',
    a: 'Yes. In YouTube Studio or the app you can set a related video on a Short, which shows a link to that video from your channel under the Short. It is the simplest way to send Shorts viewers to the full episode.',
  },
  {
    q: 'Is OpenShorts free for making Shorts?',
    a: `On two terms. The hosted free plan clips your first video whole up to ${FIRST_VIDEO_MINUTES} minutes, then ${FREE.monthly.minutes} minutes a month, with a watermark and no credit card; paid plans start at ${money(STARTER.monthly)}/month with no watermark. The self-hosted edition is free under MIT with no watermark.`,
  },
]

const makeShorts = () => {
  const path = '/how-to/make-youtube-shorts'
  return guide(path, 'How to make YouTube Shorts', {
    title: 'How to Make YouTube Shorts (Phone, Desktop, Long Videos)',
    description:
      'How to make YouTube Shorts as of October 2026: the YouTube app camera, uploading a vertical video up to 3 minutes, and cutting Shorts out of long videos.',
    h1: 'How to make YouTube Shorts: with the camera, an upload or a long video',
    cta: guideCta('Turn a long video into Shorts with AI', 'Paste a YouTube link and get several 9:16 Shorts with captions, ready to post.'),
    tldr: [
      'There are three ways to make a YouTube Short. <strong>1. Film it in the YouTube app:</strong> tap the plus button, choose <strong>Create a Short</strong>, record, add sound and text, tap <strong>Next</strong> and upload. <strong>2. Upload a vertical video:</strong> any square or vertical video <strong>up to 3 minutes</strong>, from the app or YouTube Studio, becomes a Short automatically. <strong>3. Cut it from a long video</strong> you already made.',
      'The third is where most channels find their Shorts: one long video holds several moments that stand on their own. You can cut them by hand, use YouTube\'s own tool for your uploads, or let an AI clipper find and cut them for you.',
      `Make it <strong>9:16, 1080 x 1920</strong>, put the point in the first seconds and caption it for viewers on mute. Steps as of ${AS_OF}.`,
    ],
    facts: [
      { k: 'Shape', v: '9:16', s: 'Or square; never horizontal' },
      { k: 'Max length', v: '3 min', s: 'Uploads from 15 Oct 2024' },
      { k: 'Size', v: '1080 x 1920', s: 'Pixels' },
      { k: 'Hashtag', v: 'Not needed', s: 'Shape and length decide it' },
    ],
    body: `
<h2>What makes a video a Short</h2>
<p>YouTube's help pages define a Short by two things: a <strong>square or
vertical</strong> aspect ratio and a length of <strong>up to 3 minutes</strong>
(the limit for videos uploaded from 15 October 2024; it was 60 seconds before).
Any upload with both is a Short, whichever way you made it, and appears on the
Shorts shelf and in the Shorts feed. A horizontal video is a regular video at
any length, and a #Shorts hashtag does not change that. The full specs, with
safe zones, are in <a href="/how-to/youtube-shorts-aspect-ratio">YouTube Shorts
aspect ratio and size</a>.</p>

<h2>Method 1: film a Short in the YouTube app</h2>
<p>The Shorts camera in the YouTube app for iPhone and Android is the quickest
route when you are filming something new. As of ${AS_OF}:</p>
<ol>
<li><strong>Tap the plus button</strong> at the bottom of the YouTube app and choose <strong>Create a Short</strong> (on some versions, <strong>Short</strong>).</li>
<li><strong>Choose the length</strong> with the duration control at the top of the camera, if you want a Short longer than the default.</li>
<li><strong>Add a sound first</strong> if the Short is set to music: tap <strong>Add sound</strong> and pick a track from the library, so you can film to the beat.</li>
<li><strong>Record.</strong> Hold the record button, or tap to start and stop. You can film in several clips; the bar at the top shows how much time is left. Use the timer for hands-free takes, and the speed, filter and green-screen tools if you need them.</li>
<li><strong>Tap the tick</strong> to finish, then edit: add text and time it to the right moments, a voice-over, filters, or trim the clips on the timeline.</li>
<li><strong>Tap Next</strong>, write a title (it is what most viewers read, keep it short), choose the visibility and whether it is made for kids, and tap <strong>Upload Short</strong>. You can also schedule it instead of publishing straight away where your app offers it.</li>
</ol>

<h2>Method 2: upload a vertical video you already have</h2>
<p>If you edit somewhere else (CapCut, Premiere, DaVinci Resolve, your phone's
editor), export a 9:16 file at 1080 x 1920, no longer than 3 minutes, and upload
it. There is no separate Shorts upload: shape and length are enough.</p>
<h3>From your phone</h3>
<ol>
<li>Tap the plus button and choose <strong>Create a Short</strong>.</li>
<li>Tap the gallery thumbnail in the bottom-left corner and pick the video.</li>
<li>Trim it if needed, add sound or text, tap <strong>Next</strong>, add the title and upload.</li>
</ol>
<p>Choosing <strong>Upload a video</strong> instead of the Shorts camera works too:
a vertical video up to 3 minutes is still published as a Short.</p>
<h3>From a computer</h3>
<ol>
<li>Open YouTube Studio and choose <strong>Create</strong>, then <strong>Upload videos</strong>.</li>
<li>Pick the vertical or square file, up to 3 minutes.</li>
<li>Add the title and description, choose the audience, and on the Visibility step publish it or set a date and time to schedule it.</li>
</ol>
<p>The Shorts camera, the sound library and the Shorts effects are only in the
mobile app; on a computer you upload a finished file.</p>
<p>One rule for both routes: YouTube blocks a Short longer than one minute
worldwide while it has an active Content ID claim, for example from a song you
added in your editor. Keep claimed music out of longer Shorts, or use the sound
library in the app.</p>

<h2>Method 3: make Shorts from your long videos</h2>
<p>A long video you already published is the best source of Shorts most channels
have: a 40-minute podcast or tutorial often holds half a dozen moments that make
sense to someone who has never seen the channel. There are three ways to get
them out.</p>
<h3>YouTube's own tool, for your uploads</h3>
<p>In the YouTube app, open one of your own long videos, tap <strong>Remix</strong>
and then <strong>Edit into a Short</strong> where it is available. Choose the
segment, and it opens in the Shorts editor, where you can reframe it, add text
and publish. It is free and stays inside YouTube, but you pick the moment
yourself and make one Short at a time, and the tool's segment length and
availability can differ from the full 3-minute Shorts limit.</p>
<h3>By hand, in an editor</h3>
<p>Download your own upload from YouTube Studio (Content, three-dot menu,
Download) or use the original file, then for each Short: find the moment
(the transcript makes this faster: search for a phrase and jump to its
timestamp), cut it on sentence boundaries, crop the 16:9 frame to 9:16 so the
speaker fills it, burn in captions, and export at 1080 x 1920. It gives you full
control, and it takes most people well over ten minutes a Short. The detailed
steps, including the ffmpeg commands, are in <a href="/how-to/clip-a-youtube-video">how
to clip a YouTube video</a>.</p>
<h3>With an AI clipper</h3>
<p>An AI clipper does the slow part: it reads the whole video and returns the
strongest moments already cut, reframed and captioned. With OpenShorts:</p>
<ol>
<li>Paste the YouTube link, or upload the file.</li>
<li>The video is transcribed word by word, and Gemini scores every stretch of it for how well it would stand alone.</li>
<li>The best moments are cut on sentence boundaries, 15 to 60 seconds by default or up to 3 minutes if you raise the maximum.</li>
<li>Each is reframed to 9:16: the speaker tracked, two people stacked, or a screen kept readable beside the presenter. Captions are burned in from the transcript and a hook is drawn over the first seconds.</li>
<li>Publish them to your channel, schedule a week of them, or download the files.</li>
</ol>
<p>Use it on your own videos, on channels you manage, or on footage you are
licensed to clip; each job asks you to confirm that.</p>

<h2>What makes a Short work</h2>
<ul>
<li><strong>The first second.</strong> Viewers decide in the feed whether to stay. Start on the point, not on a greeting or a logo.</li>
<li><strong>One idea.</strong> A Short that needs the previous ten minutes of context loses a stranger. Pick moments that stand alone.</li>
<li><strong>Captions.</strong> Many people watch with the sound off. Burn subtitles in, above the bottom strip where the title and channel name sit.</li>
<li><strong>A clean ending.</strong> End on the payoff. A Short that loops smoothly back to its start often gets watched twice.</li>
<li><strong>A link to the long video.</strong> Set the Short's related video to the full episode, so viewers who want more find it.</li>
<li><strong>A steady rhythm.</strong> One Short a day from last week's long video does more than ten on one day and nothing after.</li>
</ul>

${nextStep(path, {
  heading: 'Next step: make a week of Shorts from one video',
  html: `<p>If you already publish long videos, your next Shorts are in them.
Paste a link and OpenShorts returns several 9:16 Shorts with captions, a hook and
a title written for the Shorts feed, and can post them to your channel one a day.
The details are on <a href="/platforms/youtube-shorts">the YouTube Shorts
maker</a>; for any YouTube source, see <a href="/platforms/youtube">the YouTube
clip maker</a>; and for the one-link flow, <a href="/youtube-to-shorts-converter">the
YouTube to Shorts converter</a>.</p>`,
  title: 'Paste a YouTube link, get Shorts',
  body: 'The AI picks the moments, reframes them to 9:16 and captions them word by word.',
})}

${faqBlock(MAKE_SHORTS_FAQ)}

${sources([
  SRC_YT_UPLOAD,
  SRC_YT_3MIN,
  'YouTube app and YouTube Studio steps described as of October 2026; YouTube rolls out interface changes gradually, so labels can differ by account and region.',
  `OpenShorts pipeline: <a href="/how-openshorts-works">how OpenShorts works</a> and the <a href="${SITE.repo}" rel="noopener">source on GitHub</a>.`,
])}
`,
    faq: MAKE_SHORTS_FAQ,
    extraNodes: [
      howToSteps(path, 'How to make a YouTube Short',
        'Make a YouTube Short with the YouTube app camera, by uploading a vertical video, or by cutting it from a long video.', [
          ['Start a Short', 'In the YouTube app, tap the plus button and choose Create a Short. On a computer, open YouTube Studio and choose Create, then Upload videos.'],
          ['Record or pick a vertical video', 'Film with the Shorts camera, or pick a square or vertical video up to 3 minutes, ideally 1080 x 1920. From a long video, cut the moment and reframe it to 9:16 first.'],
          ['Add sound, text and captions', 'Add a track from the sound library or keep the original audio, and place text and captions above the bottom strip.'],
          ['Add a title', 'Tap Next and write a short title. Choose the visibility and whether the Short is made for kids.'],
          ['Upload or schedule', 'Tap Upload Short, or schedule it for a date and time.'],
        ], { totalTime: 'PT15M' }),
    ],
    related: ['/platforms/youtube-shorts', '/youtube-to-shorts-converter', '/how-to/youtube-shorts-aspect-ratio'],
  })
}

/* --------------------------------------------- /how-to/best-time-to-post-youtube-shorts */

const BEST_TIME_FAQ = [
  {
    q: 'What is the best time to post YouTube Shorts?',
    a: 'There is no single best time that holds for every channel, and YouTube does not publish one. The best time for you is shortly before your own viewers are most active, which YouTube Analytics shows in the "When your viewers are on YouTube" chart. Then test it.',
  },
  {
    q: 'Does the time you post a YouTube Short matter?',
    a: 'Less than for most formats. Shorts are shown by a recommendation feed and can keep picking up views for days or weeks, so a good Short posted at an odd hour still finds viewers. Timing mostly affects how quickly the first views arrive from people who already watch you.',
  },
  {
    q: 'How do I find when my viewers are on YouTube?',
    a: 'In YouTube Studio, open Analytics, then the Audience tab, and look for "When your viewers are on YouTube". It is a chart of days and hours, darker where more of your viewers are online, based on the last 28 days. It covers your whole channel, not only Shorts, and needs enough viewers to appear.',
  },
  {
    q: 'What times are commonly recommended for Shorts?',
    a: 'Scheduling-tool blogs often cite weekday early afternoons (around 12 to 3 pm) and evenings (around 6 to 9 pm) in the viewers\' time zone, and late mornings at weekends. Those are averages over other channels, not YouTube guidance. Use them as starting slots for a test if your own chart is empty.',
  },
  {
    q: 'How often should I post YouTube Shorts?',
    a: 'As often as you can keep up good ones. A steady rhythm, such as one Short a day or a few a week at similar times, is easier to test and to sustain than bursts. Several weak Shorts do not help a channel.',
  },
  {
    q: 'Should I post Shorts in my time zone or my viewers\'?',
    a: 'Your viewers\'. Check the top geographies in YouTube Analytics, and if most viewers are in another time zone, plan around their day. YouTube Studio\'s scheduler uses the time zone it shows next to the date and time, so check it before you schedule.',
  },
  {
    q: 'How long should I wait before judging a time slot?',
    a: 'Compare each Short at the same age, such as 48 hours and 7 days after posting, and only after several Shorts per slot. One Short going well or badly says more about the Short than about the time.',
  },
  {
    q: 'Can I schedule YouTube Shorts?',
    a: 'Yes. In YouTube Studio, set the visibility to Schedule and pick a date and time when you upload; the mobile app offers scheduling too. OpenShorts can schedule a batch of Shorts one a day at the time and time zone you choose.',
  },
]

const bestTimeShorts = () => {
  const path = '/how-to/best-time-to-post-youtube-shorts'
  return guide(path, 'Best time to post YouTube Shorts', {
    title: 'Best Time to Post YouTube Shorts: How to Find Yours',
    description:
      'There is no universal best time to post YouTube Shorts. How to find yours in YouTube Analytics, test time slots properly, and post on a schedule you can keep.',
    h1: 'The best time to post YouTube Shorts, and how to find your own',
    cta: guideCta('Schedule a week of Shorts from one video', 'Paste a link, get Shorts, and post them one a day at the hour you choose.'),
    tldr: [
      '<strong>There is no universal best time to post YouTube Shorts</strong>, and YouTube does not publish one. Shorts are shown by a recommendation feed and can keep finding viewers for days, so the time you post matters less than the Short itself.',
      'The time that does matter is <strong>when your own viewers are online</strong>. YouTube Studio shows it in Analytics, under Audience, in the <strong>"When your viewers are on YouTube"</strong> chart. Post a little before the darkest blocks, in your viewers\' time zone.',
      'Then <strong>test</strong>: rotate two or three time slots for a few weeks, compare each Short at the same age, and keep the slot that wins. Above all, <strong>be consistent</strong>: one good Short a day at a steady time beats a burst and a silence.',
    ],
    facts: [
      { k: 'Universal best time', v: 'None', s: 'YouTube does not publish one' },
      { k: 'Your data', v: 'Analytics', s: 'Audience tab, last 28 days' },
      { k: 'Test window', v: '3-4 weeks', s: 'Several Shorts per slot' },
      { k: 'Rhythm', v: 'Steady', s: 'Similar times, sustainable pace' },
    ],
    body: `
<h2>Why there is no single best time</h2>
<p>Search for the best time to post Shorts and you will find confident answers
that disagree with each other. They disagree because they are averages over
different sets of channels, and your audience is not an average. A channel
whose viewers are students in one country, one whose viewers are night-shift
workers, and one whose viewers are spread across five time zones have three
different best times.</p>
<p>Shorts also make timing matter less than in a chronological feed. The Shorts
feed shows each viewer what it predicts they will watch, not what was posted
most recently, and a Short can keep collecting views long after it is
published. Posting when your existing viewers are online helps a Short get its
first views sooner; after that, how the Short performs with the people it is
shown to has far more weight than the minute it went up. A strong Short posted
at a bad time still finds its audience. A weak one posted at the perfect time
does not.</p>
<p>So the useful question is not "what is the best time" but "when are my
viewers on YouTube, and does posting then make a difference for my channel?"
Both have answers you can find yourself.</p>

<h2>Step 1: find when your viewers are on YouTube</h2>
<p>YouTube Studio has a chart for exactly this:</p>
<ol>
<li>Open <strong>YouTube Studio</strong> on a computer and choose <strong>Analytics</strong>.</li>
<li>Open the <strong>Audience</strong> tab.</li>
<li>Find the card <strong>When your viewers are on YouTube</strong>. It is a grid of days and hours, darker where more of your viewers are online.</li>
</ol>
<p>Things to know about that chart:</p>
<ul>
<li>It covers the <strong>last 28 days</strong>, across all devices, and shows when your viewers are on YouTube in general, not only when they watch you.</li>
<li>It is <strong>channel-wide</strong>, not specific to Shorts. If most of your viewers come from long videos, it describes them. That is usually still the best starting point you have.</li>
<li>It needs <strong>enough viewers</strong> to appear. On a new channel it may be missing; use the fallback below.</li>
<li>Check the <strong>time zone</strong> the chart shows, and compare it with the one your YouTube Studio scheduler uses.</li>
</ul>
<p>Read it for the pattern, not the single darkest square. Most channels show a
daily rise and fall, often with a different shape at weekends. A common
practice is to publish an hour or two before the start of the busiest period,
so the Short has been out a little while when most of your viewers arrive.</p>
<h3>If the chart is empty: start from geography</h3>
<p>On a small channel, open the same Audience tab and look at the top
geographies, or simply think about who you make videos for. Pick the time zone
most of your viewers live in and start with two plausible slots in their day,
such as early afternoon and evening. Scheduling-tool blogs often cite weekday
early afternoons (around 12 to 3 pm) and evenings (around 6 to 9 pm) in the
viewers' time zone, and late mornings at weekends. Treat those as starting
slots for a test, not as rules: they are averages over other people's channels,
and YouTube does not endorse them.</p>

<h2>Step 2: test your time slots properly</h2>
<p>A chart tells you when viewers are online. A test tells you whether posting
then actually changes anything for your Shorts. A simple method that works
without any tools beyond YouTube Studio and a spreadsheet:</p>
<ol>
<li><strong>Choose two or three slots</strong> from Step 1, for example 1 pm and 7 pm in your viewers' time zone.</li>
<li><strong>Rotate them</strong> for three to four weeks, so each slot gets several Shorts and each weekday sees each slot. Posting one Short a day, alternating slots, is easy to keep up.</li>
<li><strong>Keep everything else as steady as you can:</strong> similar kinds of Shorts, similar length, the same posting rhythm. If one slot gets all your best Shorts, you are testing the Shorts, not the time.</li>
<li><strong>Compare at the same age.</strong> Record each Short's views, and if you can, its average percentage viewed and how many viewers chose to keep watching, at 48 hours and at 7 days after posting. In YouTube Studio, the Content tab lists your Shorts and each one's analytics shows those figures.</li>
<li><strong>Compare medians, not totals.</strong> One Short that takes off can make any slot look like the winner. The median Short per slot is what tells you about the time.</li>
<li><strong>Keep the winner and test again later.</strong> Audiences shift with seasons, school terms and your own growth; a test every few months keeps your slot current.</li>
</ol>
<p>Expect the difference to be small. If two slots perform about the same, that
is a useful result too: post at whichever time you can keep up.</p>

<h2>Step 3: be consistent, then automate it</h2>
<p>For most channels the biggest gain is not the perfect hour but a steady
rhythm. A Short a day, or a few a week at similar times, gives the feed a
regular supply, gives returning viewers something to expect, and makes your
tests readable. Bursts (ten Shorts on Sunday, nothing for two weeks) are hard
to sustain and hard to learn from.</p>
<p>The way to keep a rhythm is to stop depending on being online at the right
moment:</p>
<ul>
<li><strong>YouTube Studio</strong> lets you schedule a Short: when you upload, choose <strong>Schedule</strong> on the Visibility step and pick the date and time. The mobile app offers scheduling too.</li>
<li><strong>OpenShorts</strong> can schedule a whole batch: after it cuts the Shorts from a long video, <strong>Schedule a week</strong> posts one a day, starting the next day, at the time you choose in your own time zone, to YouTube Shorts and, if you want, TikTok and Instagram.</li>
<li><strong>Autopilot</strong> (on paid plans) goes one step further: it clips each new upload on your connected channel on its own and, with autopublish on, schedules the best clips of each video one a day at the hour you pick, in your time zone. It only picks up videos published after you switch it on.</li>
</ul>

<h2>What matters more than the time</h2>
<ul>
<li><strong>The first second.</strong> Viewers decide in the feed. Open on the point.</li>
<li><strong>Retention.</strong> A Short that people watch to the end, or twice, is shown to more people. Cut the slow parts.</li>
<li><strong>One idea per Short.</strong> A moment that stands alone works for strangers, who are most of the Shorts audience.</li>
<li><strong>Captions.</strong> Many viewers have the sound off.</li>
<li><strong>Volume you can sustain.</strong> A steady supply of good Shorts is what a posting time optimises; without it there is nothing to optimise.</li>
</ul>

${nextStep(path, {
  heading: 'Next step: a week of Shorts, posted at your time',
  html: `<p>The hardest part of posting at a consistent time is having a Short ready
every day. If you publish long videos, OpenShorts cuts several Shorts from each
one and can schedule them one a day at the hour your viewers are online. See
<a href="/platforms/youtube-shorts">the YouTube Shorts maker</a> for the clips and
posting, <a href="/auto-clip">auto clip</a> for clipping every new upload on its
own, and <a href="/youtube-automation">YouTube automation</a> for Autopilot, n8n
and the API.</p>`,
  title: 'Paste a link, schedule a week of Shorts',
  body: 'Shorts cut from your long video, posted one a day at the time you choose.',
})}

${faqBlock(BEST_TIME_FAQ)}

${sources([
  '<a href="https://support.google.com/youtube/answer/9314416" rel="noopener">YouTube Help: Understand your YouTube audience</a> ("When your viewers are on YouTube", last 28 days, all devices).',
  'Commonly cited posting windows are from social-media scheduling blogs that aggregate other channels\' data; YouTube does not publish a best time to post.',
  `Schedule a week (one clip a day at a chosen time and time zone) is <code>ScheduleWeekModal.jsx</code>; Autopilot's rules are in <code>cloud/autopilot.py</code> at <a href="${SITE.repo}" rel="noopener">github.com/mutonby/openshorts</a>.`,
])}
`,
    faq: BEST_TIME_FAQ,
    extraNodes: [
      howToSteps(path, 'How to find the best time to post YouTube Shorts for your channel',
        'Use YouTube Analytics to find when your viewers are online, test two or three time slots, and post on a consistent schedule.', [
          ['Open the audience chart', 'In YouTube Studio, open Analytics, then the Audience tab, and find "When your viewers are on YouTube" (last 28 days).'],
          ['Pick two or three slots', 'Choose times shortly before your viewers\' busiest periods, in their time zone. With no chart, start from early afternoon and evening in your main viewers\' time zone.'],
          ['Rotate the slots for three to four weeks', 'Post similar Shorts at each slot, several per slot, keeping the rest of your routine steady.'],
          ['Compare at the same age', 'Record views and retention for each Short at 48 hours and 7 days, and compare the median per slot.'],
          ['Schedule at the winning time', 'Schedule Shorts at the slot that performs best, keep a steady rhythm, and test again every few months.'],
        ], { totalTime: 'P28D' }),
    ],
    related: ['/platforms/youtube-shorts', '/auto-clip', '/youtube-automation'],
  })
}

export function guidePages() {
  return [
    selfHosted(),
    freeCompared(),
    howToClip(),
    reelDimensions(),
    shortsAspectRatio(),
    facebookReel(),
    makeShorts(),
    bestTimeShorts(),
  ]
}
