"""FastAPI Events API receiver for Echo.

Slack POSTs events to /slack/events. Tailscale Funnel terminates TLS publicly
at https://<machine>.<tailnet>.ts.net/slack/events and forwards to 127.0.0.1.

Run: uvicorn echo_slack.server:app --host 127.0.0.1 --port 8080
"""

import json
import logging
import time
from collections import OrderedDict
from threading import Lock

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from slack_sdk.signature import SignatureVerifier

from . import config, handlers

logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("echo_slack.server")

app = FastAPI(title="echo-slack", version="1.0.0")
_verifier = SignatureVerifier(signing_secret=config.signing_secret())

_DEDUPE_MAX = 2048
_dedupe_seen: "OrderedDict[str, float]" = OrderedDict()
_dedupe_lock = Lock()


def _seen_event(event_id: str) -> bool:
    if not event_id:
        return False
    with _dedupe_lock:
        if event_id in _dedupe_seen:
            return True
        _dedupe_seen[event_id] = time.time()
        while len(_dedupe_seen) > _DEDUPE_MAX:
            _dedupe_seen.popitem(last=False)
    return False


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.post("/slack/events")
async def slack_events(
    request: Request,
    background: BackgroundTasks,
    x_slack_signature: str = Header(default=""),
    x_slack_request_timestamp: str = Header(default=""),
    x_slack_retry_num: str = Header(default=""),
) -> JSONResponse | PlainTextResponse:
    body = await request.body()

    if not _verifier.is_valid(body=body, timestamp=x_slack_request_timestamp, signature=x_slack_signature):
        log.warning("invalid Slack signature; ts=%s sig_prefix=%s", x_slack_request_timestamp, x_slack_signature[:12])
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid json")

    if payload.get("type") == "url_verification":
        return PlainTextResponse(content=payload.get("challenge", ""))

    if payload.get("type") == "event_callback":
        event = payload.get("event") or {}
        event_id = payload.get("event_id", "")
        if _seen_event(event_id):
            log.info("duplicate event_id=%s retry_num=%s — ignoring", event_id, x_slack_retry_num)
            return JSONResponse({"ok": True})
        background.add_task(handlers.dispatch, event)
        return JSONResponse({"ok": True})

    log.debug("unhandled payload type: %s", payload.get("type"))
    return JSONResponse({"ok": True})
