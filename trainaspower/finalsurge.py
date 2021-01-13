import json
from datetime import timedelta, date
from itertools import count
from typing import Optional, Union

import requests
from loguru import logger

from trainaspower import models

finalsurge_session = requests.Session()


user_key = "NOT LOGGED IN"


def login(email: str, password: str) -> None:
    login_params = {
        "email": email,
        "password": password,
        "deviceManufacturer": "",
        "deviceModel": "Netscape",
        "deviceOperatingSystem": "Win32",
        "deviceUniqueIdentifier": "",
    }
    r = finalsurge_session.post(
        "https://beta.finalsurge.com/api/Data?request=login",
        data=json.dumps(login_params).replace(" ", ""),
    )
    login_info = r.json()
    if not login_info["success"]:
        raise Exception("Failed to log in to Final Surge")
    finalsurge_session.headers.update(
        {"Authorization": f"Bearer {login_info['data']['token']}"}
    )
    global user_key
    user_key = login_info["data"]["user_key"]


def convert_workout(workout: models.Workout) -> dict:
    counter = count(1)
    result = {
        "target_options": [
            {
                "name": workout.name,
                "sport": "running",
                "steps": [convert_step(s, counter) for s in workout.steps],
                "target": "power",
            }
        ],
        "target_override": None,
    }
    return result


def convert_step(step: models.Step, id_counter) -> dict:
    if isinstance(step, models.RepeatStep):
        return convert_repeat(step, id_counter)
    if not isinstance(step, models.ConcreteStep):
        raise ValueError(f"unknown step type received {step.type}")
    s = {
        "type": "step",
        "id": next(id_counter),
        "name": None,
        "durationType": "TIME" if step.length.check("[time]") else "DISTANCE",
        "duration": (
            str(timedelta(seconds=step.length.to("seconds").magnitude))
            if step.length.check("[time]")
            else 0
        ),
        "targetAbsOrPct": "",
        "durationDist": 0 if step.length.check("[time]") else step.length.magnitude,
        "data": [],
        "distUnit": f"{step.length.units:~}" if step.length.check("[length]") else "mi",
        "target": [
            {
                "targetType": "power",
                "zoneBased": False,
                "targetLow": round(step.power_range.min),
                "targetHigh": round(step.power_range.max),
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


def convert_repeat(step: models.RepeatStep, id_counter) -> dict:
    return {
        "type": "repeat",
        "name": None,
        "id": next(id_counter),
        "data": [convert_step(s, id_counter) for s in step.steps],
        "repeats": step.repetitions,
        "durationType": "OPEN",
        "comments": None,
    }


def get_existing_tap_workout(wo_date: date) -> Optional[str]:
    """Checks if TrainAsPower already has an (uncompleted) workout on the same day as given workout."""
    logger.debug(f"Checking TrainAsPower workout exists on Final Surge")
    params = {
        "request": "WorkoutList",
        "scope": "USER",
        "scopekey": user_key,
        "startdate": wo_date.strftime("%Y-%m-%d"),
        "enddate": wo_date.strftime("%Y-%m-%d"),
        "ishistory": False,
        "completedonly": False,
    }
    data = finalsurge_session.get(
        "https://beta.finalsurge.com/api/Data", params=params
    ).json()
    for existing_workout in data["data"]:
        if existing_workout["workout_completion"] == 1:
            continue
        if "TrainAsPower" in (existing_workout["description"] or ""):
            return existing_workout["key"]
    return None


def add_workout(workout: models.Workout) -> None:
    wo_key = get_existing_tap_workout(workout.date)
    if wo_key:
        logger.info(f"Updating workout `{workout.name}` on Final Surge")
    else:
        logger.info(f"Posting workout `{workout.name}` to Final Surge")
    wo = convert_workout(workout)
    params = {"request": "WorkoutSave", "scope": "USER", "scope_key": user_key}

    add_wo = finalsurge_session.post(
        "https://beta.finalsurge.com/api/Data",
        params=params,
        json={
            "key": wo_key,
            "workout_date": workout.date.isoformat(),
            "order": 1,
            "name": workout.name,
            "description": "TrainAsPower converted workout",
            "is_race": False,
            "Activity": {
                "activity_type_key": "00000001-0001-0001-0001-000000000001",
                "activity_type_name": "Run",
                "planned_amount": workout.distance.magnitude,
                "planned_amount_type": f"{workout.distance.units:~}",
                "planned_duration": round(workout.duration.to("seconds").magnitude),
            },
        },
    )
    if not wo_key:
        wo_key = add_wo.json()["new_workout_key"]
    params = {
        "request": "WorkoutBuilderSave",
        "scope": "USER",
        "scopekey": user_key,
        "workout_key": wo_key,
    }
    finalsurge_session.post(
        "https://beta.finalsurge.com/api/Data", params=params, json=wo
    )


def remove_workout(wo_date: date) -> None:
    wo_key = get_existing_tap_workout(wo_date)
    if not wo_key:
        return
    logger.info(f"Deleting existing TrainAsPower workout `{wo_key}`")
    params = {
        "request": "WorkoutDelete",
        "scope": "USER",
        "scopekey": user_key,
        "workout_key": wo_key,
    }
    response = finalsurge_session.get(
        "https://beta.finalsurge.com/api/Data", params=params
    )