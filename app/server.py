"""FastAPI server for Conversation Sparring (Days 1-2).

Endpoints:
  POST /sessions                  create a session (no body needed)
  POST /sessions/{id}/messages   send one question, get the reply + score
  GET  /sessions/{id}            session state (turns, decisions, score)
  GET  /                         the single-page chat UI

The server uses only the scripted character, so it works with no API
key. It never imports or instantiates MetaSparkClient. State is
in-memory only: restarting the server drops all sessions.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.character import ScriptedCharacter
from app.graph import load_scenario
from app.session import Session

# Scenario path resolved relative to this file's package, not the CWD:
# app/server.py -> project root -> scenarios/teammate.json.
SCENARIO_PATH = Path(__file__).resolve().parent.parent / "scenarios" / "teammate.json"
STATIC_INDEX = Path(__file__).resolve().parent / "static" / "index.html"

_scenario = None


def get_scenario():
    """Load (once, cached) the scenario dict from SCENARIO_PATH."""
    global _scenario
    if _scenario is None:
        _scenario = load_scenario(SCENARIO_PATH)
    return _scenario


@asynccontextmanager
async def lifespan(app):
    # Load the scenario at startup; endpoints also lazy-load it via
    # get_scenario() so in-process TestClient use works without a
    # lifespan context manager.
    get_scenario()
    yield


app = FastAPI(lifespan=lifespan)

# One global scripted character instance; sessions are id -> Session.
character = ScriptedCharacter()
sessions = {}


class MessageIn(BaseModel):
    text: str


def _score(session):
    return {"revealed": session.score_count, "total": session.score_total}


def _score_display(session):
    score = _score(session)
    return f"{score['revealed']}/{score['total']}"


def _revealed_titles(session, nodes):
    """Titles of revealed nodes, in graph order (never full text)."""
    return [node["title"] for node in nodes if node["id"] in session.revealed]


def _get_session(session_id):
    session = sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="unknown session")
    return session


@app.post("/sessions")
def create_session():
    scenario = get_scenario()
    session = Session(scenario)
    session_id = uuid4().hex
    sessions[session_id] = session
    return {
        "id": session_id,
        "scenario_id": session.scenario_id,
        "title": scenario["title"],
        "character": {
            "name": scenario["character"]["name"],
            "opening_line": scenario["character"]["opening_line"],
        },
        "score": _score(session),
        "revealed_titles": [],
        "turns": [],
    }


@app.post("/sessions/{session_id}/messages")
def post_message(session_id: str, body: MessageIn):
    session = _get_session(session_id)
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")
    turn = session.add_turn(body.text)
    scenario = get_scenario()
    nodes_by_id = {node["id"]: node for node in scenario["nodes"]}
    # Build newly-revealed node dicts from the scenario nodes matching
    # the turn's ids. The character never receives unrevealed text.
    newly_revealed = [
        nodes_by_id[node_id]
        for node_id in turn["newly_revealed"]
        if node_id in nodes_by_id
    ]
    reply = character.respond(session.session_view(), body.text, newly_revealed)
    score = _score(session)
    return {
        "reply": reply,
        "question_type": turn["question_type"],
        "newly_revealed": [node["title"] for node in newly_revealed],
        "score": score,
        "score_display": f"{score['revealed']}/{score['total']}",
    }


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    session = _get_session(session_id)
    scenario = get_scenario()
    score = _score(session)
    return {
        "id": session_id,
        "scenario_id": session.scenario_id,
        "score": score,
        "score_display": f"{score['revealed']}/{score['total']}",
        "revealed_titles": _revealed_titles(session, scenario["nodes"]),
        "turns": session.turns,
        "decisions": session.decisions,
    }


@app.get("/")
def index():
    return FileResponse(STATIC_INDEX)
