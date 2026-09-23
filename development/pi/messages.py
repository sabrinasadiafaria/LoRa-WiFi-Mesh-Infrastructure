"""
Message Router — Phase 10.

Handles outgoing messages with ACK tracking, retry, and priority.

Message flow:
    1. create_message(src, dest, text, priority) → msg_id
    2. Message queued in DB (status=PENDING)
    3. Sent via mesh → status=SENT
    4. ACK received → status=ACKNOWLEDGED
    5. Timeout without ACK → retry (up to max_retries)
    6. Retries exhausted → status=FAILED, alert generated

This works alongside (not replacing) the existing mesh.send_data().
The router adds reliability tracking on top.
"""

import time
import threading
import logging

import config

log = logging.getLogger("messages")


class MessageRouter:
    """
    Tracks outgoing messages, handles ACK/retry.

    mesh.send_data() is the actual transmit path — this module
    wraps it with reliability.
    """

    def __init__(self, db, mesh, alert_mgr=None, publish_fn=None):
        self.db = db
        self.mesh = mesh
        self.alerts = alert_mgr
        self.publish = publish_fn or (lambda k, d: None)
        self._stop = threading.Event()

    def start(self):
        t = threading.Thread(target=self._retry_loop, daemon=True, name="msg-retry")
        t.start()
        log.info("Message Router started (ACK timeout=%.0fs, max retries=%d)",
                 config.MSG_ACK_TIMEOUT_S, config.MSG_MAX_RETRIES)

    def stop(self):
        self._stop.set()

    # ---- public API ------------------------------------------------------

    def send(self, src, dest, text, priority=3):
        """
        Send a tracked message. Returns msg_id.
        """
        text = str(text).strip()[:config.MSG_MAX_LENGTH]
        if not text:
            return None

        msg_id = self.db.msg_create(src, dest, text, priority)

        # Actually send via mesh
        # Prefix the mesh payload with the msg_id so the receiver can ACK it
        payload = f"M:{msg_id}:{text}"
        self.mesh.send_data(dest, payload)
        self.db.msg_sent(msg_id)

        # Also log in the legacy messages table for backward compat
        self.db.message(src, dest, text, "out")

        self.publish("message", {
            "msg_id": msg_id, "src": src, "dest": dest,
            "text": text, "priority": priority, "status": "SENT",
        })
        log.info("MSG SENT [%s] %s→%s: %s", msg_id, src, dest, text[:40])
        return msg_id

    def ack_received(self, msg_id, ack_by=""):
        """Called when a MSGACK is received from the destination."""
        msg = self.db.msg_get(msg_id)
        if msg and msg["status"] not in ("ACKNOWLEDGED", "FAILED"):
            self.db.msg_acked(msg_id, ack_by)
            self.publish("message_ack", {
                "msg_id": msg_id, "ack_by": ack_by,
                "status": "ACKNOWLEDGED",
            })
            log.info("MSG ACK [%s] by %s", msg_id, ack_by)

    def list_messages(self, limit=50):
        return self.db.msg_list(limit)

    def get_message(self, msg_id):
        return self.db.msg_get(msg_id)

    # ---- retry loop ------------------------------------------------------

    def _retry_loop(self):
        """Check for unacknowledged messages and retry them."""
        while not self._stop.wait(5.0):
            try:
                pending = self.db.msg_pending()
                now = time.time()
                for msg in pending:
                    if msg["status"] == "SENT" and msg["sent_at"]:
                        age = now - msg["sent_at"]
                        if age > config.MSG_ACK_TIMEOUT_S:
                            if msg["retry_count"] < msg["max_retries"]:
                                # Retry
                                payload = f"M:{msg['msg_id']}:{msg['text']}"
                                self.mesh.send_data(msg["dest"], payload)
                                self.db.msg_sent(msg["msg_id"])
                                log.info("MSG RETRY [%s] attempt %d/%d",
                                         msg["msg_id"], msg["retry_count"] + 1,
                                         msg["max_retries"])
                            else:
                                # Exhausted retries
                                self.db.msg_failed(msg["msg_id"])
                                if self.alerts:
                                    self.alerts.create(
                                        "MESSAGE_FAILED",
                                        source=msg["dest"],
                                        message=f"Message to {msg['dest']} failed after {msg['max_retries']} retries",
                                        data={"msg_id": msg["msg_id"]},
                                    )
                                self.publish("message_failed", {
                                    "msg_id": msg["msg_id"],
                                    "dest": msg["dest"],
                                })
                                log.warning("MSG FAILED [%s] to %s", msg["msg_id"], msg["dest"])
            except Exception as e:
                log.error("Message retry loop error: %s", e)
