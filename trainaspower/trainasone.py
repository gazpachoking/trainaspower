import re
from datetime import timedelta
from typing import Generator

import dateparser
import requests_html

from . import models

from .stryd import convert_pace_range_to_power, suggested_power_range_for_distance, suggested_power_range_for_time

tao_session = requests_html.HTMLSession()


def login(email, password) -> None:
    tao_session.post(
        "https://beta.trainasone.com/login", data={"email": email, "password": password}
    )


def get_next_workout() -> models.Workout:
    r = tao_session.get("https://beta.trainasone.com/calendarView")
    upcoming = r.html.find(".today, .future")
    for day in upcoming:
        if day.find(".summary>b>a"):
            break
    else:
        raise Exception("Next tao workout not found.")
    date = dateparser.parse(day.find(".title", first=True).text)
    workout_url = day.find(".summary>b>a", first=True).absolute_links.pop()
    # 6 min
    #workout_url = "https://beta.trainasone.com/plannedWorkout?targetUserId=016e89c82ff200004aa88d95b508101c&workoutId=017543a5980d00004aa88d95b50894b6"
    # 3.2k
    #workout_url = "https://beta.trainasone.com/plannedWorkout?targetUserId=016e89c82ff200004aa88d95b508101c&workoutId=0174f4e2df5d00004aa88d95b50877e2"
    workout_html = tao_session.get(workout_url).html
    steps = workout_html.find(".workoutSteps>ol>li")
    w = models.Workout()
    w.date = date
    name = workout_html.find(".summary span", first=True).text
    number = workout_html.find(".summary sup", first=True).text
    w.duration = parse_duration(workout_html.find(".detail>span", first=True).text)
    w.distance = parse_distance(workout_html.find(".detail", first=True).text)
    w.id = number
    w.name = f"{number} {name}"
    w.steps = list(convert_steps(steps))
    w.steps[0].type = "WARMUP"
    return w


def convert_steps(steps) -> Generator[models.Step, None, None]:
    for i, step in enumerate(steps):
        if step.find("ol"):
            times = int(re.search(r" (\d+) times", step.text).group(1))
            out_step = models.RepeatStep(times)
            out_step.steps = list(convert_steps(step.find("ol>li")))
        else:
            out_step = models.ConcreteStep()
            out_step.description = step.text
            out_step.type = "ACTIVE"
            try:
                out_step.length = parse_duration(step.text)
            except ValueError:
                # 3.2km assessments are the only steps that do not have a duration
                distance = parse_distance(step.text)
                out_step.power_range = suggested_power_range_for_distance(distance)
                out_step.length = distance
                yield out_step
                continue

            try:
                out_step.pace_range = parse_pace_range(step.text)
            except ValueError:
                # 6 minute assesments and RECOVERY segments do not have a pace
                if "pace-RECOVERY" in step.attrs["class"]:
                    # Just hard coding this for now
                    out_step.power_range = models.PowerRange(0, 280)
                elif "pace-EXTREME" in step.attrs["class"]:
                    out_step.power_range = suggested_power_range_for_time(out_step.length)
            else:
                out_step.power_range = convert_pace_range_to_power(out_step.pace_range)

            if "pace-EASY" in step.attrs["class"]:
                # Widen the range for 'easy' pace, don't need so much beeping in my ears
                out_step.power_range = models.PowerRange(
                    out_step.power_range.min - 1.5, out_step.power_range.max + 1.5
                )
            elif "pace-VERY_EASY" in step.attrs["class"] or "pace-RECOVERY" in step.attrs["class"]:
                out_step.type = "REST"

        yield out_step


def parse_pace(pace_string: str) -> int:
    min, sec = map(int, pace_string.split(":"))
    return min * 60 + sec


def parse_pace_range(step_string: str) -> models.PaceRange:
    range_match = re.search(r"\[(.*)\]", step_string)
    if not range_match:
        raise ValueError(f"Could not find pace range in `{step_string}`")
    range_string = range_match.group(1).strip(" /mi")
    min, max = range_string.split("-")
    if range_string.startswith(">"):
        max = parse_pace(max)
        min = -1
    else:
        min, max = parse_pace(min), parse_pace(max)
    return models.PaceRange(min, max)


def parse_distance(text: str) -> float:
    match = re.search(r"\(~?([\d.]+) mi\)", text)
    if not match:
        raise ValueError(f"No distance found in `{text}`")
    return float(match.group(1))


def parse_duration(step_string: str) -> timedelta:
    match = re.search(
        r"(?=\d+ (hour|minute|second))((?P<hours>\d+) hours?)?[, ]*((?P<minutes>\d+) minutes?)?[, ]*((?P<seconds>\d+) seconds?)?",
        step_string,
    )
    if not match:
        raise ValueError(f"No duration found in text `{step_string}`")
    parts = match.groupdict()
    time_params = {}
    for (name, param) in parts.items():
        if param:
            time_params[name] = int(param)
    return timedelta(**time_params)
