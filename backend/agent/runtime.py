"""Backend A's single-process JSON store; seeds are never overwritten.

Share one RuntimeStore per FastAPI process. Read/write locking is in-process;
run one worker while using JSON. Selection transactions are future work.
"""
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from threading import RLock
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from ..models import Preference, Trip

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class RuntimeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    trip: Trip
    preferences: Preference


class RuntimeStorageError(Exception):
    """Invalid or unavailable storage; never silently reset user state."""


class RuntimeStore:
    def __init__(self, runtime_dir: Path | None = None, *, seed_dir: Path = DATA_DIR):
        self.seed_dir = Path(seed_dir)
        self.path = Path(runtime_dir or DATA_DIR / "runtime") / "state.json"
        self._lock = RLock()

    def load_state(self) -> RuntimeState:
        with self._lock:
            return self._read()

    def get_trip(self) -> Trip:
        return self.load_state().trip

    def get_preferences(self) -> Preference:
        return self.load_state().preferences

    def save_trip(self, trip: Trip) -> None:
        with self._lock:
            state = self._read()
            state.trip = trip
            self._write(state)

    def save_preferences(self, preferences: Preference) -> None:
        with self._lock:
            state = self._read()
            state.preferences = preferences
            self._write(state)

    def save_state(self, trip: Trip, preferences: Preference) -> None:
        """Persist a trusted trip/preferences pair together, not a selection API."""
        with self._lock:
            self._read()  # Refuse to overwrite a corrupt or unsupported state.
            self._write(RuntimeState(trip=trip, preferences=preferences))

    def update_state(
        self, update: Callable[[RuntimeState], RuntimeState],
    ) -> RuntimeState:
        """Atomically apply one validated state transition under the process lock."""
        with self._lock:
            current = self._read()
            candidate = update(current.model_copy(deep=True))
            try:
                validated = RuntimeState.model_validate(candidate.model_dump())
            except (AttributeError, ValidationError) as exc:
                raise RuntimeStorageError(
                    "Runtime JSON 更新結果格式不正確；既有資料未變更。",
                ) from exc
            self._write(validated)
            return validated.model_copy(deep=True)

    def _read(self) -> RuntimeState:
        try:
            try:
                contents = self.path.read_text(encoding="utf-8")
            except FileNotFoundError:
                state = RuntimeState(
                    trip=Trip.model_validate_json(
                        (self.seed_dir / "trip.json").read_text(encoding="utf-8")),
                    preferences=Preference.model_validate_json(
                        (self.seed_dir / "preferences.json").read_text(encoding="utf-8")),
                )
                self._write(state)
                return state
            return RuntimeState.model_validate_json(contents)
        except (OSError, ValueError, ValidationError) as exc:
            raise RuntimeStorageError("Runtime JSON 無法讀取或格式不正確；既有資料未重置。") from exc

    def _write(self, state: RuntimeState) -> None:
        temp_path = None
        try:
            # Revalidate nested values even if a caller mutated a model in place.
            payload = RuntimeState.model_validate(state.model_dump()).model_dump_json(indent=2)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=".state-", suffix=".tmp", delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(payload + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        except (OSError, ValueError, ValidationError) as exc:
            raise RuntimeStorageError("Runtime JSON 無法儲存；請檢查資料格式與目錄權限。") from exc
        finally:
            if temp_path is not None:
                # Cleanup must not mask a storage error or report a committed write as failed.
                with suppress(OSError):
                    temp_path.unlink(missing_ok=True)
