"""ffprobe/ffmpeg media helpers (argv only, bounded timeouts).

Reel targets follow Instagram Graph API publishing specs: MOV/MP4, H.264 or
HEVC, AAC 48 kHz audio, 23-60 fps, <=1920 horizontal px, 9:16 recommended,
<=25 Mbps video bitrate, 3 s..15 min, <=1 GB.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .util import check, run

REEL_MAX_MB = 1024
REEL_MAX_BITRATE_MBPS = 25
REEL_MIN_S = 3.0
REEL_MAX_S = 900.0
REEL_MAX_W = 1920
REEL_VIDEO_CODECS = {"h264", "hevc"}
REEL_ASPECT = 9 / 16
ASPECT_TOL = 0.06


def probe(path: str | Path) -> dict:
    if not check("ffprobe"):
        raise RuntimeError("ffprobe not on PATH")
    r = run(["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)], timeout=60)
    return json.loads(r.stdout)


def reel_errors(path: str | Path) -> list[str]:
    p = Path(path)
    errors = []
    if not p.exists():
        return [f"missing file: {p}"]
    try:
        info = probe(p)
    except Exception as e:
        return [f"probe failed: {e}"]
    fmt = info.get("format", {})
    duration = float(fmt.get("duration", 0))
    size_mb = int(fmt.get("size", 0)) / 1e6
    bitrate_mbps = int(fmt.get("bit_rate", 0)) / 1e6
    if not REEL_MIN_S <= duration <= REEL_MAX_S:
        errors.append(f"duration {duration:.1f}s outside {REEL_MIN_S}-"
                      f"{REEL_MAX_S}s")
    if size_mb > REEL_MAX_MB:
        errors.append(f"size {size_mb:.0f}MB > {REEL_MAX_MB}MB")
    if bitrate_mbps > REEL_MAX_BITRATE_MBPS:
        errors.append(f"bitrate {bitrate_mbps:.1f}Mbps > "
                      f"{REEL_MAX_BITRATE_MBPS}Mbps")
    vstreams = [s for s in info.get("streams", [])
                if s.get("codec_type") == "video"]
    if not vstreams:
        errors.append("no video stream")
    else:
        v = vstreams[0]
        if v.get("codec_name") not in REEL_VIDEO_CODECS:
            errors.append(f"video codec {v.get('codec_name')} not in "
                          f"{sorted(REEL_VIDEO_CODECS)}")
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        if w > REEL_MAX_W:
            errors.append(f"width {w} > {REEL_MAX_W}")
        if w and h and abs(w / h - REEL_ASPECT) > ASPECT_TOL:
            errors.append(f"aspect {w}x{h} not ~9:16")
    for s in info.get("streams", []):
        if s.get("codec_type") == "audio" and s.get("codec_name") != "aac":
            errors.append(f"audio codec {s.get('codec_name')} != aac")
    return errors


def assemble_reel(images: list[Path], out: Path,
                  audio: Path | None = None, fps: int = 30,
                  seconds_per_image: float = 2.5,
                  size: tuple[int, int] = (1080, 1920)) -> None:
    """Stills -> 9:16 h264/aac reel via concat. libx264 for portability."""
    if not check("ffmpeg"):
        raise RuntimeError("ffmpeg not on PATH")
    if not images:
        raise RuntimeError("no images")
    w, h = size
    argv = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for img in images:
        argv += ["-loop", "1", "-t", f"{seconds_per_image}", "-i", str(img)]
    if audio:
        argv += ["-i", str(audio)]
    n = len(images)
    filters = []
    for i in range(n):
        filters.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{i}]")
    filters.append("".join(f"[v{i}]" for i in range(n))
                   + f"concat=n={n}:v=1:a=0[vout]")
    argv += ["-filter_complex", ";".join(filters), "-map", "[vout]"]
    if audio:
        argv += ["-map", f"{n}:a", "-c:a", "aac", "-ar", "48000", "-shortest"]
    argv += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps),
             "-movflags", "+faststart", str(out)]
    run(argv, timeout=1800)
