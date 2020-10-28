from datetime import timedelta, date
from functools import lru_cache

import requests
from loguru import logger

from trainaspower import models

stryd_session = requests.Session()


def login(email, password) -> None:
    r = stryd_session.post(
        "https://www.stryd.com/b/email/signin",
        json={"email": email, "password": password},
    )
    login_info = r.json()
    stryd_session.headers.update({"Authorization": f"Bearer: {login_info['token']}"})


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


@lru_cache()
def get_power_from_time(seconds: int) -> float:
    if seconds <= 0:
        return 0
    logger.debug(f"Converting {seconds}s/mile to power via Stryd calculator")
    r = stryd_session.get(prediction_url, params={**params, "target_time": seconds})
    return r.json()["power_range"]["target"]


def convert_pace_range_to_power(pace_range: models.PaceRange) -> models.PowerRange:
    return models.PowerRange(
        get_power_from_time(pace_range.min), get_power_from_time(pace_range.max)
    )


def suggested_power_range_for_distance(distance: float) -> models.PowerRange:
    logger.debug(f"Getting suggested power range for {distance} miles")
    r = stryd_session.get(
        prediction_url, params={**params, "race_distance": 1609.34 * distance}
    )
    suggested_range = r.json()["power_range_suggested"]
    return models.PowerRange(suggested_range["min"], suggested_range["max"])


def suggested_power_range_for_time(time: timedelta) -> models.PowerRange:
    logger.debug(f"Getting suggested power range for {time.total_seconds()} seconds.")
    today = date.today()
    url = "https://www.stryd.com/b/api/v1/users/powerdurationcurve?datarange=07.22.2020-10.20.2020&detraining=0"
    params = {
        "detraining": 0,
        "daterange": f"{today-timedelta(days=90):%m.%d.%Y}-{today:%m.%d.%Y}",
    }
    power = stryd_session.get(url, params=params).json()[0]["power_list"][
        int(time.total_seconds() - 1)
    ]
    # What should the range be?
    return models.PowerRange(power - 5, power + 10)
