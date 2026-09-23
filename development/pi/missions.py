"""
Mission Manager — Phase 10.

A mission is a named unit of work assigned to teams and optionally a rover.
The manager provides CRUD operations and status tracking.

Mission states:
    PLANNED → ACTIVE → PAUSED / COMPLETED / CANCELLED
"""

import time
import json
import logging

import config

log = logging.getLogger("missions")

_next_seq = [0]


def _make_id():
    _next_seq[0] += 1
    return f"{config.MISSION_ID_PREFIX}{_next_seq[0]:03d}"


class MissionManager:
    """CRUD + lifecycle for missions."""

    def __init__(self, db, publish_fn=None):
        self.db = db
        self.publish = publish_fn or (lambda k, d: None)
        # seed the sequence from existing missions
        existing = db.missions_list()
        if existing:
            nums = []
            for m in existing:
                try:
                    nums.append(int(m["id"].lstrip(config.MISSION_ID_PREFIX)))
                except (ValueError, TypeError):
                    pass
            if nums:
                _next_seq[0] = max(nums)

    def create(self, name, description="", teams=None, rover="",
               target_lat=0, target_lon=0, radius=0):
        mid = _make_id()
        self.db.mission_create(
            mid, name=name, description=description,
            teams=teams, rover=rover,
            target_lat=target_lat, target_lon=target_lon, radius=radius,
        )
        m = self.db.mission_get(mid)
        self.publish("mission", {"action": "created", "mission": m})
        log.info("Mission created: %s '%s'", mid, name)
        return m

    def update(self, mission_id, **kwargs):
        self.db.mission_update(mission_id, **kwargs)
        m = self.db.mission_get(mission_id)
        if m:
            self.publish("mission", {"action": "updated", "mission": m})
            log.info("Mission updated: %s → %s", mission_id, kwargs)
        return m

    def activate(self, mission_id):
        return self.update(mission_id, status="ACTIVE")

    def pause(self, mission_id):
        return self.update(mission_id, status="PAUSED")

    def complete(self, mission_id):
        return self.update(mission_id, status="COMPLETED")

    def cancel(self, mission_id):
        return self.update(mission_id, status="CANCELLED")

    def get(self, mission_id):
        return self.db.mission_get(mission_id)

    def list_all(self, status=None):
        return self.db.missions_list(status)
