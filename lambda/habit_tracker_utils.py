import datetime
import json
import random


def get_active_streak(dates_iso, current_date_iso):

    # Handle empty date lists
    if not dates_iso:
        return 0

    # Convert from ISO Format to Dates Format
    dates = [datetime.date.fromisoformat(d) for d in dates_iso]
    current_date = datetime.date.fromisoformat(current_date_iso)

    # If the current day is in the dates list, start streak at 1 and pop it
    if (dates[-1] - current_date).days == 0:
        streak = 1
        dates.pop(-1)
    # Otherwise start the streak at 0, do nothing to 'dates'
    else:
        streak = 0

    # Get current day (delegated to alexa handler)
    # current_date = datetime.date.today()

    # Iterate backwards from today
    for date in dates[::-1]:
        # If the difference in days is 1, add to the streak
        if (current_date - date).days == 1:
            streak += 1
        # Otherwise, the streak is over
        else:
            break
        # Update current date
        current_date = date

    return streak


def get_present_tense(verb):

    # Instantiate verbs_map dict
    verbs_map = {}

    # Attempt to load json, default response is just the input
    try:
        with open("./documents/verb_tenses.json", "r") as verb_file:
            verbs_map = json.load(verb_file)
    except:
        return verb

    # If we have a present tense associated, return it
    if verb in verbs_map:

        return verbs_map[verb]

    # Otherwise return the original verb by default
    else:

        return verb


def get_phrase(streak_length):

    # Attempt to open json, return default phrases if failure
    try:
        with open("./documents/phrases.json", "r") as phrases_file:
            phrases_map = json.load(phrases_file)
    except:
        return "Way to go!" if streaks_length else "Start your streak strong! Let me know when you've finished by saying: Check Off a Habit for me."

    # Map streak length to an appropriate phrase
    if streak_length == 0:
        return random.choice(phrases_map["0"])

    elif 0 < streak_length <= 7:
        return random.choice(phrases_map["first week"])

    elif 7 < streak_length <= 58:
        return random.choice(phrases_map["mid weeks"])

    elif 58 < streak_length <= 65:
        return random.choice(phrases_map["last week"])

    elif streak_length == 66:
        return random.choice(phrases_map["66"])

    # Return default phrase for weirdness
    else:
        return "Way to go!"
