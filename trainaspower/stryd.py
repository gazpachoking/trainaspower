from datetime import timedelta, date
from functools import lru_cache

import requests
from loguru import logger

from trainaspower import models

stryd_session = requests.Session()
user_id = None


def login(email, password) -> None:
    r = stryd_session.post(
        "https://www.stryd.com/b/email/signin",
        json={"email": email, "password": password},
    )
    if r.status_code != 200:
        raise Exception("Failed to log in to Stryd")
    login_info = r.json()
    stryd_session.headers.update({"Authorization": f"Bearer: {login_info['token']}"})
    global user_id
    user_id = login_info["id"]


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
@models.ureg.check("[time] / [length]")
def get_power_from_pace(pace: models.Quantity) -> float:
    seconds = round(pace.to("seconds/mile").magnitude)
    if seconds <= 0:
        return 0
    logger.debug(f"Converting {pace} to power via Stryd calculator")
    r = stryd_session.get(prediction_url, params={**params, "target_time": seconds})
    return r.json()["power_range"]["target"]


def convert_pace_range_to_power(pace_range: models.PaceRange) -> models.PowerRange:
    return models.PowerRange(
        get_power_from_pace(pace_range.min), get_power_from_pace(pace_range.max)
    )


@models.ureg.check("[length]")
def suggested_power_range_for_distance(distance: models.Quantity) -> models.PowerRange:
    logger.debug(f"Getting suggested power range for {distance}")
    r = stryd_session.get(
        prediction_url, params={**params, "race_distance": distance.to(models.ureg.meter).magnitude}
    )
    suggested_range = r.json()["power_range_suggested"]
    return models.PowerRange(suggested_range["min"], suggested_range["max"])


@models.ureg.check("[time]")
def suggested_power_range_for_time(time: models.Quantity) -> models.PowerRange:
    logger.debug(f"Getting suggested power range for {time}.")
    today = date.today()
    url = "https://www.stryd.com/b/api/v1/users/powerdurationcurve"
    params = {
        "datarange": f"{today-timedelta(days=90):%m.%d.%Y}-{today:%m.%d.%Y}",
        "detraining": 0,
    }
    response = stryd_session.get(url, params=params)
    power = response.json()[0]["power_list"][
        round(time.to('seconds').magnitude - 1)
    ]
    # What should the range be?
    return models.PowerRange(power - 5, power + 10)


@lru_cache()
def get_profile() -> dict:
    url = f"https://www.stryd.com/b/api/v1/users/{user_id}"
    return stryd_session.get(url).json()


def get_critical_power() -> float:
    return get_profile()["training_info"]["critical_power"]
