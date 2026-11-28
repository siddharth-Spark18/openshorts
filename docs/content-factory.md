# Content factory setup

Each factory project has its own account connections, creative direction, daily target and publishing mode. Manual mode requires review. Automatic mode creates original workplace skits and publishes approved output without a further review, spaced across the connected accounts. The current visual style uses simple 2D illustrations and synthetic offline speech; it is not a photorealistic or full character-animation system.

## Google Cloud voices

Enable the Cloud Text-to-Speech API and billing in a Google Cloud project, then provide application default credentials to the backend or set `GOOGLE_TTS_CREDENTIALS_JSON` to a service-account JSON credential. Keep the credential private and out of version control. Choose Google Cloud Neural2 and the character voices in the project's Voices tab. This workspace reserves characters before each request and stops at 750,000 characters per UTC month across all projects. Failed requests count conservatively. Usage from other applications or projects using the same Google Cloud billing account is not included in this counter; configure the appropriate Google Cloud quotas too. Changing voices affects the next render, so existing videos must be rendered again.

## YouTube

The private deployment can reuse `DRIVE_CLIENT_ID` and `DRIVE_CLIENT_SECRET`. Alternatively set `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET`. Enable the YouTube Data API for that Google Cloud project and add the exact authorized redirect URI configured in `YOUTUBE_OAUTH_REDIRECT_URI` (default `https://openshorts-dev.duckdns.org/api/factory/youtube/callback`). In the factory project, connect the intended YouTube channel and grant the requested upload and channel-read permissions. Connecting Drive does not authorize YouTube.

## Instagram

An Instagram professional account and a Meta app with Instagram Login are required. Set `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`, and `INSTAGRAM_OAUTH_REDIRECT_URI` (default `https://openshorts-dev.duckdns.org/api/factory/instagram/callback`). Configure the same redirect in Meta's app dashboard and add the Instagram account to the app. `FACTORY_PUBLIC_SITE_URL` must be the externally reachable HTTPS origin of this deployment. Meta fetches the selected video through a random, temporary link, which expires and is revoked after processing.

## Operations

An upload whose outcome is uncertain is not automatically repeated; check the destination account to avoid duplicates. Automatic production stops after an error and can be retried from the project. The queue is persisted, and only one skit renders at a time; rendering requires at least 2 GB of free disk. The project target is a pacing goal, not a guarantee of successful posts. Gemini, Google, and Meta availability, credentials, account eligibility, and quotas still apply.
