from touch_sdk import Watch
import logging
import time
from collections import deque
from enum import Enum


logging.basicConfig(level=logging.INFO)


class Flick(Enum):
    """Enumeration of possible flick gestures."""
    Tap = 0    # Just a tap without movement
    Up = 1     # Flick upward after tap
    Down = 2   # Flick downward after tap
    Left = 3   # Flick leftward after tap
    Right = 4  # Flick rightward after tap


class FlickDetector:
    """Detects flick gestures based on tap and subsequent movement.
    
    The detector works by monitoring sensor data after a tap is detected.
    It analyzes the movement pattern to determine if a flick occurred and in which direction.
    
    Attributes:
        left_handed (bool): Set to True for left-handed mode, False for right-handed
        screen_rotated (bool): Set to True if the screen orientation is rotated
    
    Example:
        ```python
        # Create a detector with custom sensitivity
        detector = FlickDetector(
            flick_initiation_threshold=25.0,  # More sensitive
            flick_delay_ms=150,              # Longer window to detect flick
            scale=8.0                        # Increased movement scaling
        )
        
        # Use in your Watch class
        def on_sensors(self, sensors):
            detector.update()
            detector.on_sensors(sensors)
            if gesture := detector.get():
                print(f"Detected {gesture.name}")
        ```
    """

    def __init__(
        self,
        flick_initiation_threshold: float = 30.0,
        flick_delay_ms: int = 100,
        flick_min_interval: int = 300,
        scale: float = 6.0,
        update_interval: float = 2.0,
    ):
        """Initialize the FlickDetector with customizable parameters.
        
        Args:
            flick_initiation_threshold (float): Minimum movement magnitude to trigger a flick.
                                              Lower values make detection more sensitive.
                                              Default: 30.0
            flick_delay_ms (int): Time window in milliseconds after a tap to detect a flick.
                                Increase for slower flick gestures.
                                Default: 100
            flick_min_interval (int): Minimum time in milliseconds between flick detections.
                                    Prevents rapid-fire flicks.
                                    Default: 300
            scale (float): Movement scaling factor. Higher values make flicks more responsive
                         but potentially more erratic.
                         Default: 6.0
            update_interval (float): Sensor data update interval in milliseconds.
                                  Default: 2.0
        """
        self.scale = scale
        self.update_interval = update_interval

        self.left_handed = True
        self.screen_rotated = True

        self.flick_initiation_threshold = flick_initiation_threshold
        self.flick_delay_ms = flick_delay_ms
        self.flick_min_interval = flick_min_interval

        self.tap_detected = False
        self.flick_timeout = False

        self.tap_time = 0
        self.flick_reset_time = 0

        self.flick_queue = deque()

    def on_sensors(self, sensors):
        """Process new sensor data to detect flick gestures.
        
        This method analyzes gyroscope and gravity data to determine flick direction
        after a tap has been detected.
        
        Args:
            sensors: Sensor data object containing angular_velocity (gyroscope)
                    and gravity vectors.
        """
        gyro = sensors.angular_velocity or (0.0, 0.0, 0.0)
        grav = sensors.gravity or (9.81, 0.0, 0.0)

        gyro_y, gyro_z = gyro[1], gyro[2]
        grav_y, grav_z = grav[1], grav[2]

        sign_l = -1 if self.left_handed else 1
        sign_r = -1 if self.screen_rotated else 1
        sign = sign_l * sign_r

        # Calculate movement in x and y directions
        dx = self.scale * self.update_interval * (-gyro_z * grav_z - gyro_y * grav_y)
        dy = sign * self.scale * self.update_interval * (gyro_z * grav_y - gyro_y * grav_z)

        if self.tap_detected and not self.flick_timeout:
            # Check for vertical flick (up/down)
            if abs(dy) > self.flick_initiation_threshold and abs(dy / dx) > 2:
                self._output_flick(Flick.Down if dy > 0 else Flick.Up)
            # Check for horizontal flick (left/right)
            elif abs(dx) > self.flick_initiation_threshold and abs(dx / dy) > 2:
                self._output_flick(Flick.Right if dx > 0 else Flick.Left)
            else:
                self._output_flick(Flick.Tap)

    def _output_flick(self, gesture):
        """Internal method to output a detected flick gesture.
        
        Args:
            gesture (Flick): The detected flick gesture enum value.
        """
        self.tap_detected = False
        self.flick_timeout = True
        self.flick_reset_time = self._now() + self.flick_min_interval
        self.flick_queue.append(gesture)

    def on_tap(self):
        """Call this method when a tap is detected to start watching for flicks."""
        self.tap_detected = True
        self.tap_time = self._now() + self.flick_delay_ms

    def get(self):
        """Get the next detected flick gesture from the queue.
        
        Returns:
            Flick: The next flick gesture, or None if queue is empty.
        """
        return self.flick_queue.popleft() if self.flick_queue else None

    def clear(self):
        """Clear the current tap detection state."""
        self.tap_detected = False

    def update(self, now_ms=None):
        """Update internal timers and states.
        
        Should be called regularly, typically in the on_sensors handler.
        
        Args:
            now_ms (int, optional): Current time in milliseconds.
                                  If None, uses internal time source.
        """
        now = now_ms if now_ms is not None else self._now()
        if self.tap_detected and now > self.tap_time:
            self.tap_detected = False
        if self.flick_timeout and now > self.flick_reset_time:
            self.flick_timeout = False

    def _now(self):
        """Get current time in milliseconds."""
        return int(time.time() * 1000)


class MyWatch(Watch):
    """Example Watch implementation using the FlickDetector.
    
    This example shows how to integrate FlickDetector into your Watch class
    and process flick gestures.
    """

    def __init__(self):
        super().__init__()
        # Create FlickDetector with default parameters
        # Adjust these parameters to change flick detection sensitivity
        self.flick_detector = FlickDetector(
            flick_initiation_threshold=30.0,  # Minimum movement to trigger a flick
            flick_delay_ms=100,              # Time window after tap to detect flick
            flick_min_interval=300,          # Minimum time between flicks
            scale=6.0,                       # Movement scaling factor
            update_interval=2.0              # Sensor update interval
        )

    def on_tap(self):
        self.flick_detector.on_tap()

    def on_sensors(self, sensors):
        self.flick_detector.update()
        self.flick_detector.on_sensors(sensors)
        gesture = self.flick_detector.get()
        if gesture:
            print("Detected:", gesture.name)


# Create and start the watch
watch = MyWatch()
watch.start()
