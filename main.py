import yaml

import finalsurge
import stryd
import trainasone


with open("creds.yaml") as f:
    creds = yaml.safe_load(f)


if __name__ == "__main__":
    trainasone.login(creds["trainasone_email"], creds["trainasone_password"])
    finalsurge.login(creds["finalsurge_email"], creds["finalsurge_password"])
    stryd.login(creds["stryd_email"], creds["stryd_password"])
    wo = trainasone.get_next_workout()
    finalsurge.add_workout(wo)
