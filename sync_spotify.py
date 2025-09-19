#!/usr/bin/env python3
"""
sync_spotify_complete.py

Usage:
    python sync_spotify_complete.py [--playlists playlists.txt] [--base-dir ~/Music/Spotify]
                                    [--config /path/to/config.json] [--no-strip] [--dry-run]

What it does:
- Reads your spotDL config (tries several locations / env var)
- Reads playlist URLs/IDs from playlists.txt (one per line)
- Resolves a friendly playlist name (Spotify API -> scrape -> id)
- Creates a folder per playlist, cds into it, runs:
    spotdl sync <playlist_url> --save-file "<playlist_name>.spotdl"
- Optionally strips mp3 metadata/artwork using ffmpeg (fast, no re-encode)
"""

from pathlib import Path
import os
import json
import re
import subprocess
import shutil
import sys
import argparse

# Optional 3rd-party libs (used only if installed)
try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    requests = None
    BeautifulSoup = None

# spotipy optional for private playlist name resolution
try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except Exception:
    spotipy = None
    SpotifyClientCredentials = None

# -------------------------
# Helpers
# -------------------------
def find_spotdl_config(explicit: str | None = None) -> Path | None:
    """
    Locate spotdl config. Order:
      1) explicit path (argument)
      2) SPOTDL_CONFIG env var
      3) $XDG_CONFIG_HOME/spotdl/config.json or ~/.config/spotdl/config.json
      4) ~/.spotdl/config.json
      5) %APPDATA%/spotdl/config.json (Windows)
    """
    if explicit:
        p = Path(explicit).expanduser()
        if p.exists():
            return p

    envp = os.environ.get("SPOTDL_CONFIG")
    if envp:
        p = Path(envp).expanduser()
        if p.exists():
            return p

    xdg = os.environ.get("XDG_CONFIG_HOME", None)
    if xdg:
        p = Path(xdg) / "spotdl" / "config.json"
        if p.exists():
            return p
    else:
        p = Path.home() / ".config" / "spotdl" / "config.json"
        if p.exists():
            return p

    p = Path.home() / ".spotdl" / "config.json"
    if p.exists():
        return p

    appdata = os.environ.get("APPDATA")
    if appdata:
        p = Path(appdata) / "spotdl" / "config.json"
        if p.exists():
            return p

    return None

def load_spotdl_config(path: str | None = None) -> dict:
    p = find_spotdl_config(path)
    if not p:
        return {}
    try:
        with open(p, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
            print(f"Loaded spotDL config from: {p}")
            return cfg
    except Exception as e:
        print(f"Warning: failed to read spotDL config at {p}: {e}")
        return {}

def sanitize_filename(s: str, max_len: int = 200) -> str:
    s = (s or "").strip()
    # Remove disallowed FS characters and control chars
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', s)
    # collapse spaces
    s = re.sub(r'\s+', ' ', s).strip()
    return s[:max_len] or "Playlist"

def extract_playlist_id(url_or_id: str) -> str:
    # accept open.spotify.com/playlist/<id>, spotify:playlist:<id>, or raw id
    m = re.search(r"playlist[/:]([A-Za-z0-9]+)", url_or_id)
    if m:
        return m.group(1)
    m = re.search(r"open\.spotify\.com/playlist/([A-Za-z0-9]+)", url_or_id)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9]+", url_or_id):
        return url_or_id
    return url_or_id

def get_name_via_spotify_api(playlist_id: str) -> str | None:
    """Requires SPOTIPY_CLIENT_ID & SPOTIPY_CLIENT_SECRET env vars and spotipy installed."""
    if spotipy is None or SpotifyClientCredentials is None:
        return None
    cid = os.environ.get("SPOTIPY_CLIENT_ID")
    secret = os.environ.get("SPOTIPY_CLIENT_SECRET")
    if not cid or not secret:
        return None
    try:
        auth = SpotifyClientCredentials()
        sp = spotipy.Spotify(auth_manager=auth)
        data = sp.playlist(playlist_id, fields="name")
        if data and "name" in data:
            return data["name"]
    except Exception:
        return None
    return None

def get_name_via_scrape(playlist_id: str) -> str | None:
    """Scrape open.spotify.com/playlist/<id> og:title. Works for public playlists."""
    if requests is None or BeautifulSoup is None:
        return None
    url = f"https://open.spotify.com/playlist/{playlist_id}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; sync-script/1.0)"}
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        meta = soup.find("meta", property="og:title")
        if meta and meta.get("content"):
            return meta["content"]
        if soup.title and soup.title.string:
            return soup.title.string
    except Exception:
        return None
    return None

def resolve_playlist_name(url_or_id: str) -> str:
    pid = extract_playlist_id(url_or_id)
    # 1) Spotify API (private playlists possible)
    name = get_name_via_spotify_api(pid)
    if name:
        return sanitize_filename(name)
    # 2) Scrape public page (if available)
    name = get_name_via_scrape(pid)
    if name:
        return sanitize_filename(name)
    # 3) fallback to id
    return sanitize_filename(pid)

