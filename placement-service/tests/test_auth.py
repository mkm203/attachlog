import jwt
import pytest

from app import config
from app.users import USERS

PASSWORDS = {uid: f"Demo-{uid}-2026" for uid in USERS}


def login(client, username, password):
    return client.post("/v1/auth/login", json={"username": username, "password": password})


@pytest.mark.parametrize("username", sorted(USERS))
def test_every_demo_user_can_log_in_with_the_right_role(client, username):
    r = login(client, username, PASSWORDS[username])
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["sub"] == username
    assert body["role"] == USERS[username].role and body["name"] == USERS[username].name
    assert body["expires_in"] == config.jwt_ttl_minutes() * 60
    claims = jwt.decode(body["access_token"], config.jwt_secret(), algorithms=["HS256"])
    assert claims["sub"] == username and claims["role"] == USERS[username].role
    assert claims["exp"] > claims["iat"]


def test_token_from_login_opens_the_api(client):
    token = login(client, "co-1", PASSWORDS["co-1"]).json()["access_token"]
    assert client.get("/v1/placements", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_wrong_password_is_401(client):
    r = login(client, "co-1", "not-the-password")
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_credentials"


def test_unknown_user_gets_the_same_answer_as_a_wrong_password(client):
    unknown = login(client, "nobody", "whatever")
    wrong = login(client, "co-1", "whatever")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_a_caller_cannot_choose_their_own_role(client):
    r = client.post("/v1/auth/login", json={"username": "stu-1", "password": PASSWORDS["stu-1"], "role": "coordinator"})
    assert r.status_code == 200 and r.json()["role"] == "student"


def test_the_old_open_token_endpoint_is_gone(client):
    r = client.post("/v1/auth/token", json={"sub": "co-1", "role": "coordinator"})
    assert r.status_code in (404, 405)


def test_missing_or_empty_fields_are_422(client):
    assert client.post("/v1/auth/login", json={"username": "co-1"}).status_code == 422
    assert client.post("/v1/auth/login", json={"username": "", "password": "x"}).status_code == 422


def test_passwords_are_stored_only_as_hashes():
    for user in USERS.values():
        assert PASSWORDS[user.username] not in (user.password_hash, user.salt)
        assert len(user.password_hash) == 64