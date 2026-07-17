# AGENTS.md

## Project
**Clawchive** — send media (video/image/audio) to the `openclaw` agent via Telegram/WhatsApp/Instagram,
`openclaw` scrapes it, captions/transcribes it, and indexes it for semantic search. Hackathon MVP,
optimized for shipping fast, not for scale or security hardening.

## Stack & pinned versions
- Python 3.12.x — do not move to 3.13 yet, several vision/ML deps still lag on 3.13 support.
- FastAPI >=0.115 + Pydantic v2 + Uvicorn.
- React 19 + TypeScript 5.6+, Vite. Deployed on Vercel.
- PostgreSQL 17 (managed: Neon or Supabase free tier) + pgvector 0.8.x, HNSW index, cosine distance.
- `yt-dlp` (pin a recent release, it moves fast) for video, `gallery-dl` for images.
- Gemini 2.5 Flash via `google-genai` SDK — default captioning/embedding backend.
- Moondream Cloud API — secondary adapter, OpenAI-compatible, no self-hosting needed for MVP.
- No Docker, no containers. Two deploy targets: Vercel (frontend + thin API) and one long-running
  worker process (Fly.io/Railway free tier, or a local machine for the demo).

## Architecture — 3 pieces, why they're split
1. `frontend/` — React+TS on Vercel. Search UI + media viewer. Talks only to `api/`.
2. `api/` — FastAPI on Vercel as Python serverless functions. Handles: platform webhook receivers
   (Telegram/WhatsApp/Instagram), the search endpoint (pgvector similarity query), CRUD reads.
   Every handler in here must return in a few seconds — no downloads, no model calls here.
3. `worker/` — a single always-running Python process, NOT deployed to Vercel. Polls a `jobs` table
   in Postgres and does everything slow: `yt-dlp`/`gallery-dl` download, subtitle extraction,
   captioning call, embedding, pgvector insert.

**Do not** try to run downloads or model inference inside the Vercel `api/` functions. Vercel Python
functions are stateless, ephemeral, have no persistent disk, and have a hard execution timeout —
that's incompatible with `yt-dlp` on a long video or any self-hosted model inference (vLLM in
particular needs a GPU and a long-lived process, neither of which Vercel provides). If a webhook
handler needs something slow done, it writes a row to `jobs` and returns immediately; `worker/`
picks it up.

## Commands
```
# frontend
cd frontend && npm install && npm run dev
cd frontend && npm run build && npm run lint

# api (local dev)
cd api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# worker (run this as a persistent process, not via Vercel)
cd worker && python main.py

# tests
pytest api/ worker/ -q
npm run test --prefix frontend
```

## Code style
- Python: follow the Google Python Style Guide. Type hints on every function signature, docstrings
  on public functions, no bare `except`, no mutable default arguments. Use `ruff` for lint+format.
- TypeScript: follow the Google TypeScript Style Guide. Strict mode on, no `any`, functional
  components only (no class components), props typed with explicit interfaces.
- Don't add abstractions "for later" — this is an MVP, prefer the direct solution.

## Media ingestion rules
- `yt-dlp`: always pass `--write-subs --write-auto-subs --sub-lang en` so subtitle text is captured
  alongside the video. If no subs exist, that's fine — fall back to the caption/transcription model.
- `gallery-dl`: used for image/carousel posts (Instagram). Store the original files, not thumbnails.
- English transcription only for now. Do not add translation or multi-language detection logic —
  that's explicitly out of scope until after the hackathon.

## Indexing / RAG
- Pipeline: extract text (subtitles or model caption) -> chunk -> embed -> `pgvector` HNSW index.
- Media descriptions may additionally be exported as OKF-formatted markdown blocks for portability
  (so the knowledge base isn't locked into this one vector index) — this is additive, it does not
  replace the pgvector RAG path.
- Build the HNSW index after a bulk insert, not row-by-row — rebuilding per insert is slow.

## Inference adapters
Keep a single interface so the model backend is swappable:
```python
class MediaDescriber(Protocol):
    def describe(self, media_path: str) -> MediaDescription: ...
```
- `GeminiFlashAdapter` — default, uses `gemini-2.5-flash` free tier.
- `MoondreamCloudAdapter` — fallback/alternate, hosted API, no local GPU needed.
- `MoondreamLocalAdapter` — stub only for now, behind an env flag; do not wire this up unless
  you actually have a GPU box, it's not for the Vercel-hosted parts of this project.
- Select via `INFERENCE_ADAPTER` env var. Do not hardcode a provider call anywhere outside `worker/inference/`.

## Known constraints — don't rediscover these mid-hackathon
- Gemini free tier is rate-limited (roughly 10 RPM, low hundreds of requests/day) — add retry with
  backoff in the worker, and don't fan out concurrent captioning calls.
- Vercel Python functions have a bundle size cap — never import `torch`/`transformers` inside `api/`,
  those only belong in `worker/`.
- `worker/` is the only place allowed to write to disk (for temp downloads) — clean up temp files
  after each job or the disk fills up over a long demo session.

## Security / scope for this MVP — explicitly deferred
- No `nemoclaw`, no per-user auth, no content moderation. Rely on each platform's own webhook
  verification token and nothing else.
- API keys and tokens live in env vars only, never committed, never logged.
- If asked to add auth/security hardening beyond webhook verification, flag it as future work
  instead of building it — it's out of scope for the hackathon submission.

## Commit / PR
- Small commits, one concern each. Conventional-ish prefixes (`feat:`, `fix:`, `worker:`, `api:`) are
  fine but not enforced.