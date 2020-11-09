import datetime
from typing import List, NamedTuple, Union

from pint import UnitRegistry, Quantity
from pydantic import BaseModel


ureg = UnitRegistry()
mile = ureg.mile
kilometer = ureg.kilometer
second = ureg.second
minute = ureg.minute


class Config(BaseModel):
    stryd_email: str
    stryd_password: str
    trainasone_email: str
    trainasone_password: str
    finalsurge_email: str
    finalsurge_password: str


class PowerRange(NamedTuple):
    min: Union[float, int]
    max: Union[float, int]


class PaceRange(NamedTuple):
    min: Quantity
    max: Quantity


class Workout:
    name: str
    description: str
    steps: List["Step"]
    date: datetime.date
    id: str
    duration: Quantity
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