# -------------------------
# spotdl sync runner
# -------------------------
def run_spotdl_sync_into_folder(playlist_url: str, folder: str, playlist_name: str, dry_run: bool = False):
    """
    Create folder, cd into it, run:
      spotdl sync <playlist_url> --save-file "<playlist_name>.spotdl"
    """
    clean_url = playlist_url.split("?", 1)[0]
    Path(folder).mkdir(parents=True, exist_ok=True)
    orig_cwd = os.getcwd()
    try:
        os.chdir(folder)
        save_name = f"{playlist_name}.spotdl"
        if not save_name.endswith(".spotdl"):
            save_name += ".spotdl"
        cmd = ["spotdl", "sync", clean_url, "--save-file", save_name]
        print(f"  Running in {os.getcwd()}: {' '.join(cmd)}")
        if dry_run:
            print("  (dry-run) skipping actual spotdl call")
            return
        subprocess.run(cmd, check=True)
    finally:
        os.chdir(orig_cwd)

# -------------------------
# Post-process (ffmpeg)
# -------------------------
def strip_mp3_metadata_in_folder(folder: str, ffmpeg_cmd: str, dry_run: bool = False):
    """
    For each .mp3 in folder (recursively), run:
      ffmpeg -i input.mp3 -map_metadata -1 -vn -c:a copy input.mp3.tmp && replace
    Keeps file data identical (no re-encode) and removes images+metadata.
    """
    if dry_run:
        print("  (dry-run) skipping post-strip")
        return
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".mp3"):
                full = os.path.join(root, f)
                tmp = full + ".tmp.mp3"
                cmd = [ffmpeg_cmd, "-i", full, "-map_metadata", "-1", "-vn", "-c:a", "copy", tmp, "-y"]
                try:
                    # hide ffmpeg stdout/stderr for cleanliness; errors will raise
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    # replace original atomically
                    shutil.move(tmp, full)
                    print(f"    Stripped metadata: {os.path.relpath(full, folder)}")
                except subprocess.CalledProcessError:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                    print(f"    ⚠️ Failed to strip metadata for {full} (left unchanged)")

# -------------------------
# Main
# -------------------------
def main():
    ap = argparse.ArgumentParser(description="Sync Spotify playlists to per-playlist folders using spotdl.")
    ap.add_argument("--playlists", "-p", default="playlists.txt", help="File with playlist URLs/IDs (one per line)")
    ap.add_argument("--base-dir", "-b", default="~/Music/Spotify", help="Base directory to save playlists (default: ~/Music/Spotify)")
    ap.add_argument("--config", "-c", default=None, help="Explicit spotdl config.json path (optional)")
    ap.add_argument("--no-strip", action="store_true", help="Do NOT run ffmpeg metadata stripping after download")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be done, but don't call spotdl or ffmpeg")
    ap.add_argument("--ffmpeg-cmd", default=None, help="Override ffmpeg executable (optional)")
    args = ap.parse_args()

    playlists_file = Path(args.playlists).expanduser()
    base_dir = Path(args.base_dir).expanduser()

    if not playlists_file.exists():
        print(f"Playlists file not found: {playlists_file}")
        sys.exit(1)

    cfg = load_spotdl_config(args.config)
    # Determine ffmpeg command: config > --ffmpeg-cmd > FFMPEG env > default 'ffmpeg'
    ffmpeg_cmd = cfg.get("ffmpeg") or args.ffmpeg_cmd or os.environ.get("FFMPEG") or "ffmpeg"
    # Respect config's skip_album_art or custom 'post_strip' key
    skip_album_art_config = bool(cfg.get("skip_album_art", False))
    # default behaviour is to strip; user can disable with --no-strip or set "post_strip": false
    do_post_strip = not args.no_strip
    if "post_strip" in cfg:
        do_post_strip = bool(cfg["post_strip"])

    print("Loaded spotDL config:", "yes" if cfg else "no (using defaults)")
    if cfg:
        try:
            # helpful info
            outtmpl = cfg.get("output", "(not set in config)")
            print("spotdl output template:", outtmpl)
        except Exception:
            pass
    print("ffmpeg cmd:", ffmpeg_cmd)
    print("post-processing (strip metadata):", "yes" if do_post_strip else "no")
    print("base dir:", base_dir)
    print("playlists file:", playlists_file)
    print("dry-run:", args.dry_run)
    print()

    base_dir.mkdir(parents=True, exist_ok=True)

    with open(playlists_file, "r", encoding="utf-8") as fh:
        lines = [ln.strip() for ln in fh if ln.strip() and not ln.strip().startswith("#")]

    try:
        for url in lines:
            print("➡️ Processing:", url)
            # resolve nice folder name
            name = resolve_playlist_name(url)
            folder = str(base_dir / name)
            print("  Resolved playlist name:", name)
            # run spotdl sync inside the playlist folder so output files (using spotdl's output template) land in the folder
            try:
                run_spotdl_sync_into_folder(url, folder, name, dry_run=args.dry_run)
            except subprocess.CalledProcessError as e:
                print(f"  ❌ spotdl failed for {url} — {e}")
                # continue to next playlist rather than aborting the whole run
                continue
            except Exception as e:
                print(f"  ❌ Unexpected error while running spotdl for {url} — {e}")
                continue

            # post-process mp3s
            if do_post_strip:
                strip_mp3_metadata_in_folder(folder, ffmpeg_cmd, dry_run=args.dry_run)

            print(f"✅ Done: {name}\n")
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting.")
        sys.exit(1)

    print("All done.")

if __name__ == "__main__":
    main()
