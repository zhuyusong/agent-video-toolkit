"""Sequential real source frames → isolated Canvas workers → silent H.264."""
import base64
from fractions import Fraction
import hashlib
from importlib.resources import files
import io
import json
import os
from pathlib import Path
import subprocess
import time

from PIL import Image
from playwright.sync_api import sync_playwright

from . import __version__
from .media import executable, inspect_video, same_clock, decode_check, run, process_options
from .project import Toolkit
from .storage import InputError, atomic_json, digest, file_hash, locked, read_json


PAGE = """<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' 'unsafe-eval'; worker-src blob:; connect-src 'none'; img-src data: blob:">
<title>Agent Video local frame executor</title>"""
EXECUTE = """async ({script, data, timeout}) => {
  // A new worker and drawing context per frame prevent cross-frame/employee state leaks.
  const url = URL.createObjectURL(new Blob([script], {type:'text/javascript'}));
  const worker = new Worker(url);
  try {
    return await new Promise((resolve, reject) => {
      const timer = setTimeout(() => {worker.terminate(); reject(new Error('Frame deadline exceeded'));}, timeout);
      worker.onmessage = ({data}) => {clearTimeout(timer); data.error ? reject(new Error(data.error)) : resolve(data.png);};
      worker.onerror = e => {clearTimeout(timer); reject(new Error(e.message));};
      worker.postMessage(data);
    });
  } finally {worker.terminate(); URL.revokeObjectURL(url);}
}"""


def read_exact(handle, size):
    chunks, received = [], 0
    while received < size:
        data = handle.read(size - received)
        if not data:
            raise InputError("Source decoder ended before the complete frame count")
        chunks.append(data)
        received += len(data)
    return b"".join(chunks)


