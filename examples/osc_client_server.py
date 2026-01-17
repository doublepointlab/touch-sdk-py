"""
Touch SDK OSC Bridge

Connects to a Touch SDK watch and forwards gestures as OSC messages.
Outputs: Tap, Double Tap, Triple Tap (with Palm-Up variants), Hold, Release, Left, Right

Gesture detection uses immediate classification per GESTURE_DETECTION_LOGIC.md:
- Palm-up detection via quaternion orientation (verticalCos + supinationAngle)
- Tap/Double/Triple decided instantly based on time since previous taps

Usage:
    python osc_client_server.py
    python osc_client_server.py --verbose
    python osc_client_server.py --model-index 1
"""

import argparse
import asyncio
import contextlib
import logging
import random
import signal
import threading
import time
from typing import Any, Optional, Coroutine, FrozenSet
import math

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

from touch_sdk import GestureType, Watch
from touch_sdk.watch import Hand


# =============================================================================
# CONFIGURATION - Edit these values to customize behavior
# =============================================================================

# Network settings
DEFAULT_IP = "127.0.0.1"
DEFAULT_SEND_PORT = 6666      # Port to send OSC messages TO (e.g. TouchDesigner)
DEFAULT_LISTEN_PORT = 6667    # Port to receive OSC messages FROM

# Multiple instances: duplicate this file and change ports for each watch
# e.g. watch1: 6666/6667, watch2: 6668/6669, watch3: 6670/6671

# Multi-tap waiting behavior
# When True: waits for time window before emitting, to avoid spurious intermediate gestures
# When False: emits immediately (lower latency, but fires tap before double-tap, etc.)
ENABLE_DOUBLE_TAP = True      # If True, single tap waits to see if double-tap is coming
ENABLE_TRIPLE_TAP = True      # If True, double tap waits to see if triple-tap is coming

# OSC addresses (what TouchDesigner sees)
OSC_TAP = "/tap"
OSC_DOUBLE_TAP = "/double-tap"
OSC_TRIPLE_TAP = "/triple-tap"
OSC_PALM_UP_TAP = "/palm-up-tap"
OSC_PALM_UP_DOUBLE_TAP = "/palm-up-double-tap"
OSC_PALM_UP_TRIPLE_TAP = "/palm-up-triple-tap"
OSC_LEFT = "/left"
OSC_RIGHT = "/right"
OSC_BACK_BUTTON = "/back-button"

# Timing (seconds) - tweak these if gestures feel laggy or too sensitive
HOLD_DELAY = 0.05             # How long before a press becomes a "Hold"
RELEASE_DELAY = 0.10          # How long before releasing counts as "Release"
TAP_COOLDOWN = 0.12           # Ignore rapid repeated taps within this window (SDK noise filter)
DOUBLE_TAP_WINDOW_PALM_DOWN = 0.30  # Max time between taps when palm is down
DOUBLE_TAP_WINDOW_PALM_UP = 0.50    # Max time between taps when palm is up (more lenient)
DPAD_COOLDOWN = 0.15          # Ignore rapid repeated left/right within this window
PULSE_DURATION = 0.10         # How long tap/left/right stays at 1 before going to 0


# Palm-up detection (uses quaternion orientation)
# verticalCos < 0.866 means tilted more than ~30° from vertical
# supinationAngle > 110° means wrist rotated past 110° (palm facing up)
VERTICAL_COS_THRESHOLD = 0.866
SUPINATION_ANGLE_THRESHOLD = 110


# =============================================================================
# INTERNALS - You probably don't need to edit below this line
# =============================================================================

logger = logging.getLogger(__name__)


def _gesture_name(gesture: GestureType) -> str:
    """Convert GestureType.PINCH_TAP to 'pinch tap'."""
    return gesture.name.replace("_", " ").lower()


def _gesture_list(gestures) -> str:
    """Convert a set of gestures to a readable string."""
    if not gestures:
        return "none"
    names = sorted(_gesture_name(g) for g in gestures if g != GestureType.NONE)
    return ", ".join(names) if names else "none"


