import re
from datetime import timedelta
from typing import Generator

import dateparser
import requests_html
from loguru import logger

from . import models

from .stryd import (
    convert_pace_range_to_power,
    suggested_power_range_for_distance,
    suggested_power_range_for_time,
)

tao_session = requests_html.HTMLSession()


class FindWorkoutException(Exception):
    def __init__(self, message, filename, html):
        super().__init__(message)
        self.message = message
        self.html = html
        self.filename = filename


def login(email, password) -> None:
    r = tao_session.post(
        "https://beta.trainasone.com/login",
        data={"email": email, "password": password},
        allow_redirects=False,
    )
    if not r.is_redirect:
        raise Exception("Failed to login to Train as One")


def get_next_workout() -> models.Workout:
    logger.info("Fetching next TrainAsOne workout.")
    r = tao_session.get("https://beta.trainasone.com/calendarView")
    try:
        upcoming = r.html.find(".today, .future")
        for day in upcoming:
            if day.find(".workout"):
                break
        else:
            raise Exception("Next tao workout not found.")
        date = dateparser.parse(day.find(".title", first=True).text)
        workout_url = day.find(".workout a", first=True).absolute_links.pop()
    except Exception as exc:
        raise FindWorkoutException(
            f"Error finding next TaO workout: {exc.args[0]}", "taocalendar.html", r.text
        ) from exc

    r = tao_session.get(workout_url)
    try:
        workout_html = r.html
        steps = workout_html.find(".workoutSteps>ol>li")
        w = models.Workout()
        w.date = date
        name = workout_html.find(".summary span", first=True).text
        number = workout_html.find(".summary sup", first=True).text
        w.duration = parse_duration(workout_html.find(".detail>span", first=True).text)
        w.distance = parse_distance(workout_html.find(".detail", first=True).text)
        w.id = number
        w.name = f"{number} {name}"
        logger.info("Converting TrainAsOne workout to power.")
        w.steps = list(convert_steps(steps))
        return w
    except Exception as exc:
        raise FindWorkoutException(
            f"Error finding workout steps: {exc.args[0]}", "taoworkout.html", r.text
        ) from exc


def convert_steps(steps) -> Generator[models.Step, None, None]:
    for step in steps:
        if step.find("ol"):
            times = int(re.search(r" (\d+) times", step.text).group(1))
            out_step = models.RepeatStep(times)
            out_step.steps = list(convert_steps(step.find("ol>li")))
            out_step.steps[0].type = "REST"
        else:
            out_step = models.ConcreteStep()
            out_step.description = step.text

            if "pace-VERY_EASY" in step.attrs["class"]:
                out_step.type = "WARMUP"
            elif any(
                t in step.attrs["class"] for t in ["pace-RECOVERY", "pace-STANDING"]
            ):
                out_step.type = "REST"
            else:
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
                # 6 minute assesments, RECOVERY, and perceived effort segments do not have a pace
                if "pace-RECOVERY" in step.attrs["class"]:
                    # TODO: Just hard coding this for now
                    out_step.power_range = models.PowerRange(0, 280)
                elif "pace-EXTREME" in step.attrs["class"]:
                    out_step.power_range = suggested_power_range_for_time(
                        out_step.length
                    )
                elif "pace-VERY_EASY" in step.attrs["class"]:
                    # Perceived effort warmup
                    # TODO: figure out something better for this
                    out_step.power_range = models.PowerRange(100, 280)
                elif "pace-EASY" in step.attrs["class"]:
                    # Perceived effort main body
                    # TODO: figure out something better for this
                    out_step.power_range = models.PowerRange(200, 300)

            else:
                out_step.power_range = convert_pace_range_to_power(out_step.pace_range)

            if "pace-EASY" in step.attrs["class"]:
                # Widen the range for 'easy' pace, don't need so much beeping in my ears
                out_step.power_range = models.PowerRange(
                    out_step.power_range.min - 1.8, out_step.power_range.max + 1.8
                )
            elif "pace-STANDING" in step.attrs["class"]:
                out_step.power_range = models.PowerRange(0, 50)

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
