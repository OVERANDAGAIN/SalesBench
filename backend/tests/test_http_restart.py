"""Actual localhost HTTP, two independent clients and a restarted Uvicorn process."""

from contextlib import contextmanager
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx

from salesbench_engine.actions import CreateListing, Procure, Purchase
from salesbench_engine.runner.codec import data

from helpers import request_for, setup_market


@contextmanager
def server(store, directory):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env["SALESBENCH_DATABASE_URL"] = store["url"]
    env["SALESBENCH_ADMIN_TOKEN"] = "integration-test-admin"
    env["SALESBENCH_AUTO_RUN"] = "1"
    logfile = Path(directory) / ("server-" + uuid4().hex + ".log")
    with logfile.open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--workers", "1"],
                                   cwd=Path(__file__).resolve().parents[1], env=env, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            url = f"http://127.0.0.1:{port}"
            for _ in range(100):
                assert process.poll() is None, "Test server exited; inspect its private log"
                try:
                    if httpx.get(url + "/health", timeout=0.5, trust_env=False).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.05)
            else:
                raise AssertionError("Test server did not become ready")
            yield url
        finally:
            process.terminate()  # Only the owned test server PID, never a port-wide kill.
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def wait_version(client, sid, version):
    for _ in range(150):
        response = client.get(f"/api/v1/sessions/{sid}/observation")
        assert response.status_code == 200, response.text
        observation = response.json()
        if observation["published_version"] >= version:
            return observation
        time.sleep(0.05)
    raise AssertionError("Publication did not progress")


def test_two_http_clients_restart_partial_wave_and_retry_unknown_purchase(store, tmp_path):
    sid = "http-" + uuid4().hex
    with server(store, tmp_path) as url:
        with httpx.Client(base_url=url, trust_env=False) as admin:
            response = admin.post("/api/v1/sessions", headers={"Authorization": "Bearer integration-test-admin"},
                                  json={"session_id": sid, "setup": data(setup_market()), "market_config": {"max_rounds": 1, "ticks_per_round": 1}})
            assert response.status_code == 200, response.text
            tokens = response.json()["actor_tokens"]
        with httpx.Client(base_url=url, headers={"Authorization": "Bearer " + tokens["seller"]}, trust_env=False) as seller:
            initial = seller.get(f"/api/v1/sessions/{sid}/observation").json()
            assert seller.post(f"/api/v1/sessions/{sid}/actions", json=request_for(initial, (Procure("cups", 1, 100),))).status_code == 202
            listing_obs = wait_version(seller, sid, 1)
            assert seller.post(f"/api/v1/sessions/{sid}/actions", json=request_for(listing_obs, (CreateListing("seller/cup", "cup", 300, "Cup"),))).status_code == 202
            wait_version(seller, sid, 2)
        with httpx.Client(base_url=url, headers={"Authorization": "Bearer " + tokens["buyer"]}, trust_env=False) as first, \
                httpx.Client(base_url=url, headers={"Authorization": "Bearer " + tokens["other-buyer"]}, trust_env=False) as second:
            first_obs = first.get(f"/api/v1/sessions/{sid}/observation").json()
            second_obs = second.get(f"/api/v1/sessions/{sid}/observation").json()
            assert first_obs["state"]["public"] == second_obs["state"]["public"]
            first_request = request_for(first_obs, (Purchase("seller/cup", 1, 300, 1),), "purchase-retry")
            second_request = request_for(second_obs, (Purchase("seller/cup", 1, 300, 1),), "purchase-second")
            assert first.post(f"/api/v1/sessions/{sid}/actions", json=first_request).status_code == 202
            assert first.get(f"/api/v1/sessions/{sid}/receipts/purchase-retry").json()["status"] == "pending"
            assert second.get(f"/api/v1/sessions/{sid}/observation").json()["published_version"] == 2
    # Old process is gone. Database, actor tokens and pending batch are the only handoff.
    with server(store, tmp_path) as url:
        with httpx.Client(base_url=url, headers={"Authorization": "Bearer " + tokens["buyer"]}, trust_env=False) as first, \
                httpx.Client(base_url=url, headers={"Authorization": "Bearer " + tokens["other-buyer"]}, trust_env=False) as second:
            pending = first.get(f"/api/v1/sessions/{sid}/receipts/purchase-retry").json()
            assert pending["status"] == "pending"
            assert first.post(f"/api/v1/sessions/{sid}/actions", json=first_request).json()["replayed"]
            assert second.post(f"/api/v1/sessions/{sid}/actions", json=second_request).status_code == 202
            a, b = wait_version(first, sid, 4), wait_version(second, sid, 4)
            assert a["runtime"]["status"] == b["runtime"]["status"] == "completed"
            assert a["runtime"]["engine_step"] == 1
            assert a["published_version"] == b["published_version"] == 4
            assert len(a["state"]["own"]["orders"]) + len(b["state"]["own"]["orders"]) == 1
            assert a["state"]["own"]["account"]["balance_cents"] + b["state"]["own"]["account"]["balance_cents"] == 1700
            duplicate = first.post(f"/api/v1/sessions/{sid}/actions", json=first_request).json()
            assert duplicate["replayed"] and duplicate["status"] != "pending"
            notices = first.get(f"/api/v1/sessions/{sid}/notifications", params={"after_version": 2}).json()["notices"]
            assert [n["published_version"] for n in notices] == [3, 4]
            assert all(set(n) == {"session_id", "published_version", "kind"} for n in notices)
    restored = store["service"].recover(sid)
    assert restored.published_version == 4
    assert len(restored.economic_state().orders) == 1
