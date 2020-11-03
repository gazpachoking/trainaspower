import datetime
from typing import List, NamedTuple, Union

from pint import UnitRegistry, Quantity


ureg = UnitRegistry()
mile = ureg.mile
kilometer = ureg.kilometer
second = ureg.second


class PowerRange(NamedTuple):
    min: Union[float, int]
    max: Union[float, int]


class PaceRange(NamedTuple):
    min: int
    max: int


class Workout:
    name: str
    description: str
    steps: List["Step"]
    date: datetime.date
    id: str
    duration: datetime.timedelta
    distance: Quantity


class Step:
    description: str
    type: str


class ConcreteStep(Step):
    power_range: PowerRange
    pace_range: PaceRange
    length: Quantity


class RepeatStep(Step):
    repetitions: int
    steps: List["Step"]

    def __init__(self, repetitions):
        super().__init__()
        self.description = f"Repeat the following steps {repetitions} time{'s' if repetitions>1 else ''}."
        self.repetitions = repetitions
        self.type = "REPEAT"
