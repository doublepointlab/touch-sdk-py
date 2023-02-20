from touch_sdk import Watch

class RayCastingWatch(Watch):

    def __init__(self, name=None):
        super().__init__(name)

        self.ray_x = 0
        self.ray_y = 0

    def on_arm_direction_change(self, delta_x, delta_y):
        speed = 3

        # Integrate
        self.ray_x += delta_x * speed
        self.ray_y += delta_y * speed

        # Box clamp (optional)
        size = 100
        self.ray_x = max(-size, min(size, self.ray_x))
        self.ray_y = max(-size, min(size, self.ray_y))

        # Output
        print('raycasting\t{:.1f}\t{:.1f}'.format(self.ray_x, self.ray_y))

    def on_tap(self):
        print('tap')


watch = RayCastingWatch()
watch.start()
