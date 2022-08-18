class SQS_Queue():
    # Connect to the SQS Queue
    def __init__(self, name, *args, **kwargs):
        self.currentM = None
        self.name = name

    def task_done(self):
        pass

    def reset_message(self):
        pass