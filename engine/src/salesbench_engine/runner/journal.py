"""Host-private audit journal and single-process, locked action deduplication."""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
from threading import RLock

from ..environment import Engine
from .codec import action_data, data, digest


def source_digest() -> str:
    root = Path(__file__).resolve().parents[1]
    return digest({p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in sorted(root.rglob("*.py"))})


class Journal:
    def __init__(self):
        self._records: list[dict] = []

    @property
    def records(self) -> list[dict]:
        return deepcopy(self._records)

    def append(self, kind: str, **payload) -> None:
        self._records.append({"seq": len(self._records), "kind": kind,
                              "recorded_at": datetime.now(timezone.utc).isoformat(), **deepcopy(data(payload))})

    def write(self, path: str | Path) -> None:
        # Explicit path only. Contains participant-private data and raw outputs.
        Path(path).write_text(json.dumps(self.records, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


class IdempotencyConflict(ValueError):
    pass


class ExecutionFault(RuntimeError):
    def __init__(self, action_id: str, code: str):
        self.action_id = action_id
        self.code = code
        super().__init__(code)


class ActionExecutor:
    """Trusted Runner component; not an actor API or a durable transaction log."""

    def __init__(self, engine: Engine, journal: Journal):
        self._engine = engine
        self._journal = journal
        self._cache = {}
        self._lock = RLock()
        self._fault: ExecutionFault | None = None
        # Replay may stop before a recorded implementation fault to audit prefix.
        self._replay_faults: dict[str, str] = {}

    def execute(self, action_id: str, actor_id: str, context, action):
        body = {"actor_id": actor_id, "context": data(context), "action": action_data(action)}
        fingerprint = digest(body)
        with self._lock:
            if action_id in self._cache:
                prior_fingerprint, result = self._cache[action_id]
                if prior_fingerprint != fingerprint:
                    raise IdempotencyConflict("ACTION_ID_CONFLICT")
                return result
            if self._fault:
                raise self._fault
            before = data(self._engine.snapshot())
            self._journal.append("action_attempt", action_id=action_id, **body)
            try:
                if action_id in self._replay_faults:
                    raise ExecutionFault(action_id, self._replay_faults[action_id])
                result = self._engine.execute(actor_id, action)
            except Exception as error:
                code = error.code if isinstance(error, ExecutionFault) else type(error).__name__
                self._fault = ExecutionFault(action_id, code)
                self._journal.append("execution_fault", action_id=action_id, code=code,
                                     state_digest=digest(self._engine.snapshot()))
                raise self._fault from None
            # Save before journaling: never re-execute a committed action if logging fails.
            self._cache[action_id] = (fingerprint, result)
            after = data(self._engine.snapshot())
            self._journal.append("action_result", action_id=action_id, result=result,
                                 state_digest=digest(after), changes={k: after[k] for k in after if before[k] != after[k]})
            return result
