# Agent Video Toolkit

Version **0.1.0**. [中文完整说明](README.md)

A standalone local execution toolkit for Codex and other MCP hosts. The host supplies reasoning and coordinates up to four equal-role workers over adjacent complete paragraphs. Every worker owns meaning, explanatory visuals, captions/graphics, camera treatment and executable Canvas code for its assigned paragraphs.

The toolkit freezes inputs, claims tasks, validates content-bound submissions, assembles coverage, executes real source frames and exports a silent MP4 with actual encoded samples. It contains no model, ASR, TTS, asset-generation or wallet calls and requires no Studio/Core installation.

## Install and run

Use Python 3.11+, FFmpeg/ffprobe on `PATH` (with `libx264`), and Playwright Chromium:

```bash
git clone https://github.com/zhuyusong/agent-video-toolkit.git
cd agent-video-toolkit
python -m venv .venv
# Activate .venv, or invoke its Python executable directly.
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m agent_video --root runtime demo demo-output
```

On Windows the interpreter is `.venv\Scripts\python.exe`; on Linux/macOS it is `.venv/bin/python`. Linux browser dependencies can be installed with `python -m playwright install --with-deps chromium`. `AVT_FFMPEG` and `AVT_FFPROBE` may specify absolute executable paths instead of `PATH`.

`demo-output` must not already exist. The demo creates synthetic inputs, four complete example submissions, a real lower-resolution derivative, 48 rendered frames, silent encoding and output samples. Its timing evidence remains `synthetic_not_asr`; the demo is a pipeline check, not an aesthetic quality claim.

## Host integration

Register the installed interpreter as an MCP stdio server with arguments:

```text
-m agent_video.mcp_server --root /absolute/dedicated/runtime
```

Use an absolute interpreter path and a dedicated runtime. See the [Chinese README](README.md#codex-接入) for Codex TOML and the [official MCP documentation](https://developers.openai.com/codex/mcp).

MCP tools are `avt_projects`, `avt_prepare`, `avt_task`, `avt_submit`, `avt_assemble`, `avt_render`, and `avt_status`. The JSON CLI exposes equivalent subcommands: `python -m agent_video --root runtime <command>`. See [protocol documentation](docs/protocol.md) for manifests, transcripts, claims, revision CAS and Canvas code.

Real work requires existing video, final ASR text with global word timings, the exact recognition audio and their hashes. ASR is performed outside this toolkit. `caller_supplied_final_asr` records the caller's assertion and byte bindings; it does not authenticate ASR provenance or prove transcript accuracy or lip synchronization. Synthetic timestamps require explicit opt-in and retain a distinct evidence label.

## Limits

Inputs must use CFR (1–120 fps), regular zero-based timestamps, square pixels, even dimensions of 2–4096, and at most 432,000 frames. Nonzero rotation metadata is rejected; normalize the final source before binding ASR. Input JSON is limited to 16 MiB. Preview derivation retains the full frame clock. Existing assets are limited to 16 PNG/JPEG images (20 MiB and 16 megapixels each). Additional B-roll, subject matting and audio mixing are not provided.

Frame code runs in fresh browser Workers with network restrictions and deadlines. This is **not an operating-system security sandbox**: execute only trusted, reviewed JavaScript. Fonts come from the host system; layout may vary.

Technical receipts verify execution, media and output hashes. `quality_status` remains `host_review_required`; inspect the actual samples and video before judging meaning, readability, visual consistency or style. A failed/interrupted run is retained; create a new run rather than replaying it.

```bash
python -m pytest -m 'not integration'
python -m pytest -m integration
python -m build
```

New project-owned code is [MIT licensed](LICENSE). This permissive license supports integration into different hosts while retaining notices. Dependencies retain their own terms; see [THIRD_PARTY.md](THIRD_PARTY.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [SECURITY.md](SECURITY.md). No user media, credentials, sessions, private binaries or unlicensed fonts are included.
