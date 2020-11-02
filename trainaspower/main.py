from pathlib import Path
import sys

from loguru import logger
import yaml

import trainaspower
from trainaspower import finalsurge, stryd, trainasone


if getattr(sys, "frozen", False):
    directory = Path(sys.executable).parent
else:
    directory = Path(trainaspower.__file__).parent.parent

logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(
    directory / "trainaspower.log", level="DEBUG", rotation="3 days", retention="6 days"
)

try:
    with open(directory / "config.yaml") as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    logger.error(f"Could not find config.yaml in `{directory}`")
    sys.exit(1)
except yaml.YAMLError:
    logger.exception("Error parsing YAML from config.yaml")
    sys.exit(1)


@logger.catch
def main():
    trainasone.login(config["trainasone_email"], config["trainasone_password"])
    finalsurge.login(config["finalsurge_email"], config["finalsurge_password"])
    stryd.login(config["stryd_email"], config["stryd_password"])
    try:
        wo = trainasone.get_next_workout()
    except trainasone.FindWorkoutException as exc:
        with open(directory / exc.filename, "w") as f:
            f.write(exc.html)
        logger.error(f"Could not find next Train as One workout. Created {exc.filename} for debugging.")
        sys.exit(1)
    finalsurge.add_workout(wo)


if __name__ == "__main__":
    main()
