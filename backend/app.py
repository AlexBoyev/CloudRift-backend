from __future__ import annotations

from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import sys
import time
import requests
from typing import Any, Dict, Optional, Tuple

app = Flask(__name__)
CORS(app)
#blabla testddddddd
# ----------------------------
# Configuration
# ----------------------------
def _must_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"CRITICAL ERROR: Missing environment variable {name}", file=sys.stderr)
        sys.exit(1)
    return v.rstrip("/")


STACK_URL = _must_env("STACK_URL")            # e.g. http://stack-service:80
LINKEDLIST_URL = _must_env("LINKEDLIST_URL")  # e.g. http://linkedlist-service:8080
GRAPH_URL = _must_env("GRAPH_URL")            # e.g. http://graph-service:5000

# Keep names generic now that everything is routed via one ingress path (/api -> backend)
UPSTREAM_TIMEOUT_SECONDS = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "10"))
UPSTREAM_RETRY_ATTEMPTS = int(os.getenv("UPSTREAM_RETRY_ATTEMPTS", "3"))
UPSTREAM_RETRY_BASE_SLEEP = float(os.getenv("UPSTREAM_RETRY_BASE_SLEEP", "0.2"))

_session = requests.Session()

print("--- Configuration Loaded ---", file=sys.stderr)
print(f"STACK_URL={STACK_URL}", file=sys.stderr)
print(f"LINKEDLIST_URL={LINKEDLIST_URL}", file=sys.stderr)
print(f"GRAPH_URL={GRAPH_URL}", file=sys.stderr)
print(
    f"TIMEOUT={UPSTREAM_TIMEOUT_SECONDS}s RETRIES={UPSTREAM_RETRY_ATTEMPTS} BACKOFF={UPSTREAM_RETRY_BASE_SLEEP}s",
    file=sys.stderr,
)


# ----------------------------
# Helpers
# ----------------------------
def _json_error(message: str, status: int, **extra: Any):
    payload: Dict[str, Any] = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def _get_json_silent() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}


def _with_retry(fn, *args, **kwargs) -> requests.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(1, UPSTREAM_RETRY_ATTEMPTS + 1):
        try:
            return fn(*args, **kwargs)
        except requests.RequestException as e:
            last_exc = e
            sleep_s = UPSTREAM_RETRY_BASE_SLEEP * (2 ** (attempt - 1))
            print(
                f"[WARN] upstream attempt {attempt}/{UPSTREAM_RETRY_ATTEMPTS} failed: {e}. sleep={sleep_s:.2f}s",
                file=sys.stderr,
            )
            time.sleep(sleep_s)
    assert last_exc is not None
    raise last_exc


def _upstream_json_or_text(resp: requests.Response) -> Tuple[Dict[str, Any], bool]:
    """
    Returns (payload, is_json). If upstream returned invalid JSON, payload contains upstream_raw.
    """
    try:
        return resp.json(), True
    except ValueError:
        return {"upstream_raw": resp.text}, False


def _proxy_upstream_error_if_any(resp: requests.Response) -> Optional[Tuple[Any, int]]:
    """
    If upstream status is >= 400, return a Flask response tuple immediately (proxy error through).
    Otherwise return None.
    """
    if resp.status_code >= 400:
        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code
    return None


# ----------------------------
# Health
# ----------------------------
@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


# =========================================================
# Stack APIs
# (UI calls /api/stack/... ; Ingress rewrites /api -> / ; Backend routes are /stack/...)
# =========================================================

