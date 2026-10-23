import logging, os, time, uuid
from collections import defaultdict, deque
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from . import agent, db, services as S
from .models import AssessRequest

log = logging.getLogger("kisanmate")
app = FastAPI(title="KISANMATE", docs_url=None, redoc_url=None)
UPLOADS = Path(os.getenv("KISANMATE_UPLOADS", "uploads"))
_hits = defaultdict(deque)
LIMIT, WINDOW = 30, 60  # lightweight in-memory limit: 30 requests/min/IP (per instance)

@app.middleware("http")
async def limiter(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        q, t = _hits[request.client.host if request.client else "x"], time.time()
        while q and t - q[0] > WINDOW: q.popleft()
        if len(q) >= LIMIT:
            return JSONResponse({"error": "Too many requests. Please wait a minute."}, status_code=429)
        q.append(t)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'"
    return resp

@app.exception_handler(Exception)
async def safe_errors(request, exc):
    log.exception("unhandled")
    return JSONResponse({"error": "Something went wrong. Please try again."}, status_code=500)

@app.get("/api/health")
def health():
    return {"status": "ok", "ai": "configured" if S.ai_configured() else "demo-mode", "weather_provider": "open-meteo"}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read(S.MAX_IMG + 1)
    try: ext = S.validate_image(data, file.content_type or "")
    except ValueError as e: raise HTTPException(400, str(e))
    UPLOADS.mkdir(exist_ok=True)
    iid = uuid.uuid4().hex
    (UPLOADS / f"{iid}.{ext}").write_bytes(data)
    return {"image_id": iid, "note": "Stored locally on the server. Not sent to any AI or external service; photos cannot confirm a diagnosis."}

@app.post("/api/assess")
async def assess(req: AssessRequest):
    result = await agent.run(req)
    if result["status"] != "NEEDS_MORE_INFORMATION":
        result["id"] = db.save(req.profile.crop, result["status"], result)
    return result

@app.get("/api/history")
def history(): return db.list_all()

@app.get("/api/history/{item_id}")
def history_item(item_id: str):
    r = db.get(item_id)
    if not r: raise HTTPException(404, "Assessment not found.")
    return r

@app.delete("/api/history")
def clear_history():
    db.clear(); return {"cleared": True}

app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
