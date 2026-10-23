# KISANMATE — evidence-aware, bounded AI farming assistant

**Status: code written and syntax-checked only. Tests were NOT run (the build sandbox had no network, so FastAPI could not be installed). Nothing has been deployed.**

## Run locally
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                      # run this first and fix anything that fails
cp .env.example .env           # optional: add a free LLM key
uvicorn app.main:app --reload  # open http://localhost:8000
```
## Free APIs
- **Weather:** Open-Meteo (free, no key, geocoding + 7-day forecast). On failure the app says so; it never invents a forecast. DEMO weather is opt-in and labelled.
- **AI (optional):** any free OpenAI-compatible provider, e.g. Groq or Google Gemini. Set `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` (see `.env.example`; check provider docs for current model names and free-tier limits). The AI only rewrites an already-verified plan in simple words. Without a key, the app shows a labelled DEMO summary.
## Design notes
- Agent: up to 3 follow-up questions, max 2 plan attempts, one revision. Diagnosis stays "possible, not confirmed".
- `verifier.py` is deterministic and separate from the AI (evidence basis, budget, chemicals, guarantees, source refs, weather status).
- Evidence panel holds **pointers** to ICAR/KVK/Soil Health/IMD. Their content is not fetched, and the UI says so. No pesticide doses or prices are invented.
- Security: validation, magic-byte image checks (4 MB), random filenames, in-memory rate limit (30/min/IP, per instance), no stack traces to users, CSP header, no code execution.
## Deploy free (not yet executed)
Push to GitHub → Render.com → New Web Service → use `render.yaml` → add `LLM_API_KEY` (optional). Note: free-tier disk is ephemeral, so SQLite history and uploads reset on redeploy or sleep.
## Known gaps
Single-page UI (profile, assessment, weather, plan, evidence and history are sections, not separate pages); Hindi/Marathi cover main labels only; no vision model; knowledge retrieval is static pointers, not live document retrieval; the demo scenario is the "Load soybean demo" button.
