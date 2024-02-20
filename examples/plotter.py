# To use this example, make sure to install extra dependencies:
# pip install matplotlib numpy

from threading import Thread
from queue import Queue, Empty
from collections import deque

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from touch_sdk import Watch
import logging
# Get helpful log info
logging.basicConfig(level=logging.INFO)


class MyWatch(Watch):
    def __init__(self, name=""):
        super().__init__(name)
        self.sensor_queue = Queue()

    def on_sensors(self, sensors):
        self.sensor_queue.put(sensors)


def anim(_, watch, ax, lines, gyro_data):

    while True:
        try:
            sensors = watch.sensor_queue.get(block=False)
        except Empty:
            break

        gyro_data.append(sensors.angular_velocity)

    while len(gyro_data) > 100:
        gyro_data.popleft()

    if len(gyro_data) == 0:
        return (ax,)

    arr = np.array(gyro_data).T

    ymax, ymin = np.max(arr), np.min(arr)
    range = max(abs(ymax), abs(ymin))
    ax.set_ylim(range, -range)

    x = np.arange(arr.shape[1])
    for line, data in zip(lines, arr):
        line.set_data(x, data)

    return lines


if __name__ == "__main__":
    fig, ax = plt.subplots()

    ax.set_xlim(0, 100)
    lines = ax.plot(np.zeros((0, 3)))

    watch = MyWatch()
    thread = Thread(target=watch.start)
    thread.start()

    gyro_data = deque()

    _ = FuncAnimation(
        fig, anim, fargs=(watch, ax, lines, gyro_data), interval=1, blit=True,
        cache_frame_data=False
    )

    plt.show()
    watch.stop()
    thread.join()
