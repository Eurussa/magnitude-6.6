import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent.parser import parse_event
from .models import ReplanRequest, ReplanResponse, Trip
from .replanner.planner import candidate_plans

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")
app = FastAPI(title="SmartTrip Hackathon", version="0.1.0")
app.add_middleware(CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


def load_trip() -> Trip:
    return Trip.model_validate(json.loads((ROOT / "data/trip.json").read_text()))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/trip", response_model=Trip)
def trip() -> Trip:
    return load_trip()


@app.post("/api/replan", response_model=ReplanResponse)
def replan(request: ReplanRequest) -> ReplanResponse:
    return ReplanResponse(event=parse_event(request.message),
        plans=candidate_plans(load_trip()),
        warnings=["Placeholder：未呼叫 LLM、未套用天氣、未驗證可行性，不能當作實際重排結果。"])
