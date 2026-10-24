"""Identity contract for section 6.9 and 6.10.

Test tokens are signed with a fixture key that lives only in memory. Nothing here talks to Google;
the point is to prove that signature, issuer, audience, and expiry are actually verified rather than
decoded and trusted.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import jwt

# Fixture-only values. A real deployment reads these from the environment, never from source.
FIXTURE_SECRET = "TEST-ONLY-KEY-not-a-real-secret"
ISSUER = "https://accounts.example.test"
AUDIENCE = "day3-client-id"

LOGIN_SCOPES = ["openid", "email", "profile"]

COOKIE_CONTRACT = {
    "name": "__Host-day3_session",
    "httponly": True,      # unreadable from JavaScript
    "secure": True,        # HTTPS only
    "samesite": "Lax",     # blocks cross-site POST while keeping top-level redirects working
    "path": "/",
    "max_age_seconds": 3600,
    "domain": None,        # host-only cookie
}


def issue(sub: str = "U-002", *, issuer: str = ISSUER, audience: str = AUDIENCE,
          expires_in: int = 600, scopes: list[str] | None = None) -> str:
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": sub,
        "iat": now,
        "exp": now + expires_in,
        "scope": " ".join(scopes if scopes is not None else LOGIN_SCOPES),
    }
    return jwt.encode(payload, FIXTURE_SECRET, algorithm="HS256")


@dataclass
class Verification:
    ok: bool
    claims: dict | None
    reason: str


def verify(token: str, *, audience: str = AUDIENCE, issuer: str = ISSUER) -> Verification:
    """Full check: signature, issuer, audience, expiry. Decoding without these proves nothing."""
    try:
        claims = jwt.decode(
            token,
            FIXTURE_SECRET,
            algorithms=["HS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        return Verification(False, None, "expired")
    except jwt.InvalidIssuerError:
        return Verification(False, None, "bad_issuer")
    except jwt.InvalidAudienceError:
        return Verification(False, None, "bad_audience")
    except jwt.InvalidSignatureError:
        return Verification(False, None, "bad_signature")
    except jwt.MissingRequiredClaimError as exc:
        return Verification(False, None, f"missing_{exc.claim}")
    except jwt.InvalidTokenError:
        return Verification(False, None, "invalid_token")
    return Verification(True, claims, "ok")


def unsign_only(token: str) -> dict:
    """What a naive implementation does: read the claims and skip verification. Shown for contrast."""
    return jwt.decode(token, options={"verify_signature": False, "verify_exp": False,
                                      "verify_aud": False, "verify_iss": False})
