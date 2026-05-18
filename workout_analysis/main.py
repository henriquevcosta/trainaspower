#!/usr/bin/env python3
"""
Minimal script:
  - Fetch workout(s) from FinalSurge API
  - Cache results locally (JSON file) to avoid repeat calls
  - Load the current plan (JSON/YAML) from disk
  - Build a prompt that includes the plan slice + workout metrics
  - Call a LiteLLM-exposed model (OpenAI-compatible) to get natural-language feedback
"""

import os
import json
import datetime as dt
import requests
from pathlib import Path

# ------------------- CONFIG -------------------
FINALSURGE_API_KEY = os.getenv("FS_API_KEY")          # set in your env
ATHLETE_ID = "YOUR_ATHLETE_ID"                       # replace with your FS athlete id
CACHE_DIR = Path("./fs_cache")
CACHE_DIR.mkdir(exist_ok=True)
WORKOUT_CACHE = CACHE_DIR / "workouts.json"

PLAN_FILE = Path("./plan.json")   # you can export your plan to JSON and keep it here
LITELLM_URL = "http://localhost:8000/v1/chat/completions"  # adjust to your LiteLLM host
LITELLM_MODEL = "your-model-name"   # e.g., "llama3-8b-instruct"

# ------------------- HELPERS -------------------
def _cache_path_for_date(date_str: str) -> Path:
    return CACHE_DIR / f"workout_{date_str}.json"

def get_workout_from_cache(date_str: str):
    """Return cached workout dict for a given date, or None."""
    p = _cache_path_for_date(date_str)
    if p.is_file():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None

def cache_workout(date_str: str, workout: dict):
    _cache_path_for_date(date_str).write_text(json.dumps(workout, indent=2))

def fetch_workouts(start_date: dt.date, end_date: dt.date):
    """Pull workouts from FinalSurge for the date range; use per-date caching."""
    url = f"https://api-finalsurge.com/v1/athlete/{ATHLETE_ID}/workouts"
    headers = {"Authorization": f"Bearer {FINALSURGE_API_KEY}"}
    params = {"startDate": start_date.isoformat(),
              "endDate":   end_date.isoformat()}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    workouts = resp.json()                     # list of dicts
    for w in workouts:
        d = w["date"]
        cache_workout(d, w)                    # store per-date cache
    return workouts

def load_plan():
    """Load the plan you keep locally (JSON). Edit this file when you swap days."""
    if not PLAN_FILE.is_file():
        raise FileNotFoundError(f"Plan file not found: {PLAN_FILE}")
    return json.loads(PLAN_FILE.read_text())

def build_prompt(plan_slice: dict, workout: dict) -> str:
    """
    Compose a prompt for the LLM.
    Includes:
      - High-level plan info (taken from source [1] and [2] - pace ranges, RPE guidance)
      - The specific day's plan entry (distance, description, target RPE/pace)
      - The actual workout metrics (distance, time, avg HR, RPE, notes)
    """
    # Pace ranges from source [1]
    pace_ranges = (
        "Easy: 6:00-6:50/km\n"
        "Marathon pace (RPE 6): 5:25-5:40/km\n"
        "Half-marathon effort (RPE 7): 5:05-5:20/km\n"
        "10K effort (RPE 8): 4:45-5:00/km"
    )
    # Plan name / target race from source [2]
    plan_name = plan_slice.get("plan_name", "Unnamed plan")
    target_race = plan_slice.get("target_race", "Target race")

    prompt = f"""
You are an experienced running coach. Using the information below, give a concise, actionable insight about the athlete's recent workout and suggest any adjustments for the upcoming days.

=== PLAN OVERVIEW (from source [1] and [2]) ===
Plan: {plan_name}
Target race: {target_race}
Pace zones (approx. flat road):
{pace_ranges}
General guidelines: RPE-based pacing, electrolytes every 20 min & gel every 45 min on long runs, calf prehab after easy runs, flexibility to swap days, reduce intensity before volume, rest if fatigue accumulates.

=== TODAY'S PLANNED WORKOUT ===
Date: {plan_slice.get('date')}
Description: {plan_slice.get('description')}
Distance: {plan_slice.get('distance_km')} km
Target RPE: {plan_slice.get('target_rpe')}
Target pace range: {plan_slice.get('pace_min_per_km')}-{plan_slice.get('pace_max_per_km')} /min km

=== ACTUAL WORKOUT (from FinalSurge) ===
Date: {workout.get('date')}
Distance: {workout.get('distanceMeters',0)/1000:.2f} km
Duration: {workout.get('durationSeconds',0)//60} min {workout.get('durationSeconds',0)%60} s
Average HR: {workout.get('averageHR','n/a')} bpm
Average pace: {workout.get('averagePace','n/a')} sec/100m (approx {workout.get('averagePace',0)*6 if isinstance(workout.get('averagePace'),(int,float)) else 'n/a'} sec/km)
RPE: {workout.get('customFields',{}).get('RPE','n/a')}
Notes: {workout.get('notes','')}

=== YOUR TASK ===
1. Compare the actual workout to the planned target (distance, pace, RPE, HR).
2. Highlight any notable deviations (e.g., pace too fast/slow, HR high/low, RPE mismatch).
3. Provide a brief recommendation: keep as-is, adjust intensity, add recovery, modify nutrition, etc., respecting the plan's flexibility guidelines.
Answer in 3-5 short sentences, plain language, no markdown.
""".strip()
    return prompt

def call_litellm(prompt: str) -> str:
    payload = {
        "model": LITELLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 250,
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(LITELLM_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()

# ------------------- MAIN -------------------
def main():
    # Example: look at yesterday's workout; adjust window as needed
    yesterday = dt.date.today() - dt.timedelta(days=1)
    workouts = fetch_workouts(yesterday, yesterday)
    if not workouts:
        print("No workout found for the selected date.")
        return
    workout = workouts[0]   # we asked for a single day

    # Load plan and find the entry for this date
    plan_data = load_plan()
    # Assuming plan_data is a dict with a key "workouts" that is a list of daily entries
    plan_slice = None
    for entry in plan_data.get("workouts", []):
        if entry.get("date") == workout["date"]:
            plan_slice = entry
            break
    if plan_slice is None:
        print(f"No plan entry found for {workout['date']}. Check your plan file.")
        return

    prompt = build_prompt(plan_slice, workout)
    print("\n--- Prompt sent to LiteLLM ---\n")
    print(prompt)
    print("\n--- Model response ---\n")
    insight = call_litellm(prompt)
    print(insight)

if __name__ == "__main__":
    main()