"""
Rover Command Coordinator — Phase 10.

Manages the rover's state machine from the Pi's perspective.
Tracks the rover's reported state, handles GOTO command lifecycle,
generates alerts on communication loss, and provides a queryable
snapshot for the dashboard.

Rover states:
    OFFLINE, ONLINE, MANUAL, AUTO, AUTO_GPS, PAUSED,
    OBSTACLE, GPS_LOST, LINK_LOST, ARRIVED, EMERGENCY_STOP, FAULT

Safety priority (highest first):
    EMERGENCY_STOP > OBSTACLE > COMMUNICATION > GPS_NAV > NORMAL
"""

import time
import threading
import logging

import config

log = logging.getLogger("rover")

VALID_STATES = {
    "OFFLINE", "ONLINE", "MANUAL", "AUTO", "AUTO_GPS", "RELAY",
    "PAUSED", "OBSTACLE", "GPS_LOST", "LINK_LOST", "ARRIVED",
    "EMERGENCY_STOP", "FAULT",
}


class RoverManager:
    """Tracks rover state and handles command coordination."""

    def __init__(self, db, mesh, alert_mgr=None, publish_fn=None):
        self.db = db
        self.mesh = mesh
        self.alerts = alert_mgr
        self.publish = publish_fn or (lambda k, d: None)

        self._lock = threading.Lock()
        self._stop = threading.Event()

        # Rover state
        self.state = "OFFLINE"
        self.mode = "MANUAL"
        self.last_telemetry = 0
        self.last_gps = None           # (lat, lon)
        self.target_gps = None         # (lat, lon) - current GOTO target
        self.distance_m = -1
        self.heading_error = -999
        self.obstacle_cm = -1
        self.battery_pct = -1
        self.gps_fix = False
        self.link_lost_alerted = False

    def start(self):
        t = threading.Thread(target=self._watchdog_loop, daemon=True, name="rover-wd")
        t.start()
        log.info("Rover Manager started (watchdog=%.0fs)", config.ROVER_COMM_WATCHDOG_S)

    def stop(self):
        self._stop.set()

    # ---- telemetry update (from mesh) ------------------------------------

    def telemetry_update(self, rover_id, mode, obstacle_cm, battery_pct,
                         dist_m=-1, heading_err=-999, lat=None, lon=None,
                         target_lat=None, target_lon=None, gps_fix=False,
                         rssi=None):
        """Called when a ROVER telemetry packet arrives."""
        with self._lock:
            was_offline = self.state in ("OFFLINE", "LINK_LOST")
            self.last_telemetry = time.time()
            self.mode = mode
            self.obstacle_cm = obstacle_cm
            self.battery_pct = battery_pct
            self.distance_m = dist_m
            self.heading_error = heading_err
            self.gps_fix = gps_fix
            if lat is not None and lon is not None:
                self.last_gps = (lat, lon)
            if target_lat is not None and target_lon is not None:
                self.target_gps = (target_lat, target_lon)

            # Determine state from mode
            if mode == "AUTO_GPS":
                if dist_m >= 0 and dist_m <= config.ROVER_ARRIVE_RADIUS_M:
                    self.state = "ARRIVED"
                elif obstacle_cm >= 0 and obstacle_cm < config.ROVER_OBSTACLE_THRESHOLD_CM:
                    self.state = "OBSTACLE"
                elif not gps_fix:
                    self.state = "GPS_LOST"
                else:
                    self.state = "AUTO_GPS"
            elif mode in VALID_STATES:
                self.state = mode
            else:
                self.state = "ONLINE"

            # Recovery from link-lost
            if was_offline and self.link_lost_alerted:
                self.link_lost_alerted = False
                if self.alerts:
                    self.alerts.create(
                        "NODE_RECOVERED", source=rover_id,
                        message=f"Rover {rover_id} communication restored",
                        severity="INFO",
                    )

            # Store telemetry history
            self.db.rover_telemetry(
                rover_id, mode,
                lat or 0, lon or 0,
                target_lat or 0, target_lon or 0,
                dist_m, 0, 0, heading_err,
                obstacle_cm, battery_pct, 1 if gps_fix else 0,
                self.state,
            )

            # Check for arrival
            if self.state == "ARRIVED":
                if self.alerts:
                    self.alerts.create(
                        "ROVER_ARRIVED", source=rover_id,
                        message=f"Rover {rover_id} arrived at target",
                        severity="INFO",
                    )

    # ---- commands --------------------------------------------------------

    def goto(self, rover_id, lat, lon):
        """Send a GOTO command to the rover."""
        # Validate coords
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return False, "Coordinates out of range"

        with self._lock:
            self.target_gps = (lat, lon)

        # Convert to microdegrees for the wire
        normalised = f"{int(round(lat * 1e6))},{int(round(lon * 1e6))}"
        self.mesh.send_cmd(rover_id, "GOTO", normalised)
        cmd_id = self.db.rover_cmd_log(rover_id, "GOTO", normalised)
        log.info("GOTO %s → %s (%s)", rover_id, normalised, cmd_id)
        return True, cmd_id

    def stop_rover(self, rover_id):
        self.mesh.send_cmd(rover_id, "STOP")
        self.db.rover_cmd_log(rover_id, "STOP")
        log.info("STOP → %s", rover_id)
        return True

    def pause_rover(self, rover_id):
        """Pause by switching to RELAY mode (motors off)."""
        self.mesh.send_cmd(rover_id, "MODE", "RELAY")
        self.db.rover_cmd_log(rover_id, "MODE", "RELAY")
        log.info("PAUSE (MODE RELAY) → %s", rover_id)
        return True

    def resume_rover(self, rover_id):
        """Resume by switching back to AUTO mode."""
        self.mesh.send_cmd(rover_id, "MODE", "AUTO")
        self.db.rover_cmd_log(rover_id, "MODE", "AUTO")
        log.info("RESUME (MODE AUTO) → %s", rover_id)
        return True

    def emergency_stop(self, rover_id):
        """Immediate stop — highest priority."""
        self.mesh.send_cmd(rover_id, "STOP")
        self.mesh.send_cmd(rover_id, "STOP")  # send twice for reliability
        self.db.rover_cmd_log(rover_id, "EMERGENCY_STOP")
        if self.alerts:
            self.alerts.create(
                "ROVER_FAULT", source=rover_id,
                message=f"Emergency stop sent to {rover_id}",
                severity="CRITICAL",
            )
        log.warning("EMERGENCY STOP → %s", rover_id)
        return True

    # ---- query -----------------------------------------------------------

    def snapshot(self):
        with self._lock:
            return {
                "state": self.state,
                "mode": self.mode,
                "last_telemetry": self.last_telemetry,
                "last_gps": self.last_gps,
                "target_gps": self.target_gps,
                "distance_m": self.distance_m,
                "heading_error": self.heading_error,
                "obstacle_cm": self.obstacle_cm,
                "battery_pct": self.battery_pct,
                "gps_fix": self.gps_fix,
                "age_s": round(time.time() - self.last_telemetry, 1) if self.last_telemetry else None,
            }

    # ---- watchdog --------------------------------------------------------

    def _watchdog_loop(self):
        """Detect communication loss."""
        while not self._stop.wait(5.0):
            with self._lock:
                if self.last_telemetry == 0:
                    continue  # never heard from rover
                age = time.time() - self.last_telemetry
                if age > config.ROVER_COMM_WATCHDOG_S and not self.link_lost_alerted:
                    self.state = "LINK_LOST"
                    self.link_lost_alerted = True
                    if self.alerts:
                        self.alerts.create(
                            "ROVER_LINK_LOST",
                            source=config.ROVER_ID,
                            message=f"No rover telemetry for {age:.0f}s",
                            severity="CRITICAL",
                            data={"last_telemetry": self.last_telemetry},
                        )
                    log.warning("Rover LINK_LOST (%.0fs since last telemetry)", age)
