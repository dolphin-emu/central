from .. import utils
from ..config import cfg

import json
import jwt
import logging
import requests
import time

_AUTH_MANAGER = None
_JWT_EXPIRY_SECS = 600
_INSTALL_TOKEN_EXPIRY_SECS = 3600

_EXPECTED_PERMS = {
    "checks": "write",
    "contents": "read",
    "issues": "write",
    "members": "read",
    "metadata": "read",
    "pull_requests": "write",
    "statuses": "write",
}

_EXPECTED_WEBHOOK_EVENTS = [
    "check_run",
    "commit_comment",
    "issue_comment",
    "pull_request",
    "pull_request_review",
    "pull_request_review_comment",
    "push",
]


class AuthManager:
    def __init__(self, app_id, app_priv_key_path):
        self.app_id = str(app_id)
        with open(app_priv_key_path, "rb") as fp:
            self.app_pkey = jwt.jwk_from_pem(fp.read())

        self.cached_app_jwt = None
        self.cached_app_jwt_deadline = 0

        self.org_installs = {}
        self.org_tokens = {}

        self._update_installations()

    def _update_installations(self):
        new_org_installs = {}

        installs = requests.get(
            "https://api.github.com/app/installations", auth=AppAuth(auth_manager=self)
        ).json()
        for install in installs:
            if install["target_type"].lower() == "organization":
                new_org_installs[install["account"]["login"]] = install["id"]

        self.org_installs = new_org_installs

    @property
    def app_jwt(self):
        t = int(time.time())
        if t < self.cached_app_jwt_deadline:
            return self.cached_app_jwt

        payload = {
            "iat": t,
            "exp": t + _JWT_EXPIRY_SECS,
            "iss": self.app_id,
        }
        self.cached_app_jwt = jwt.JWT().encode(payload, self.app_pkey, alg="RS256")
        self.cached_app_jwt_deadline = t + int(_JWT_EXPIRY_SECS * 0.8)
        return self.cached_app_jwt

    def org_token(self, org):
        if org not in self.org_installs:
            self._update_installations()
            if org not in self.org_installs:
                raise RuntimeError(f"App is not installed for org {org}")
        iid = self.org_installs[org]

        t = time.time()
        if org in self.org_tokens:
            tok, deadline = self.org_tokens[org]
            if t < deadline:
                return tok

        res = requests.post(
            f"https://api.github.com/app/installations/{iid}/access_tokens",
            auth=AppAuth(auth_manager=self),
            data="{}",
        ).json()
        tok = res["token"]
        deadline = t + _INSTALL_TOKEN_EXPIRY_SECS * 0.8
        self.org_tokens[org] = (tok, deadline)
        return tok


class AppAuth(requests.auth.AuthBase):
    """Use to authenticate as the GitHub app (not a repo/org instance of it)."""

    def __init__(self, auth_manager=None):
        super().__init__()
        self.auth_manager = auth_manager if auth_manager is not None else _AUTH_MANAGER

    def __call__(self, r):
        r.headers["authorization"] = f"Bearer {self.auth_manager.app_jwt}"
        return r


class OrgAuth(requests.auth.AuthBase):
    """Use to authenticate as an org install of the GitHub app."""

    def __init__(self, org, auth_manager=None):
        super().__init__()
        self.org = org
        self.auth_manager = auth_manager if auth_manager is not None else _AUTH_MANAGER

    def __call__(self, r):
        r.headers["authorization"] = f"Bearer {self.auth_manager.org_token(self.org)}"
        return r


def check_app_configuration():
    app = requests.get("https://api.github.com/app", auth=AppAuth()).json()

    for (perm, val) in sorted(_EXPECTED_PERMS.items()):
        if perm not in app["permissions"]:
            logging.error("Missing GH app permission: %s (should be: %s)", perm, val)
        elif val != app["permissions"][perm]:
            logging.error("Wrong GH app permission: %s should be %s", perm, val)

    for evt in _EXPECTED_WEBHOOK_EVENTS:
        if evt not in app["events"]:
            logging.error("Missing GH app webhook delivery: %s", evt)

    hook_data = {
        "content_type": "json",
        "url": cfg.web.external_url + "/gh/hook/",
        "secret": cfg.github.hook_hmac_secret,
        "insecure_ssl": "0",
    }
    requests.patch(
        "https://api.github.com/app/hook/config",
        auth=AppAuth(),
        data=json.dumps(hook_data),
    )


def start():
    global _AUTH_MANAGER
    _AUTH_MANAGER = AuthManager(cfg.github.app.id, cfg.github.app.priv_key_path)

    utils.spawn_periodic_task(600, check_app_configuration)