class OscBridgeWatch(Watch):
    """Watch subclass that bridges Touch SDK gestures to OSC messages."""

    def __init__(
        self,
        ip: str,
        send_port: int,
        listen_port: int,
        name_filter: Optional[str] = None,
        model_index: Optional[int] = None,
    ):
        super().__init__(name_filter)

        # --- OSC connection ---
        self.osc_ip = ip
        self.osc_send_port = send_port
        self.osc_listen_port = listen_port
        self.osc_client = SimpleUDPClient(self.osc_ip, self.osc_send_port)

        # --- OSC server (for receiving haptics commands) ---
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/vib/intensity", self._on_haptic_intensity)
        self.dispatcher.map("/vib/duration", self._on_haptic_duration)
        self.osc_server = ThreadingOSCUDPServer(
            (self.osc_ip, self.osc_listen_port), self.dispatcher
        )
        self._server_thread: Optional[threading.Thread] = None

        # --- Haptics state (set via incoming OSC) ---
        self._haptic_intensity: Optional[float] = None
        self._haptic_duration_ms: Optional[int] = None

        # --- Hold detection state ---
        self.is_holding: bool = False
        self._hold_started_at: Optional[float] = None
        self._release_started_at: Optional[float] = None
        self._hold_osc_address: str = OSC_TAP  # Track which address hold is using

        # --- Tap detection state (per GESTURE_DETECTION_LOGIC.md) ---
        self._tap_count: int = 0                      # Taps in current sequence
        self._last_tap_time: float = 0.0              # When last tap in sequence occurred
        self._last_emit_time: float = 0.0             # When last gesture was emitted (post-emit cooldown)
        self._tap_sequence_id: int = 0                # Increments on each tap (for timer validity)
        self._tap_off_task: Optional[Any] = None
        self._pending_gesture_timer: Optional[Any] = None  # Timer for delayed emission
        self._pending_palm_up: bool = False           # Palm state when sequence started

        # --- Palm-up detection (from quaternion orientation) ---
        self._orientation: tuple = (0.0, 0.0, 0.0, 1.0)  # (qx, qy, qz, qw)

        # --- DPAD detection state ---
        self._last_left_at: Optional[float] = None
        self._last_right_at: Optional[float] = None

        # --- Model selection ---
        self._requested_model_index: Optional[int] = model_index
        self._model_requested: bool = False
        self._last_logged_model: Optional[FrozenSet[GestureType]] = None
        self._last_logged_hand: Optional[Hand] = None

        # --- Async loop reference ---
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def start_osc_server(self):
        """Start the background thread that listens for incoming OSC."""
        if self._server_thread and self._server_thread.is_alive():
            return
        self._server_thread = threading.Thread(
            target=self.osc_server.serve_forever,
            name="osc-server",
            daemon=True,
        )
        self._server_thread.start()
        logger.debug("OSC: listening on %s:%s, sending to %s:%s",
                     self.osc_ip, self.osc_listen_port,
                     self.osc_ip, self.osc_send_port)

    def stop_osc_server(self):
        """Stop the OSC server thread."""
        with contextlib.suppress(Exception):
            self.osc_server.shutdown()
        with contextlib.suppress(Exception):
            self.osc_server.server_close()
        if self._server_thread:
            self._server_thread.join(timeout=1.0)

    def stop(self):
        """Signal the watch to stop and cancel pending tasks."""
        # Cancel any pending gesture tasks
        self._cancel_task("_tap_off_task")
        self._cancel_task("_pending_gesture_timer")
        # Signal stop
        stop_event = getattr(self, "_stop_event", None)
        if stop_event is not None:
            stop_event.set()

    # -------------------------------------------------------------------------
    # OSC output helpers
    # -------------------------------------------------------------------------

    def _send(self, address: str, value: Any):
        """Send an OSC message (with error handling)."""
        try:
            self.osc_client.send_message(address, value)
        except Exception:
            logger.exception("OSC send failed: %s %r", address, value)

    def _schedule(self, coro: Coroutine) -> Optional[Any]:
        """Schedule an async task on the event loop."""
        try:
            loop = asyncio.get_running_loop()
            self._loop = loop
            return loop.create_task(coro)
        except RuntimeError:
            pass
        if self._loop and self._loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, self._loop)
        return None

    def _cancel_task(self, attr_name: str):
        """Cancel an async task by attribute name and clear the reference."""
        task = getattr(self, attr_name, None)
        if task is None:
            return
        setattr(self, attr_name, None)
        cancel = getattr(task, "cancel", None)
        if callable(cancel):
            with contextlib.suppress(Exception):
                cancel()

    # -------------------------------------------------------------------------
    # Hold detection (debounced state machine)
    # -------------------------------------------------------------------------

    async def _on_protobuf(self, message):
        """Intercept raw protobuf to track hold state frame-by-frame."""
        try:
            is_hold_present = any(
                GestureType(g.type) == GestureType.PINCH_HOLD
                for g in getattr(message, "gestures", [])
            )
        except Exception:
            is_hold_present = False

        self._update_hold_state(is_hold_present)
        await super()._on_protobuf(message)

    def _update_hold_state(self, is_hold_present: bool):
        """Update hold/release state with debouncing."""
        now = time.monotonic()

        if is_hold_present:
            self._release_started_at = None

            if self.is_holding:
                self._hold_started_at = None
                return

            # Start tracking potential hold
            if self._hold_started_at is None:
                self._hold_started_at = now
                return

            # Check if hold threshold reached
            if (now - self._hold_started_at) >= HOLD_DELAY:
                self.is_holding = True
                self._hold_started_at = None
                # Cancel any pending tap gestures
                self._cancel_task("_tap_off_task")
                self._cancel_task("_pending_gesture_timer")
                self._reset_tap_sequence()
                # Route to palm-up variant if palm is up
                if self._is_palm_up():
                    logger.info("Palm-Up Hold")
                    self._hold_osc_address = OSC_PALM_UP_TAP
                else:
                    logger.info("Hold")
                    self._hold_osc_address = OSC_TAP
                self._send(self._hold_osc_address, 1)
        else:
            self._hold_started_at = None

            if not self.is_holding:
                self._release_started_at = None
                return

            # Start tracking potential release
            if self._release_started_at is None:
                self._release_started_at = now
                return

            # Check if release threshold reached
            if (now - self._release_started_at) >= RELEASE_DELAY:
                self.is_holding = False
                self._release_started_at = None
                logger.info("Release")
                self._cancel_task("_tap_off_task")
                # Send 0 to whichever address the hold was using
                self._send(self._hold_osc_address, 0)

    # -------------------------------------------------------------------------
    # Tap detection (per GESTURE_DETECTION_LOGIC.md with optional waiting)
    # -------------------------------------------------------------------------

    def _is_palm_up(self) -> bool:
        """Check if palm is facing up based on quaternion orientation.
        
        Uses verticalCos (tilt from vertical) and supinationAngle (wrist rotation).
        See GESTURE_DETECTION_LOGIC.md for algorithm details.
        """
        qx, qy, qz, qw = self._orientation
        
        # Compute orientation vector from quaternion
        orient_x = 2 * (qx * qz + qw * qy)
        orient_y = 2 * (qy * qz - qw * qx)
        orient_z = 1 - 2 * (qx * qx + qy * qy)
        
        # verticalCos: how much the device is tilted from vertical
        vertical_cos = orient_x / 9.81
        
        # supinationAngle: wrist rotation angle in degrees
        supination_angle = abs(math.degrees(math.atan2(orient_y, orient_z)))
        
        # Palm-up: tilted from vertical AND wrist rotated past threshold
        return vertical_cos < VERTICAL_COS_THRESHOLD and supination_angle > SUPINATION_ANGLE_THRESHOLD

    def _get_tap_window(self, is_palm_up: bool) -> float:
        """Get the tap timing window based on palm orientation."""
        return DOUBLE_TAP_WINDOW_PALM_UP if is_palm_up else DOUBLE_TAP_WINDOW_PALM_DOWN

    def on_tap(self):
        """Called by SDK when a tap gesture is detected.
        
        Behavior depends on ENABLE_DOUBLE_TAP and ENABLE_TRIPLE_TAP:
        - If waiting enabled: delays emission to avoid spurious intermediate gestures
        - If waiting disabled: emits immediately (lower latency)
        """
        # Don't emit tap while holding
        if self.is_holding:
            return

        now = time.monotonic()
        
        # Calculate time since last tap
        time_since_last = now - self._last_tap_time
        
        # Debounce: ignore rapid duplicate tap events from SDK (hold model sends many)
        if self._last_tap_time > 0 and time_since_last < TAP_COOLDOWN:
            return
        
        # Also ignore taps that arrive shortly after a gesture was emitted (trailing SDK events)
        time_since_emit = now - self._last_emit_time
        if self._last_emit_time > 0 and time_since_emit < TAP_COOLDOWN:
            return
        
        is_palm_up = self._is_palm_up()
        window = self._get_tap_window(is_palm_up)
        
        # Check if this tap is within the double-tap window (continuation of sequence)
        is_continuation = self._tap_count > 0 and time_since_last < window
        
        # Increment sequence ID on every tap (used to detect stale timers)
        self._tap_sequence_id += 1
        current_seq_id = self._tap_sequence_id
        
        # Always update last tap time
        self._last_tap_time = now
        
        if is_continuation:
            # Continue existing sequence
            self._tap_count += 1
        else:
            # Start new sequence
            self._tap_count = 1
            self._pending_palm_up = is_palm_up
        
        # Cancel any pending emission timer (may not cancel in time due to race)
        self._cancel_task("_pending_gesture_timer")
        
        # Decide whether to emit now or wait
        if self._tap_count == 1:
            # First tap - always wait for hold check, optionally wait for double-tap
            if ENABLE_DOUBLE_TAP:
                # Wait for double-tap window (includes hold check)
                self._pending_gesture_timer = self._schedule(
                    self._emit_after_window(window, current_seq_id)
                )
            else:
                # Wait briefly to check if this is actually a hold starting
                self._pending_gesture_timer = self._schedule(
                    self._emit_after_hold_check(current_seq_id)
                )
        
        elif self._tap_count == 2:
            # Second tap
            if ENABLE_TRIPLE_TAP:
                # Wait to see if triple-tap is coming
                self._pending_gesture_timer = self._schedule(
                    self._emit_after_window(window, current_seq_id)
                )
            else:
                # Emit double tap immediately
                self._emit_tap_gesture(2, self._pending_palm_up)
                self._reset_tap_sequence()
        
        else:  # tap_count >= 3
            # Third+ tap - emit triple tap immediately (max gesture)
            self._emit_tap_gesture(3, self._pending_palm_up)
            self._reset_tap_sequence()

    async def _emit_after_hold_check(self, seq_id: int):
        """Wait for hold delay, then emit tap if not holding.
        
        Used when ENABLE_DOUBLE_TAP=False to avoid emitting tap before hold is detected.
        """
        await asyncio.sleep(HOLD_DELAY + 0.02)  # Slightly longer than hold detection
        
        # Check if stale or if hold started
        if seq_id != self._tap_sequence_id:
            return
        if self.is_holding or self._hold_started_at is not None:
            return  # Hold detected - don't emit tap
        
        # Not a hold - emit the tap
        if self._tap_count > 0:
            self._emit_tap_gesture(self._tap_count, self._pending_palm_up)
            self._reset_tap_sequence()

    async def _emit_after_window(self, window: float, seq_id: int):
        """Wait for tap window, then emit the accumulated gesture.
        
        Uses seq_id to detect if a new tap arrived (making this timer stale).
        """
        await asyncio.sleep(window)
        
        # Check if this timer is stale (a new tap arrived after we were scheduled)
        if seq_id != self._tap_sequence_id:
            return  # Stale timer - a new tap incremented the sequence ID
        
        # Check if hold started during the wait
        if self.is_holding or self._hold_started_at is not None:
            return  # Hold detected - don't emit tap
        
        # Emit whatever tap count we reached
        if self._tap_count > 0:
            self._emit_tap_gesture(self._tap_count, self._pending_palm_up)
            self._reset_tap_sequence()

    def _reset_tap_sequence(self):
        """Reset tap sequence state."""
        self._tap_count = 0
        self._last_tap_time = 0.0
        self._pending_palm_up = False

    def _emit_tap_gesture(self, count: int, is_palm_up: bool):
        """Emit tap gesture based on count."""
        # Record emit time for post-emit cooldown
        self._last_emit_time = time.monotonic()
        
        if count == 1:
            self._emit_single_tap(is_palm_up)
        elif count == 2:
            self._emit_double_tap(is_palm_up)
        else:
            self._emit_triple_tap(is_palm_up)

    def _emit_single_tap(self, is_palm_up: bool):
        """Emit single tap (or palm-up tap)."""
        if is_palm_up:
            logger.info("Palm-Up Tap")
            self._send(OSC_PALM_UP_TAP, 1)
            self._schedule(self._send_off_later(OSC_PALM_UP_TAP))
        else:
            logger.info("Tap")
            self._send(OSC_TAP, 1)
            self._cancel_task("_tap_off_task")
            self._tap_off_task = self._schedule(self._send_off_later(OSC_TAP))

    def _emit_double_tap(self, is_palm_up: bool):
        """Emit double tap (or palm-up double tap)."""
        if is_palm_up:
            logger.info("Palm-Up Double Tap")
            self._send(OSC_PALM_UP_DOUBLE_TAP, 1)
            self._schedule(self._send_off_later(OSC_PALM_UP_DOUBLE_TAP))
        else:
            logger.info("Double Tap")
            self._send(OSC_DOUBLE_TAP, 1)
            self._schedule(self._send_off_later(OSC_DOUBLE_TAP))

    def _emit_triple_tap(self, is_palm_up: bool):
        """Emit triple tap (or palm-up triple tap)."""
        if is_palm_up:
            logger.info("Palm-Up Triple Tap")
            self._send(OSC_PALM_UP_TRIPLE_TAP, 1)
            self._schedule(self._send_off_later(OSC_PALM_UP_TRIPLE_TAP))
        else:
            logger.info("Triple Tap")
            self._send(OSC_TRIPLE_TAP, 1)
            self._schedule(self._send_off_later(OSC_TRIPLE_TAP))

    async def _send_off_later(self, address: str):
        """Send value=0 after pulse duration for any OSC address."""
        await asyncio.sleep(PULSE_DURATION)
        self._send(address, 0)

    # -------------------------------------------------------------------------
    # DPAD (Left/Right) detection
    # -------------------------------------------------------------------------

    def on_gesture(self, gesture: GestureType):
        """Called by SDK for each gesture event."""
        # Tap and Hold are handled separately with debouncing
        if gesture in (GestureType.NONE, GestureType.PINCH_TAP, GestureType.PINCH_HOLD):
            return

        if gesture == GestureType.DPAD_LEFT:
            self._on_left()
            return

        if gesture == GestureType.DPAD_RIGHT:
            self._on_right()
            return

        logger.debug("Gesture: %s", _gesture_name(gesture))

    def _on_left(self):
        """Handle left swipe."""
        now = time.monotonic()
        if self._last_left_at and (now - self._last_left_at) < DPAD_COOLDOWN:
            return
        self._last_left_at = now

        logger.info("Left")
        self._send(OSC_LEFT, 1)
        self._schedule(self._send_left_off())

    def _on_right(self):
        """Handle right swipe."""
        now = time.monotonic()
        if self._last_right_at and (now - self._last_right_at) < DPAD_COOLDOWN:
            return
        self._last_right_at = now

        logger.info("Right")
        self._send(OSC_RIGHT, 1)
        self._schedule(self._send_right_off())

    async def _send_left_off(self):
        """Send left=0 after pulse duration."""
        await asyncio.sleep(PULSE_DURATION)
        self._send(OSC_LEFT, 0)

    async def _send_right_off(self):
        """Send right=0 after pulse duration."""
        await asyncio.sleep(PULSE_DURATION)
        self._send(OSC_RIGHT, 0)

    # -------------------------------------------------------------------------
    # Haptics (incoming OSC triggers vibration)
    # -------------------------------------------------------------------------

    def _on_haptic_intensity(self, _address: str, *args: Any):
        """Handle incoming /vib/intensity OSC message."""
        self._haptic_intensity = float(args[0]) if args else None
        self._try_trigger_haptics()

    def _on_haptic_duration(self, _address: str, *args: Any):
        """Handle incoming /vib/duration OSC message."""
        self._haptic_duration_ms = int(args[0]) if args else None
        self._try_trigger_haptics()

    def _try_trigger_haptics(self):
        """Trigger haptics if both intensity and duration are set, then reset."""
        if self._haptic_intensity is None or self._haptic_duration_ms is None:
            return
        self.trigger_haptics(self._haptic_intensity, self._haptic_duration_ms)
        # Reset so next trigger requires both values again
        self._haptic_intensity = None
        self._haptic_duration_ms = None

    # -------------------------------------------------------------------------
    # Sensor data (forwarded as OSC)
    # -------------------------------------------------------------------------

    def on_sensors(self, sensors: Any):
        """Forward sensor data as OSC and track orientation for palm detection."""
        self._send("/angular-velocity", sensors.angular_velocity)
        self._send("/gravity", sensors.gravity)
        self._send("/acceleration", sensors.acceleration)
        self._send("/orientation", sensors.orientation)

        # Track quaternion orientation for palm-up detection
        # Orientation is (qx, qy, qz) - we compute qw from unit quaternion constraint
        if sensors.orientation and len(sensors.orientation) >= 3:
            qx, qy, qz = sensors.orientation[0], sensors.orientation[1], sensors.orientation[2]
            # qw = sqrt(max(0, 1 - qx² - qy² - qz²)) for unit quaternion
            qw_sq = max(0.0, 1.0 - qx * qx - qy * qy - qz * qz)
            qw = math.sqrt(qw_sq)
            self._orientation = (qx, qy, qz, qw)

    # -------------------------------------------------------------------------
    # Touch screen (forwarded as OSC)
    # -------------------------------------------------------------------------

    def on_touch_down(self, x: float, y: float):
        self._send("/touch-down", [x, y])

    def on_touch_up(self, x: float, y: float):
        self._send("/touch-up", [x, y])

    def on_touch_move(self, x: float, y: float):
        self._send("/touch-move", [x, y])

    # -------------------------------------------------------------------------
    # Other inputs
    # -------------------------------------------------------------------------

    def on_rotary(self, direction: int):
        """Handle rotary dial input."""
        self._send("/rotary", direction)

    def on_back_button(self):
        """Handle back button press."""
        self._send(OSC_BACK_BUTTON, 1)
        self.trigger_haptics(1.0, 20)
        self._schedule(self._send_back_button_off())

    async def _send_back_button_off(self):
        await asyncio.sleep(PULSE_DURATION)
        self._send(OSC_BACK_BUTTON, 0)

    # -------------------------------------------------------------------------
    # Connection callbacks
    # -------------------------------------------------------------------------

    def on_connect(self):
        """Called when watch connects."""
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        logger.info("Ready. Perform a gesture now (Tap).")

    def on_info_update(self):
        """Called when watch info updates (e.g. model changes)."""
        # Log hand when first detected (useful for palm-up detection)
        if self.hand != Hand.NONE and self.hand != self._last_logged_hand:
            hand_name = "left" if self.hand == Hand.LEFT else "right"
            logger.info("Detected %s hand", hand_name)
            logger.info("Note: Swipe/Hold require different models. Switch via watch menu or right button.")
            self._last_logged_hand = self.hand

        # Log model changes at debug level
        current_model = frozenset(self.active_model)
        if current_model != self._last_logged_model:
            logger.debug("Active gestures: %s", _gesture_list(self.active_model))
            self._last_logged_model = current_model

        # Handle manual model selection
        if self._requested_model_index is None or self._model_requested:
            return
        if not self.available_models:
            return

        if not (0 <= self._requested_model_index < len(self.available_models)):
            logger.warning("Model index %d out of range (0..%d)",
                           self._requested_model_index,
                           len(self.available_models) - 1)
            self._model_requested = True
            return

        model = self.available_models[self._requested_model_index]
        logger.info("Requesting model %d: %s",
                    self._requested_model_index, _gesture_list(model))
        self.request_model(model)
        self._model_requested = True


