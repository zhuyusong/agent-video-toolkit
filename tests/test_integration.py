import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image
import pytest

from agent_video.cli import wait
from agent_video.demo import create_inputs, demo, example_result
from agent_video.media import inspect_video, same_clock, run
from agent_video.project import Toolkit
from agent_video.storage import InputError, read_json


pytestmark = pytest.mark.integration


def test_real_preview_render_samples_and_no_replay(tmp_path):
    toolkit = Toolkit(tmp_path / "runtime")
    state = demo(toolkit, tmp_path / "inputs")
    assert state["state"] == "succeeded", state
    receipt = read_json(state["receipt"])
    assert receipt["timing_evidence"] == "synthetic_not_asr"
    assert receipt["executed_frames"] == 48
    assert receipt["media"]["fps"] == "12"
    assert receipt["media"]["width"] == 320
    assert receipt["media"]["audio_streams"] == 0
    assert receipt["source_sha256"] != receipt["render_source_sha256"]
    assert receipt["quality_status"] == "host_review_required"
    with Image.open(state["samples"][0]) as picture:
        assert picture.size == (320,180)
    assert toolkit.render(state["run_id"])["request_id"] == state["request_id"]
    assert len(list(toolkit.folder(state["run_id"]).glob("output*.mp4"))) == 1
    Path(state["samples"][0]).write_bytes(b"tampered")
    with pytest.raises(InputError, match="Output changed"):
        toolkit.status(state["run_id"])
    with pytest.raises(InputError, match="Output changed"):
        toolkit.render(state["run_id"])


def test_canvas_infinite_loop_fails_without_retry(tmp_path):
    toolkit = Toolkit(tmp_path / "runtime")
    manifest = create_inputs(tmp_path / "inputs")
    state = toolkit.prepare(manifest, "Test code deadline", workers=1, allow_synthetic=True)
    task = toolkit.task(state["run_id"], "worker-1", "test")
    result = example_result(task); result["code"] = "while(true){}"
    toolkit.submit(state["run_id"], "worker-1", task["claim_token"], result)
    toolkit.assemble(state["run_id"])
    request = toolkit.render(state["run_id"])
    toolkit.render(state["run_id"])
    state = wait(toolkit, state["run_id"], 90)
    assert state["state"] == "failed", state
    assert "deadline" in state["error"]
    assert toolkit.render(state["run_id"])["request_id"] == request["request_id"]
    assert not (toolkit.folder(state["run_id"]) / "receipt.json").exists()


def test_mcp_stdio_roundtrip(tmp_path):
    manifest = create_inputs(tmp_path / "mcp-inputs")
    async def check():
        params = StdioServerParameters(command=sys.executable, args=["-m", "agent_video.mcp_server", "--root", str(tmp_path / "mcp-runtime")],
            env={**{k: v for k, v in os.environ.items() if k in ("AVT_FFMPEG", "AVT_FFPROBE")}, "PYTHONIOENCODING": "utf-8"})
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                listed = await session.list_tools()
                assert {tool.name for tool in listed.tools} == {"avt_" + n for n in ("projects", "prepare", "task", "submit", "assemble", "render", "status")}
                async def call(name, arguments):
                    result = await session.call_tool("avt_" + name, arguments)
                    assert not result.isError, result
                    return json.loads(result.content[0].text)
                assert await call("projects", {}) == {"runs": []}
                prepared = await call("prepare", {"manifest_path": str(manifest), "visual_brief": "MCP synthetic integration check", "workers": 1, "preview_width": 320, "allow_synthetic": True})
                run_id = prepared["run_id"]
                task = await call("task", {"run_id": run_id, "worker_id": "worker-1", "claimant": "mcp-test"})
                await call("submit", {"run_id": run_id, "worker_id": "worker-1", "claim_token": task["claim_token"], "result": example_result(task)})
                await call("assemble", {"run_id": run_id})
                request = await call("render", {"run_id": run_id})
                assert (await call("render", {"run_id": run_id}))["request_id"] == request["request_id"]
                for _ in range(120):
                    state = await call("status", {"run_id": run_id})
                    if state["state"] != "rendering": break
                    await asyncio.sleep(.25)
                assert state["state"] == "succeeded", state
                assert Path(state["video"]).is_file()
    asyncio.run(check())


def test_fractional_fps_clock(tmp_path):
    source = tmp_path / "fractional.mp4"
    run("ffmpeg", ["-v", "error", "-nostdin", "-n", "-f", "lavfi", "-i", "testsrc2=size=64x64:rate=30000/1001", "-frames:v", "30", "-an", "-c:v", "libx264", source])
    measured = inspect_video(source)
    assert measured["fps"] == "30000/1001"
    assert measured["frames"] == 30


def test_rotation_metadata_is_rejected(monkeypatch):
    from agent_video import media
    probe = {"streams": [{"codec_type": "video", "side_data_list": [{"rotation": 90}]}]}
    monkeypatch.setattr(media, "run", lambda *_: json.dumps(probe).encode())
    with pytest.raises(InputError, match="Rotation"):
        media.inspect_video("rotated.mp4")
