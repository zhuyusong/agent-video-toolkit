"""Immutable input snapshots and cross-process compare-and-swap workflow."""
from copy import deepcopy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

from PIL import Image

from . import __version__
from .contracts import INSTRUCTIONS, exact, identifier, text, validate_transcript, segments_for, workers_for, validate_result
from .media import inspect_video, preview, process_options
from .storage import InputError, atomic_json, confined, digest, file_hash, locked, read_json


class Toolkit:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def folder(self, run_id):
        return confined(self.root, identifier(run_id))

    def load(self, run_id, verify_files=False):
        folder = self.folder(run_id)
        frozen = read_json(confined(folder, "input.json"))
        if digest(frozen["context"]) != frozen["input_sha256"]:
            raise InputError("Frozen input integrity failure")
        if verify_files:
            for name, identity in frozen["context"]["files"].items():
                if file_hash(confined(folder, name)) != identity:
                    raise InputError("Frozen file changed: " + name)
        return folder, frozen

    def projects(self):
        return {"runs": [{"run_id": p.name, "state": self.status(p.name)["state"]}
                         for p in sorted(self.root.iterdir()) if p.is_dir() and (p / "input.json").is_file()]}

    def prepare(self, manifest_path, visual_brief, workers=4, preview_width=None, allow_synthetic=False):
        text(visual_brief)
        manifest_path = Path(manifest_path).resolve(strict=True)
        manifest = read_json(manifest_path)
        exact(manifest, ("schema", "source", "transcript"), ("audio", "assets"))
        if manifest["schema"] != "avt-project/v1":
            raise InputError("Expected avt-project/v1")
        def local(value):
            text(value)
            p = (manifest_path.parent / value).resolve(strict=True)
            if not p.is_file():
                raise InputError("Inputs must be existing local files")
            return p
        source, transcript_path = local(manifest["source"]), local(manifest["transcript"])
        audio = local(manifest["audio"]) if manifest.get("audio") else None
        source_sha, audio_sha = file_hash(source), file_hash(audio) if audio else None
        metadata = inspect_video(source)
        transcript = validate_transcript(read_json(transcript_path), source_sha, audio_sha, metadata, allow_synthetic)
        segments = segments_for(transcript, metadata)
        workers_data = workers_for(segments, workers)
        # A failed preparation is retained for diagnosis and never listed as ready.
        run_id = uuid4().hex
        folder = self.folder(run_id)
        folder.mkdir()
        files = {}
        def snapshot(path, name, expected=None):
            identity = expected or file_hash(path)
            shutil.copyfile(path, confined(folder, name))
            if file_hash(confined(folder, name)) != identity or file_hash(path) != identity:
                raise InputError("Input changed while freezing: " + name)
            files[name] = identity
        snapshot(source, "source" + source.suffix.lower(), source_sha)
        source_name = "source" + source.suffix.lower()
        snapshot(transcript_path, "transcript.json")
        if read_json(folder / "transcript.json") != transcript:
            raise InputError("Transcript changed while freezing")
        if audio:
            snapshot(audio, "recognition-audio" + audio.suffix.lower(), audio_sha)
        assets = {}
        for asset in manifest.get("assets", []):
            exact(asset, ("id", "path", "kind", "rights"))
            asset_id = identifier(asset["id"])
            text(asset["rights"])
            if asset_id in assets or asset["kind"] != "image" or len(assets) >= 16:
                raise InputError("At most 16 unique local image assets are supported")
            path = local(asset["path"])
            if path.stat().st_size > 20 * 1024 * 1024:
                raise InputError("Image exceeds 20 MiB")
            with Image.open(path) as im:
                if im.format not in ("PNG", "JPEG") or im.width * im.height > 16000000:
                    raise InputError("Assets must be PNG/JPEG <=16 megapixels")
                im.verify()
            name = "asset-" + asset_id + path.suffix.lower()
            snapshot(path, name)
            assets[asset_id] = {"file": name, "sha256": files[name], "rights": asset["rights"], "kind": "image"}
        render_source, render_metadata = source_name, metadata
        if preview_width is not None:
            render_source = "preview.mp4"
            render_metadata = preview(folder / source_name, folder / render_source, preview_width, metadata)
            files[render_source] = file_hash(folder / render_source)
        context = {"schema": "avt-input/v1", "toolkit_version": __version__, "run_id": run_id,
                   "visual_brief": visual_brief, "transcript": transcript, "word_clock_sha256": digest(transcript["words"]),
                   "source": source_name, "source_sha256": source_sha, "original_media": metadata,
                   "render_source": render_source, "render_source_sha256": files[render_source], "media": render_metadata,
                   "clock_mapping": "identity", "segments": segments, "workers": workers_data,
                   "assets": assets, "files": files,
                   "timing_evidence": "synthetic_not_asr" if transcript["kind"] == "synthetic" else "caller_supplied_final_asr"}
        frozen = {"input_sha256": digest(context), "context": context}
        atomic_json(folder / "input.json", frozen)
        atomic_json(folder / "state.json", {"state": "prepared", "input_sha256": frozen["input_sha256"], "claims": {}, "results": {}, "created_at": time.time()})
        return self.status(run_id)

    @staticmethod
    def worker(frozen, worker_id):
        for worker in frozen["context"]["workers"]:
            if worker["id"] == worker_id:
                return worker
        raise InputError("Unknown worker")

    def task(self, run_id, worker_id, claimant):
        text(claimant, 128)
        folder, frozen = self.load(run_id)
        worker = self.worker(frozen, worker_id)
        with locked(folder):
            state = read_json(folder / "state.json")
            claim = state["claims"].get(worker_id)
            if claim and claim["claimant"] != claimant:
                raise InputError("Worker already claimed; do not overwrite another worker")
            if not claim:
                if state["state"] not in ("prepared", "assembled"):
                    raise InputError("Run is frozen after rendering is requested")
                claim = {"claimant": claimant, "token": uuid4().hex}
                state["claims"][worker_id] = claim
                atomic_json(folder / "state.json", state)
        return {"run_id": run_id, "input_sha256": frozen["input_sha256"], "claim_token": claim["token"],
                "previous_result_sha256": state["results"].get(worker_id), "worker": worker,
                "context": frozen["context"], "instructions": INSTRUCTIONS,
                "code_contract": "Synchronous Canvas2D function body: ctx, input, helpers. See docs/protocol.md. No imports/network. Global frame and original words stay unchanged."}

    def submit(self, run_id, worker_id, claim_token, result, expected_sha256=None):
        folder, frozen = self.load(run_id)
        worker = self.worker(frozen, worker_id)
        validate_result(result, frozen, worker)
        identity = digest(result)
        with locked(folder):
            state = read_json(folder / "state.json")
            if state["claims"].get(worker_id, {}).get("token") != claim_token:
                raise InputError("Claim token mismatch")
            if state["state"] not in ("prepared", "assembled"):
                raise InputError("Run is frozen after rendering is requested")
            previous = state["results"].get(worker_id)
            if previous == identity:
                return {"result_sha256": identity, "reused": True}
            if previous != expected_sha256:
                raise InputError("CAS conflict: re-read task and supply previous_result_sha256")
            # Content-addressed immutable result history; state is the commit point.
            path = confined(folder, "result-" + identity + ".json")
            if path.exists() and file_hash(path) != identity:
                raise InputError("Result object integrity failure")
            if not path.exists():
                atomic_json(path, result)
            state["results"][worker_id] = identity
            state["state"] = "prepared"
            state.pop("assembly_sha256", None)
            atomic_json(folder / "state.json", state)
        return {"result_sha256": identity, "reused": False}

    def read_results(self, folder, frozen, state):
        results = []
        for worker in frozen["context"]["workers"]:
            identity = state["results"].get(worker["id"])
            if not identity:
                raise InputError("Missing result: " + worker["id"])
            result = read_json(confined(folder, "result-" + identifier(identity) + ".json"))
            if digest(result) != identity:
                raise InputError("Result object changed")
            results.append(validate_result(result, frozen, worker))
        return results

    def assemble(self, run_id):
        folder, frozen = self.load(run_id, verify_files=True)
        with locked(folder):
            state = read_json(folder / "state.json")
            if state["state"] not in ("prepared", "assembled"):
                raise InputError("Run is frozen after rendering is requested")
            results = self.read_results(folder, frozen, state)
            assembly = {"input_sha256": frozen["input_sha256"], "results": [digest(r) for r in results],
                        "coverage": frozen["context"]["segments"]}
            identity = digest(assembly)
            atomic_json(folder / "assembly.json", assembly)
            state.update(state="assembled", assembly_sha256=identity)
            atomic_json(folder / "state.json", state)
        return {"run_id": run_id, "assembly_sha256": identity, "quality_status": "host_review_required"}

    def render(self, run_id):
        folder, frozen = self.load(run_id, verify_files=True)
        with locked(folder):
            state = read_json(folder / "state.json")
            if state["state"] in ("rendering", "succeeded", "failed"):
                return self.status(run_id)
            if state["state"] != "assembled":
                raise InputError("Assemble all worker results first")
            self.read_results(folder, frozen, state)
            if digest(read_json(folder / "assembly.json")) != state["assembly_sha256"]:
                raise InputError("Assembly changed")
            state.update(state="rendering", request_id=uuid4().hex, started_at=time.time(), progress_frame=0)
            atomic_json(folder / "state.json", state)
            try:
                with open(folder / "render.log", "ab") as log:
                    p = subprocess.Popen([sys.executable, "-m", "agent_video", "--root", str(self.root), "_render", run_id],
                        stdin=subprocess.DEVNULL, stdout=log, stderr=log, **process_options())
                state["pid"] = p.pid
            except OSError:
                state.update(state="failed", error="Unable to start local renderer")
            atomic_json(folder / "state.json", state)
        return self.status(run_id)

    def _public(self, run_id, frozen, state):
        public = {k: deepcopy(v) for k, v in state.items() if k not in ("claims",)}
        public.update(run_id=run_id, workers=[w["id"] for w in frozen["context"]["workers"]],
                      timing_evidence=frozen["context"]["timing_evidence"], quality_status="host_review_required",
                      model_api_called=False, input_sha256=frozen["input_sha256"])
        return public

    def status(self, run_id):
        folder, frozen = self.load(run_id)
        state = read_json(folder / "state.json")
        if state["input_sha256"] != frozen["input_sha256"]:
            raise InputError("State binding changed")
        public = self._public(run_id, frozen, state)
        if state["state"] == "rendering" and time.time() - state["started_at"] > 60:
            try:
                with locked(folder, "render", timeout=0):
                    public.update(state="interrupted", error="Renderer no longer owns its lock; outputs are unverified. Prepare a new run.")
            except InputError:
                pass
        if state["state"] == "succeeded":
            receipt_path = confined(folder, "receipt.json")
            receipt = read_json(receipt_path)
            if digest(receipt) != state["receipt_sha256"]:
                raise InputError("Receipt changed")
            for name, identity in receipt["outputs"].items():
                if file_hash(confined(folder, name)) != identity:
                    raise InputError("Output changed: " + name)
            public.update(video=str(folder / "output.mp4"), receipt=str(receipt_path), samples=[str(folder / s) for s in receipt["samples"]])
        return public
