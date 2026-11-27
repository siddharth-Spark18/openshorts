# Run a private OpenShorts workspace

Use this configuration for one person on a Docker host. The dashboard, API, rendered videos, and clip library share one password. Each browser signs in for up to 12 hours. Restarting the backend signs all sessions out.

## Start the workspace

From the checkout on the server, add `OWNER_PASSWORD` to the server's untracked `.env` with a long password you choose. Use single quotes around passwords containing literal dollar signs. Set `GEMINI_API_KEY` there or enter it in Settings after signing in. Upload-Post credentials are needed only for publishing.

```sh
docker compose -f docker-compose.private.yml up --build -d
```

Use this file by itself. Stop a previously running development stack before switching deployments. The private configuration exposes only the dashboard on the server's loopback interface. From your own computer, open an SSH tunnel and leave it running while using the dashboard.

```sh
ssh -N -L 5175:127.0.0.1:5175 YOUR_SSH_USER@YOUR_AWS_HOST
```

Open [your private workspace](http://127.0.0.1:5175). To rotate the password, edit the server's `.env` and run the Compose command again.

## Manage clips

After a job finishes, **Manage clips** lists its generated MP4s. Download saves the chosen file. Delete asks for confirmation and removes that library copy. Existing downloads, published posts, and temporary editor files have their own lifetimes. The library holds the generated version at job completion. Download subsequent edits from the editor.

The `library` Docker volume uses space on the host disk and requires no storage account or subscription. The host disk itself is subject to your AWS account's pricing. Keep the volume when updating containers. Removing the volume or losing the host disk loses the archive. Source uploads and editor files live in separate working volumes and expire. A fresh private installation starts with empty volumes. To migrate an earlier installation, copy its output and uploads into the matching private volumes before starting the backend. Startup imports finished clips from surviving job directories.

## Long videos

The private defaults run one video job and one clip render at a time, keep downloaded speech models on disk, and use a Whisper beam size of one. Videos of four minutes or longer are transcribed in two-minute sections with overlapping audio for boundary words. Each finished section is saved to the job directory so restarting an interrupted transcription can reuse it. The default Whisper base model, two-minute sections, lazy video detector loading, and lighter scene detector reduce peak memory use on small servers. Set `SCENE_ENGINE=transnetv2` to use the neural scene detector when memory permits. The first run includes a model download. Set `WHISPER_MODEL=small` for a larger model when the server has enough memory. For more thorough decoding set `WHISPER_BEAM_SIZE=5`. For full-source transcription set `ASR_PART_SECONDS=0`. Recreate the backend after changing settings.

## YouTube links

If YouTube asks the server to sign in, export YouTube cookies in Netscape format using the yt-dlp instructions, then upload the text file under **Settings → YouTube connection**. The file is stored in the persistent output volume with owner-only file permissions. Replace it if the login expires. Treat it like a password.

In **Clip Generator**, select **Video URL**, paste a single-video link, confirm your rights, and submit. If YouTube refuses the AWS host, the local importer handles the download and upload in one command over the same SSH tunnel. On your computer it needs Python 3, curl, FFmpeg, and a current yt-dlp with its default dependencies and a supported JavaScript runtime such as Deno. Set the Gemini key on the server first.

```sh
python3 cli/import_youtube.py --own-content 'https://www.youtube.com/watch?v=VIDEO_ID'
```

The importer prompts for the workspace password and prints the submitted job ID. Temporary media and the cookie file are removed when the command exits. The file upload limit is 2 GiB. Private or otherwise inaccessible videos still require a source you can access.

## Deploy updates from GitHub

The GitHub Actions workflow deploys pushes to `dev` after you configure the repository. On EC2, keep a clean checkout of `dev`, configure the private `.env`, and ensure the SSH user can run Git and Docker Compose. The server must be able to fetch the repository.

In GitHub repository settings, add the Actions secrets `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY` (the private key for that user), and `EC2_KNOWN_HOSTS` (the verified SSH host key line). Add the Actions variable `EC2_DIRECTORY` with the absolute path to the checkout. Set the variable `EC2_DEPLOY_ENABLED` to `true` when ready. The workflow also supports manual runs from the Actions tab. It fetches `dev`, requires a fast-forward update, pauses new jobs, and waits for active jobs before rebuilding and starting the private Compose stack. Jobs queued during deployment resume afterward. GitHub's runner must be able to reach the instance's SSH port.

## Google Drive folder connection

The Settings page can connect a Google account and select a folder with Google Picker. Finished clips in the local library are copied to the selected Drive folder in the background and retried if an upload fails. Local copies are retained. If a local clip is missing, Manage clips can download its verified Drive copy while the connection remains active. Deleting a clip from the app library does not delete the Drive copy. Source videos are not archived to Drive.

In Google Cloud, enable the Google Drive API and Google Picker API. Configure an OAuth web client with this authorized JavaScript origin:

```text
https://openshorts-dev.duckdns.org
```

Add this authorized redirect URI:

```text
https://openshorts-dev.duckdns.org/api/drive/callback
```

Create a browser API key for Picker and restrict it to the Picker API and this website origin. Add your Google account as an OAuth test user if the application is in testing. Add these settings to the server's private `.env`:

```text
DRIVE_CLIENT_ID='your-web-client-id'
DRIVE_CLIENT_SECRET='your-client-secret'
DRIVE_PICKER_API_KEY='your-picker-api-key'
```

Recreate the backend with Docker Compose, sign out and back into OpenShorts, then use **Settings → Google Drive** to authorize and choose the folder. The refresh token is stored with owner-only permissions in the persistent library volume. Disconnect removes the local token. You can also revoke access in your Google account.

## Source video statistics

To rank discovered videos by average views per day, enable the YouTube Data API v3 in Google Cloud and set `YOUTUBE_DATA_API_KEY` in the server `.env`. Use an API key restricted to the YouTube Data API. Discovery and topic matching continue without this key.
