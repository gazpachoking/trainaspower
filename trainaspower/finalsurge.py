import json
from datetime import timedelta
from itertools import count

import requests


finalsurge_session = requests.Session()


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
    finalsurge_session.headers.update(
        {"Authorization": f"Bearer {login_info['data']['token']}"}
    )


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


def check_workout_exists(workout):
    params = {
        "request": "WorkoutList",
        "scope": "USER",
        "scopekey": "123a8bc7-3911-4960-9b79-dfaa163c69b2",
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
    if check_workout_exists(workout):
        return
    wo = convert_workout(workout)
    params = {
        "request": "WorkoutSave",
        "scope": "USER",
        "scope_key": "123a8bc7-3911-4960-9b79-dfaa163c69b2",
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
                "planned_amount": workout.distance,
                "planned_amount_type": "mi",
                "planned_duration": workout.duration.total_seconds(),
            },
        },
    )
    wo_key = add_wo.json()["new_workout_key"]
    params = {
        "request": "WorkoutBuilderSave",
        "scope": "USER",
        "scopekey": "123a8bc7-3911-4960-9b79-dfaa163c69b2",
        "workout_key": wo_key,
    }
    finalsurge_session.post(
        "https://beta.finalsurge.com/api/Data", params=params, json=wo
    )