# Repository instructions

This is the standalone Agent Video Toolkit project. Read `README.md` and `docs/protocol.md` before changing public contracts. Do not assume another Studio/Core repository or runtime is available.

- The host owns model reasoning and may coordinate up to four equal-role workers over adjacent complete paragraphs. Each worker performs the complete picture job for its paragraphs.
- Keep execution local and model-free. Do not add hidden model, ASR, TTS, generated-asset or wallet calls.
- Preserve exact manuscript text, original global word timings, rational frame rate and complete frame count. Synthetic timing remains explicitly synthetic.
- Keep frozen input identities, content-addressed result history, claim ownership, CAS revisions, process locks and render idempotency. Do not replay failed or interrupted runs automatically.
- Preserve technical evidence separately from host aesthetic conclusions. Successful media verification keeps `quality_status=host_review_required`.
- Use isolated synthetic fixtures and a dedicated runtime for tests. Never inspect or copy unrelated user media, sessions, keys or private configuration into this repository.
- Do not vendor binaries or fonts without explicit licensing and distribution review. Record dependency changes in `THIRD_PARTY.md`.
- Run focused tests; media/Canvas/workflow changes need real integration tests with FFmpeg and Chromium. Report actual checks and their limits.
- Update public protocol and installation documentation when behavior changes. Version this project independently of other applications.
