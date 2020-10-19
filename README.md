# TrainAsPower

Automatically converts [TrainAsOne](https://www.trainasone.com) training plans to use power, and uploads them to [Final 
Surge](https://finalsurge.com) (Which [Stryd](https://stryd.com) can use in its workout app.)


## Installation
1. Install [Poetry](https://python-poetry.org/docs/#installation)
1. Check out the git repository.
1. Run `poetry install` from the git repo.
1. Rename `config.yaml.example` to `config.yaml` and fill in your passwords.

## Execution

Run `poetry run trainaspower` from the checkout directory. 

### Crontab
If you want to set it up in crontab, you have to get the path to the executable.
Run `echo $(poetry env info --path)/bin/trainaspower` to get the full path, which you can then enter into crontab.