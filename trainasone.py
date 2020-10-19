import re
from datetime import timedelta
from typing import Generator

import dateparser
import models
import requests_html
from stryd import convert_pace_range_to_power

tao_session = requests_html.HTMLSession()


def login(email, password) -> None:
    tao_session.post(
        "https://beta.trainasone.com/login",
        data={
            "email": email,
            "password": password,
        },
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
    # workout_url = "https://beta.trainasone.com/plannedWorkout?targetUserId=016e89c82ff200004aa88d95b508101c&workoutId=017529245aae00014aa88d95b5080ab6"
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
            out_step.steps[0].type = "REST"
            out_step.steps[1].type = "ACTIVE"
        else:
            out_step = models.ConcreteStep()
            out_step.description = step.text
            out_step.pace_range = models.PaceRange(*parse_pace_range(step.text))
            power_range = convert_pace_range_to_power(out_step.pace_range)
            if "pace-EASY" in step.attrs["class"]:
                power_range = models.PowerRange(power_range.min - 1.5, power_range.max + 1.5)
            out_step.power_range = models.PowerRange(
                round(power_range.min), round(power_range.max)
            )
            out_step.length = parse_duration(step.text)
            out_step.type = "ACTIVE"

        yield out_step


def parse_pace(pace_string: str) -> int:
    min, sec = map(int, pace_string.split(":"))
    return min * 60 + sec


def parse_pace_range(step_string: str) -> models.PaceRange:
    range_string = re.search(r"\[(.*)\]", step_string).group(1)
    range_string = range_string.strip(" /mi")
    min, max = range_string.split("-")
    if range_string.startswith(">"):
        max = parse_pace(max)
        min = -1
    else:
        min, max = parse_pace(min), parse_pace(max)
    return models.PaceRange(min, max)


def parse_distance(text: str) -> float:
    match = re.search(r"\(~?([\d.]+) mi\)", text)
    return float(match.group(1))


def parse_duration(step_string: str) -> timedelta:
    match = re.search(
        r"((?P<hours>\d+) hours?)?[, ]*((?P<minutes>\d+) minutes?)?[, ]*((?P<seconds>\d+) seconds?)?",
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
