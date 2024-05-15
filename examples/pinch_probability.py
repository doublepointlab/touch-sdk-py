from touch_sdk import Watch

class MyWatch(Watch):

    def on_gesture_probability(self, prob):
        print(f'pinch probability: {prob}')


watch = MyWatch()
watch.start()
