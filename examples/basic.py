from touch_sdk import Watch

class MyWatch(Watch):

    # def on_sensors(self, sensors):
    #     print(sensors)

    def on_tap(self):
        print('tap')

    def on_touch_down(self, x, y):
        print('touch down', x, y)

    def on_touch_up(self, x, y):
        print('touch up', x, y)

    def on_touch_move(self, x, y):
        print('touch move', x, y)

    def on_rotary(self, direction):
        print('rotary', direction)

    def on_back_button(self):
        print('back button')

watch = MyWatch()
watch.start()
