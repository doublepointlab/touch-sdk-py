from touch_sdk import Watch

class MyWatch(Watch):

    def on_gesture_probability(self, probs):
        print(f'Probabilities: {probs}')


watch = MyWatch()
watch.start()
