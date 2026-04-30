"""Echo Slack integration over Tailscale Funnel.

Replaces Socket Mode with Slack Events API. Slack POSTs events to a public
HTTPS URL fronted by Tailscale Funnel, which terminates TLS and forwards to a
local FastAPI server. Outbound calls use the Slack Web API over plain HTTPS.
No persistent WebSocket.
"""
