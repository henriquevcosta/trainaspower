import datetime
from math import log
import re
from collections.abc import Generator
from itertools import compress

import dateparser
import requests_html
from fitparse import FitFile
from loguru import logger
import json
from . import models

# session = requests_html.HTMLSession()


# def login(email, password) -> None:
#     r = tao_session.post(
#         "https://beta.trainasone.com/login",
#         data={"email": email, "password": password},
#         allow_redirects=False,
#     )
#     if not r.is_redirect:
#         raise Exception("Failed to login to Train as One")

# Vert has what seems to be difficulty levels in workouts (0-2), we're taking the middle
ARRAY_INDEX=1

LANGUAGE="en"

def get_next_workouts(config: models.Config) -> Generator[models.Workout, None, None]:
    """
    Not redy for the online processing just yet
    """

    logger.info("Fetching next Vert.run workouts.")
    if config.vert_file:
        # Load JSON
        with open(config.vert_file, "r", encoding="utf-8") as file:
            full_plan = json.load(file)
    else:
        # something something full_plan = json.loads(...)
        raise Exception("Vert online fetching not supported yet")

    days = full_plan["days"]
    for day_raw in days:
        # I have never observed a day that wasn't a list of size 1
        day = day_raw[0]
        planned_date = day["plannedDate"]
        logger.info(f"Processing {planned_date}")
        date = dateparser.parse(planned_date, date_formats=["%d/%m/%Y"])
        if date.date() < datetime.date.today():
            logger.info("Skipping past activity")
            continue

        parameterized_workout = day["parametrizedWorkout"][ARRAY_INDEX]
        if not parameterized_workout:
            logger.info("Rest day")
            continue

        title = day["title"][LANGUAGE]
        description = day["description"][LANGUAGE]
        estimated_time_minutes = day["estimatedTime"][ARRAY_INDEX]

        conditioning = []
        other_steps = []
        for step in parameterized_workout:
            if step.get("action", "") == "Conditioning training":
                conditioning.append(step)
            else:
                other_steps.append(step)


        # In mixed workouts the conditioning steps are mixed in with the run steps, and each is a separate workout garmin-wise
        for step in conditioning:
            w = models.Workout()

            w.date = date
            # TODO change to enum
            w.type = "Strength Training"
            w.name = title
            w.description = description
            if step.get("variable","") == "Time":
                duration = datetime.datetime.strptime(step["value"],  "%Hh:%Mm:%Ss")
                w.duration = duration.hour * models.hour + duration.minute * models.minute + duration.second * models.second

            yield w

        if other_steps:
            w = models.Workout()
            w.date = date
            # TODO change to enum
            w.type = "Run"
            w.name = title
            w.description = description

            logger.warning("Not yielding workouts yet!")
            # yield w
        found = True
    if not found:
        raise Exception("No workouts found.")


def convert_step_type(step: dict) -> str:
    if step["intensity"] in ["warmup", "cooldown"]:
        return step["intensity"].upper()

    if step["intensity"] == "active" and step["wkt_step_name"] == "Preparation":
        return "REST"

    if step["intensity"] == "active":
        return "ACTIVE"

    return "REST"


def convert_step_length(step: dict) -> str | None:
    if step["duration_type"] == "distance":
        return round(step["duration_distance"]) * models.meter

    if step["duration_type"] == "open":
        # Runback step
        return None

    return step["duration_time"] * models.second


