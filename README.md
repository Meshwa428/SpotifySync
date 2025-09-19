# 🎵 Spotify Playlist Sync Script

A Python script that uses [spotDL](https://github.com/spotDL/spotify-downloader) to **sync all your Spotify playlists to local folders**, one directory per playlist.

Features:

* 🟢 Automatically reads your **spotDL config** (supports `$SPOTDL_CONFIG`, XDG paths, `~/.spotdl/config.json`, `%APPDATA%`).
* 🟢 Resolves **playlist names**:

  * Uses the Spotify Web API (if `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET` are set),
  * Falls back to scraping `open.spotify.com`,
  * Falls back to playlist ID if nothing else works.
* 🟢 Creates **separate folders per playlist** under your chosen base directory.
* 🟢 Runs:

  ```bash
  spotdl sync <playlist-url> --save-file "<playlist_name>.spotdl"
  ```

  inside each folder.
* 🟢 Optional **post-processing with ffmpeg** to strip artwork/metadata from MP3s (lossless, fast).
* 🟢 Supports **dry-run mode** to preview actions.
* 🟢 Safe handling of errors & keyboard interrupts.

---

## 📦 Requirements

* Python **3.9+**
* [spotDL](https://github.com/spotDL/spotify-downloader) installed and available in `$PATH`
* [ffmpeg](https://ffmpeg.org/) installed and in `$PATH`

Optional extras:

```bash
pip install spotipy requests beautifulsoup4
```

* `spotipy`: resolve **private playlist names** using Spotify API
* `requests + beautifulsoup4`: resolve **public playlist names** via scraping

---

## ⚙️ Setup

1. Clone or copy this script to your machine:

   ```bash
   wget https://example.com/sync_spotify.py
   chmod +x sync_spotify.py
   ```

2. Create a `playlists.txt` file with one playlist URL or ID per line:

   ```txt
   https://open.spotify.com/playlist/59Q1gNuTXGAM6lB6R6QPjd
   https://open.spotify.com/playlist/7a4hTeHg6okijPpRqUH3ud
   ```

3. Make sure your [spotDL config](https://spotdl.rtfd.io/en/latest/configuration/) exists at one of:

   * `$SPOTDL_CONFIG`
   * `~/.config/spotdl/config.json`
   * `~/.spotdl/config.json`
   * `%APPDATA%/spotdl/config.json`

---

## ▶️ Usage

Basic sync:

```bash
python sync_spotify.py
```

### Options

| Option             | Description                                                       |
| ------------------ | ----------------------------------------------------------------- |
| `--playlists FILE` | Path to playlist list file (default: `playlists.txt`)             |
| `--base-dir DIR`   | Base folder for downloaded playlists (default: `~/Music/Spotify`) |
| `--config PATH`    | Explicit `config.json` for spotDL                                 |
| `--no-strip`       | Disable ffmpeg metadata/artwork stripping                         |
| `--dry-run`        | Show what would happen, without running `spotdl` or `ffmpeg`      |
| `--ffmpeg-cmd CMD` | Override ffmpeg executable path                                   |

---

## 🛠️ Examples

### Sync all playlists into `~/Music/Spotify`

```bash
python sync_spotify.py
```

### Sync into a custom directory

```bash
python sync_spotify.py --base-dir /mnt/music/spotify
```

### Use a custom spotDL config

```bash
python sync_spotify.py --config ~/.spotdl/my_config.json
```

### Dry-run (test mode, no downloads)

```bash
python sync_spotify.py --dry-run
```

### Disable metadata stripping

```bash
python sync_spotify.py --no-strip
```

---

## 🔧 Post-processing

By default, the script strips metadata/artwork from `.mp3` files after downloading:

```bash
ffmpeg -i song.mp3 -map_metadata -1 -vn -c:a copy song.mp3.tmp && mv song.mp3.tmp song.mp3
```

This makes files lighter, cleaner, and avoids duplicate album art blobs.
Use `--no-strip` to disable this step.

---

## ⚡ Troubleshooting

* **Playlist names not resolved**
  → Install `spotipy` and set `SPOTIPY_CLIENT_ID` / `SPOTIPY_CLIENT_SECRET` env vars, or set them in spotdl's `config.json` file.
  → The config file is located at `C:\Users\your_username\.spotdl\config.json` or `~/.spotdl/config.json` under linux

---

## 📜 License

MIT — free to use, modify, and share.
