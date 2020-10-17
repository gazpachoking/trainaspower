from datetime import timedelta
from itertools import count


def convert_workout(workout):
    counter = count(1)
    result = {
        "target_options": [
            {
                "name": workout.name,
                "sport": "running",
                "steps": [convert_step(s, counter) for s in workout.steps],
            }
        ],
        "target_override": None,
    }
    return result


def convert_step(step, id_counter):
    if hasattr(step, "repetitions"):
        return convert_repeat(step, id_counter)
    s = {
        "type": "step",
        "id": next(id_counter),
        "name": None,
        "durationType": "TIME" if isinstance(step.length, timedelta) else "DISTANCE",
        "duration": str(step.length) if isinstance(step.length, timedelta) else 0,
        "targetAbsOrPct": "",
        "durationDist": 0 if isinstance(step.length, timedelta) else step.length,
        "data": [],
        "distUnit": "mi",
        "target": [
            {
                "targetType": "power",
                "zoneBased": False,
                "targetLow": step.power_range.min,
                "targetHigh": step.power_range.max,
                "targetOption": None,
                "targetIsTimeBased": False,
                "zone": 0,
            },
            {
                "targetType": "open",
                "zoneBased": False,
                "targetLow": "0",
                "targetHigh": "0",
                "targetOption": "",
                "targetIsTimeBased": False,
                "zone": 0,
            },
        ],
        "intensity": step.type,
        "comments": None,
    }
    return s


def convert_repeat(step, id_counter):
    return {
        "type": "repeat",
        "name": None,
        "id": next(id_counter),
        "data": [convert_step(s, id_counter) for s in step.steps],
        "repeats": step.repetitions,
        "durationType": "OPEN",
        "comments": None,
    }
