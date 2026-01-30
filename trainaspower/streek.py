from collections.abc import Generator
import datetime
import json
import re
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from loguru import logger
from pint import Quantity

from . import models


class StreekWorkoutLoader:
    """Loader for Streek workout day JSON files."""

    # Steps to ignore
    IGNORED_STEPS = [
        "3 Minute Morning Stretching Routine",
        "Foam Rolling and Massage Ball"
    ]

    DAY_NAMES = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }

    def __init__(self, folder_path: Path | str, plan_start_date: datetime.date, plan_web_base_url: str):
        """
        Initialize the loader.

        Args:
            folder_path: Path to folder containing workout-day JSON files
            plan_start_date: Starting date of the training plan
            plan_web_base_url: Base URL that you see in the browser for this plan up until the ?, e.g. https://app.streek.run/training-plan/uta50-training-plan/
        """
        self.folder_path = Path(folder_path)
        self.plan_start_date = plan_start_date
        self.base_url = plan_web_base_url

    def get_next_workouts(self, config: models.Config) -> Generator[models.Workout, None, None]:
        """
        Load workouts from JSON files in the folder.

        Args:
            config: Configuration object

        Yields:
            Workout objects
        """
        logger.info(f"Fetching Streek workouts from {self.folder_path}")

        if not self.folder_path.exists():
            raise FileNotFoundError(f"Folder not found: {self.folder_path}")

        # Find all JSON files in the folder
        json_files = sorted(self.folder_path.glob("*.json"))

        if not json_files:
            logger.warning(f"No JSON files found in {self.folder_path}")
            return

        found = False
        for json_file in json_files:
            logger.info(f"Processing {json_file.name}")
            try:
                workouts = self._parse_workout_file(json_file)
                for workout in workouts:
                    found = True
                    yield workout
            except Exception as exc:
                logger.error(f"Error processing {json_file.name}: {exc}")
                continue

        if not found:
            logger.warning("No workouts found in any files.")

    def _parse_workout_file(self, json_file: Path) -> list[models.Workout]:
        """Parse a single workout day JSON file."""
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not data.get("success") or "data" not in data:
            logger.warning(f"Invalid JSON structure in {json_file.name}")
            return []

        html_content = data["data"].get("html")
        if not html_content:
            logger.warning(f"No HTML content in {json_file.name}")
            return []

        soup = BeautifulSoup(html_content, "html5lib")

        # Extract week/day info
        week_day_info = self._extract_week_day(soup)
        if not week_day_info:
            logger.warning(f"Could not extract week/day info from {json_file.name}")
            return []

        day_name, week_number = week_day_info
        workout_date = self._calculate_date(day_name, week_number)

        # Extract workout steps, separating strength and running workouts
        strength_workouts, running_steps, workout_level_notes = self._extract_workout_steps(soup)

        # Create workout(s) with sequential counter starting at 1 for each file
        workouts = []
        counter = 1

        # Create strength workout if present
        if strength_workouts:
            strength_url = self._build_strength_url(week_number, day_name)
            strength_workout = self._create_strength_workout(
                workout_date=workout_date,
                week_number=week_number,
                day_name=day_name,
                strength_url=strength_url,
                counter=counter
            )
            workouts.append(strength_workout)
            counter += 1

        # Create running workout if present
        if running_steps:
            workout = self._create_workout(
                soup=soup,
                workout_type="Run",
                workout_date=workout_date,
                week_number=week_number,
                day_name=day_name,
                steps=running_steps,
                counter=counter,
                workflow_notes=workout_level_notes
            )
            workouts.append(workout)
            counter += 1

        if not workouts:
            logger.info(f"No valid workout steps found in {json_file.name}")

        return workouts

    def _extract_week_day(self, soup: BeautifulSoup) -> Optional[tuple[str, int]]:
        """Extract day name and week number from HTML."""
        # Look for text like "Wednesday Wk 9"
        week_day_pattern = re.compile(r"(\w+)\s+Wk\s+(\d+)", re.IGNORECASE)

        # Search in all text
        for element in soup.find_all(text=True):
            match = week_day_pattern.search(element)
            if match:
                day_name = match.group(1).capitalize()
                week_number = int(match.group(2))
                if day_name in self.DAY_NAMES:
                    return (day_name, week_number)

        return None

    def _calculate_date(self, day_name: str, week_number: int) -> datetime.date:
        """Calculate workout date from day name and week number."""
        day_offset = self.DAY_NAMES[day_name]
        # Calculate: start_date + (week_number - 1) * 7 + day_offset
        # But we need to find the first occurrence of that day in week 1
        # Assuming plan_start_date is the start of week 1 (could be any day)
        # We need to find the first occurrence of the target day

        # Get the day of week for plan_start_date (0=Monday, 6=Sunday)
        start_weekday = self.plan_start_date.weekday()
        target_weekday = day_offset

        # Calculate days to add to get to the first occurrence of target day
        days_to_first_occurrence = (target_weekday - start_weekday) % 7

        # Calculate the date: first occurrence + (week_number - 1) * 7
        first_occurrence = self.plan_start_date + datetime.timedelta(days=days_to_first_occurrence)
        workout_date = first_occurrence + datetime.timedelta(weeks=week_number - 1)

        return workout_date

    def _build_strength_url(self, week_number: int, day_name: str) -> str:
        """Build the strength workout detail page URL."""
        # URL format: https://app.streek.run/training-plan/base-training-plan/?week=9&day=Saturday
        return f"{self.base_url}?week={week_number}&day={day_name}"

    def _create_strength_workout(
        self,
        workout_date: datetime.date,
        week_number: int,
        day_name: str,
        strength_url: str,
        counter: int
    ) -> models.Workout:
        """Create a strength workout object."""
        workout = models.Workout()
        workout.name = "Strength work"
        workout.description = f"Go to the detail page at {strength_url}"
        workout.date = workout_date
        workout.type = "Strength Training"
        workout.id = f"Wk{week_number}-{day_name}-{counter}"
        workout.steps = None
        workout.distance = None
        workout.duration = None

        return workout

    def _extract_workout_steps(self, soup: BeautifulSoup) -> tuple[list[str], list[models.ConcreteStep], list[str]]:
        """
        Extract workout steps from HTML, filtering out ignored steps.

        Returns:
            tuple: (list of strength workout names, list of running workout steps, the workout level description from the steps)
        """
        strength_workouts = []
        running_steps = []
        workout_level_notes = []

        # Find all anchor tags that represent workout steps
        step_anchors = soup.find_all("a", class_=re.compile("min-h-"))

        for anchor in step_anchors:
            # Extract step name from h5
            h5 = anchor.find("h5")
            if not h5:
                continue

            step_name = h5.get_text(strip=True)

            # Skip ignored steps
            if any(ignored in step_name for ignored in self.IGNORED_STEPS):
                logger.debug(f"Skipping ignored step: {step_name}")
                continue

            # Check if this is a strength workout
            if "strength" in step_name.lower():
                strength_workouts.append(step_name)
                continue

            # Extract description from p tag for running workouts
            p_tag = anchor.find("div", class_=re.compile("font-regular"))
            if not p_tag:
                continue
            p_tag = p_tag.find("p")
            if not p_tag:
                continue

            # Only process "Run" steps
            if step_name != "Run":
                continue

            # Replace <br /> tags with newlines before getting text
            for br in p_tag.find_all("br"):
                br.replace_with("\n")

            # Get the text, preserving line breaks
            description_text = p_tag.get_text(separator="\n", strip=True)

            # Split by newlines to get individual step descriptions
            step_descriptions = [s.strip() for s in description_text.split("\n") if s.strip()]

            # Create a step for each description
            for step_desc in step_descriptions:
                # Collect for workout-level notes
                workout_level_notes.append(step_desc)

                # Check if this is a "detail" line, in which case it is not a new step
                if (
                    self._is_elevation_line(step_desc)
                    or self._is_including_line(step_desc)
                    or step_desc.startswith("in ")
                ):
                    if running_steps:
                        # Attach to previous step's comments
                        running_steps[-1].comments += f"\n{step_desc}"

                    continue

                step = self._create_step_from_description(step_name, step_desc)
                if step:
                    running_steps.append(step)

        return (strength_workouts, running_steps, workout_level_notes)

    def _is_elevation_line(self, description: str) -> bool:
        """Check if a description is an elevation line (e.g., 'Elev: 200m', 'Elev: 100-200m')."""
        # Pattern to match "Elev: " followed by a distance or distance range
        elevation_pattern = re.compile(r"^Elev:\s*\d+(?:-\d+)?\s*(km|m)", re.IGNORECASE)
        return bool(elevation_pattern.match(description))

    def _is_including_line(self, description: str) -> bool:
        """Check if a description line starts with 'including' (case-insensitive) or '+ '."""
        desc_stripped = description.strip()
        return desc_stripped.lower().startswith("including") or desc_stripped.startswith("+ ")

    def _create_step_from_description(self, step_name: str, description: str) -> Optional[models.ConcreteStep]:
        """Create a ConcreteStep from a step description."""
        step = models.ConcreteStep()
        # For "Run" steps, use the full description as step description
        # For other steps, use step_name
        if step_name == "Run":
            step.description = description
            step.comments = ""
        else:
            step.description = step_name
            step.comments = description
        step.type = self._determine_step_type(description)

        # Parse distance
        distance = self._parse_distance(description)
        if distance:
            step.length = distance

        return step

    def _determine_step_type(self, description: str) -> str:
        """Determine step type from description."""
        desc_lower = description.lower()
        if "warm up" in desc_lower or "warm-up" in desc_lower:
            return "WARMUP"
        elif "cool down" in desc_lower or "cool-down" in desc_lower:
            return "COOLDOWN"
        elif "recover" in desc_lower or "rest" in desc_lower:
            return "REST"
        else:
            return "ACTIVE"

    def _parse_distance(self, description: str) -> Optional[Quantity]:
        """Parse distance from description (e.g., '2-3km', '5km', '2km')."""
        # Pattern to match distances like "2-3km", "5km", "2km", "500m"
        distance_pattern = re.compile(r"(\d+(?:-\d+)?)\s*(km|m)", re.IGNORECASE)

        matches = distance_pattern.findall(description)
        if not matches:
            return None

        # Use the first match (or could sum all if multiple distances)
        distance_str, unit = matches[0]

        # Handle ranges like "2-3km" - use maximum value
        if "-" in distance_str:
            parts = distance_str.split("-")
            distance_value = float(parts[1])  # Use max value
        else:
            distance_value = float(distance_str)

        # Convert to Quantity
        if unit.lower() == "km":
            return distance_value * models.kilometer
        elif unit.lower() == "m":
            return distance_value * models.meter
        else:
            logger.warning(f"Unknown distance unit: {unit}")
            return None

    def _create_workout(
        self,
        soup: BeautifulSoup,
        workout_type: str,
        workout_date: datetime.date,
        week_number: int,
        day_name: str,
        steps: list[models.ConcreteStep],
        counter: int = 1,
        workflow_notes: list[str] | None = None
    ) -> models.Workout:
        """Create a Workout object."""
        workout = models.Workout()

        # Extract workout name from h3
        h3 = soup.find("h3")
        if h3:
            base_name = h3.get_text(strip=True)
        else:
            base_name = f"{day_name} Workout"
        workout.name = base_name

        workout.description = "\n".join(workflow_notes)

        workout.date = workout_date
        workout.type = workout_type
        workout.id = f"Wk{week_number}-{day_name}-{counter}"
        workout.steps = steps

        # Calculate total distance
        total_distance = self._calculate_total_distance(steps)
        workout.distance = total_distance

        workout.duration = None  # Not available in HTML

        return workout

    def _calculate_total_distance(self, steps: list[models.ConcreteStep]) -> Optional[Quantity]:
        """Calculate total distance from all steps."""
        total = None
        for step in steps:
            if step.length:
                if total is None:
                    total = step.length
                else:
                    # Ensure units are compatible
                    try:
                        if total.check(step.length):
                            total += step.length
                        else:
                            # Convert to same units
                            total = total.to(total.units) + step.length.to(total.units)
                    except Exception as e:
                        logger.warning(f"Could not add distances: {e}")
                        return None

        return total


def get_next_workouts(config: models.Config, folder_path: Path | str, plan_start_date: datetime.date) -> Generator[models.Workout, None, None]:
    """
    Convenience function to get workouts from Streek files.

    Args:
        config: Configuration object
        folder_path: Path to folder containing workout-day JSON files
        plan_start_date: Starting date of the training plan

    Yields:
        Workout objects
    """
    loader = StreekWorkoutLoader(folder_path, plan_start_date)
    yield from loader.get_next_workouts(config)

