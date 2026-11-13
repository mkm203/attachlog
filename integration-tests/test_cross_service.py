"""End-to-end pytest: real placement + logbook + GraphQL BFF over HTTP.

Run from the repo root:
    .\\.venv\\Scripts\\python.exe -m pytest integration-tests -q

The three services are started as real uvicorn processes on free ports, each
with its own temporary SQLite database, so nothing is mocked. All HTTP calls
share one ``httpx.Client`` (reusing connections also keeps the run fast).
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SECRET = "integration-secret-integration-secret"
CLIENT_TIMEOUT = 60.0


@dataclass
class Stack:
    placement_url: str
    logbook_url: str
    bff_url: str
    token: Callable[[str, str], str]
    client: httpx.Client

    def headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_health(client: httpx.Client, url: str, log: Path, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if client.get(f"{url}/health", timeout=2.0).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    contents = log.read_text(errors="replace") if log.exists() else ""
    raise RuntimeError(f"{url} did not become healthy. Log:\n{contents[-4000:]}")


@pytest.fixture(scope="module")
def stack():
    tmp = Path(tempfile.mkdtemp(prefix="attachlog-e2e-"))
    placement_port, logbook_port, bff_port = _free_port(), _free_port(), _free_port()
    placement_url = f"http://127.0.0.1:{placement_port}"
    logbook_url = f"http://127.0.0.1:{logbook_port}"
    bff_url = f"http://127.0.0.1:{bff_port}"
    base_env = {**os.environ, "JWT_SECRET": SECRET, "PYTHONUNBUFFERED": "1"}
    specs = [
        ("placement", ROOT / "placement-service", placement_port,
         {**base_env, "DATABASE_URL": f"sqlite:///{(tmp / 'placement.db').as_posix()}",
          "TERM_START": "2026-09-01", "TERM_END": "2027-02-28"}),
        ("logbook", ROOT / "logbook-service", logbook_port,
         {**base_env, "DATABASE_URL": f"sqlite:///{(tmp / 'logbook.db').as_posix()}",
          "PLACEMENT_SERVICE_URL": placement_url}),
        ("bff", ROOT / "bff", bff_port,
         {**base_env, "PLACEMENT_SERVICE_URL": placement_url, "LOGBOOK_SERVICE_URL": logbook_url}),
    ]
    processes = []
    client = httpx.Client(timeout=CLIENT_TIMEOUT)
    try:
        for name, cwd, port, env in specs:
            log = tmp / f"{name}.log"
            handle = log.open("wb")
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                 "--port", str(port)],
                cwd=str(cwd), env=env, stdout=handle, stderr=subprocess.STDOUT)
            processes.append((process, handle, log))
        for name, _, port, _ in specs:
            _wait_health(client, f"http://127.0.0.1:{port}", tmp / f"{name}.log")

        def get_token(sub: str, role: str) -> str:
            response = client.post(f"{placement_url}/v1/auth/login",
                                   json={"username": sub, "password": f"Demo-{sub}-2026"}, timeout=10.0)
            assert response.status_code == 200, response.text
            assert response.json()["role"] == role
            return response.json()["access_token"]

        yield Stack(placement_url, logbook_url, bff_url, get_token, client)
    finally:
        client.close()
        for process, handle, _ in processes:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            handle.close()
        if os.getenv("ATTACHLOG_KEEP_E2E"):
            print(f"Keeping E2E logs in {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def test_rest_rules_and_graphql_flow(stack):
    client = stack.client
    coordinator = stack.token("co-1", "coordinator")
    student = stack.token("stu-1", "student")
    supervisor = stack.token("cs-1", "company_supervisor")
    other_supervisor = stack.token("cs-2", "company_supervisor")
    academic = stack.token("as-1", "academic_supervisor")

    # Reads need a token.
    assert client.get(f"{stack.placement_url}/v1/placements").status_code == 401

    placement = client.post(f"{stack.placement_url}/v1/placements",
                            headers=stack.headers(coordinator), json={
                                "student_id": "stu-1", "student_name": "Clarisse Ngo",
                                "company_name": "Douala Tech SARL", "company_city": "Douala",
                                "company_supervisor_id": "cs-1", "academic_supervisor_id": "as-1",
                                "start_date": "2026-09-07", "end_date": "2026-11-29",
                            })
    assert placement.status_code == 201, placement.text
    placement_id = placement.json()["id"]

    entry = client.post(f"{stack.logbook_url}/v1/placements/{placement_id}/entries",
                        headers=stack.headers(student),
                        json={"week": 1, "tasks": "Fixed bugs", "hours": 35})
    assert entry.status_code == 201, entry.text
    entry_id = entry.json()["id"]

    # Business rule: one entry per placement/week -> 409.
    duplicate = client.post(f"{stack.logbook_url}/v1/placements/{placement_id}/entries",
                            headers=stack.headers(student),
                            json={"week": 1, "tasks": "Again", "hours": 35})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "entry_exists"

    review = client.post(f"{stack.logbook_url}/v1/entries/{entry_id}/reviews",
                         headers=stack.headers(supervisor), json={"decision": "approved"})
    assert review.status_code == 201, review.text

    # Business rule: an approved entry is locked -> 409.
    locked = client.put(f"{stack.logbook_url}/v1/entries/{entry_id}",
                        headers=stack.headers(student), json={"tasks": "Changed", "hours": 10})
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "entry_locked"

    progress = client.get(f"{stack.logbook_url}/v1/placements/{placement_id}/progress",
                          headers=stack.headers(academic))
    assert progress.status_code == 200
    assert progress.json()["approved"] == 1 and progress.json()["completion_percent"] == 8.3

    # GraphQL query composes placement + progress + entries.
    query = """
    query Placement($id: ID!) {
      placement(id: $id) {
        student { name }
        company { name city }
        completionPercent
        entries(status: PENDING) { week hours status }
      }
    }
    """
    graph = client.post(f"{stack.bff_url}/graphql", headers=stack.headers(academic),
                        json={"query": query, "variables": {"id": placement_id}})
    assert graph.status_code == 200, graph.text
    data = graph.json()["data"]["placement"]
    assert data["student"]["name"] == "Clarisse Ngo"
    assert data["company"] == {"name": "Douala Tech SARL", "city": "Douala"}
    assert data["completionPercent"] == 8.3
    assert data["entries"] == []

    # A second entry is reviewed through the GraphQL mutation.
    second = client.post(f"{stack.logbook_url}/v1/placements/{placement_id}/entries",
                         headers=stack.headers(student),
                         json={"week": 2, "tasks": "Wrote tests", "hours": 40})
    assert second.status_code == 201, second.text
    second_id = second.json()["id"]
    mutation = """
    mutation Review($input: ReviewInput!) {
      reviewLogEntry(input: $input) { entry { status } errors { code message } }
    }
    """
    reviewed = client.post(f"{stack.bff_url}/graphql", headers=stack.headers(supervisor),
                           json={"query": mutation,
                                 "variables": {"input": {"entryId": second_id,
                                                         "decision": "APPROVED"}}})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["data"]["reviewLogEntry"] == {
        "entry": {"status": "APPROVED"}, "errors": []}

    # GraphQL denied access: no token, wrong role, and unassigned supervisor.
    no_token = client.post(f"{stack.bff_url}/graphql",
                           json={"query": query, "variables": {"id": placement_id}})
    assert no_token.status_code == 401
    assert no_token.json()["errors"][0]["extensions"]["code"] == "not_authenticated"

    wrong_role = client.post(f"{stack.bff_url}/graphql", headers=stack.headers(student),
                             json={"query": mutation,
                                   "variables": {"input": {"entryId": second_id,
                                                           "decision": "APPROVED"}}})
    assert wrong_role.status_code == 403
    assert wrong_role.json()["errors"][0]["extensions"]["code"] == "forbidden"

    third = client.post(f"{stack.logbook_url}/v1/placements/{placement_id}/entries",
                        headers=stack.headers(student),
                        json={"week": 3, "tasks": "Docs", "hours": 20})
    assert third.status_code == 201, third.text
    unassigned = client.post(f"{stack.bff_url}/graphql",
                             headers=stack.headers(other_supervisor),
                             json={"query": mutation,
                                   "variables": {"input": {"entryId": third.json()["id"],
                                                           "decision": "APPROVED"}}})
    assert unassigned.status_code == 403
    assert unassigned.json()["data"]["reviewLogEntry"]["errors"][0]["code"] == "not_assigned_supervisor"

    # Direct REST call outside GraphQL.
    direct = client.get(f"{stack.placement_url}/v1/placements/{placement_id}",
                        headers=stack.headers(academic))
    assert direct.status_code == 200 and direct.json()["id"] == placement_id