def convert_step_target(
    step: dict,
    out_step: models.ConcreteStep,
    perceived_effort: bool,
    num_steps: int,
) -> tuple[models.PaceRange | None, models.PowerRange | None]:
    if step["target_type"] == "speed":
        pace_range = parse_pace_range(
            step["custom_target_speed_low"],
            step["custom_target_speed_high"],
        )
        power_range = convert_pace_range_to_power(pace_range)
        return pace_range, power_range

    # 6 minute assessments, RECOVERY, COOLDOWN, and perceived effort segments do not have a pace
    # Provide a generous power range based on %CP for slower ranges
    if step["target_type"] == "open":
        cp = get_critical_power()
        if perceived_effort:
            # Some perceived effort workouts have a warmup
            if num_steps > 3 and step["message_index"] == 1:
                # Perceived effort warmup
                return None, models.PowerRange(cp * 0.3, cp * 0.8)
            # Penultimate step is always the main effort
            if step["message_index"] == num_steps - 1:
                # Perceived effort main body
                return None, models.PowerRange(
                    cp * 0.55,
                    cp * 0.9,
                )
            # Perceived effort workouts start and end with a standing step
            return None, models.PowerRange(0, 50)

        # Recovery steps after hard assessments
        if step["wkt_step_name"] in ["Recovery", "Preparation"]:
            return None, models.PowerRange(0, cp * 0.9)

        if step["duration_type"] == "distance":
            return None, suggested_power_range_for_distance(out_step.length)

        if step["duration_type"] == "time":
            return None, suggested_power_range_for_time(out_step.length)

        # Run back step has no target. Add a wide power range.
        return None, models.PowerRange(
            cp * 0.55,
            cp * 0.9,
        )

    msg = f"Unknown target type {step['target_type']}"
    raise ValueError(msg)


def convert_step_target_pace(step: dict) -> models.PaceRange | None:
    if step["target_type"] == "speed":
        return parse_pace_range(
            step["custom_target_speed_low"],
            step["custom_target_speed_high"],
        )

    return None


def convert_steps(
    steps: list[dict],
    config: models.Config,
    perceived_effort: bool,
) -> list[models.Step]:
    steps_out = []
    valid_step = []
    for step in steps:
        # This does not support nested repeat steps
        if step["duration_type"] == "repeat_until_steps_cmplt":
            times = step["repeat_steps"]
            out_step = models.RepeatStep(times)
            out_step.steps = steps_out[
                step["duration_step"] : step["message_index"] + 1
            ].copy()
            valid_step[step["duration_step"] : step["message_index"] + 1] = [
                False,
            ] * (step["message_index"] - step["duration_step"])
        else:
            out_step = models.ConcreteStep()
            out_step.description = step["notes"]
            out_step.type = convert_step_type(step)
            out_step.length = convert_step_length(step)
            if config.pace_only:
                out_step.power_range = None
                out_step.pace_range = convert_step_target_pace(step)
            else:
                out_step.pace_range, out_step.power_range = convert_step_target(
                    step,
                    out_step,
                    perceived_effort,
                    len(steps),
                )
                # Add adjustment from config
                out_step.power_range += config.power_adjust

        valid_step.append(True)
        steps_out.append(out_step)

    # Remove steps that are part of repeats
    return list(compress(steps_out, valid_step))


def parse_time(pace_string: str) -> models.Quantity:
    minutes, sec = map(int, pace_string.split(":"))
    return minutes * models.minute + sec * models.second


def parse_pace_range(min_provided: float, max_provided: float) -> models.PaceRange:
    minutes = 0.0
    if min_provided != 0.0:
        minutes = 1 / min_provided
    return models.PaceRange(
        minutes * models.second / models.meter,
        (1 / max_provided) * models.second / models.meter,
    )


def parse_distance(text: str) -> models.Quantity:
    match = re.search(r"\(~?([\d.]+ (mi|k?m))\)", text)
    if not match:
        raise ValueError(f"No distance found in `{text}`")
    return models.ureg.parse_expression(match.group(1))


def parse_duration(step_string: str) -> models.Quantity:
    match = re.search(
        r"(?=\d+ (hour|minute|second))((?P<hours>\d+) hours?)?[, ]*((?P<minutes>\d+) minutes?)?[, ]*((?P<seconds>\d+) seconds?)?",
        step_string,
    )
    if not match:
        raise ValueError(f"No duration found in text `{step_string}`")
    parts = match.groupdict()
    duration = models.ureg.Quantity("0 seconds")
    for unit, amount in parts.items():
        if amount:
            duration += int(amount) * models.ureg.parse_units(unit)
    return duration
