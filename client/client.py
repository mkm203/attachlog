"""AttachLog demo client.

Runs:
  1. a GraphQL query (placement) with variables,
  2. a GraphQL mutation (reviewLogEntry) with variables,
  3. one direct REST call outside GraphQL.

With no --placement-id / --entry-id it seeds a fresh placement and week-1 entry
through the REST API first, so it can be run repeatedly against a local stack.
"""
import argparse
import json
import sys

import httpx

PLACEMENT_QUERY = """
query Placement($id: ID!) {
  placement(id: $id) {
    id
    student { name }
    company { name city }
    totalWeeks
    completionPercent
    entries(status: PENDING) { week hours status }
  }
}
"""

REVIEW_MUTATION = """
mutation Review($input: ReviewInput!) {
  reviewLogEntry(input: $input) {
    entry { id week status }
    errors { code message }
  }
}
"""


TIMEOUT = 30.0
_http: httpx.Client | None = None


class ClientError(Exception):
    pass


def http() -> httpx.Client:
    """One pooled client for the whole run (keeps the demo fast)."""
    global _http
    if _http is None:
        _http = httpx.Client(timeout=TIMEOUT)
    return _http


def rest(method: str, url: str, token: str | None = None, **kwargs):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = http().request(method, url, headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        raise ClientError(f"Cannot reach {url}: {exc}") from exc
    if response.status_code >= 400:
        try:
            error = response.json()["error"]
            raise ClientError(f"{error['code']}: {error['message']} (HTTP {response.status_code})")
        except (ValueError, KeyError, TypeError):
            raise ClientError(f"HTTP {response.status_code} from {url}: {response.text[:300]}")
    return response.json()


def graphql(url: str, query: str, variables: dict, token: str) -> dict:
    try:
        response = http().post(url, json={"query": query, "variables": variables},
                               headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        raise ClientError(f"Cannot reach {url}: {exc}") from exc
    try:
        body = response.json()
    except ValueError as exc:
        raise ClientError(f"HTTP {response.status_code} from {url}: {response.text[:300]}") from exc
    if body.get("errors"):
        messages = "; ".join(
            f"{e.get('extensions', {}).get('code', 'graphql_error')}: {e.get('message', '')}"
            for e in body["errors"])
        raise ClientError(f"GraphQL error(s) (HTTP {response.status_code}): {messages}")
    if response.status_code >= 400:
        raise ClientError(f"HTTP {response.status_code} from {url}")
    return body["data"]

# Synthetic demo accounts (see the README). They protect no real data.
DEMO_PASSWORDS = {uid: f"Demo-{uid}-2026" for uid in ("stu-1", "stu-2", "cs-1", "cs-2", "as-1", "co-1")}


def token(base_url: str, username: str, role: str) -> str:
    """Log in with the demo password and check that the account has the role we expect."""
    body = rest("POST", f"{base_url}/v1/auth/login",
                json={"username": username, "password": DEMO_PASSWORDS[username]})
    if body["role"] != role:
        raise ClientError(f"{username} logged in as {body['role']}, expected {role}")
    return body["access_token"]

def seed(client: argparse.Namespace, placement_url: str) -> tuple[str, str]:
    coordinator = token(placement_url, "co-1", "coordinator")
    placement = rest("POST", f"{placement_url}/v1/placements", coordinator, json={
        "student_id": "stu-1", "student_name": "Clarisse Ngo",
        "company_name": "Douala Tech SARL", "company_city": "Douala",
        "company_supervisor_id": "cs-1", "academic_supervisor_id": "as-1",
        "start_date": "2026-09-07", "end_date": "2026-11-29",
    })
    placement_id = placement["id"]
    print(f"Seeded placement {placement_id} ({placement['total_weeks']} weeks)")

    student = token(placement_url, "stu-1", "student")
    entry = rest("POST", f"{client.logbook_url}/v1/placements/{placement_id}/entries", student, json={
        "week": 1, "tasks": "Set up the dev environment and fixed two bugs.", "hours": 35,
    })
    print(f"Seeded entry {entry['id']} (week 1)")
    return placement_id, entry["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description="AttachLog GraphQL + REST demo client")
    parser.add_argument("--placement-url", default="http://localhost:8001")
    parser.add_argument("--logbook-url", default="http://localhost:8002")
    parser.add_argument("--graphql-url", default="http://localhost:8003/graphql")
    parser.add_argument("--placement-id")
    parser.add_argument("--entry-id")
    parser.add_argument("--decision", choices=("approved", "rejected"), default="approved")
    parser.add_argument("--comment", default=None)
    args = parser.parse_args()

    placement_id = args.placement_id
    entry_id = args.entry_id
    if not placement_id or not entry_id:
        placement_id, entry_id = seed(args, args.placement_url)

    academic = token(args.placement_url, "as-1", "academic_supervisor")
    print("\n1) GraphQL query: placement")
    data = graphql(args.graphql_url, PLACEMENT_QUERY, {"id": placement_id}, academic)
    print(json.dumps(data, indent=2))

    comment = args.comment
    if args.decision == "rejected" and not comment:
        comment = "Please add more detail about the tasks."
    supervisor = token(args.placement_url, "cs-1", "company_supervisor")
    print("\n2) GraphQL mutation: reviewLogEntry")
    data = graphql(args.graphql_url, REVIEW_MUTATION,
                   {"input": {"entryId": entry_id, "decision": args.decision.upper(), "comment": comment}},
                   supervisor)
    print(json.dumps(data, indent=2))
    if data["reviewLogEntry"]["errors"]:
        raise ClientError(f"Review failed: {data['reviewLogEntry']['errors']}")

    print("\n3) Direct REST call: GET /v1/placements/{id}")
    placement = rest("GET", f"{args.placement_url}/v1/placements/{placement_id}", academic)
    print(json.dumps(placement, indent=2))
    print("\nAll three calls succeeded.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ClientError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        if _http is not None:
            _http.close()
