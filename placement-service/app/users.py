"""Synthetic users for the demo. Passwords are stored only as salted PBKDF2 hashes.

The demo passwords are listed in the README (they protect no real data). A real deployment
would read users from a database or an identity provider instead of this table.
"""
import hashlib
import hmac
from dataclasses import dataclass

ITERATIONS = 200000


@dataclass(frozen=True)
class User:
    username: str
    name: str
    role: str
    salt: str       # hex
    password_hash: str  # hex of PBKDF2-HMAC-SHA256


USERS = {
    "stu-1": User("stu-1", "Clarisse Ngo", "student", "de06c1a3f5337a1aa1d8fe8c823e7855", "ff7e6b430957583eb9ed93ece044002abd3c2de6fc7e15ea88e463cf2363ad9a"),
    "stu-2": User("stu-2", "Arnaud Tchoupe", "student", "b4b2e5b142a56f80d2eeff3aa9c2636f", "7710b73c7376cf82f56626e5d992c6876c50672e281a4bad31da24595f79dc8e"),
    "cs-1": User("cs-1", "Paul Mbarga", "company_supervisor", "ae0628e7b20f4596be5a9a9dcefb875b", "4da3f28803e42aa01cefb0e650f2bd411f3896834e08540316b1c469e160c294"),
    "cs-2": User("cs-2", "Sandrine Fotso", "company_supervisor", "b6ddf4f5ed723e5e6e9c1453974c7740", "901e7c8762cf601b58717d8d7a8906d062db0bc7184fae606761c57ae659ca60"),
    "as-1": User("as-1", "Elise Ngono", "academic_supervisor", "7b0f525e4a81d594d24cedb5eb812e81", "36b835b8cc577f7aa86bb0a6ec467b23ccf4b7026b410605f6b3f2978b46b5e2"),
    "co-1": User("co-1", "Julie Mbia", "coordinator", "c87627ccb772124d1e7658801a481bdf", "890b116be426c4b2ddb1bee785d749578f1e0690ead0a2825204f0e9629032d7"),
}

# Used to spend the same time when the username does not exist, so response time
# does not reveal which usernames are real.
_DUMMY_SALT = bytes(16)


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)


def authenticate(username: str, password: str) -> User | None:
    """Return the user when the password is right, otherwise None (same result for unknown user)."""
    user = USERS.get(username)
    if user is None:
        _hash(password, _DUMMY_SALT)
        return None
    expected = bytes.fromhex(user.password_hash)
    return user if hmac.compare_digest(_hash(password, bytes.fromhex(user.salt)), expected) else None