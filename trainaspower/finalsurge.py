import json
from itertools import count

import requests
from loguru import logger

finalsurge_session = requests.Session()


user_key = "NOT LOGGED IN"


def login(email, password) -> None:
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
        "durationType": "TIME" if step.length.check("[time]") else "DISTANCE",
        "duration": (
            round(step.length.to("seconds").magnitude)
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


def check_workout_exists(workout):
    logger.debug(f"Checking `{workout.name}` exists on Final Surge")
    params = {
        "request": "WorkoutList",
        "scope": "USER",
        "scopekey": user_key,
        "startdate": workout.date.strftime("%Y-%m-%d"),
        "enddate": workout.date.strftime("%Y-%m-%d"),
        "ishistory": False,
        "completedonly": False,
    }
    data = finalsurge_session.get(
        "https://beta.finalsurge.com/api/Data", params=params
    ).json()
    if any(workout.id in w["name"] for w in data["data"]):
        return True
    return False


def add_workout(workout):
    logger.info("Posting workout to Final Surge")
    if check_workout_exists(workout):
        logger.info(f"Workout {workout.name} already exists on Final Surge")
        return
    wo = convert_workout(workout)
    params = {
        "request": "WorkoutSave",
        "scope": "USER",
        "scope_key": user_key,
    }

    add_wo = finalsurge_session.post(
        "https://beta.finalsurge.com/api/Data",
        params=params,
        json={
            "key": None,
            "workout_date": workout.date.isoformat(),
            "order": 1,
            "name": workout.name,
            "description": "",
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
