from touch_sdk import Watch, GestureType
import logging

# Get helpful log info
logging.basicConfig(level=logging.INFO)


class MyWatch(Watch):

    def on_gesture(self, gesture):
        if gesture != GestureType.NONE:
            print("Gesture:", gesture)

    def on_connect(self):
        print("Following models are available:")
        for i, m in enumerate(self.available_models):
            print("{}:".format(i), m)

        print("Requesting last of the list")
        # This may take a second or two
        self.request_model(self.available_models[-1])

    def on_info_update(self):
        print("Active model:", self.active_model)


watch = MyWatch()
watch.start()
