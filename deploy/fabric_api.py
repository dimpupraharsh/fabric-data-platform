"""Small authenticated Fabric client for exports and read-back verification.

Credentials come from the already authenticated Azure CLI (interactive bootstrap
or GitHub OIDC login). Tokens are never written to disk. POST requests are not
blindly retried: a timeout can mean the server already accepted the operation.
"""

from __future__ import annotations

import time
import os
import json
import subprocess
import re
from urllib.parse import urlparse

import requests
from azure.core.credentials import AccessToken

BASE = "https://api.fabric.microsoft.com/v1"


class CliCredential:
    """Use the signed-in CLI; isolate custom Mac CLI libraries from project Python."""

    def get_token(self, *scopes, **kwargs):
        env = os.environ.copy()
        if env.get("AZURE_CLI_PYTHONPATH"):
            env["PYTHONPATH"] = env["AZURE_CLI_PYTHONPATH"]
        resource = scopes[0].removesuffix("/.default")
        result = json.loads(subprocess.check_output(
            ["az", "account", "get-access-token", "--resource", resource, "-o", "json"],
            env=env, text=True,
        ))
        return AccessToken(result["accessToken"], int(result["expires_on"]))


class FabricAPI:
    """Call Fabric REST and wait for long-running definition operations."""

    def __init__(self):
        self.credential = CliCredential()

    def call(self, method, path, body=None):
        """Return decoded JSON; follow pagination using list_all separately."""
        url = path if path.startswith("https://") else f"{BASE}/{path.lstrip('/')}"
        host = urlparse(url).hostname or ""
        if host != "api.fabric.microsoft.com" and not host.endswith(".api.fabric.microsoft.com"):
            raise ValueError("Refusing to send a Fabric token to another host")
        for attempt in range(5):
            token = self.credential.get_token("https://api.fabric.microsoft.com/.default").token
            response = requests.request(method, url, json=body,
                                        headers={"Authorization": f"Bearer {token}"}, timeout=120)
            if method == "GET" and response.status_code in (429, 502, 503, 504):
                time.sleep(min(int(response.headers.get("Retry-After", "10")), 60))
                continue
            response.raise_for_status()
            if response.status_code == 202:
                return self._wait(response.headers.get("Location"))
            return response.json() if response.content else {}
        raise RuntimeError(f"Fabric read failed after retries: {method} {url}")

    def _wait(self, location):
        """Poll an accepted operation, then fetch its result without duplicating it."""
        if not location:
            raise RuntimeError("Accepted Fabric operation has no Location header")
        # Fabric can return a regional analysis.windows.net redirect. Poll the
        # documented public operation endpoint instead of broadening token hosts.
        operation_path = urlparse(location).path
        if not re.fullmatch(r"/v1/operations/[0-9a-fA-F-]{36}", operation_path):
            raise ValueError(f"Unexpected Fabric operation path: {operation_path}")
        location = "https://api.fabric.microsoft.com" + operation_path
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            result = self.call("GET", location)
            status = result.get("status")
            if status == "Succeeded":
                return self.call("GET", location.rstrip("/") + "/result")
            if status in ("Failed", "Cancelled"):
                raise RuntimeError(f"Fabric operation {status}: {result.get('error')}")
            time.sleep(5)
        raise TimeoutError(f"Fabric operation did not complete: {location}")

    def list_all(self, path):
        """Collect every page rather than silently missing items after page one."""
        rows = []
        while path:
            result = self.call("GET", path)
            rows.extend(result.get("value", []))
            path = result.get("continuationUri")
        return rows
