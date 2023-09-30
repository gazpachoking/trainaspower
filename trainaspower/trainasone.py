import datetime
from typing import Generator

import dateparser
import requests_html
from loguru import logger
import re

from . import models

from .stryd import (
    convert_pace_range_to_power,
    suggested_power_range_for_distance,
    suggested_power_range_for_time,
    get_critical_power,
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


def get_next_workouts(config) -> Generator[models.Workout, None, None]:
    logger.info("Fetching next TrainAsOne workout.")
    r = tao_session.get("https://beta.trainasone.com/calendarView")
    found = False
    try:
        upcoming = r.html.find(".today, .future")
        for day in upcoming:
            if day.find(".workout"):
                date = dateparser.parse(day.find(".title", first=True).text)
                workout_url = day.find(
                    ".workout a", first=True).absolute_links.pop()
                yield get_workout(workout_url, date, config)
                found = True
        if not found:
            raise Exception("Next tao workout not found.")
    except Exception as exc:
        raise FindWorkoutException(
            f"Error finding next TaO workout: {exc.args[0]}", "taocalendar.html", r.text
        ) from exc


def decode_cloudflare_email(encoded_email):
    """
    The workout id gets protected as if it was an email address by cloudflare. :eyeroll:
    """
    decoded = ""
    chunks = [encoded_email[i:i+2] for i in range(0, len(encoded_email), 2)]
    k = int(chunks[0], 16)

    for chunk in chunks[1:]:
        decoded += chr(int(chunk, 16) ^ k)

    return decoded


def get_workout(workout_url: str, date: datetime.date, config: models.Config) -> models.Workout:
    workout_json_url = workout_url.replace(
        "plannedWorkout?", "plannedWorkoutDownload?sourceFormat=GARMIN_TRAINING&")
    r = tao_session.get(workout_json_url, headers={
                        'Content-Type': 'application/json; charset=utf-8'})
    r.encoding = r.apparent_encoding
    r_base = tao_session.get(workout_url)
    w = models.Workout()
    w.date = date

    try:
        # Fetch the duration and distance from TAO
        workout_html = r_base.html
        w.duration = parse_duration(
            workout_html.find(".detail>span", first=True).text)
        w.distance = parse_distance(
            workout_html.find(".detail", first=True).text)

        r.encoding = 'utf-8'
        workout_json = r.json()
        steps = workout_json["steps"]
        title = workout_json["workoutName"]
        number, name = title.split(' ', maxsplit=1)
        w.id = number
        w.name = f"{number} {name}"

        logger.info("Converting TrainAsOne workout to power.")
        w.steps = list(convert_steps(
            steps, config, "Perceived Effort" in name))
        return w
    except Exception as exc:
        raise FindWorkoutException(
            f"Error finding workout steps: {exc.args}", "taoworkout.html", r.text
        ) from exc


def convert_steps(steps, config: models.Config, perceived_effort: bool) -> Generator[models.Step, None, None]:
    recovery_step_types = ["REST", "RECOVERY", "COOLDOWN"]
    active_step_types = ["ACTIVE", "INTERVAL"]
    valid_target_types = ["OPEN", "SPEED"]
    for step in steps:
        if step["type"] == "WorkoutRepeatStep":
            times = int(step["repeatValue"])
            out_step = models.RepeatStep(times)
            repeat_steps = list(convert_steps(
                step["steps"], config, perceived_effort))
            out_step.steps = repeat_steps
        else:
            out_step = models.ConcreteStep()
            if "description" in step:
                out_step.description = step["description"]

            if not step["targetType"] in valid_target_types:
                raise ValueError(
                    f"Unsupported target type {step['targetType']}. Please ensure that you have selected speed as \"Workout step target\" in the TAO settings under \"Garmin workout preferences\"")

            if step["intensity"] in ["WARMUP", "COOLDOWN"]:
                out_step.type = step["intensity"]
            elif step["intensity"] in active_step_types:
                if "targetValueLow" in step and step["targetValueLow"] == 0.0:
                    out_step.type = "REST"
                else:
                    out_step.type = "ACTIVE"
            elif step["intensity"] in recovery_step_types:
                out_step.type = "REST"

            if step["durationType"] == "DISTANCE":
                out_step.length = round(
                    step["durationValue"]) * models.meter
            elif step["durationType"] == "OPEN":
                # Runback step
                out_step.length = None
            else:
                out_step.length = step["durationValue"] * models.second

            try:
                out_step.pace_range = parse_pace_range(
                    step["targetValueLow"], step["targetValueHigh"])
            except (ValueError, KeyError):
                # 6 minute assessments, RECOVERY, COOLDOWN, and perceived effort segments do not have a pace
                # Provide a generous power range based on %CP for slower ranges
                if step["targetType"] == "OPEN":
                    if perceived_effort:
                        # Some perceived effort workouts have a warmup
                        if len(steps) > 3 and step["stepOrder"] == 2:
                            # Perceived effort warmup
                            cp = get_critical_power()
                            out_step.power_range = models.PowerRange(
                                cp * 0.3, cp * 0.8)
                        # Penultimate step is always the main effort
                        elif step["stepOrder"] == len(steps)-1:
                            # Perceived effort main body
                            cp = get_critical_power()
                            out_step.power_range = models.PowerRange(
                                cp * 0.55, cp * 0.9)
                        else:
                            # Perceived effort workouts start and end with a standing step
                            out_step.power_range = models.PowerRange(0, 50)
                    elif step["intensity"] in recovery_step_types:
                        out_step.power_range = models.PowerRange(
                            0, get_critical_power() * 0.8)
                    else:
                        if step["durationType"] == "DISTANCE":
                            out_step.power_range = suggested_power_range_for_distance(
                                out_step.length)
                        else:
                            out_step.power_range = suggested_power_range_for_time(
                                out_step.length)
                else:
                    raise ValueError(
                        "Failed to parse pace_range for step without an OPEN target.")
            else:
                out_step.power_range = convert_pace_range_to_power(
                    out_step.pace_range)
            # Add adjustment from config
            out_step.power_range += config.power_adjust

        yield out_step


def parse_time(pace_string: str) -> models.Quantity:
    min, sec = map(int, pace_string.split(":"))
    return min * models.minute + sec * models.second


def parse_pace_range(min_provided: float, max_provided: float) -> models.PaceRange:
    min = 0.0
    if min_provided != 0.0:
        min = (1 / min_provided)
    return models.PaceRange(min * models.second / models.meter, (1 / max_provided) * models.second / models.meter)


def parse_distance(text: str) -> models.Quantity:
    match = re.search(r"\(~?([\d.]+ (mi|k?m))\)", text)
    if not match:
        raise ValueError(f"No distance found in `{text}`")
    return models.ureg.parse_expression(match.group(1))


def parse_duration(step_string: str) -> models.Quantity:
    match = re.search(
        r"(?=\d+ (hour|minute|second))((?P<hours>\d+) hours?)?[, ]*((?P<minutes>\d+) minutes?)?[, ]*((?P<seconds>\d+) seconds?)?",
        step_string,
    )
    if not match:
        raise ValueError(f"No duration found in text `{step_string}`")
    parts = match.groupdict()
    duration = models.ureg.Quantity("0 seconds")
    for (unit, amount) in parts.items():
        if amount:
            duration += int(amount) * models.ureg.parse_units(unit)
    return duration
