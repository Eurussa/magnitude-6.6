import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agent.context import build_context
from .agent.explanation import explain_plan
from .agent.preference import get_preferences, preference_insight
from .agent.runtime import RuntimeStorageError, RuntimeStore
from .agent.selection import (
    SelectionConflictError,
    SelectionNotFoundError,
    apply_selection,
)
from .contracts import Replanner
from .models import (
    ErrorResponse,
    HealthResponse,
    Preference,
    ReplanRequest,
    ReplanResponse,
    ReplanSnapshot,
    SelectionRequest,
    SelectionResponse,
    Trip,
)
from .replanner.planner import candidate_plans

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")
app = FastAPI(title="SmartTrip Hackathon", version="0.1.0")
app.add_middleware(CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


_store = RuntimeStore()  # Constructing the shared store does not read or write files.
_replanner: Replanner | None = None


def get_store() -> RuntimeStore:
    return _store


def get_replanner() -> Replanner | None:
    """Return B's configured implementation; None keeps the safe placeholder path."""
    return _replanner


@app.exception_handler(RuntimeStorageError)
async def storage_error(request: Request, exc: RuntimeStorageError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


STORAGE_ERROR_RESPONSE = {
    503: {"model": ErrorResponse, "description": "Runtime storage unavailable"},
}


@app.get("/api/trip", response_model=Trip, responses=STORAGE_ERROR_RESPONSE)
def trip(store: RuntimeStore = Depends(get_store)) -> Trip:
    return store.get_trip()


@app.get("/api/preferences", response_model=Preference, responses=STORAGE_ERROR_RESPONSE)
def preferences(store: RuntimeStore = Depends(get_store)) -> Preference:
    return get_preferences(store)


@app.post("/api/replan", response_model=ReplanResponse, responses=STORAGE_ERROR_RESPONSE)
async def replan(
    request: ReplanRequest,
    store: RuntimeStore = Depends(get_store),
    replanner: Replanner | None = Depends(get_replanner),
) -> ReplanResponse:
    context = await build_context(request, store)
    if replanner is not None:
        result = await replanner.generate_plans(context)
        plans = [explain_plan(plan) for plan in result.plans]
        replan_id = uuid4()
        snapshot = ReplanSnapshot(
            replan_id=replan_id,
            trip_id=context.trip.id,
            trip_version=context.trip.version,
            planning_source=result.source,
            plans=plans,
            recommended_plan_id=result.recommended_plan_id,
            created_at=datetime.now(timezone.utc),
        )
        store.save_replan_snapshot(snapshot)
        recommended = next(
            (plan for plan in plans if plan.id == result.recommended_plan_id),
            None,
        )
        return ReplanResponse(
            status="ready",
            replan_id=replan_id,
            planning_source=result.source,
            event=context.event,
            weather=context.weather,
            preferences=context.preferences,
            plans=plans,
            recommended_plan_id=result.recommended_plan_id,
            preference_insight=preference_insight(
                context.preferences,
                recommended.strategy if recommended is not None else None,
            ),
            warnings=context.weather.warnings + result.warnings,
        )

    plans = candidate_plans(context.trip, event=context.event, weather=context.weather,
                            preferences=context.preferences, now=context.now)
    return ReplanResponse(
        status="placeholder",
        replan_id=None,
        planning_source="unavailable",
        event=context.event, weather=context.weather, preferences=context.preferences,
        plans=[explain_plan(plan) for plan in plans],
        recommended_plan_id=None,
        preference_insight=None,
        warnings=context.weather.warnings + [
            "Placeholder：事件已由離線 parser 解析並取得天氣與偏好 context；"
            "尚未接通重排實作，"
            "但尚未套用於排程、評分或可行性驗證。",
        ],
    )


@app.post(
    "/api/selections",
    response_model=SelectionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Replan snapshot or plan not found"},
        409: {
            "model": ErrorResponse,
            "description": "Selection conflict, infeasible plan, or stale trip",
        },
        **STORAGE_ERROR_RESPONSE,
    },
)
def select_plan(
    selection: SelectionRequest,
    store: RuntimeStore = Depends(get_store),
) -> SelectionResponse:
    try:
        return apply_selection(store, selection)
    except SelectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SelectionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
