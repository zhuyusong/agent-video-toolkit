"""Self-contained synthetic fixtures. These timings are never represented as ASR."""
from pathlib import Path

from .media import run
from .storage import atomic_json, file_hash


EXAMPLE_CODE = """// Synthetic demonstration only: fill a progress bar over the paragraph interval.
const {width:w, height:h, frame, segment:s} = input;
const t = (frame - s.start_frame) / Math.max(1, s.end_frame - s.start_frame - 1);
ctx.fillStyle = 'rgba(10,20,35,.85)'; ctx.fillRect(0, 0, w, h);
ctx.fillStyle = '#e7edf4'; ctx.font = `${w/25}px sans-serif`;
ctx.fillText('SYNTHETIC PIPELINE DEMO', w*.07, h*.17);
ctx.font = `${w/38}px sans-serif`;
ctx.fillText(s.id + ' / global frame ' + frame, w*.07, h*.28);
ctx.fillStyle = '#334155'; ctx.fillRect(w*.08,h*.42,w*.84,h*.12);
ctx.fillStyle = '#65d9b6'; ctx.fillRect(w*.08,h*.42,w*.84*t,h*.12);
helpers.caption(s.start_word,s.end_word,w/2,h*.78,w/25);
"""


def example_result(task):
    return {"schema": "avt-worker/v1", "input_sha256": task["input_sha256"], "worker_id": task["worker"]["id"],
            "designs": [{"segment_id": s["id"], "meaning": "Synthetic progress demonstration; no real narration.",
                         "visual_explanation": "A horizontal bar fills during this exact paragraph interval.",
                         "caption_graphics": "Original synthetic words reveal at their fixture timestamps.", "camera": "Fixed camera; no subject footage.",
                         "states": [{"start_word": s["start_word"], "end_word": s["end_word"], "action": "Fill bar from zero to full", "explanation": "Shows local progress while global frame count stays continuous."}], "assets": []}
                        for s in task["worker"]["segments"]], "code": EXAMPLE_CODE}


def create_inputs(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "synthetic.mp4"
    run("ffmpeg", ["-v", "error", "-nostdin", "-n", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=12:duration=4",
                   "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", source])
    words = [{"id": i, "text": item, "start_ms": i*500, "end_ms": i*500+450}
             for i, item in enumerate(["First ", "stage. ", "Second ", "stage. ", "Third ", "stage. ", "Final ", "stage."])]
    atomic_json(output / "transcript.json", {"kind": "synthetic", "final": True, "engine": "deterministic-demo-fixture-not-ASR",
        "source_sha256": file_hash(source), "audio_sha256": None, "text": "".join(w["text"] for w in words), "words": words,
        "paragraphs": [{"start_word": i, "end_word": i+2} for i in range(0, 8, 2)]})
    atomic_json(output / "project.json", {"schema": "avt-project/v1", "source": "synthetic.mp4", "transcript": "transcript.json", "assets": []})
    return output / "project.json"


def demo(toolkit, output, prepare_only=False):
    from .cli import wait
    manifest = create_inputs(output)
    state = toolkit.prepare(manifest, "Synthetic execution demonstration: clearly label fixture status and preserve every frame.", allow_synthetic=True, preview_width=320)
    if prepare_only:
        return state
    for worker_id in state["workers"]:
        task = toolkit.task(state["run_id"], worker_id, "synthetic-demo")
        result = example_result(task)
        atomic_json(Path(output) / (worker_id + ".json"), result)
        toolkit.submit(state["run_id"], worker_id, task["claim_token"], result)
    toolkit.assemble(state["run_id"])
    toolkit.render(state["run_id"])
    return wait(toolkit, state["run_id"])
