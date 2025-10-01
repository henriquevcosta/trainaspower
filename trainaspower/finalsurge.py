import json
from datetime import date, timedelta
from itertools import count
from typing import Optional, Union

import requests
from loguru import logger
from pint import Quantity

from trainaspower import models

finalsurge_session = requests.Session()


user_key = "NOT LOGGED IN"

CONVERSION_DESCRIPTION_TAG = "By TrainAsPower"

def login(email: str, password: str) -> None:
    login_params = {
        "email": email,
        "password": password,
        "deviceManufacturer": "",
        "deviceModel": "Netscape",
        "deviceOperatingSystem": "Win32",
        "deviceUniqueIdentifier": "",
    }
    r = finalsurge_session.post(
        "https://beta.finalsurge.com/api/login",
        json=login_params,
    )
    login_info = r.json()
    if not login_info["success"]:
        raise Exception("Failed to log in to Final Surge")
    finalsurge_session.headers.update(
        {"Authorization": f"Bearer {login_info['data']['token']}"}
    )
    global user_key
    user_key = login_info["data"]["user_key"]


def convert_workout(workout: models.Workout) -> dict:
    counter = count(1)
    try:
        steps = workout.steps or []
    except AttributeError:
        steps = []

    target = "pace"
    if steps:
        first_step = steps[0]
        try:
            if first_step.power_range:
                target = "power"
            elif first_step.pace_range:
                target = "pace"
            elif first_step.hr_zone:
                target = "hr"
        except AttributeError:
            target = "pace"

    result = {
        "target_options": [
            {
                "name": workout.name,
                "sport": "running",
                "steps": [convert_step(s, counter) for s in steps],
                "target": target,
            }
        ],
        "target_override": None,
    }
    return result


def pace_to_time(pace: Quantity) -> str:
    pace = pace.to("minute/kilometer").magnitude
    mins = int(pace)
    secs = int(60 * (pace % 1))
    return f"{mins:02d}:{secs:02d}"


def convert_step(step: models.Step, id_counter) -> dict:
    if isinstance(step, models.RepeatStep):
        return convert_repeat(step, id_counter)
    if not isinstance(step, models.ConcreteStep):
        raise ValueError(f"unknown step type received {step.type}")
    if step.length is None:
        s = {"durationType": "OPEN"}
    elif step.length.check("[time]"):
        s = {
            "durationType": "TIME",
            "duration": str(timedelta(seconds=step.length.to("seconds").magnitude)),
        }
    else:
        s = {
            "durationType": "DISTANCE",
            "durationDist": step.length.magnitude,
            "distUnit": f"{step.length.units:~}",
        }

    target_open = {
        "targetType": "open",
        "zoneBased": False,
        "targetLow": 0,
        "targetHigh": 0,
        "targetOption": None,
        "targetIsTimeBased": False,
        "zone": 0,
    }

    if step.power_range:
        target_base = {
            "targetType": "power",
            "zoneBased": False,
            "targetLow": round(step.power_range.min),
            "targetHigh": round(step.power_range.max),
            "targetOption": None,
            "targetIsTimeBased": False,
            "zone": 0,
        }
    elif step.pace_range:
        target_base = {
            "targetType": "pace",
            "zoneBased": False,
            "targetLow": pace_to_time(step.pace_range.min),
            "targetHigh": pace_to_time(step.pace_range.max),
            "targetOption": "min/km",
            "targetIsTimeBased": False,
            "zone": 0,
        }
    elif step.hr_zone:
        target_base = {
            "targetType": "hr_zone",
            "zoneBased": True,
            "targetLow": None,
            "targetHigh": None,
            "targetOption": None,
            "targetIsTimeBased": False,
            "zone": step.hr_zone.zone,
        }
    else:
        target_base = target_open

    s.update(
        {
            "type": "step",
            "id": next(id_counter),
            "name": step.description,
            "targetAbsOrPct": "",
            "data": [],
            "target": [
                target_base,
                target_open,
            ],
            "intensity": step.type,
            "comments": None,
        }
    )
    return s


def convert_repeat(step: models.RepeatStep, id_counter) -> dict:
    return {
        "type": "repeat",
        "name": None,
        "id": next(id_counter),
        "data": [convert_step(s, id_counter) for s in step.steps],
        "repeats": step.repetitions,
        "durationType": "OPEN",
        "comments": None,
    }


def get_existing_tap_workout(wo_date: date) -> Optional[str]:
    """Checks if TrainAsPower already has an (uncompleted) workout on the same day as given workout."""
    logger.debug(f"Checking TrainAsPower workout exists on Final Surge")
    params = {
        "scope": "USER",
        "scopekey": user_key,
        "startdate": wo_date.strftime("%Y-%m-%d"),
        "enddate": wo_date.strftime("%Y-%m-%d"),
        "ishistory": False,
        "completedonly": False,
    }
    data = finalsurge_session.get(
        "https://beta.finalsurge.com/api/WorkoutList", params=params
    ).json()
    for existing_workout in data["data"]:
        if existing_workout["workout_completion"] == 1:
            continue
        if CONVERSION_DESCRIPTION_TAG in (existing_workout["description"] or ""):
            return existing_workout["key"]
    return None


def add_workout(workout: models.Workout) -> None:
    wo_key = get_existing_tap_workout(workout.date)
    if wo_key:
        logger.info(f"Updating workout `{workout.name}` on Final Surge")
    else:
        logger.info(f"Posting workout `{workout.name}` to Final Surge")
    wo = convert_workout(workout)
    params = {"scope": "USER", "scope_key": user_key}

    description = workout.description + "\n\n" if workout.description else ""
    description = f"{description}{CONVERSION_DESCRIPTION_TAG}"

    add_wo = finalsurge_session.post(
        "https://beta.finalsurge.com/api/WorkoutSave",
        params=params,
        data=json.dumps({
            "key": wo_key,
            "workout_date": workout.date.isoformat(),
            "order": 1,
            "name": workout.name,
            "description": description,
            "is_race": False,
            "Activity": {
                "activity_type_key": convert_activity_type(workout.type),
                "activity_type_name": workout.type,
                "planned_amount": workout.distance.magnitude if workout.distance else None,
                "planned_amount_type": f"{workout.distance.units:~}" if workout.distance else None,
                "planned_duration": round(workout.duration.to("seconds").magnitude) if workout.duration else None,
            },
        }).encode("utf-8"),
        headers={'Content-Type': 'application/json; charset=UTF-8'},
    )
    if not wo_key:
        wo_key = add_wo.json()["new_workout_key"]

    if workout.type != "Strength Training":
        params = {
            "scope": "USER",
            "scopekey": user_key,
            "workout_key": wo_key,
        }
        finalsurge_session.post(
            "https://beta.finalsurge.com/api/WorkoutBuilderSave", params=params, json=wo
        )


def remove_workout(wo_date: date) -> None:
    wo_key = get_existing_tap_workout(wo_date)
    if not wo_key:
        return
    logger.info(f"Deleting existing TrainAsPower workout `{wo_key}`")
    params = {
        "scope": "USER",
        "scopekey": user_key,
        "workout_key": wo_key,
    }
    response = finalsurge_session.get(
        "https://beta.finalsurge.com/api/WorkoutDelete", params=params
    )
    logger.debug(f"Deletion response: {response.json()}")


def convert_activity_type(type: str) -> str:
    match type.lower():
        case "run":
            return "00000001-0001-0001-0001-000000000001"
        case "strength training":
            return "00000005-0005-0005-0005-000000000005"
        case _:
            raise ValueError(f"Unknown activity type: {type}")