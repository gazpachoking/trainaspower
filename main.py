from functools import lru_cache
import re

import requests
import requests_html
import yaml

import workout

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
stryd_session = requests.Session()
tao_session = requests_html.HTMLSession()
tao_user_id = ""


def stryd_login(session: requests.Session) -> None:
    r = session.post(
        "https://www.stryd.com/b/email/signin",
        json={"email": creds["stryd_email"], "password": creds["stryd_password"]},
    )
    login_info = r.json()
    session.headers.update({"Authorization": f"Bearer: {login_info['token']}"})


def tao_login(session: requests.Session) -> None:
    r = session.post(
        "https://beta.trainasone.com/login",
        data={"email": creds["trainasone_email"], "password": creds["trainasone_password"]},
    )


def get_tao_workout():
    r = tao_session.get("https://beta.trainasone.com/home", allow_redirects=False)
    if r.status_code == 302:
        tao_login(tao_session)
        r = tao_session.get("https://beta.trainasone.com/home")
    workout_url = "https://beta.trainasone.com" + r.html.find(".planned-workout-data", first=True).attrs["data-href"]
    workout_url = "https://beta.trainasone.com/plannedWorkout?targetUserId=016e89c82ff200004aa88d95b508101c&workoutId=017529245aae00014aa88d95b5080ab6"
    workout_html = tao_session.get(workout_url)
    steps = workout_html.html.find(".workoutSteps", first=True)
    w = workout.Workout()
    w.steps = list(convert_steps(steps))
    return w


def convert_steps(steps):
    for step in steps.find('li'):
        if step.find('ol'):
            times = int(re.search(r" (\d+) times", step.text).group(1))
            out_step = workout.RepeatStep(times)
            out_step.steps = list(convert_steps(step.find('ol', first=True)))
        else:
            out_step = workout.ConcreteStep()
            out_step.description = step.text
            out_step.pace_range = workout.Range(*parse_tao_step(step.text))
            out_step.power_range = workout.Range(*convert_time_range_to_power(out_step.pace_range))
        yield out_step


@lru_cache()
def get_power_from_time(seconds: int) -> int:
    if seconds <= 0:
        return 0
    r = stryd_session.get(prediction_url, params={**params, "target_time": seconds})
    if r.status_code == 401:
        stryd_login(stryd_session)
        r = stryd_session.get(prediction_url, params={**params, "target_time": seconds})
    return round(r.json()["power_range"]["target"])


def convert_time_range_to_power(range):
    return get_power_from_time(range[0]), get_power_from_time(range[1])


def parse_time(time_string: str) -> int:
    min, sec = map(int, time_string.split(":"))
    return min * 60 + sec


def parse_tao_range(range_string: str) -> tuple:
    range_string = range_string.strip(" /mi")
    min, max = range_string.split("-")
    if range_string.startswith(">"):
        max = parse_time(max)
        min = -1
    else:
        min, max = parse_time(min), parse_time(max)
    return min, max


def parse_tao_step(step_text: str):
    # r = re.search(r"\[(.*)\]", step_text)
    step_text = step_text.replace("\xa0", " ")
    return parse_tao_range(re.search(r"\[(.*)\]", step_text).group(1))


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    #print(get_power_from_time(478))
    #print(get_power_from_time(984))
    #exit()
    a = get_tao_workout()
    print(a)
    #print(parse_tao_range("05:29 - 05:14 /mi"))
    #print(parse_tao_range(">- 07:34 /mi"))
    exit()
    s = requests.Session()
    print(get_power_from_time(s, 5 * 60 + 30))


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