def encode_frames(folder, context, results, progress):
    metadata = context["media"]
    width, height, count = metadata["width"], metadata["height"], metadata["frames"]
    worker_script = files("agent_video").joinpath("canvas_worker.js").read_text("utf-8")
    asset_bytes = {name: base64.b64encode((folder / a["file"]).read_bytes()).decode() for name, a in context["assets"].items()}
    programs = {r["worker_id"]: r for r in results}
    assignment = {s["id"]: w["id"] for w in context["workers"] for s in w["segments"]}
    frame_digest = hashlib.sha256()
    segment_index = 0
    with open(folder / "decode.log", "wb") as decode_log, open(folder / "encode.log", "wb") as encode_log:
        decoder = subprocess.Popen([executable("ffmpeg"), "-v", "error", "-xerror", "-nostdin", "-noautorotate", "-i", str(folder / context["render_source"]),
            "-map", "0:v:0", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=decode_log, **process_options())
        encoder = None
        try:
            encoder = subprocess.Popen([executable("ffmpeg"), "-v", "error", "-nostdin", "-n", "-f", "image2pipe", "-framerate", metadata["fps"],
                "-vcodec", "png", "-i", "pipe:0", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(folder / "output.mp4")],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=encode_log, **process_options())
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page(service_workers="block", accept_downloads=False)
                    page.route("**/*", lambda route: route.abort())
                    page.set_content(PAGE)
                    for frame in range(count):
                        while frame >= context["segments"][segment_index]["end_frame"]:
                            segment_index += 1
                        segment = context["segments"][segment_index]
                        raw = read_exact(decoder.stdout, width * height * 3)
                        buffer = io.BytesIO()
                        Image.frombytes("RGB", (width, height), raw).save(buffer, "PNG")
                        request = {"code": programs[assignment[segment["id"]]]["code"], "assets": asset_bytes,
                                   "source": base64.b64encode(buffer.getvalue()).decode(),
                                   "input": {"frame": frame, "time_ms": float(Fraction(frame * 1000, 1) / Fraction(metadata["fps"])),
                                             "width": width, "height": height, "fps": metadata["fps"], "frames": count,
                                             "segment": segment, "words": context["transcript"]["words"]}}
                        encoded = page.evaluate(EXECUTE, {"script": worker_script, "data": request, "timeout": 10000})
                        png = base64.b64decode(encoded, validate=True)
                        with Image.open(io.BytesIO(png)) as picture:
                            if picture.size != (width, height) or picture.format != "PNG":
                                raise InputError("Canvas returned invalid frame dimensions")
                            picture.verify()
                        frame_digest.update(hashlib.sha256(png).digest())
                        encoder.stdin.write(png)
                        if frame % 24 == 0 or frame == count - 1:
                            progress(frame + 1)
                finally:
                    browser.close()
            if decoder.stdout.read(1):
                raise InputError("Source decoder produced extra frames")
            decoder.stdout.close()
            encoder.stdin.close()
            if decoder.wait(timeout=30) or encoder.wait(timeout=120):
                raise InputError("FFmpeg failed; inspect local encode/decode logs")
        finally:
            for process in (decoder, encoder):
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
                    for stream in (process.stdin, process.stdout):
                        if stream and not stream.closed:
                            stream.close()
    return frame_digest.hexdigest()


def render_run(root, run_id):
    toolkit = Toolkit(root)
    folder = toolkit.folder(run_id)
    with locked(folder, "render", timeout=0):
        with locked(folder):
            state = read_json(folder / "state.json")
            if state["state"] != "rendering":
                return
        try:
            folder, frozen = toolkit.load(run_id, verify_files=True)
            context = frozen["context"]
            results = toolkit.read_results(folder, frozen, state)
            assembly = read_json(folder / "assembly.json")
            if digest(assembly) != state["assembly_sha256"] or assembly["results"] != [digest(r) for r in results] or assembly["input_sha256"] != frozen["input_sha256"]:
                raise InputError("Assembly provenance mismatch")
            def progress(frame):
                with locked(folder):
                    current = read_json(folder / "state.json")
                    current.update(progress_frame=frame, heartbeat_at=time.time())
                    atomic_json(folder / "state.json", current)
            frames_sha = encode_frames(folder, context, results, progress)
            measured = inspect_video(folder / "output.mp4")
            same_clock(context["media"], measured)
            if measured["audio_streams"] or any(measured[k] != context["media"][k] for k in ("width", "height")):
                raise InputError("Silent video or geometry contract failed")
            decode_check(folder / "output.mp4")
            n = measured["frames"]
            sample_frames = sorted({0, n//4, n//2, 3*n//4, n-1} | {f for s in context["segments"] for f in (s["start_frame"], s["end_frame"]-1)})
            sample_dir = folder / "samples"
            sample_dir.mkdir()
            samples = []
            for frame in sample_frames:
                name = f"samples/frame-{frame:08d}.png"
                run("ffmpeg", ["-v", "error", "-nostdin", "-n", "-i", folder / "output.mp4", "-vf", f"select=eq(n\\,{frame})", "-frames:v", "1", folder / name])
                with Image.open(folder / name) as picture:
                    if picture.size != (measured["width"], measured["height"]):
                        raise InputError("Encoded sample geometry changed")
                    picture.verify()
                samples.append(name)
            toolkit.load(run_id, verify_files=True)
            toolkit.read_results(folder, frozen, state)
            receipt = {"schema": "avt-render-receipt/v1", "toolkit_version": __version__,
                       "input_sha256": frozen["input_sha256"], "assembly_sha256": state["assembly_sha256"],
                       "result_sha256": assembly["results"], "source_sha256": context["source_sha256"],
                       "render_source_sha256": context["render_source_sha256"], "word_clock_sha256": context["word_clock_sha256"],
                       "clock_mapping": "identity", "timing_evidence": context["timing_evidence"],
                       "media": measured, "executed_frames": n, "frame_sha256_sequence_digest": frames_sha,
                       "technical_execution_verified": True, "full_decode_verified": True,
                       "quality_status": "host_review_required", "samples": samples,
                       "sample_frames": sample_frames, "outputs": {name: file_hash(folder / name) for name in ["output.mp4", *samples]},
                       "runtime": {"ffmpeg": run("ffmpeg", ["-version"]).decode("utf-8", "replace").splitlines()[0]}}
            atomic_json(folder / "receipt.json", receipt)
            with locked(folder):
                current = read_json(folder / "state.json")
                current.update(state="succeeded", receipt_sha256=digest(receipt), completed_at=time.time())
                atomic_json(folder / "state.json", current)
        except Exception as exc:
            with locked(folder):
                current = read_json(folder / "state.json")
                current.update(state="failed", error=str(exc)[:3000], completed_at=time.time())
                atomic_json(folder / "state.json", current)
            raise
