{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import json\n",
    "import pandas as pd\n",
    "\n",
    "# Specify the path to your JSON file\n",
    "file_path = \"vert-plan-uta2026.json\"\n",
    "\n",
    "# Load and parse the JSON file\n",
    "try:\n",
    "    with open(file_path, \"r\", encoding=\"utf-8\") as file:\n",
    "        data = json.load(file)\n",
    "except json.JSONDecodeError as e:\n",
    "    print(f\"Error decoding JSON: {e}\")\n",
    "except FileNotFoundError:\n",
    "    print(\"File not found. Please ensure the file path is correct.\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "def process_workout_step(step, prefix):\n",
    "    result = ''\n",
    "    if step.get('type','') == 'repeat':\n",
    "        result += f'{prefix}{process_workout_repeats(step, prefix)}'\n",
    "    elif step.get('type','') == 'step':\n",
    "        result += f'{prefix}[{step['variable']}] {step['action']} for {step['value']}'\n",
    "        if step['targetType'] != 'No Target':\n",
    "            result += f' at {step['targetValue']} {step['targetType']}'\n",
    "        result += '<br/>'\n",
    "\n",
    "    return result\n",
    "\n",
    "def process_workout_repeats(step, prefix):\n",
    "    result = f'{prefix}Repeat {step.get('times', -1)} times:<br/> <ul>'\n",
    "    for substep in step.get('steps',[]):\n",
    "        result += process_workout_step(substep, prefix+'<li>') + '</li>'\n",
    "    return result + '</ul>'\n",
    "\n",
    "def process_workout(steps):\n",
    "    result = ''\n",
    "    for step in steps:\n",
    "        result += process_workout_step(step, '')\n",
    "    return result\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "def map_training(training):\n",
    "    keys_to_retain = [\"trainingPeriod\", \"workoutType\", \"surface\", \"difficultyLevel\", \"estimatedTime\", \"parametrizedWorkout\", \"description\", \"id\", \"title\", \"trainingTime\", \"plannedDate\"]\n",
    "    result = {key: training.get(key, None) for key in keys_to_retain }\n",
    "    result[\"description\"] = result.get(\"description\", {\"en\":\"\"})[\"en\"]\n",
    "    result[\"title\"] = result.get(\"title\", {\"en\":\"\"})[\"en\"]\n",
    "    result[\"estimatedTime\"] = result.get(\"estimatedTime\", ['0','0','0'])[1]\n",
    "    result[\"parametrizedWorkout\"] = result.get(\"parametrizedWorkout\", [[],[],[]])[1]\n",
    "    result[\"renderedWorkout\"] = process_workout(result[\"parametrizedWorkout\"])\n",
    "    return result\n",
    "\n",
    "\n",
    "\n",
    "'''\n",
    "[\n",
    "[{'variable': 'Time', 'targetValue': '', 'action': 'Warm up', 'isDeleteOpen': False, 'targetType': 'No Target', 'id': 1666739524841, 'type': 'step', 'value': '00h:20m:00s'}, {'times': 4, 'id': 1666739548134, 'type': 'repeat', 'steps': [{'variable': 'Time', 'targetValue': '8', 'action': 'Run Uphill', 'isDeleteOpen': False, 'targetType': 'RPE', 'id': 1666739554725, 'type': 'step', 'value': '00h:03m:00s', 'selected': False, 'chosen': False}, {'variable': 'Time', 'targetValue': '', 'action': 'Recover', 'isDeleteOpen': False, 'targetType': 'No Target', 'id': 1666739575154, 'type': 'step', 'value': '00h:03m:00s', 'selected': False, 'chosen': False}]}, {'variable': 'Time', 'targetValue': '', 'action': 'Cool down', 'isDeleteOpen': False, 'targetType': 'No Target', 'id': 1666739617873, 'type': 'step', 'value': '00h:15m:00s'}],\n",
    "\n",
    "[{'variable': 'Time', 'targetValue': '', 'action': 'Warm up', 'isDeleteOpen': False, 'targetType': 'No Target', 'id': 1666739524841, 'type': 'step', 'value': '00h:20m:00s'}, {'times': 5, 'id': 1666739548134, 'type': 'repeat', 'steps': [{'variable': 'Time', 'targetValue': '8', 'action': 'Run Uphill', 'isDeleteOpen': False, 'targetType': 'RPE', 'id': 1666739554725, 'type': 'step', 'value': '00h:03m:00s', 'selected': False, 'chosen': False}, {'variable': 'Time', 'targetValue': '', 'action': 'Recover', 'isDeleteOpen': False, 'targetType': 'No Target', 'id': 1666739575154, 'type': 'step', 'value': '00h:03m:00s', 'selected': False, 'chosen': False}]}, {'variable': 'Time', 'targetValue': '', 'action': 'Cool down', 'isDeleteOpen': False, 'targetType': 'No Target', 'id': 1666739617873, 'type': 'step', 'value': '00h:25m:00s'}],\n",
    "\n",
    "[{'variable': 'Time', 'targetValue': '', 'action': 'Warm up', 'isDeleteOpen': False, 'targetType': 'No Target', 'id': 1666739524841, 'type': 'step', 'value': '00h:20m:00s'}, {'times': 6, 'id': 1666739548134, 'type': 'repeat', 'steps': [{'variable': 'Time', 'targetValue': '8', 'action': 'Run Uphill', 'isDeleteOpen': False, 'targetType': 'RPE', 'id': 1666739554725, 'type': 'step', 'value': '00h:03m:00s', 'selected': False, 'chosen': False}, {'variable': 'Time', 'targetValue': '', 'action': 'Recover', 'isDeleteOpen': False, 'targetType': 'No Target', 'id': 1666739575154, 'type': 'step', 'value': '00h:03m:00s', 'selected': False, 'chosen': False}]}, {'variable': 'Time', 'targetValue': '', 'action': 'Cool down', 'isDeleteOpen': False, 'targetType': 'No Target', 'id': 1666739617873, 'type': 'step', 'value': '00h:20m:00s'}]]\n",
    "'''\n",
    "\n",
    "training_days_raw = pd.DataFrame([map_training(session[0]) for session in data['days'] if session[0].get(\"isDone\",False) == False])\n",
    "training_days = training_days_raw.drop(columns=['parametrizedWorkout', 'id'])\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "training_days = training_days[[    'plannedDate', 'workoutType', 'title', 'description', 'renderedWorkout', 'difficultyLevel', 'trainingTime', 'trainingPeriod', 'surface', 'estimatedTime' ]]\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "training_days.rename(columns={'trainingPeriod': 'Period',\n",
    "                              'workoutType': 'Type',\n",
    "                              'surface': 'Surface',\n",
    "                              'difficultyLevel': 'Difficulty',\n",
    "                              'description': 'Description',\n",
    "                              'title': 'Title',\n",
    "                              'trainingTime': 'Time',\n",
    "                              'plannedDate': 'Date',\n",
    "                              'renderedWorkout': 'Workout Detail',\n",
    "                              }, inplace=True)\n",
    "training_days\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Assign class to the rows so that we can scroll to today\n",
    "classes = pd.DataFrame('', index=training_days.index, columns=training_days.columns)\n",
    "classes.loc[:, 'Date'] = training_days['Date']"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "from IPython.display import display, HTML\n",
    "\n",
    "styled_table = training_days.style.format({\n",
    "    \"Description\": lambda x: x,\n",
    "    \"title\": lambda x: x,\n",
    "    \"Workout Detail\":lambda x: x,\n",
    "    }).set_properties(**{'font-size': '11pt', 'font-family': 'Arial', 'border': '1px solid #000000'}).hide(axis=\"index\")  # Apply HTML format to the \"description\" column\n",
    "\n",
    "styled_table.set_td_classes(classes)\n",
    "\n",
    "code = styled_table.to_html(escape=False, classes='table')\n",
    "\n",
    "\n",
    "# Wrap the table HTML in a full HTML document that includes JavaScript to scroll to the element with class \"today\"\n",
    "html_content = f\"\"\"\n",
    "<html>\n",
    "<head>\n",
    "  <meta charset=\"UTF-8\">\n",
    "  <title>UTA50 2026 Training Plan</title>\n",
    "  <script>\n",
    "      function scrollToToday() {{\n",
    "        const today = new Date();\n",
    "        const dd = String(today.getDate()).padStart(2, '0');\n",
    "        const mm = String(today.getMonth() + 1).padStart(2, '0'); // Months are zero-indexed\n",
    "        const yyyy = today.getFullYear();\n",
    "\n",
    "        const formattedDate = `${{dd}}/${{mm}}/${{yyyy}}`;\n",
    "      // Find the first element with the \"today\" class\n",
    "      var el = document.getElementsByClassName(formattedDate)[0];\n",
    "      if (el) {{\n",
    "        el.scrollIntoView({{behavior: 'smooth', block: 'center'}});\n",
    "      }}\n",
    "    }};\n",
    "    window.onload = scrollToToday;\n",
    "  </script>\n",
    "</head>\n",
    "<body>\n",
    "   <button onclick=\"scrollToToday()\">Scroll to Today's Date</button>\n",
    "  {code}\n",
    "</body>\n",
    "</html>\n",
    "\"\"\"\n",
    "\n",
    "with open('plan.html', 'w') as f:\n",
    "    f.write(html_content)\n",
    "display(html_content)\n"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "vertconverter",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.13.1"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}
