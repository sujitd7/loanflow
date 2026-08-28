from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time

from app.config import settings
from app.errors import Unauthorized
from app.models.user import Role, Team, User
from app.security import create_access_token, decode_token, hash_password
from app.services import auth as auth_service
from tests.conftest import TestingSessionLocal

# --- login ---------------------------------------------------------------


def test_login_success_returns_token_pair(client: TestClient, make_user) -> None:
    user = make_user(Role.UW_MAKER, password="s3cret")

    resp = client.post("/auth/login", json={"email": user.email, "password": "s3cret"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    access = decode_token(body["access_token"], "access")
    assert access["sub"] == str(user.id)
    assert access["role"] == Role.UW_MAKER.value
    decode_token(body["refresh_token"], "refresh")


def test_login_wrong_password_is_401(client: TestClient, make_user) -> None:
    user = make_user(password="right")
    resp = client.post("/auth/login", json={"email": user.email, "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_email_is_401(client: TestClient) -> None:
    resp = client.post("/auth/login", json={"email": "nobody@loanflow.dev", "password": "x"})
    assert resp.status_code == 401


def test_login_inactive_user_is_401(client: TestClient, make_user) -> None:
    user = make_user(password="pw", is_active=False)
    resp = client.post("/auth/login", json={"email": user.email, "password": "pw"})
    assert resp.status_code == 401


def test_login_rejects_malformed_email(client: TestClient) -> None:
    resp = client.post("/auth/login", json={"email": "not-an-email", "password": "x"})
    assert resp.status_code == 422


# --- /auth/me ----------------------------------------------------------


def test_me_returns_current_user(client: TestClient, make_user, token_headers) -> None:
    user = make_user(Role.ADMIN)
    resp = client.get("/auth/me", headers=token_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": Role.ADMIN.value,
        "team": None,
    }


def test_me_without_token_is_401(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401


def test_me_with_malformed_token_is_401(client: TestClient) -> None:
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


def test_me_with_expired_token_is_401(client: TestClient, make_user) -> None:
    user = make_user()
    with freeze_time(datetime.now(UTC) - timedelta(hours=2)):
        stale = create_access_token(user.id, user.role.value)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {stale}"})
    assert resp.status_code == 401


def test_me_rejects_refresh_token_as_access(client: TestClient, make_user) -> None:
    user = make_user()
    login = client.post("/auth/login", json={"email": user.email, "password": "pw"})
    refresh = login.json()["refresh_token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 401


# --- refresh rotation ------------------------------------------------


def _login(client: TestClient, email: str, password: str = "pw") -> dict[str, str]:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()


def test_refresh_rotates_tokens(client: TestClient, make_user) -> None:
    user = make_user()
    first = _login(client, user.email)

    rotated = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert rotated.status_code == 200
    new_pair = rotated.json()
    assert new_pair["refresh_token"] != first["refresh_token"]

    # the old refresh token no longer works
    replay = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401


def test_refresh_reuse_burns_the_whole_family(client: TestClient, make_user) -> None:
    user = make_user()
    first = _login(client, user.email)
    second = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).json()

    # replay the already-rotated token -> reuse detected
    assert (
        client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code
        == 401
    )
    # ...and the token that was still valid is now dead too
    assert (
        client.post("/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code
        == 401
    )


def test_refresh_reuse_burn_is_committed_before_the_401() -> None:
    """The family revocation must survive the request rollback that the 401
    triggers — so it runs in its own committed unit of work. Exercised here with
    real per-request sessions rather than the shared test session."""
    with TestingSessionLocal() as setup:
        user = User(
            email="reuse@loanflow.dev",
            full_name="Reuse Probe",
            password_hash=hash_password("pw"),
            role=Role.UW_MAKER,
            team=Team.UW,
        )
        setup.add(user)
        setup.commit()
        first = auth_service.issue_pair(setup, user)
        setup.commit()

    with TestingSessionLocal() as s:
        second = auth_service.rotate(s, first.refresh_token)
        s.commit()

    with TestingSessionLocal() as s:  # attacker replays the rotated-away token
        with pytest.raises(Unauthorized):
            auth_service.rotate(s, first.refresh_token)
        s.rollback()  # mimic get_db on the raised exception

    # the still-"valid" token is now dead too
    with TestingSessionLocal() as s, pytest.raises(Unauthorized):
        auth_service.rotate(s, second.refresh_token)


def test_refresh_rejects_access_token(client: TestClient, make_user) -> None:
    user = make_user()
    access = _login(client, user.email)["access_token"]
    resp = client.post("/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401


def test_refresh_rejects_expired_token(client: TestClient, make_user) -> None:
    user = make_user()
    with freeze_time(datetime.now(UTC) - timedelta(days=settings.jwt_refresh_ttl_days + 1)):
        stale = _login(client, user.email)["refresh_token"]
    resp = client.post("/auth/refresh", json={"refresh_token": stale})
    assert resp.status_code == 401


def test_refresh_rejects_garbage(client: TestClient) -> None:
    resp = client.post("/auth/refresh", json={"refresh_token": "nonsense"})
    assert resp.status_code == 401


# --- logout ----------------------------------------------------------


def test_logout_revokes_refresh_token(client: TestClient, make_user) -> None:
    user = make_user()
    pair = _login(client, user.email)
    auth = {"Authorization": f"Bearer {pair['access_token']}"}

    assert (
        client.post(
            "/auth/logout", json={"refresh_token": pair["refresh_token"]}, headers=auth
        ).status_code
        == 204
    )
    assert (
        client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code
        == 401
    )


def test_logout_requires_authentication(client: TestClient, make_user) -> None:
    user = make_user()
    pair = _login(client, user.email)
    resp = client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]})
    assert resp.status_code == 401


def test_logout_will_not_revoke_another_users_token(
    client: TestClient, make_user, token_headers
) -> None:
    victim = make_user()
    victim_pair = _login(client, victim.email)
    attacker = make_user()

    resp = client.post(
        "/auth/logout",
        json={"refresh_token": victim_pair["refresh_token"]},
        headers=token_headers(attacker),
    )
    assert resp.status_code == 204  # silent no-op
    # the victim's token still works
    assert (
        client.post(
            "/auth/refresh", json={"refresh_token": victim_pair["refresh_token"]}
        ).status_code
        == 200
    )


def test_logout_is_idempotent_for_unknown_token(
    client: TestClient, make_user, token_headers
) -> None:
    user = make_user()
    fake = jwt.encode(
        {"sub": str(user.id), "type": "refresh", "jti": "deadbeef"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    resp = client.post("/auth/logout", json={"refresh_token": fake}, headers=token_headers(user))
    assert resp.status_code == 204


# --- RBAC probe routes ---------------------------------------------


_ALLOWED = [
    ("/_probe/ops-maker", "auth_ops_maker"),
    ("/_probe/ops-checker", "auth_ops_checker"),
    ("/_probe/uw-maker", "auth_uw_maker"),
    ("/_probe/uw-checker", "auth_uw_checker"),
    ("/_probe/admin", "auth_admin"),
]

_FORBIDDEN = [
    ("/_probe/admin", "auth_ops_maker"),
    ("/_probe/ops-maker", "auth_admin"),
    ("/_probe/uw-checker", "auth_ops_checker"),
    ("/_probe/uw-maker", "auth_uw_checker"),
]


@pytest.mark.parametrize(("path", "headers_fixture"), _ALLOWED)
def test_probe_allows_matching_role(
    client: TestClient, request: pytest.FixtureRequest, path: str, headers_fixture: str
) -> None:
    headers = request.getfixturevalue(headers_fixture)
    resp = client.get(path, headers=headers)
    assert resp.status_code == 200


@pytest.mark.parametrize(("path", "headers_fixture"), _FORBIDDEN)
def test_probe_forbids_other_roles(
    client: TestClient, request: pytest.FixtureRequest, path: str, headers_fixture: str
) -> None:
    headers = request.getfixturevalue(headers_fixture)
    resp = client.get(path, headers=headers)
    assert resp.status_code == 403


def test_probe_requires_authentication(client: TestClient) -> None:
    assert client.get("/_probe/admin").status_code == 401
