import datetime
import re
from typing import Generator

import dateparser
import requests_html
from loguru import logger

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
    chunks = [encoded_email[i:i+2] for i in range(0, len(encoded_email), 2)]
    k = int(chunks[0], 16)

    for chunk in chunks[1:]:
        decoded += chr(int(chunk, 16) ^ k)

    return decoded


def get_workout(workout_url: str, date: datetime.date, config: models.Config) -> models.Workout:
    r = tao_session.get(workout_url)
    try:
        workout_html = r.html
        steps = workout_html.find(".workoutSteps>ol>li")
        w = models.Workout()
        w.date = date
        name = workout_html.find(".summary span", first=True).text
        number_element = workout_html.find(".summary sup", first=True)
        cf_email = number_element.find(".__cf_email__", first=True)
        if cf_email:
            number = decode_cloudflare_email(cf_email.attrs['data-cfemail'])
        else:
            number = number_element.text
        number = number.rstrip("@")

        w.duration = parse_duration(workout_html.find(".detail>span", first=True).text)
        w.distance = parse_distance(workout_html.find(".detail", first=True).text)
        w.id = number
        w.name = f"{number} {name}"
        logger.info("Converting TrainAsOne workout to power.")
        w.steps = list(convert_steps(steps, config))
        return w
    except Exception as exc:
        raise FindWorkoutException(
            f"Error finding workout steps: {exc.args}", "taoworkout.html", r.text
        ) from exc


def convert_steps(steps, config: models.Config) -> Generator[models.Step, None, None]:
    for index, step in enumerate(steps):
        if step.find("ol"):
            times_match = re.search(r" (\d+) times", step.text)
            if times_match:
                times = int(times_match.group(1))
            else:
                times = 1
            out_step = models.RepeatStep(times)
            out_step.steps = list(convert_steps(step.find("ol>li"), config))
            out_step.steps[0].type = "REST"
        else:
            out_step = models.ConcreteStep()
            out_step.description = step.text

            if "pace-VERY_EASY" in step.attrs["class"]:
                if index < 2:
                    out_step.type = "WARMUP"
                else:
                    out_step.type = "REST"
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
                # 6 minute assessments, RECOVERY, and perceived effort segments do not have a pace
                # Provide a generous power range based on %CP for slower ranges
                if "pace-RECOVERY" in step.attrs["class"]:
                    out_step.power_range = models.PowerRange(0, get_critical_power() * 0.8)
                elif "pace-EXTREME" in step.attrs["class"]:
                    out_step.power_range = suggested_power_range_for_time(
                        out_step.length
                    )
                elif "pace-VERY_EASY" in step.attrs["class"]:
                    # Perceived effort warmup
                    cp = get_critical_power()
                    out_step.power_range = models.PowerRange(cp * 0.3, cp * 0.8)
                elif "pace-EASY" in step.attrs["class"]:
                    # Perceived effort main body
                    cp = get_critical_power()
                    out_step.power_range = models.PowerRange(cp * 0.55, cp * 0.9)

            else:
                out_step.power_range = convert_pace_range_to_power(out_step.pace_range)

            if "pace-VERY_EASY" in step.attrs["class"]:
                out_step.power_range = models.PowerRange(
                    out_step.power_range.min + config.very_easy_pace_adjust[0],
                    out_step.power_range.max + config.very_easy_pace_adjust[1],
                )
            elif "pace-EASY" in step.attrs["class"]:
                out_step.power_range = models.PowerRange(
                    out_step.power_range.min + config.easy_pace_adjust[0],
                    out_step.power_range.max + config.easy_pace_adjust[1],
                )
            elif "pace-RECOVERY" in step.attrs["class"]:
                out_step.power_range = models.PowerRange(
                    out_step.power_range.min + config.recovery_pace_adjust[0],
                    out_step.power_range.max + config.recovery_pace_adjust[1],
                )
            elif "pace-FAST" in step.attrs["class"]:
                out_step.power_range = models.PowerRange(
                    out_step.power_range.min + config.fast_pace_adjust[0],
                    out_step.power_range.max + config.fast_pace_adjust[1],
                )
            elif "pace-EXTREME" in step.attrs["class"]:
                out_step.power_range = models.PowerRange(
                    out_step.power_range.min + config.extreme_pace_adjust[0],
                    out_step.power_range.max + config.extreme_pace_adjust[1],
                )
            elif "pace-STANDING" in step.attrs["class"]:
                out_step.power_range = models.PowerRange(0, 50)

        yield out_step


def parse_time(pace_string: str) -> models.Quantity:
    min, sec = map(int, pace_string.split(":"))
    return min * models.minute + sec * models.second


def parse_pace_range(step_string: str) -> models.PaceRange:
    range_match = re.search(r"\[(.*)\]", step_string)
    if not range_match:
        raise ValueError(f"Could not find pace range in `{step_string}`")
    range_string = range_match.group(1).strip()
    length = models.mile
    if range_string.endswith("km"):
        length = models.kilometer
    range_string = range_string[:-4]
    min, max = range_string.split("-")
    if range_string.startswith(">"):
        max = parse_time(max) / length
        min = models.ureg.Quantity(0, units=models.second / length)
    else:
        min, max = parse_time(min) / length, parse_time(max) / length
    return models.PaceRange(min, max)


def parse_distance(text: str) -> models.Quantity:
    match = re.search(r"\(~?([\d.]+ (mi|km))\)", text)
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
