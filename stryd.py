from functools import lru_cache

import models
import requests

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
    r = stryd_session.get(prediction_url, params={**params, "target_time": seconds})
    if r.status_code == 401:
        login()
        r = stryd_session.get(prediction_url, params={**params, "target_time": seconds})
    return r.json()["power_range"]["target"]


def convert_pace_range_to_power(pace_range: models.PaceRange):
    return models.PowerRange(
        get_power_from_time(pace_range.min), get_power_from_time(pace_range.max)
    )
