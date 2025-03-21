import datetime
from itertools import compress
import re
from collections.abc import Generator

import dateparser
import requests_html
from fitparse import FitFile
from loguru import logger

from . import models
from .stryd import (
    convert_pace_range_to_power,
    get_critical_power,
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


def get_next_workouts(config) -> Generator[models.Workout, None, None]:
    logger.info("Fetching next TrainAsOne workout.")
    r = tao_session.get("https://beta.trainasone.com/calendarView")
    found = False
    try:
        upcoming = r.html.find(".today, .future")
        for day in upcoming:
            if day.find(".workout"):
                date = dateparser.parse(
                    day.find(".title", first=True).text.splitlines()[-1]
                )
                workout_url = day.find(".workout a", first=True).absolute_links.pop()
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
    chunks = [encoded_email[i : i + 2] for i in range(0, len(encoded_email), 2)]
    k = int(chunks[0], 16)

    for chunk in chunks[1:]:
        decoded += chr(int(chunk, 16) ^ k)

    return decoded


def fit_to_dict(records: dict) -> dict:
    return {r["name"]: r["value"] for r in records["fields"]}


def fit_get_workout_name(fit_file: FitFile) -> str:
    return next(
        filter(
            lambda x: x["name"] == "wkt_name",
            next(fit_file.get_messages("workout", as_dict=True))["fields"],
        ),
    )["value"]


def fit_get_workout_steps(fit_file: FitFile) -> list[dict]:
    steps = [
        fit_to_dict(step)
        for step in fit_file.get_messages("workout_step", as_dict=True)
    ]
    steps.sort(key=lambda x: x["message_index"])
    return steps


def get_workout(
    workout_url: str,
    date: datetime.date,
    config: models.Config,
) -> models.Workout:
    workout_id = re.search(r"workoutId=([^&]+)", workout_url).group(1)
    workout_download_url = "https://beta.trainasone.com/plannedWorkoutDownload"
    r = tao_session.post(
        workout_download_url,
        data={
            "workoutId": workout_id,
            "temperature": "",
            "undulation": "",
            "sourceFormat": "FIT",
            "includeRunBackStep": config.include_runback_step,
            "_includeRunBackStep": "on",
            "workoutStepEnd": "DURATION",
            "workoutStepName": "STEP_NAME",
            "workoutSlowStepTarget": "SPEED",
            "workoutEasyStepTarget": "SPEED",
            "workoutFastStepTarget": "SPEED",
        },
    )

    fit_file = FitFile(r.content)
    workout_name = fit_get_workout_name(fit_file)
    workout_steps = fit_get_workout_steps(fit_file)

    r_base = tao_session.get(workout_url)
    w = models.Workout()
    w.date = date

    try:
        # Fetch the duration and distance from TAO
        workout_html = r_base.html
        w.duration = parse_duration(workout_html.find(".detail>span", first=True).text)
        w.distance = parse_distance(workout_html.find(".detail", first=True).text)

        steps = workout_steps
        title = workout_name
        number, name = title.split(" ", maxsplit=1)
        w.id = number
        w.name = title

        logger.info("Converting TrainAsOne workout to power.")
        w.steps = convert_steps(steps, config, "Perceived Effort" in name)
        return w
    except Exception as exc:
        raise FindWorkoutException(
            f"Error finding workout steps: {exc.args}", "taoworkout.html", r.text
        ) from exc


def convert_step_type(step: dict) -> str:
    if step["intensity"] in ["warmup", "cooldown"]:
        return step["intensity"].upper()

    if step["intensity"] == "active" and step["wkt_step_name"] == "Preparation":
        return "REST"

    if step["intensity"] == "active":
        return "ACTIVE"

    return "REST"


def convert_step_length(step: dict) -> str:
    if step["duration_type"] == "distance":
        return round(step["duration_distance"]) * models.meter

    if step["duration_type"] == "open":
        # Runback step
        return None

    return step["duration_time"] * models.second


def convert_step_target(
    step: dict,
    out_step: models.ConcreteStep,
    perceived_effort: bool,
    num_steps: int,
) -> str:
    if step["target_type"] == "speed":
        pace_range = parse_pace_range(
            step["custom_target_speed_low"],
            step["custom_target_speed_high"],
        )
        power_range = convert_pace_range_to_power(pace_range)
        return pace_range, power_range

    # 6 minute assessments, RECOVERY, COOLDOWN, and perceived effort segments do not have a pace
    # Provide a generous power range based on %CP for slower ranges
    if step["target_type"] == "open":
        cp = get_critical_power()
        if perceived_effort:
            # Some perceived effort workouts have a warmup
            if num_steps > 3 and step["message_index"] == 1:
                # Perceived effort warmup
                return None, models.PowerRange(cp * 0.3, cp * 0.8)
            # Penultimate step is always the main effort
            if step["message_index"] == num_steps - 1:
                # Perceived effort main body
                return None, models.PowerRange(
                    cp * 0.55,
                    cp * 0.9,
                )
            # Perceived effort workouts start and end with a standing step
            return None, models.PowerRange(0, 50)

        # Recovery steps after hard assessments
        if step["wkt_step_name"] in ["Recovery", "Preparation"]:
            return None, models.PowerRange(0, cp * 0.9)

        if step["duration_type"] == "distance":
            return None, suggested_power_range_for_distance(out_step.length)

        if step["duration_type"] == "time":
            return None, suggested_power_range_for_time(out_step.length)

        # Run back step has no target. Add a wide power range.
        return None, models.PowerRange(
            cp * 0.55,
            cp * 0.9,
        )

    msg = f"Unknown target type {step['target_type']}"
    raise ValueError(msg)


def convert_steps(
    steps: list[dict],
    config: models.Config,
    perceived_effort: bool,
) -> list[models.Step]:
    steps_out = []
    valid_step = []
    for step in steps:
        # This does not support nested repeat steps
        if step["duration_type"] == "repeat_until_steps_cmplt":
            times = step["repeat_steps"]
            out_step = models.RepeatStep(times)
            out_step.steps = steps_out[
                step["duration_step"] : step["message_index"] + 1
            ].copy()
            valid_step[step["duration_step"] : step["message_index"] + 1] = [
                False,
            ] * (step["message_index"] - step["duration_step"])
        else:
            out_step = models.ConcreteStep()
            out_step.description = step["notes"]
            out_step.type = convert_step_type(step)
            out_step.length = convert_step_length(step)
            out_step.pace_range, out_step.power_range = convert_step_target(
                step,
                out_step,
                perceived_effort,
                len(steps),
            )

            # Add adjustment from config
            out_step.power_range += config.power_adjust

        valid_step.append(True)
        steps_out.append(out_step)

    # Remove steps that are part of repeats
    return list(compress(steps_out, valid_step))


def parse_time(pace_string: str) -> models.Quantity:
    minutes, sec = map(int, pace_string.split(":"))
    return minutes * models.minute + sec * models.second


def parse_pace_range(min_provided: float, max_provided: float) -> models.PaceRange:
    minutes = 0.0
    if min_provided != 0.0:
        minutes = 1 / min_provided
    return models.PaceRange(
        minutes * models.second / models.meter,
        (1 / max_provided) * models.second / models.meter,
    )


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
    for unit, amount in parts.items():
        if amount:
            duration += int(amount) * models.ureg.parse_units(unit)
    return duration
