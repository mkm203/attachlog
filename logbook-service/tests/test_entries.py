from tests.conftest import OTHER_STUDENT, STUDENT, SUPERVISOR, COORDINATOR, submit


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "logbook"}


def test_student_submits_an_entry(client):
    r = submit(client)
    assert r.status_code == 201
    assert r.json()["status"] == "pending" and r.json()["week"] == 1 and r.json()["student_id"] == "stu-1"


# --- business rule 1: one entry per student per week -> 409
def test_second_entry_for_the_same_week_is_409(client):
    assert submit(client, week=2).status_code == 201
    r = submit(client, week=2)
    assert r.status_code == 409 and r.json()["error"]["code"] == "entry_exists"


def test_same_week_in_another_placement_is_allowed(client):
    assert submit(client, week=1, placement="P1").status_code == 201
    assert submit(client, week=1, placement="P2", headers=OTHER_STUDENT).status_code == 201


def test_week_beyond_the_placement_is_422(client):
    r = submit(client, week=5)
    assert r.status_code == 422 and r.json()["error"]["code"] == "week_out_of_range"


def test_invalid_hours_and_missing_fields_are_422(client):
    assert submit(client, hours=0).status_code == 422
    assert submit(client, hours=100).status_code == 422
    r = client.post("/v1/placements/P1/entries", json={"week": 1}, headers=STUDENT)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_unknown_placement_is_404(client):
    assert submit(client, placement="nope").status_code == 404


def test_cannot_write_in_someone_elses_placement(client):
    r = submit(client, placement="P2")
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_your_placement"


def test_closed_placement_refuses_entries(client):
    r = submit(client, placement="P3")
    assert r.status_code == 409 and r.json()["error"]["code"] == "placement_closed"


def test_student_edits_a_pending_entry(client):
    eid = submit(client).json()["id"]
    r = client.put(f"/v1/entries/{eid}", json={"tasks": "Better description", "hours": 40}, headers=STUDENT)
    assert r.status_code == 200 and r.json()["tasks"] == "Better description" and r.json()["hours"] == 40


def test_another_student_cannot_edit(client):
    eid = submit(client).json()["id"]
    assert client.put(f"/v1/entries/{eid}", json={"tasks": "x", "hours": 1}, headers=OTHER_STUDENT).status_code == 403


def test_get_entry_and_404(client):
    eid = submit(client).json()["id"]
    assert client.get(f"/v1/entries/{eid}", headers=STUDENT).json()["id"] == eid
    assert client.get(f"/v1/entries/{eid}", headers=OTHER_STUDENT).status_code == 403
    r = client.get("/v1/entries/nope", headers=STUDENT)
    assert r.status_code == 404 and r.json()["error"]["code"] == "entry_not_found"


def test_list_filters_and_pagination(client):
    for week in (1, 2, 3):
        submit(client, week=week)
    submit(client, week=1, placement="P2", headers=OTHER_STUDENT)
    page = client.get("/v1/entries?placementId=P1&status=pending&page=1&page_size=2", headers=SUPERVISOR).json()
    assert page["total"] == 3 and len(page["items"]) == 2 and page["items"][0]["week"] == 1
    assert client.get("/v1/entries?placementId=P1&status=approved", headers=SUPERVISOR).json()["total"] == 0
    assert client.get("/v1/entries", headers=COORDINATOR).json()["total"] == 4
    # a student only ever sees their own entries
    assert client.get("/v1/entries", headers=STUDENT).json()["total"] == 3
    assert client.get("/v1/entries?status=bogus", headers=STUDENT).status_code == 422
    assert client.get("/v1/entries?page_size=500", headers=STUDENT).status_code == 422