"""Python Flask API Auth0 integration example
"""

from functools import wraps, partial
import json
from os import environ as env
from six.moves.urllib.request import urlopen
from flask import request, _request_ctx_stack
import inspect
from jose import jwt

import os
from dotenv import load_dotenv
load_dotenv()

# Auth specific - may abstract out, but no point currently
AUTH0_DOMAIN = os.getenv("AUTH0DOMAIN")
API_IDENTIFIER = os.getenv("APIURL")

if AUTH0_DOMAIN == "" or AUTH0_DOMAIN == None:
    raise Exception(
        "No Auth0 Domain specified.  Please make sure your .env is correct")


if API_IDENTIFIER == "" or API_IDENTIFIER == None:
    raise Exception(
        "No Auth0 API URL specified.  Please make sure your .env is correct")

ALGORITHMS = ["RS256"]


# Format error response and append status code.
class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code
        self.solution = "Please login again."


def get_token_auth_header():
    """Obtains the access token from the Authorization Header
    """
    auth = request.headers.get("Authorization", None)
    if not auth:
        raise AuthError(
            {
                "code": "authorization_header_missing",
                "description": "Authorization header is expected",
            },
            401,
        )

    parts = auth.split()

    if parts[0].lower() != "bearer":
        raise AuthError(
            {
                "code": "invalid_header",
                "description": "Authorization header must start with" " Bearer",
            },
            401,
        )
    elif len(parts) == 1:
        raise AuthError(
            {"code": "invalid_header", "description": "Token not found"}, 401
        )
    elif len(parts) > 2:
        raise AuthError(
            {
                "code": "invalid_header",
                "description": "Authorization header must be" " Bearer token",
            },
            401,
        )

    token = parts[1]
    return token


def requires_scope(required_scope):
    """Determines if the required scope is present in the access token
    Args:
        required_scope (str): The scope required to access the resource
    """
    token = get_token_auth_header()
    unverified_claims = jwt.get_unverified_claims(token)
    if unverified_claims.get("scope"):
        token_scopes = unverified_claims["scope"].split()
        for token_scope in token_scopes:
            print(token_scope)
            if token_scope == required_scope:
                return True
    return False


def _requires_auth(f, permission="", error_func=""):
    """Determines if the access token is valid
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            if (
                "override_token" in inspect.signature(f).parameters
            ):  # If override token is present, will force it's use - this is used for Images
                token = kwargs["override_token"]
            else:
                token = get_token_auth_header()

            jsonurl = urlopen("https://" + AUTH0_DOMAIN +
                              "/.well-known/jwks.json")
            jwks = json.loads(jsonurl.read())
            token_scopes = ""
            try:
                unverified_header = jwt.get_unverified_header(token)
            except jwt.JWTError:
                raise AuthError(
                    {
                        "code": "invalid_header",
                        "description": "Invalid header. "
                        "Use an RS256 signed JWT Access Token",
                    },
                    401,
                )
            if unverified_header["alg"] == "HS256":
                raise AuthError(
                    {
                        "code": "invalid_header",
                        "description": "Invalid header. "
                        "Use an RS256 signed JWT Access Token",
                    },
                    401,
                )

            # Checks for correct permissions that are passed in
            unverified_claims = jwt.get_unverified_claims(token)
            if unverified_claims.get("permissions"):
                token_scopes = unverified_claims["permissions"]
                found = False
                for token_scope in token_scopes:
                    if token_scope == permission:
                        found = True
                if not found:
                    raise AuthError(
                        {
                            "code": "invalid_claims",
                            "description": "Permissions denied (Not found) - " + permission,
                        },
                        401,
                    )

            else:
                raise AuthError(
                    {
                        "code": "invalid_claims",
                        "description": "Permissions denied (No permission)",
                    },
                    401,
                )

            rsa_key = {}
            for key in jwks["keys"]:
                if key["kid"] == unverified_header["kid"]:
                    rsa_key = {
                        "kty": key["kty"],
                        "kid": key["kid"],
                        "use": key["use"],
                        "n": key["n"],
                        "e": key["e"],
                    }
            if rsa_key:
                try:
                    payload = jwt.decode(
                        token,
                        rsa_key,
                        algorithms=ALGORITHMS,
                        audience=API_IDENTIFIER,
                        issuer="https://" + AUTH0_DOMAIN + "/",
                    )
                except jwt.ExpiredSignatureError:
                    raise AuthError(
                        {"code": "token_expired",
                            "description": "token is expired"}, 401
                    )
                except jwt.JWTClaimsError as exc:
                    print(exc)
                    raise AuthError(
                        {
                            "code": "invalid_claims",
                            "description": "incorrect claims,"
                            " please check the audience and issuer",
                        },
                        401,
                    )
                except Exception:
                    raise AuthError(
                        {
                            "code": "invalid_header",
                            "description": "Unable to parse authentication" " token.",
                        },
                        401,
                    )

                _request_ctx_stack.top.current_user = payload
                if (
                    "scopes" in inspect.signature(f).parameters
                ):  # Passes out the scopes if the decorated function has it as an argument
                    kwargs["scopes"] = token_scopes

                return f(*args, **kwargs)
            raise AuthError(
                {"code": "invalid_header",
                    "description": "Unable to find appropriate key"},
                401,
            )
        except AuthError as exc:
            print(exc.error)
            return error_func(msg=exc.error, code=exc.status_code, *args, **kwargs)

    return decorated