@app.get("/stack/data")
def get_stack_data():
    try:
        resp = _with_retry(
            _session.get,
            f"{STACK_URL}/stack",
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        data, _ = _upstream_json_or_text(resp)
        return jsonify(data), resp.status_code

    except requests.Timeout:
        return _json_error("Stack service timeout", 504)
    except requests.RequestException as e:
        return _json_error("Stack service unavailable", 503, details=str(e))


@app.post("/stack/push")
def push_stack_item():
    data = _get_json_silent()
    if "value" not in data:
        return _json_error("Invalid request: provide JSON body with integer field 'value'", 400)

    try:
        val = int(data["value"])
    except (TypeError, ValueError):
        return _json_error("Invalid request: 'value' must be an integer", 400)

    try:
        resp = _with_retry(
            _session.post,
            f"{STACK_URL}/push",
            json={"value": val},
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code

    except requests.Timeout:
        return _json_error("Stack service timeout", 504)
    except requests.RequestException as e:
        return _json_error("Stack service unavailable", 503, details=str(e))


@app.post("/stack/pop")
def pop_stack_item():
    try:
        # Use an empty JSON object (or no body) consistently.
        # Some proxies/servers behave better when Content-Type isn't set for empty body.
        resp = _with_retry(
            _session.post,
            f"{STACK_URL}/pop",
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code

    except requests.Timeout:
        return _json_error("Stack service timeout", 504)
    except requests.RequestException as e:
        return _json_error("Stack service unavailable", 503, details=str(e))


# =========================================================
# LinkedList APIs
# =========================================================

@app.get("/list/data")
def get_list_data():
    try:
        resp = _with_retry(
            _session.get,
            f"{LINKEDLIST_URL}/list",
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code

    except requests.Timeout:
        return _json_error("LinkedList service timeout", 504)
    except requests.RequestException as e:
        return _json_error("LinkedList service unavailable", 503, details=str(e))


@app.post("/list/add")
def add_list_item():
    try:
        resp = _with_retry(
            _session.post,
            f"{LINKEDLIST_URL}/add",
            json=_get_json_silent(),
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code

    except requests.Timeout:
        return _json_error("LinkedList service timeout", 504)
    except requests.RequestException as e:
        return _json_error("LinkedList service unavailable", 503, details=str(e))


@app.post("/list/delete")
def delete_list_item():
    try:
        resp = _with_retry(
            _session.post,
            f"{LINKEDLIST_URL}/delete",
            json=_get_json_silent(),
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code

    except requests.Timeout:
        return _json_error("LinkedList service timeout", 504)
    except requests.RequestException as e:
        return _json_error("LinkedList service unavailable", 503, details=str(e))


@app.post("/list/remove-head")
def remove_head():
    try:
        resp = _with_retry(
            _session.post,
            f"{LINKEDLIST_URL}/remove-head",
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code

    except requests.Timeout:
        return _json_error("LinkedList service timeout", 504)
    except requests.RequestException as e:
        return _json_error("LinkedList service unavailable", 503, details=str(e))


# =========================================================
# Graph APIs
# =========================================================

@app.get("/graph/data")
def get_graph_data():
    try:
        resp = _with_retry(
            _session.get,
            f"{GRAPH_URL}/data",
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code

    except requests.Timeout:
        return _json_error("Graph service timeout", 504)
    except requests.RequestException as e:
        return _json_error("Graph service unavailable", 503, details=str(e))


@app.post("/graph/add-node")
def add_graph_node():
    try:
        resp = _with_retry(
            _session.post,
            f"{GRAPH_URL}/add-node",
            json=_get_json_silent(),
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code

    except requests.Timeout:
        return _json_error("Graph service timeout", 504)
    except requests.RequestException as e:
        return _json_error("Graph service unavailable", 503, details=str(e))


@app.post("/graph/add-edge")
def add_edge():
    try:
        resp = _with_retry(
            _session.post,
            f"{GRAPH_URL}/add-edge",
            json=_get_json_silent(),
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code

    except requests.Timeout:
        return _json_error("Graph service timeout", 504)
    except requests.RequestException as e:
        return _json_error("Graph service unavailable", 503, details=str(e))


@app.post("/graph/delete-node")
def delete_graph_node():
    try:
        resp = _with_retry(
            _session.post,
            f"{GRAPH_URL}/delete-node",
            json=_get_json_silent(),
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code

    except requests.Timeout:
        return _json_error("Graph service timeout", 504)
    except requests.RequestException as e:
        return _json_error("Graph service unavailable", 503, details=str(e))


@app.post("/graph/delete-edge")
def delete_graph_edge():
    try:
        resp = _with_retry(
            _session.post,
            f"{GRAPH_URL}/delete-edge",
            json=_get_json_silent(),
            timeout=UPSTREAM_TIMEOUT_SECONDS,
        )
        maybe_err = _proxy_upstream_error_if_any(resp)
        if maybe_err:
            return maybe_err

        body, _ = _upstream_json_or_text(resp)
        return jsonify(body), resp.status_code

    except requests.Timeout:
        return _json_error("Graph service timeout", 504)
    except requests.RequestException as e:
        return _json_error("Graph service unavailable", 503, details=str(e))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
