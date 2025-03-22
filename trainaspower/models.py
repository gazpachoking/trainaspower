import builtins
import datetime
from dataclasses import dataclass
from typing import List, NamedTuple, Union, Tuple, Any, Optional

from loguru import logger
from pint import UnitRegistry, Quantity
from pydantic import BaseModel, Field, validator

ureg = UnitRegistry()
mile = ureg.mile
kilometer = ureg.kilometer
meter = ureg.meter
second = ureg.second
minute = ureg.minute


class Config(BaseModel):
    stryd_email: str
    stryd_password: str
    trainasone_email: str
    trainasone_password: str
    finalsurge_email: str
    finalsurge_password: str
    power_adjust: Tuple[Union[float, int], Union[float, int]] = (0, 0)
    number_of_workouts: int = 1
    include_runback_step: bool = False
    pace_only: bool = False
    # Old config values
    recovery_pace_adjust: Any = Field(removed='Field `power_adjust` has been added instead')
    very_easy_pace_adjust: Any = Field(removed='Field `power_adjust` has been added instead')
    easy_pace_adjust: Any = Field(removed='Field `power_adjust` has been added instead')
    fast_pace_adjust: Any = Field(removed='Field `power_adjust` has been added instead')
    extreme_pace_adjust: Any = Field(removed='Field `power_adjust` has been added instead.')

    @validator('*')
    def warn_removed(cls, v, field):
        removed = field.field_info.extra.get('removed')
        if removed:
            message = f'Config field `{field.name}` was removed.'
            if isinstance(removed, str):
                message += f' {removed}'
            logger.warning(message)
        return v

    class Config:
        extra = 'forbid'


@dataclass
class PowerRange:
    min: Union[float, int]
    max: Union[float, int]

    def __init__(self, min_val, max_val):
        self.min = max(0, min_val)
        self.max = max_val

    def __add__(self, other):
        new = PowerRange(self.min, self.max)
        if not len(other) == 2:
            raise ValueError(f'Cannot add {repr(other)} to PowerRange')
        new.min = builtins.max(0, self.min + other[0])
        new.max += other[1]
        return new


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
    length: Optional[Quantity]


class RepeatStep(Step):
    repetitions: int
    steps: List["Step"]

    def __init__(self, repetitions):
        super().__init__()
        self.description = f"Repeat the following steps {repetitions} time{'s' if repetitions>1 else ''}."
        self.repetitions = repetitions
        self.type = "REPEAT"
