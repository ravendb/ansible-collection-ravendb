# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


def _requests():
    try:
        import requests
        return requests
    except ImportError:
        raise RuntimeError("Python 'requests' is required for RavenDB Cloud operations. Install 'requests'.")


class RavenDBCloudClient(object):
    """
    HTTP client for the RavenDB Cloud API.
    Authenticates via the X-Api-Key header.
    """

    DEFAULT_API_URL = "https://api.cloud.ravendb.net"
    API_VERSION_PATH = "/api/v1"
    REQUEST_TIMEOUT_SECONDS = 30

    def __init__(self, api_key, api_url=None):
        base = (api_url or self.DEFAULT_API_URL).rstrip("/")
        self._base = base + self.API_VERSION_PATH
        self._headers = {
            "X-Api-Key": api_key,
            "Accept": "application/json",
        }

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, body=None):
        return self._request("POST", path, body=body)

    def get_raw(self, path):
        return self._request("GET", path, raw=True)

    def _request(self, method, path, body=None, raw=False):
        url = "{}{}".format(self._base, path)
        kwargs = {
            "headers": self._headers,
            "timeout": self.REQUEST_TIMEOUT_SECONDS,
            "allow_redirects": False,
        }
        if body is not None:
            kwargs["json"] = body
        response = _requests().request(method, url, **kwargs)
        if not response.ok:
            body_text = (response.text or "").strip()
            raise RuntimeError(
                "{} {} -> {} {}: {}".format(method, url, response.status_code, response.reason, body_text or "<empty body>")
            )
        if raw:
            return response.content
        return response.json() if response.content else {}
