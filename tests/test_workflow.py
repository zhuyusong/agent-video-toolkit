from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import multiprocessing
from pathlib import Path

import pytest

from agent_video import project
from agent_video.contracts import validate_transcript
from agent_video.demo import example_result
from agent_video.project import Toolkit
from agent_video.storage import InputError, atomic_json, file_hash, read_json


METADATA = {"width": 640, "height": 360, "fps": "12", "frames": 48, "duration": "4", "audio_streams": 0}


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    source = tmp_path / "fixture.mp4"
    source.write_bytes(b"mock media only; integration tests use actual FFmpeg")
    words = [{"id": i, "text": str(i), "start_ms": i*500, "end_ms": i*500+450} for i in range(8)]
    transcript = {"kind": "synthetic", "final": True, "engine": "test-fixture", "source_sha256": file_hash(source), "audio_sha256": None,
                  "text": "01234567", "words": words, "paragraphs": [{"start_word": i, "end_word": i+2} for i in range(0,8,2)]}
    atomic_json(tmp_path / "transcript.json", transcript)
    atomic_json(tmp_path / "project.json", {"schema": "avt-project/v1", "source": source.name, "transcript": "transcript.json"})
    monkeypatch.setattr(project, "inspect_video", lambda _: METADATA.copy())
    toolkit = Toolkit(tmp_path / "runtime")
    state = toolkit.prepare(tmp_path / "project.json", "Exact test brief", allow_synthetic=True)
    return toolkit, state, transcript, tmp_path / "project.json"


def test_frozen_input_and_role_partition(prepared):
    toolkit, state, original, manifest = prepared
    assert len(state["workers"]) == 4
    task = toolkit.task(state["run_id"], "worker-1", "alice")
    assert task["context"]["transcript"] == original
    assert task["context"]["visual_brief"] == "Exact test brief"
    assert [s["start_frame"] for s in task["context"]["segments"]] == [0,12,24,36]
    manifest.with_name("fixture.mp4").write_bytes(b"original changed after freezing")
    toolkit.load(state["run_id"], verify_files=True)  # independent snapshot
    with pytest.raises(InputError, match="claimed"):
        toolkit.task(state["run_id"], "worker-1", "bob")


def test_asr_refuses_estimates_and_missing_audio(prepared):
    toolkit, state, transcript, manifest = prepared
    with pytest.raises(InputError, match="Synthetic"):
        toolkit.prepare(manifest, "Test")
    transcript["kind"] = "asr"
    with pytest.raises(InputError, match="audio"):
        validate_transcript(transcript, transcript["source_sha256"], None, METADATA)


@pytest.mark.parametrize("change", ["text", "time", "coverage", "nan", "bool"])
def test_bad_word_clock(prepared, change):
    _, _, t, _ = prepared
    t = deepcopy(t)
    if change == "text": t["text"] += "changed"
    if change == "time": t["words"][1]["start_ms"] = 10
    if change == "coverage": t["paragraphs"].pop()
    if change == "nan": t["words"][0]["end_ms"] = float("nan")
    if change == "bool": t["words"][0]["start_ms"] = False
    with pytest.raises(InputError):
        validate_transcript(t, t["source_sha256"], None, METADATA, True)


def test_cas_history_idempotency_and_invalid_design(prepared):
    toolkit, state, _, _ = prepared
    run_id = state["run_id"]
    task = toolkit.task(run_id, "worker-1", "alice")
    result = example_result(task)
    first = toolkit.submit(run_id, "worker-1", task["claim_token"], result)
    assert toolkit.submit(run_id, "worker-1", task["claim_token"], result)["reused"]
    changed = deepcopy(result); changed["code"] += "\n// revised"
    with pytest.raises(InputError, match="CAS"):
        toolkit.submit(run_id, "worker-1", task["claim_token"], changed)
    second = toolkit.submit(run_id, "worker-1", task["claim_token"], changed, first["result_sha256"])
    assert first["result_sha256"] != second["result_sha256"]
    assert len(list(toolkit.folder(run_id).glob("result-*.json"))) == 2
    changed["designs"][0]["states"][0]["end_word"] -= 1
    with pytest.raises(InputError, match="coverage"):
        toolkit.submit(run_id, "worker-1", task["claim_token"], changed, second["result_sha256"])


def test_assembly_and_source_tamper(prepared):
    toolkit, state, _, _ = prepared
    run_id = state["run_id"]
    with pytest.raises(InputError, match="Missing"):
        toolkit.assemble(run_id)
    for worker in state["workers"]:
        task = toolkit.task(run_id, worker, worker)
        toolkit.submit(run_id, worker, task["claim_token"], example_result(task))
    assert toolkit.assemble(run_id) == toolkit.assemble(run_id)
    (toolkit.folder(run_id) / "source.mp4").write_bytes(b"tampered")
    with pytest.raises(InputError, match="changed"):
        toolkit.render(run_id)


def claim_in_process(root, run_id, claimant):
    try:
        Toolkit(root).task(run_id, "worker-1", claimant)
        return "claimed"
    except InputError:
        return "conflict"


def test_cross_process_claim(prepared):
    toolkit, state, _, _ = prepared
    with ProcessPoolExecutor(2, mp_context=multiprocessing.get_context("spawn")) as pool:
        futures = [pool.submit(claim_in_process, str(toolkit.root), state["run_id"], name) for name in ("alice", "bob")]
        assert sorted(f.result(timeout=30) for f in futures) == ["claimed", "conflict"]


def test_path_escape_and_worker_limit(prepared):
    toolkit, _, _, manifest = prepared
    with pytest.raises(InputError): toolkit.status("../outside")
    with pytest.raises(InputError, match="1–4"): toolkit.prepare(manifest, "Test", workers=5, allow_synthetic=True)


def test_oversized_json_keeps_existing_state(tmp_path):
    path = tmp_path / "state.json"
    atomic_json(path, {"preserved": True})
    with pytest.raises(InputError, match="16 MiB"):
        atomic_json(path, {"text": "a" * (16 * 1024 * 1024)})
    assert read_json(path) == {"preserved": True}
