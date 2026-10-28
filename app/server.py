"""FastAPI server for Conversation Sparring (Days 1-2).

Endpoints:
  POST /sessions                  create a session (no body needed)
  POST /sessions/{id}/messages   send one question, get the reply + score
  GET  /sessions/{id}            session state (turns, decisions, score)
  GET  /                         the single-page chat UI
  POST /sessions/{id}/branches  fork a new branch (becomes active)
  GET  /sessions/{id}/branches  branch tree with per-branch scores

By default the server uses the scripted character and RuleCoach, so it
works with no API key. When BOTH META_MODEL_API_KEY and
META_MODEL_API_BASE are set it switches to MetaSparkClient and
SparkCoach (CS-6 live wiring). Partial config stays scripted.
All state is process-local: restarting the server drops all sessions.
See README.md for the live-model setup.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.character import MetaSparkClient, ScriptedCharacter
from app.coach import RuleCoach, SparkCoach
from app.graph import load_scenario
from app.portrait import portrait_payload
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
    # Only this server's working directory; never search other worktrees.
    # Shell configuration wins. Missing .env is a normal scripted startup.
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)
    # Load the scenario at startup; endpoints also lazy-load it via
    # get_scenario() so in-process TestClient use works without a
    # lifespan context manager.
    get_scenario()
    yield


app = FastAPI(lifespan=lifespan)

# Default (no-key) instances. get_character()/get_coach() select the live
# Meta Spark pair instead when both env vars are present (CS-6).
# Sessions are id -> Session.
character = ScriptedCharacter()
# Day 3/4 (CS-2): the default rule-based coach. It works with no API
# key and no network (CS-6 selects SparkCoach when configured).
coach = RuleCoach()
sessions = {}
# CS-C43: RuleCoach rotation is per-instance state, so each session gets
# its own RuleCoach. Sharing the module-global coach leaked rotation
# across sessions.
session_coaches = {}


def _live_model_configured():
    """True only when BOTH the key and base URL env vars are set."""
    return bool(os.environ.get("META_MODEL_API_KEY")) and bool(
        os.environ.get("META_MODEL_API_BASE")
    )


def get_character():
    """Active character agent: live Meta Spark iff configured (CS-6)."""
    if _live_model_configured():
        return MetaSparkClient()
    return character


def get_coach():
    """Active coach: SparkCoach iff live model configured, else RuleCoach."""
    if _live_model_configured():
        return SparkCoach()
    return coach


def get_session_coach(session_id: str):
    """Coach for one session (CS-C43): SparkCoach iff live configured
    (stateless, safe to mint per call), else that session's own
    RuleCoach so meaning rotation never leaks across sessions."""
    if _live_model_configured():
        return SparkCoach()
    coach = session_coaches.get(session_id)
    if coach is None:
        coach = session_coaches[session_id] = RuleCoach()
    return coach


class MessageIn(BaseModel):
    text: str
    branch_id: str | None = None


class BranchIn(BaseModel):
    from_turn: int
    from_branch_id: str | None = None


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
    if body.branch_id is not None:
        try:
            session.set_active_branch(body.branch_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown branch")
    turn = session.add_turn(body.text, coach=get_session_coach(session_id))
    scenario = get_scenario()
    nodes_by_id = {node["id"]: node for node in scenario["nodes"]}
    # Build newly-revealed node dicts from the scenario nodes matching
    # the turn's ids. The character never receives unrevealed text.
    newly_revealed = [
        nodes_by_id[node_id]
        for node_id in turn["newly_revealed"]
        if node_id in nodes_by_id
    ]
    reply = get_character().respond(
        session.session_view(), body.text, newly_revealed
    )
    score = _score(session)
    return {
        "reply": reply,
        "question_type": turn["question_type"],
        "newly_revealed": [node["title"] for node in newly_revealed],
        "coach_whisper": turn["coach_whisper"],
        "branch_id": session.active_branch_id,
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
        "branches": session.branch_summaries(),
        "active_branch_id": session.active_branch_id,
    }


@app.post("/sessions/{session_id}/branches")
def create_branch(session_id: str, body: BranchIn):
    session = _get_session(session_id)
    try:
        branch_id = session.create_branch(
            from_turn=body.from_turn, from_branch_id=body.from_branch_id
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown branch")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "branch": session.branches[branch_id].summary(session.score_total),
        "active_branch_id": session.active_branch_id,
    }


@app.get("/sessions/{session_id}/branches")
def list_branches(session_id: str):
    session = _get_session(session_id)
    return {
        "branches": session.branch_summaries(),
        "active_branch_id": session.active_branch_id,
    }


@app.get("/sessions/{session_id}/portrait")
def get_portrait(session_id: str, branch_id: str | None = None):
    session = _get_session(session_id)
    if branch_id is None:
        return portrait_payload(session.score_count, session.score_total)
    try:
        branch = session.branches[branch_id]
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown branch")
    return portrait_payload(branch.score_count, session.score_total)


@app.get("/")
def index():
    return FileResponse(STATIC_INDEX)
