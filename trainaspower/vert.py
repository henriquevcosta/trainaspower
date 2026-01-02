from collections.abc import Generator
import datetime
import json
from math import log
from typing import Optional

from bs4 import BeautifulSoup
import dateparser
from loguru import logger
from pint import Quantity

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
DIFFICULTY_ARRAY_INDEX=2

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

        parameterized_workout = day["parametrizedWorkout"][DIFFICULTY_ARRAY_INDEX]
        if not parameterized_workout:
            logger.info("Rest day")
            continue

        title = day["title"][LANGUAGE]
        # Convert from
        #    04 / BB Medium* / Sunday / Easy run + uphill strides
        # to
        #    Easy run + uphill strides
        if title.count("/") >= 3:
            title_parts = title.split("/", 3)
            title = title_parts[3].strip()

        description = day["description"][LANGUAGE]

        soup = BeautifulSoup(description, "html5lib")
        description = soup.get_text("\n\n")
        all_videos = soup.find_all("video")
        if all_videos:
            description += "\n\nRelated Videos:"
        for video in all_videos:
            logger.debug(f"Found video tag: {video}")
            video_src = video.find_next("source")["src"]
            logger.debug(f"Video link: {video_src}")
            description += f"\n{video_src}"

        conditioning = []
        cross_training = []
        other_steps = []
        for step in parameterized_workout:
            match step.get("action", ""):
                case "Conditioning training":
                    conditioning.append(step)
                case "Cross Training":
                    cross_training.append(step)
                case _:
                    other_steps.append(step)

        # In mixed workouts the conditioning and crosstraining steps are mixed in with the run steps, and each is a separate workout garmin-wise
        for step in conditioning:
            w = models.Workout()

            w.date = date
            # TODO change to enum
            w.type = "Strength Training"
            w.name = title
            w.description = description
            if step.get("variable","") == "Time":
                w.duration = convert_step_length(step)

            yield w

        for step in cross_training:
            w = models.Workout()

            w.date = date
            # TODO change to enum
            w.type = "Cross Training"
            w.name = title
            w.description = description
            if step.get("variable","") == "Time":
                w.duration = convert_step_length(step)

            yield w

        if other_steps:
            w = models.Workout()
            w.date = date
            # TODO change to enum
            w.type = "Run"
            # TODO choose a nicer sub-activity type depending on the type of run?
            w.name = title
            w.description = description

            w.steps = convert_steps(other_steps, config)
            w.duration = sum_steps_duration(w.steps)
            yield w
        found = True
    if not found:
        raise Exception("No workouts found.")

def sum_steps_duration(steps: list[models.Step], duration: Optional[Quantity]=None, repeats: int=1) -> Optional[Quantity]:
    inner_duration = duration
    for step in steps:
        if isinstance(step, models.ConcreteStep):
            if step.length:
                if inner_duration is None:
                    inner_duration = step.length * repeats
                else:
                    if inner_duration.check(step.length):
                        inner_duration += step.length * repeats
                    else:
                        logger.warning("Mismatching durations in steps list", steps=steps)
                        return None
            else:
                return None
        elif isinstance(step, models.RepeatStep):
            repeat_duration = sum_steps_duration(step.steps, inner_duration, step.repetitions * repeats)
            if repeat_duration is None:
                return None
            else:
                inner_duration = repeat_duration

    return inner_duration


def convert_step_type(step: dict) -> str:
    match step.get("action", "").lower():
        case "cool down":
            return "COOLDOWN"
        case "warm up":
            return "WARMUP"
        case "recover":
            return "REST"
        case _:
            return "ACTIVE"


def convert_step_length(step: dict) -> Quantity | None:
    if step["variable"] == "Time":
        duration = datetime.datetime.strptime(step["value"],  "%Hh:%Mm:%Ss")
        return duration.hour * models.hour + duration.minute * models.minute + duration.second * models.second
    else:
        logger.warning(f"Unexpected step length type: {step}")
        return None


def convert_steps(
    steps: list[dict],
    config: models.Config
) -> list[models.Step]:
    steps_out = []
    for step in steps:
        if step.get("type", "step") == "repeat":
            times = step["times"]
            out_step = models.RepeatStep(times)
            out_step.steps = convert_steps(step["steps"], config)
        else:
            out_step = models.ConcreteStep()
            out_step.description = step["action"]
            comments = f"{step['targetType']} {step['targetValue']}" if "targetType" in step else None
            out_step.comments = comments
            out_step.type = convert_step_type(step)
            out_step.length = convert_step_length(step)

        steps_out.append(out_step)

    return steps_out
