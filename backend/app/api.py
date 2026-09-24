"""HTTP transport only. Identity binding and market operations use MarketService."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field
import secrets

from .service import MarketService, ServiceError
from .contracts import CreateSession, RotateBinding, SubmitBatch

router = APIRouter(prefix="/api/v1")
bearer = HTTPBearer(auto_error=False)


def service(request: Request) -> MarketService:
    if request.app.state.market_service is None:
        raise ServiceError("PLATFORM_NOT_CONFIGURED", 503)
    return request.app.state.market_service


def token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
    if credentials is None or len(credentials.credentials) > 512:
        raise ServiceError("AUTHENTICATION_REQUIRED", 401)
    return credentials.credentials


def admin(request: Request, supplied: Annotated[str, Depends(token)]):
    expected = request.app.state.admin_token
    if not expected or not secrets.compare_digest(expected.encode("utf-8"), supplied.encode("utf-8")):
        raise ServiceError("ADMIN_REQUIRED", 403)


@router.post("/sessions", dependencies=[Depends(admin)])
def create_session(body: CreateSession, market: Annotated[MarketService, Depends(service)]):
    return market.create(body.session_id, body.setup, body.market_config)


@router.post("/sessions/{session_id}/bindings/rotate", dependencies=[Depends(admin)])
def rotate(session_id: str, body: RotateBinding, market: Annotated[MarketService, Depends(service)]):
    return market.rotate_binding(session_id, body.actor_id)


@router.get("/sessions/{session_id}/observation")
def observation(session_id: str, supplied: Annotated[str, Depends(token)], market: Annotated[MarketService, Depends(service)]):
    return market.observe(session_id, supplied)


@router.get("/sessions/{session_id}/runtime")
def runtime(session_id: str, supplied: Annotated[str, Depends(token)], market: Annotated[MarketService, Depends(service)]):
    return market.runtime(session_id, supplied)


@router.post("/sessions/{session_id}/actions")
def actions(session_id: str, body: SubmitBatch, supplied: Annotated[str, Depends(token)], market: Annotated[MarketService, Depends(service)]):
    receipt = market.submit(session_id, supplied, body.model_dump())
    status = 202 if receipt["status"] == "pending" else (409 if receipt["status"] == "rejected" else 200)
    return JSONResponse(receipt, status_code=status)


@router.get("/sessions/{session_id}/receipts/{request_id}")
def receipt(session_id: str, request_id: str, supplied: Annotated[str, Depends(token)], market: Annotated[MarketService, Depends(service)]):
    return market.receipt(session_id, supplied, request_id)


@router.get("/sessions/{session_id}/notifications")
def notifications(session_id: str, supplied: Annotated[str, Depends(token)], market: Annotated[MarketService, Depends(service)],
                  after_version: Annotated[int, Field(ge=-1)] = -1):
    return market.notifications(session_id, supplied, after_version)


@router.post("/sessions/{session_id}/run", dependencies=[Depends(admin)])
def run_ready(session_id: str, market: Annotated[MarketService, Depends(service)]):
    return market.run_ready(session_id)