# =============================================================================
# MAIN
# =============================================================================

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Bridge Touch SDK gestures to OSC messages"
    )
    parser.add_argument("--ip", default=DEFAULT_IP,
                        help=f"IP address (default: {DEFAULT_IP})")
    parser.add_argument("--client-port", type=int, default=DEFAULT_SEND_PORT,
                        help=f"Port to send OSC to (default: {DEFAULT_SEND_PORT})")
    parser.add_argument("--server-port", type=int, default=DEFAULT_LISTEN_PORT,
                        help=f"Port to receive OSC on (default: {DEFAULT_LISTEN_PORT})")
    parser.add_argument("--name-filter", default=None,
                        help="Only connect to watches matching this name")
    parser.add_argument("--model-index", type=int, default=None,
                        help="Request a specific gesture model by index")
    parser.add_argument("--verbose", action="store_true",
                        help="Show debug output")
    parser.add_argument("--test", action="store_true",
                        help="Test mode: send random OSC data without watch (Ctrl+C to stop)")
    return parser.parse_args()


async def run_test_mode(ip: str, send_port: int):
    """Send random OSC test data for testing without a watch.
    
    Sends: taps, double-taps, hold/release, left/right, and sensor data.
    Runs until cancelled with Ctrl+C.
    """
    client = SimpleUDPClient(ip, send_port)
    logger.info("TEST MODE: Sending random OSC data to %s:%d (Ctrl+C to stop)", ip, send_port)
    logger.info("Gestures: tap, double-tap, triple-tap, hold/release, left, right")
    logger.info("Sensors: orientation, acceleration, gravity, angular-velocity")
    
    start_time = time.monotonic()
    gesture_interval = 0.8  # Time between gestures
    sensor_interval = 0.05  # 20Hz sensor data
    last_gesture_time = 0.0
    last_sensor_time = 0.0
    is_holding = False
    
    gestures = [
        (OSC_TAP, "Tap"),
        (OSC_DOUBLE_TAP, "Double Tap"),
        (OSC_TRIPLE_TAP, "Triple Tap"),
        (OSC_PALM_UP_TAP, "Palm-Up Tap"),
        (OSC_LEFT, "Left"),
        (OSC_RIGHT, "Right"),
        ("hold", "Hold"),  # Special case
    ]
    
    while True:
        now = time.monotonic()
        elapsed = now - start_time
        
        # Send sensor data at high frequency
        if (now - last_sensor_time) >= sensor_interval:
            last_sensor_time = now
            # Generate smooth fake sensor data using time-based oscillation
            t = elapsed * 2
            client.send_message("/orientation", [
                math.sin(t * 0.5) * 0.3,
                math.cos(t * 0.7) * 0.3,
                math.sin(t * 0.3) * 0.3,
            ])
            client.send_message("/acceleration", [
                math.sin(t) * 2.0,
                math.cos(t * 1.3) * 2.0,
                9.81 + math.sin(t * 0.5) * 0.5,
            ])
            client.send_message("/gravity", [
                math.sin(t * 0.2) * 0.5,
                math.cos(t * 0.3) * 0.5,
                9.81,
            ])
            client.send_message("/angular-velocity", [
                math.sin(t * 2) * 0.5,
                math.cos(t * 2.5) * 0.5,
                math.sin(t * 1.5) * 0.5,
            ])
        
        # Send gestures at intervals
        if (now - last_gesture_time) >= gesture_interval:
            last_gesture_time = now
            
            # Handle hold state
            if is_holding:
                logger.info("Release")
                client.send_message(OSC_TAP, 0)
                is_holding = False
            else:
                # Pick random gesture
                address, name = random.choice(gestures)
                
                if address == "hold":
                    logger.info("Hold")
                    client.send_message(OSC_TAP, 1)
                    is_holding = True
                else:
                    logger.info(name)
                    client.send_message(address, 1)
                    await asyncio.sleep(PULSE_DURATION)
                    client.send_message(address, 0)
        
        await asyncio.sleep(0.01)


