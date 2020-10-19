import yaml

import finalsurge
import stryd
import trainasone


with open("config.yaml") as f:
    config = yaml.safe_load(f)


def main():
    trainasone.login(config["trainasone_email"], config["trainasone_password"])
    finalsurge.login(config["finalsurge_email"], config["finalsurge_password"])
    stryd.login(config["stryd_email"], config["stryd_password"])
    wo = trainasone.get_next_workout()
    finalsurge.add_workout(wo)


if __name__ == "__main__":
    main()