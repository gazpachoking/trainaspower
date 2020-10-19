from pathlib import Path
import yaml

import trainaspower
from trainaspower import finalsurge, stryd, trainasone


directory = Path(trainaspower.__file__).parent.parent
with open(directory/"config.yaml") as f:
    config = yaml.safe_load(f)


def main():
    trainasone.login(config["trainasone_email"], config["trainasone_password"])
    finalsurge.login(config["finalsurge_email"], config["finalsurge_password"])
    stryd.login(config["stryd_email"], config["stryd_password"])
    wo = trainasone.get_next_workout()
    finalsurge.add_workout(wo)


if __name__ == "__main__":
    main()