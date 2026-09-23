import asyncio

import httpx

from app.main import app


def test_health_without_database_or_credentials():
    response = asyncio.run(request("GET", "/health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "scope": "api_process"}


def test_business_route_is_not_implemented():
    response = asyncio.run(request("POST", "/actions"))
    assert response.status_code == 404


async def request(method: str, path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.request(method, path)
