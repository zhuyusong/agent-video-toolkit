"""FFmpeg execution with measured CFR/frame-count contracts."""
from fractions import Fraction
import json
import os
from pathlib import Path
import shutil
import subprocess

from .storage import InputError


def executable(name):
    selected = os.environ.get("AVT_" + name.upper()) or shutil.which(name)
    if not selected or not Path(selected).is_file():
        raise InputError(f"Install {name} on PATH or set AVT_{name.upper()} to its executable")
    return str(Path(selected).resolve())


def process_options():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def run(name, args, timeout=3600):
    result = subprocess.run([executable(name), *map(str, args)], stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=timeout, **process_options())
    if result.returncode:
        raise InputError(f"{name} failed: " + result.stderr.decode("utf-8", "replace")[-3000:])
    return result.stdout


def inspect_video(path):
    """Decode frame timestamps, rejecting VFR or a hidden retiming requirement."""
    result = json.loads(run("ffprobe", ["-v", "error", "-show_streams", "-show_frames",
        "-show_entries", "stream=index,codec_type,width,height,r_frame_rate,avg_frame_rate,time_base,duration,nb_frames,sample_aspect_ratio:stream_tags=rotate:stream_side_data=rotation:frame=media_type,best_effort_timestamp",
        "-of", "json", path]))
    videos = [s for s in result["streams"] if s["codec_type"] == "video"]
    if len(videos) != 1:
        raise InputError("Exactly one video stream is required")
    v = videos[0]
    rotations = [v.get("tags", {}).get("rotate", 0)] + [item.get("rotation", 0) for item in v.get("side_data_list", [])]
    if any(Fraction(str(rotation)) % 360 for rotation in rotations):
        raise InputError("Rotation metadata unsupported; normalize geometry externally before binding ASR")
    fps = Fraction(v["avg_frame_rate"])
    if not 1 <= fps <= 120 or fps != Fraction(v["r_frame_rate"]):
        raise InputError("Only constant frame rate input (1–120 fps) is supported")
    if v.get("sample_aspect_ratio", "1:1") not in ("1:1", "N/A"):
        raise InputError("Square pixels required; normalize externally before binding ASR")
    pts = [int(f["best_effort_timestamp"]) for f in result["frames"] if f["media_type"] == "video"]
    tick = Fraction(v["time_base"])
    if not pts or len(pts) > 432000:
        raise InputError("Video must contain 1–432000 frames")
    if any(abs(Fraction(p) * tick - Fraction(i, 1) / fps) > tick for i, p in enumerate(pts)):
        raise InputError("Nonzero start or variable timestamps; refusing to invent a time mapping")
    duration = Fraction(len(pts), 1) / fps
    if abs(Fraction(v["duration"]) - duration) > max(tick, Fraction(1, 100000)):
        raise InputError("Stream duration does not match complete frame count")
    width, height = int(v["width"]), int(v["height"])
    if width % 2 or height % 2 or not (2 <= width <= 4096 and 2 <= height <= 4096):
        raise InputError("Even dimensions between 2 and 4096 are required")
    return {"width": width, "height": height, "fps": str(fps), "frames": len(pts),
            "duration": str(duration), "audio_streams": sum(s["codec_type"] == "audio" for s in result["streams"])}


def same_clock(a, b):
    if any(a[k] != b[k] for k in ("fps", "frames", "duration")):
        raise InputError("Frame rate, full frame count or duration changed")


def decode_check(path):
    run("ffmpeg", ["-v", "error", "-xerror", "-nostdin", "-i", path, "-map", "0:v:0", "-f", "null", "-"])


def preview(source, target, width, metadata):
    if type(width) is not int or width < 2 or width % 2 or width > metadata["width"]:
        raise InputError("preview_width must be even, >=2 and no larger than source")
    height = round(metadata["height"] * width / metadata["width"] / 2) * 2
    if height < 2 or abs(height / width - metadata["height"] / metadata["width"]) > .005:
        raise InputError("Preview dimensions cannot retain aspect ratio")
    run("ffmpeg", ["-v", "error", "-nostdin", "-n", "-i", source, "-map", "0:v:0",
        "-vf", f"scale={width}:{height}", "-fps_mode", "passthrough", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", target])
    measured = inspect_video(target)
    same_clock(metadata, measured)
    decode_check(target)
    return measured
