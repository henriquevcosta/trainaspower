"""Load structured run workouts from OWL-style YAML (e.g. bondi-2-manly/owl.yml) into models."""

from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any, List, Optional

import yaml
from loguru import logger
from pint import Quantity

from trainaspower import models


def _step_intensity_from_description(description: str) -> str:
    desc_lower = description.lower()
    if "warm up" in desc_lower or "warm-up" in desc_lower:
        return "WARMUP"
    if "cool down" in desc_lower or "cool-down" in desc_lower:
        return "COOLDOWN"
    if "recover" in desc_lower or "rest" in desc_lower:
        return "REST"
    return "ACTIVE"


def _parse_pace_per_km(raw: str) -> Quantity:
    """Parse strings like '6:40 /km' or '5:05/km' to a pint pace (time per kilometer)."""
    s = raw.strip().strip('"').strip("'")
    s = re.sub(r"\s*/\s*km\s*$", "", s, flags=re.IGNORECASE).strip()
    if ":" not in s:
        raise ValueError(f"Unrecognized pace string: {raw!r}")
    mins_str, secs_str = s.split(":", 1)
    mins = int(mins_str)
    secs = int(secs_str)
    return (mins * models.minute + secs * models.second) / models.kilometer


def _parse_pace_range(data: Any) -> Optional[models.PaceRange]:
    if not data or not isinstance(data, dict):
        return None
    low = data.get("min")
    high = data.get("max")
    if low is None or high is None:
        return None
    return models.PaceRange(_parse_pace_per_km(str(low)), _parse_pace_per_km(str(high)))


def _parse_length(raw: Any) -> Optional[Quantity]:
    if raw is None:
        return None
    if isinstance(raw, Quantity):
        return raw
    s = str(raw).strip().strip('"').strip("'")
    sl = re.sub(r"\s+", "", s.lower())
    if sl.endswith("km"):
        return float(sl[:-2]) * models.kilometer
    if sl.endswith("m") and not sl.endswith("km"):
        return float(sl[:-1]) * models.meter
    m = re.match(r"^(\d+(?:\.\d+)?)\s*min(ute)?s?$", sl)
    if m:
        return float(m.group(1)) * models.minute
    m = re.match(r"^(\d+(?:\.\d+)?)\s*sec(ond)?s?$", sl)
    if m:
        return float(m.group(1)) * models.second
    raise ValueError(f"Unsupported step length: {raw!r}")


def _parse_workout_distance(raw: Any) -> Optional[Quantity]:
    if raw is None:
        return None
    return _parse_length(raw)


def _parse_concrete_step(data: dict) -> models.ConcreteStep:
    step = models.ConcreteStep()
    step.description = str(data.get("description", ""))
    step.comments = str(data.get("comments", ""))
    step.type = _step_intensity_from_description(step.description)
    step.length = _parse_length(data.get("length"))
    step.pace_range = _parse_pace_range(data.get("pace_range"))
    step.power_range = None
    step.hr_zone = None
    return step


def _parse_repeat_step(data: dict) -> models.RepeatStep:
    reps = int(data["repetitions"])
    rs = models.RepeatStep(reps)
    if "description" in data and data["description"]:
        rs.description = str(data["description"])
    rs.comments = str(data.get("comments", ""))
    nested = data.get("steps") or []
    rs.steps = [_parse_step_item(s) for s in nested]
    return rs


def _parse_step_item(raw: Any) -> models.Step:
    if not isinstance(raw, dict):
        raise ValueError(f"Step must be a mapping, got {type(raw).__name__}")
    kind = raw.get("type")
    if kind == "RepeatStep":
        return _parse_repeat_step(raw)
    if kind == "ConcreteStep" or kind is None:
        return _parse_concrete_step(raw)
    raise ValueError(f"Unknown step type: {kind!r}")


def _parse_workout_block(data: dict) -> models.Workout:
    w = models.Workout()
    w.id = str(data.get("id", ""))
    w.name = str(data.get("name", w.id))
    w.description = str(data.get("description", ""))
    raw_date = data.get("date")
    if isinstance(raw_date, datetime.datetime):
        w.date = raw_date.date()
    elif isinstance(raw_date, datetime.date):
        w.date = raw_date
    elif isinstance(raw_date, str):
        w.date = datetime.date.fromisoformat(raw_date)
    else:
        raise ValueError(f"Workout {w.id!r}: invalid date {raw_date!r}")

    w.type = str(data.get("type", "RUN")).strip() or "RUN"
    w.distance = _parse_workout_distance(data.get("distance"))
    w.duration = None

    steps_in = data.get("steps")
    if steps_in is None:
        w.steps = []
    else:
        w.steps = [_parse_step_item(s) for s in steps_in]

    return w


def load_workouts_from_yaml(path: Path | str) -> List[models.Workout]:
    """
    Load workouts from a YAML file: a list of workout objects with id, name, type, date,
    distance, description, and steps (ConcreteStep / RepeatStep), matching bondi-2-manly/owl.yml.
    """
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"OWL plan file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"OWL YAML root must be a list of workouts, got {type(raw).__name__}")

    out: List[models.Workout] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            logger.warning(f"Skipping non-dict entry at index {i}: {item!r}")
            continue
        try:
            out.append(_parse_workout_block(item))
        except Exception as exc:
            wid = item.get("id", f"index-{i}")
            raise ValueError(f"Failed to parse workout {wid!r}: {exc}") from exc

    out.sort(key=lambda wo: wo.date)
    return out
