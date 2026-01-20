# AGENTS.md

## Instructions

- When starting the django app use always uv to run python
- when implementing new functions always add the test in order to check it's functionality


## important always use `uv run`

THis project uses `uv` for dependency managment. **Never use bare `python` nor `pip` commands**
Always prefix Python commands with `uv run`.

```bash
#correct
uv run python manage.py runserver
uv run python manage.py migrate

#incorrect
python manage.py runserver
python manage.py migrate