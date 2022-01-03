import argparse
import datetime
import sys
from itertools import islice
from pathlib import Path

import yaml
from loguru import logger
from pydantic import ValidationError

import trainaspower
from trainaspower import finalsurge, models, stryd, trainasone

if getattr(sys, "frozen", False):
    directory = Path(sys.executable).parent
else:
    directory = Path(trainaspower.__file__).parent.parent


def setup_logging():
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(
        directory / "trainaspower.log",
        level="DEBUG",
        rotation="3 days",
        retention="6 days",
        diagnose=True,
        encoding="utf-8"
    )


def load_config(config_file):
    try:
        raw_config = yaml.safe_load(config_file)
    except yaml.YAMLError:
        logger.exception("Error parsing YAML from config.yaml")
        raise

    try:
        config = models.Config(**raw_config)
    except ValidationError as exc:
        logger.error(str(exc))
        raise

    return config


def daterange(start_date: datetime.date, end_date: datetime.date):
    if isinstance(start_date, datetime.datetime):
        start_date = start_date.date()
    if isinstance(end_date, datetime.datetime):
        end_date = end_date.date()
    for n in range(int((end_date - start_date).days)):
        yield start_date + datetime.timedelta(n)


@logger.catch
def main():
    setup_logging()

    config_file_default_path = directory / "config.yaml"

    parser = argparse.ArgumentParser(
        description="Create power based structured workouts from TrainAsOne data"
    )
    parser.add_argument(
        "config_file",
        type=argparse.FileType("r"),
        nargs="?",
        default=str(config_file_default_path),
        help=f"Path to config.yaml, defaults to '{config_file_default_path}'",
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config_file)
    except Exception:
        sys.exit(1)
    finally:
        args.config_file.close()

    trainasone.login(config.trainasone_email, config.trainasone_password)
    finalsurge.login(config.finalsurge_email, config.finalsurge_password)
    stryd.login(config.stryd_email, config.stryd_password)
    start_date = datetime.date.today()
    try:
        for wo in islice(
            trainasone.get_next_workouts(config), config.number_of_workouts
        ):
            # Clear any cancelled workouts
            for wo_date in daterange(start_date, wo.date):
                finalsurge.remove_workout(wo_date)
            # Add the new workout
            finalsurge.add_workout(wo)
            start_date = wo.date + datetime.timedelta(1)
    except trainasone.FindWorkoutException as exc:
        with open(directory / exc.filename, "w", encoding="utf-8") as f:
            f.write(exc.html)
        logger.opt(exception=True).debug("Error")
        logger.error(
            f"Could not load next Train as One workout. Created {exc.filename} for debugging."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
