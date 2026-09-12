import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agent.context import build_context
from .agent.explanation import explain_plan
from .agent.preference import get_preferences
from .agent.runtime import RuntimeStorageError, RuntimeStore
from .models import Preference, ReplanRequest, ReplanResponse, Trip
from .replanner.planner import candidate_plans

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")
app = FastAPI(title="SmartTrip Hackathon", version="0.1.0")
app.add_middleware(CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


_store = RuntimeStore()  # Constructing the shared store does not read or write files.


def get_store() -> RuntimeStore:
    return _store


@app.exception_handler(RuntimeStorageError)
async def storage_error(request: Request, exc: RuntimeStorageError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/trip", response_model=Trip)
def trip(store: RuntimeStore = Depends(get_store)) -> Trip:
    return store.get_trip()


@app.get("/api/preferences", response_model=Preference)
def preferences(store: RuntimeStore = Depends(get_store)) -> Preference:
    return get_preferences(store)


@app.post("/api/replan", response_model=ReplanResponse)
async def replan(
    request: ReplanRequest, store: RuntimeStore = Depends(get_store),
) -> ReplanResponse:
    context = await build_context(request, store)
    plans = candidate_plans(context.trip, event=context.event, weather=context.weather,
                            preferences=context.preferences, now=context.now)
    return ReplanResponse(
        event=context.event, weather=context.weather, preferences=context.preferences,
        plans=[explain_plan(plan) for plan in plans],
        warnings=context.weather.warnings + [
            "Placeholder：未呼叫 LLM；已取得天氣與偏好 context，但尚未套用於排程、評分或可行性驗證。",
        ],
    )
