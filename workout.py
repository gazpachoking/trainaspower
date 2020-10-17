from collections import namedtuple


Range = namedtuple("Range", ["min", "max"])


class Workout:
    def __init__(self):
        self.name = ""
        self.description = ""
        self.steps = []
        self.date = None
        self.id = None


class Step:
    def __init__(self, description=""):
        self.description = description


class ConcreteStep(Step):
    def __init__(self):
        super().__init__()
        self.power_range = Range(0, 0)
        self.pace_range = Range(0, 0)
        self.length = 0
        self.type = "WARMUP"


class RepeatStep(Step):
    def __init__(self, repetitions):
        super().__init__(
            f"Repeat the following steps {repetitions} time{'s' if repetitions>1 else ''}."
        )
        self.repetitions = repetitions
        self.steps = []
