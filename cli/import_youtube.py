"""Submit an authorized YouTube source through the private workspace SSH tunnel."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="A single YouTube video URL")
    parser.add_argument("--port", type=int, default=5175, help="Local SSH tunnel port")
    parser.add_argument("--own-content", action="store_true", required=True,
                        help="Confirm you own or have permission to process this video")
    args = parser.parse_args()
    source = urlsplit(args.url)
    host = source.hostname or ""
    if source.scheme != "https" or not (host == "youtu.be" or host == "youtube.com"
                                         or host.endswith(".youtube.com")):
        parser.error("Use an HTTPS YouTube video link.")
    if not 1 <= args.port <= 65535:
        parser.error("Invalid tunnel port.")
    base = f"http://127.0.0.1:{args.port}"
    with tempfile.TemporaryDirectory() as directory:
        jar = str(Path(directory) / "session")
        curl = ["curl", "--silent", "--show-error", "--fail-with-body"]
        password = getpass.getpass("Workspace password: ")
        subprocess.run(curl + ["-o", os.devnull, "-c", jar, "--data-urlencode",
                               "password@-", base + "/owner/login"], input=password.encode(), check=True)
        subprocess.run(["yt-dlp", "--no-playlist", "--match-filter", "!is_live",
                        "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/bv[height<=1080]+ba/b[ext=mp4]/b",
                        "--remux-video", "mp4", "-o", str(Path(directory) / "source.%(ext)s"),
                        "--", args.url], check=True)
        result = subprocess.run(curl + ["-b", jar, "-F", "acknowledged=true",
                                "-F", f"file=@{directory}/source.mp4", base + "/api/process"],
                                capture_output=True, text=True)
        if result.returncode:
            raise SystemExit(result.stdout or result.stderr)
        print(f"Submitted job {json.loads(result.stdout)['job_id']}")
        print(f"Your finished clips will appear in Manage clips at {base}.")


if __name__ == "__main__":
    main()