async def run_watch(watch: OscBridgeWatch):
    """Run the watch with proper signal handling and cleanup."""
    loop = asyncio.get_running_loop()
    watch._loop = loop

    def request_stop():
        logger.info("Stopping...")
        watch.stop()

    with contextlib.suppress(NotImplementedError):
        loop.add_signal_handler(signal.SIGINT, request_stop)
        loop.add_signal_handler(signal.SIGTERM, request_stop)

    try:
        await watch.run()
    finally:
        # Give Bleak/CoreBluetooth time to clean up
        connector = getattr(watch, "_connector", None)
        if connector:
            with contextlib.suppress(Exception):
                await connector.stop()
        await asyncio.sleep(0.25)


def main() -> int:
    """Entry point."""
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
        force=True,
    )

    # Test mode: send random data without watch
    if args.test:
        try:
            asyncio.run(run_test_mode(args.ip, args.client_port))
        except KeyboardInterrupt:
            logger.info("Interrupted")
        return 0

    watch = OscBridgeWatch(
        ip=args.ip,
        send_port=args.client_port,
        listen_port=args.server_port,
        name_filter=args.name_filter,
        model_index=args.model_index,
    )
    watch.start_osc_server()

    try:
        asyncio.run(run_watch(watch))
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        watch.stop()
        watch.stop_osc_server()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
