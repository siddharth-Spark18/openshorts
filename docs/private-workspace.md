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

The private defaults run one video job and one clip render at a time, keep downloaded speech models on disk, and use a Whisper beam size of one. Videos of 20 minutes or longer are transcribed in ten-minute sections with overlapping audio for boundary words. Each finished section is saved to the job directory so restarting an interrupted transcription can reuse it. The first run includes a model download. For more thorough decoding set `WHISPER_BEAM_SIZE=5`. For full-source transcription set `ASR_PART_SECONDS=0`. Recreate the backend after changing settings.

## YouTube links

In **Clip Generator**, select **Video URL**, paste a single-video link, confirm your rights, and submit. If YouTube refuses the AWS host, the local importer handles the download and upload in one command over the same SSH tunnel. On your computer it needs Python 3, curl, FFmpeg, and a current yt-dlp with its default dependencies and a supported JavaScript runtime such as Deno. Set the Gemini key on the server first.

```sh
python3 cli/import_youtube.py --own-content 'https://www.youtube.com/watch?v=VIDEO_ID'
```

The importer prompts for the workspace password and prints the submitted job ID. Temporary media and the cookie file are removed when the command exits. The file upload limit is 2 GiB. Private or otherwise inaccessible videos still require a source you can access.
