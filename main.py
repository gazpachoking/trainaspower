from datetime import timedelta
from functools import lru_cache
import re
import json

import dateparser
import requests
import requests_html
import yaml

import workout
import finalsurge

with open("creds.yaml") as f:
    creds = yaml.safe_load(f)

# "course_id=0&race_distance=1609.34&surface=road&training_elevation=288.9503907535875&race_elevation=288.9503907535875&training_temperature=22.77777777777778&race_temperature=22.77777777777778&training_humidity=0.5&race_humidity=0.5&target_time=330&depth=complete"
prediction_url = "https://www.stryd.com/b/api/v1/users/race/prediction"
params = {
    "course_id": 0,
    "race_distance": 1609.34,
    "surface": "road",
    "training_elevation": 288,
    "race_elevation": 288,
    "training_temperature": 22,
    "race_temperature": 22,
    "training_humidity": 0.5,
    "race_humidity": 0.5,
    "target_time": 330,
    "depth": "complete",
}
stryd_session = requests.Session()
tao_session = requests_html.HTMLSession()
finalsurge_session = requests.Session()
tao_user_id = ""


def stryd_login(session: requests.Session) -> None:
    r = session.post(
        "https://www.stryd.com/b/email/signin",
        json={"email": creds["stryd_email"], "password": creds["stryd_password"]},
    )
    login_info = r.json()
    session.headers.update({"Authorization": f"Bearer: {login_info['token']}"})


def tao_login(session: requests.Session) -> None:
    r = session.post(
        "https://beta.trainasone.com/login",
        data={
            "email": creds["trainasone_email"],
            "password": creds["trainasone_password"],
        },
    )


token = ""


def finalsurge_login(session: requests.Session) -> None:
    login_params = {
        "email": creds["finalsurge_email"],
        "password": creds["finalsurge_password"],
        "deviceManufacturer": "",
        "deviceModel": "Netscape",
        "deviceOperatingSystem": "Win32",
        "deviceUniqueIdentifier": "",
    }
    r = session.post(
        "https://beta.finalsurge.com/api/Data?request=login",
        data=json.dumps(login_params).replace(" ", ""),
    )
    login_info = r.json()
    session.headers.update({"Authorization": f"Bearer {login_info['data']['token']}"})


def check_finalsurge_workout_exists(workout):
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


def add_finalsurge_workout(workout):
    finalsurge_login(finalsurge_session)
    if check_finalsurge_workout_exists(workout):
        return
    wo = finalsurge.convert_workout(workout)
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


def get_next_tao_workout():
    r = tao_session.get("https://beta.trainasone.com/home", allow_redirects=False)
    if r.status_code == 302:
        tao_login(tao_session)
        r = tao_session.get("https://beta.trainasone.com/calendarView")
    upcoming = r.html.find(".today, .future")
    for day in upcoming:
        if day.find(".summary>b>a"):
            break
    else:
        return None
    date = dateparser.parse(day.find(".title", first=True).text)
    workout_url = day.find(".summary>b>a", first=True).absolute_links.pop()
    # workout_url = "https://beta.trainasone.com/plannedWorkout?targetUserId=016e89c82ff200004aa88d95b508101c&workoutId=017529245aae00014aa88d95b5080ab6"
    workout_html = tao_session.get(workout_url).html
    steps = workout_html.find(".workoutSteps>ol>li")
    w = workout.Workout()
    w.date = date
    name = workout_html.find(".summary span", first=True).text
    number = workout_html.find(".summary sup", first=True).text
    w.id = number
    w.name = f"{number} {name}"
    w.steps = list(convert_steps(steps))
    w.steps[0].type = "WARMUP"
    return w


def convert_steps(steps):
    for i, step in enumerate(steps):
        if step.find("ol"):
            times = int(re.search(r" (\d+) times", step.text).group(1))
            out_step = workout.RepeatStep(times)
            out_step.steps = list(convert_steps(step.find("ol>li")))
            out_step.steps[0].type = "REST"
            out_step.steps[1].type = "ACTIVE"
        else:
            out_step = workout.ConcreteStep()
            out_step.description = step.text
            out_step.pace_range = workout.Range(*parse_tao_range(step.text))
            out_step.power_range = workout.Range(
                *convert_time_range_to_power(out_step.pace_range)
            )
            out_step.length = parse_tao_length(step.text)
            out_step.type = "ACTIVE"

        yield out_step


@lru_cache()
def get_power_from_time(seconds: int) -> int:
    if seconds <= 0:
        return 0
    r = stryd_session.get(prediction_url, params={**params, "target_time": seconds})
    if r.status_code == 401:
        stryd_login(stryd_session)
        r = stryd_session.get(prediction_url, params={**params, "target_time": seconds})
    return round(r.json()["power_range"]["target"])


def convert_time_range_to_power(range):
    return get_power_from_time(range[0]), get_power_from_time(range[1])


def parse_time(time_string: str) -> int:
    min, sec = map(int, time_string.split(":"))
    return min * 60 + sec


def parse_tao_range(step_string: str) -> tuple:
    range_string = re.search(r"\[(.*)\]", step_string).group(1)
    range_string = range_string.strip(" /mi")
    min, max = range_string.split("-")
    if range_string.startswith(">"):
        max = parse_time(max)
        min = -1
    else:
        min, max = parse_time(min), parse_time(max)
    return min, max


def parse_tao_length(step_string: str):
    match = re.search(
        r"for ((?P<hours>\d+) hours?)?[, ]*((?P<minutes>\d+) minutes?)?[, ]*((?P<seconds>\d+) seconds?)?",
        step_string,
    )
    if not match:
        # This is a 3.2km assesment. e.g. "Run in as QUICK a time as you can (2.0 mi)."
        match = re.search(r"\(([\d.]+) mi\).$", step_string)
        distance = float(match.group(1))
        return distance
    parts = match.groupdict()
    time_params = {}
    for (name, param) in parts.items():
        if param:
            time_params[name] = int(param)
    return timedelta(**time_params)


if __name__ == "__main__":
    wo = get_next_tao_workout()
    add_finalsurge_workout(wo)
