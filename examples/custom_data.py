from touch_sdk import Watch
import logging
# Get helpful log info
logging.basicConfig(level=logging.INFO)

class CustomDataWatch(Watch):

    custom_data = {
        "4b574af1-72d7-45d2-a1bb-23cd0ec20c57": ">3f"
    }

    def on_custom_data(self, uuid, content):
        print(content)

watch = CustomDataWatch()
watch.start()
