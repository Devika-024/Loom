import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# minimal .env loader (no extra dependency)
env = Path(__file__).parent / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import agent  # noqa: E402

app = FastAPI()
SESSIONS: dict[str, agent.Session] = {}


class Msg(BaseModel):
    session_id: str
    message: str


def get(sid: str) -> agent.Session:
    if sid not in SESSIONS:
        raise HTTPException(404, "unknown session")
    return SESSIONS[sid]


@app.post("/api/session")
def new_session():
    s = agent.Session()
    SESSIONS[s.id] = s
    return {"session_id": s.id, "reply": agent.WELCOME}


@app.post("/api/chat")
def chat(m: Msg):
    s = get(m.session_id)
    return {"reply": agent.chat(s, m.message), "graph": s.graph()}


@app.get("/api/findings/{sid}")
def findings(sid: str):
    return {"notes": agent.findings(get(sid))}


@app.get("/api/graph/{sid}")
def graph(sid: str):
    return get(sid).graph()


@app.post("/api/end/{sid}")
def end(sid: str):
    return agent.landscape(get(sid))


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
