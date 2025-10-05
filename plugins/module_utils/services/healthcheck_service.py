# -*- coding: utf-8 -*-

# Copyright (c), RavenDB
# GNU General Public License v3.0 or later (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible_collections.ravendb.ravendb.plugins.module_utils.services.retry_service import retry_until
from ansible_collections.ravendb.ravendb.plugins.module_utils.core.tls import TLSConfig
from ansible_collections.ravendb.ravendb.plugins.module_utils.services.retry_service import BreakRetry
try:
    from urllib.parse import urlparse
except Exception:
    from urlparse import urlparse

try:
    from ipaddress import ip_address as _ip_address
except Exception:
    _ip_address = None


def _requests():
    try:
        import requests
        return requests
    except ImportError:
        raise RuntimeError("Python 'requests' is required for node operations. Install 'requests'.")


def _base(url):
    return (url or "").rstrip("/")


def pluck_tags(group):
    if not group:
        return []

    if isinstance(group, dict):
        return [str(k).strip() for k in group.keys()]

    if isinstance(group, str):
        return [group.strip()]
    try:
        items = list(group)
    except TypeError:
        return []

    out = []
    for item in items:
        if isinstance(item, str):
            out.append(item.strip())
            continue
        if isinstance(item, dict):
            t = item.get("NodeTag")
        else:
            t = getattr(item, "NodeTag", None)
        if t:
            out.append(str(t).strip())

    return list(dict.fromkeys(out))


def build_session(tls, validate_certificate=None):
    s = _requests().Session()
    s.headers.update({"User-Agent": "ravendb-ansible-healthcheck/1.0"})
    tls = tls or TLSConfig()
    cert, verify = tls.to_requests_tuple()
    if cert:
        s.cert = cert
    s.verify = False if validate_certificate is False else verify
    return s


def get_setup_alive(session, base_url, timeout=20):
    endpoint = _base(base_url) + "/setup/alive"
    try:
        r = session.get(endpoint, timeout=timeout)

        if 200 <= r.status_code < 300:
            return True, {"status": r.status_code}

        return False, "HTTP {}{}".format(
            r.status_code,
            " ({})".format(r.text.strip()[:200]) if r.text else ""
        )

    except _requests().RequestException as e:
        return False, str(e)


def get_node_ping(session, base_url, timeout=30, peer_url=None, node_tag=None):
    endpoint = _base(base_url) + "/admin/debug/node/ping"
    params = {}
    if peer_url:
        params["url"] = peer_url
    if node_tag:
        params["node"] = node_tag

    try:
        r = session.get(endpoint, params=params, timeout=timeout)
        if not (200 <= r.status_code < 300):
            return False, "HTTP {}{}".format(r.status_code, " ({})".format(r.text.strip()[:200]) if r.text else "")
        try:
            data = r.json()
        except ValueError:
            return False, "invalid JSON response"

        result = data.get("Result")
        if not result or not isinstance(result, list):
            return False, "missing/empty 'Result'"

        for item in result:
            url_i = item.get("Url") or "unknown"
            sa = (item.get("SetupAlive") or {}) or {}
            ti = (item.get("TcpInfo") or {}) or {}
            sa_err = sa.get("Error") if isinstance(sa, dict) else None
            ti_err = ti.get("Error") if isinstance(ti, dict) else None
            if sa_err or ti_err:
                return False, {
                    "peer": url_i,
                    "setup_alive_error": sa_err,
                    "tcp_info_error": ti_err
                }

        return True, {"peers": len(result)}
    except _requests().RequestException as e:
        return False, str(e)


def wait_for_node_alive(session, base_url, max_time_to_wait, retry_interval_seconds):
    return retry_until(
        get_setup_alive,
        max_time_to_wait,
        retry_interval_seconds,
        session,
        base_url,
        20
    )


