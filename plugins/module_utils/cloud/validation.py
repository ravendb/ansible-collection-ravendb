# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import re

try:
    from urllib.parse import urlparse
except Exception:
    from urlparse import urlparse


_VALID_CLOUD_PROVIDERS = ("aws", "azure", "gcp")
_PRODUCT_ID_RE = re.compile(r"^[A-Za-z0-9\-]+$")
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def is_valid_api_key(key):
    return isinstance(key, str) and len(key) > 0


def validate_api_key(key):
    if not is_valid_api_key(key):
        return False, "api_key must be a non-empty string."
    return True, None


def _is_valid_cloud_api_url(url):
    if not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if not parsed.netloc:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "https":
        return True
    if parsed.scheme == "http" and host in _LOCAL_HOSTS:
        return True
    return False


def validate_api_url(url):
    if not _is_valid_cloud_api_url(url):
        return False, "Invalid api_url: {}. Must be https:// (http:// allowed only for localhost).".format(url)
    return True, None


def is_valid_product_id(value):
    return isinstance(value, str) and bool(_PRODUCT_ID_RE.match(value))


def validate_product_id(value):
    if not is_valid_product_id(value):
        return False, "product_id must be a non-empty alphanumeric string (letters, digits, hyphen)."
    return True, None


def is_valid_cloud_provider(value):
    return value in _VALID_CLOUD_PROVIDERS


def validate_cloud_provider(value):
    if not is_valid_cloud_provider(value):
        return False, "Invalid cloud_provider: {}. Must be one of {}.".format(value, ", ".join(_VALID_CLOUD_PROVIDERS))
    return True, None


def is_positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate_positive_int(name, value):
    if not is_positive_int(value):
        return False, "Invalid {}: {}. Must be a positive integer.".format(name, value)
    return True, None
