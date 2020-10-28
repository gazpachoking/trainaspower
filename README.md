# TrainAsPower

Automatically converts [TrainAsOne](https://www.trainasone.com) training plans to use power, and uploads them to [Final 
Surge](https://finalsurge.com) (Which [Stryd](https://stryd.com) can use in its workout app.)

#### From this, to this!

<p float="left">
    <img src="https://gazpachoking.github.io/trainaspower/taoworkout.png" height="450" alt="TrainAsOne Workout">
    <img src="https://gazpachoking.github.io/trainaspower/strydworkout.png" height="450" alt="Stryd Workout">
</p>


## Installation

### From Source

1. Install [Poetry](https://python-poetry.org/docs/#installation)
1. Check out the git repository, or, download and extract the [source zip](https://github.com/gazpachoking/trainaspower/archive/master.zip).
1. Run `poetry install` from the source directory.
1. Copy `config.yaml.example` to `config.yaml` and fill in your passwords.

### Windows Package
1. Download the exe from [the latest release](https://github.com/gazpachoking/trainaspower/releases)
1. Create a `config.yaml` file in the same directory as the exe based on the [sample config](https://github.com/gazpachoking/trainaspower/blob/master/config.yaml.example)


## Execution

Run `poetry run trainaspower` from the checkout directory. 

### Crontab
If you want to set it up in crontab, you have to get the path to the executable.
Run `echo $(poetry env info --path)/bin/trainaspower` to get the full path, which you can then enter into crontab.

Each execution will add the next workout to be completed, so it needs to be scheduled once a day, at a time
after you will have finished your workout for the day.