def wait_for_cluster_connectivity(session, base_url, max_time_to_wait, retry_interval_seconds, peer_url=None, node_tag=None):
    return retry_until(
        get_node_ping,
        max_time_to_wait,
        retry_interval_seconds,
        session,
        base_url,
        30,
        peer_url,
        node_tag
    )


def wait_for_node_databases_online(ctx, max_time_to_wait, interval_seconds, excluded_tag):
    return retry_until(
        _check_all_databases_online,
        max_time_to_wait,
        interval_seconds,
        ctx,
        excluded_tag,
    )


def _list_db_names_via_http(ctx, timeout=30):
    base = _base(ctx.store.urls[0])
    session = build_session(TLSConfig())
    try:
        r = session.get(base + "/databases", timeout=timeout)
        r.raise_for_status()
        data = r.json() or {}
        dbs = data.get("Databases") or []
        return [d.get("Name") for d in dbs if d.get("Name")]
    finally:
        try:
            session.close()
        except Exception:
            pass


def _check_all_databases_online(ctx, excluded_tag):
    try:
        names = _list_db_names_via_http(ctx)
    except Exception as e:
        return False, "failed to list databases: {}".format(e)

    failing = {}
    for name in names:
        try:
            ok, detail = _db_has_usable_member(ctx, name, excluded_tag)
        except BreakRetry:
            raise

        except Exception as e:
            failing[name] = "failed to evaluate database: {}".format(e)
            continue

        if not ok and not (isinstance(detail, dict) and detail.get("skipped") == "rf=1"):
            failing[name] = detail

    if failing:
        return False, {"failing": failing}
    return True, {"checked": len(names)}


def _db_has_usable_member(ctx, db_name, excluded_tag):
    try:
        base = _base(ctx.store.urls[0])
        session = build_session(TLSConfig())
        r = session.get(base + "/databases", timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return False, "failed to read /databases: {}".format(e)
    finally:
        try:
            session.close()
        except Exception:
            pass

    dbs = data.get("Databases") or []
    info = None
    for item in dbs:
        if (item.get("Name") or "") == db_name:
            info = item
            break

    if not info:
        return False, "database_not_found_in_/databases"

    if info.get("Disabled") is True:
        return True, {"skipped": "disabled"}

    rf = info.get("ReplicationFactor")
    try:
        rf = int(rf) if rf is not None else None
    except Exception:
        rf = None
    if rf == 1:
        return True, {"skipped": "rf=1"}

    topo = info.get("NodesTopology") or {}
    members = topo.get("Members") or []
    promotables = topo.get("Promotables") or []
    rehabs = topo.get("Rehabs") or []
    status = topo.get("Status") or {}

    tags = sorted(set(pluck_tags(members) + pluck_tags(promotables) + pluck_tags(rehabs)))
    if not tags:
        return True, {"members": [], "excluded": excluded_tag, "note": "no members/promotables/rehabs"}

    ignore_substrings = [
        "(Status: Loading)",
        "Not responding",
    ]

    if isinstance(status, dict):
        for node_tag, node_status in status.items():
            st = (node_status or {})
            last_status = str(st.get("LastStatus") or "").strip().lower()
            last_err = st.get("LastError")
            if last_err and not any(s in last_err for s in ignore_substrings):
                raise BreakRetry("database_load_error", {"db": db_name, "node": node_tag, "error": last_err})

    usable_ok = []
    if isinstance(status, dict):
        for t in tags:
            if t == excluded_tag:
                continue
            st = status.get(t) or {}
            last_status = str(st.get("LastStatus") or "").strip().lower()
            if last_status == "ok":
                usable_ok.append(t)

    if usable_ok:
        return True, {"members": tags, "excluded": excluded_tag, "ok_on": usable_ok}

    return False, {
        "members": tags,
        "excluded": excluded_tag,
        "reason": "no usable member with LastStatus==Ok (or only excluded tag)",
    }


def hostname_is_ip(url):
    try:
        host = urlparse(url).hostname or ""
        _ip_address.ip_address(host)
        return True
    except Exception:
        return False
