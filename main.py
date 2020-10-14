import re

import requests
import yaml

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


def stryd_login(session: requests.Session, email: str, password: str) -> None:
    r = session.post("https://www.stryd.com/b/email/signin",
               json={"email": email, "password": password})
    login_info = r.json()
    session.headers.update({"Authorization": f"Bearer: {login_info['token']}"})


def get_power_from_time(session: requests.Session, seconds: int) -> int:
    r = session.get(prediction_url, params={"target_time": seconds, **params})
    return round(r.json()["power_range"]["target"])


def parse_time(time_string: str) -> int:
    min, sec = map(int, time_string.split(":"))
    return min * 60 + sec


def parse_tao_range(range_string: str) -> tuple:
    range_string = range_string.strip(" /mi")
    max, min = range_string.split("-")
    if range_string.startswith(">"):
        max = parse_time(min)
        min = 0
    else:
        min, max = parse_time(min), parse_time(max)
    return min, max


def parse_tao_step(step_text: str):
    #r = re.search(r"\[(.*)\]", step_text)
    return parse_tao_range(re.search(r"\[(.*)\]", step_text).group(1))


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print(parse_tao_step("Walk/slow run for 5 minutes at 08:18 /mi [16:36 - 08:03 /mi] 131 bpm (120 to 135), (0.6 mi)."))
    print(parse_tao_range("05:29 - 05:14 /mi"))
    print(parse_tao_range(">- 07:34 /mi"))
    exit()
    s = requests.Session()
    stryd_login(s, creds["stryd_email"], creds["stryd_password"])
    print(get_power_from_time(s, 5*60+30))


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
