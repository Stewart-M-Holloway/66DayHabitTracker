# -*- coding: utf-8 -*-

# This sample demonstrates handling intents from an Alexa skill using the Alexa Skills Kit SDK for Python.
# Please visit https://alexa.design/cookbook for additional examples on implementing slots, dialog management,
# session persistence, api calls, and more.
# This sample is built using the handler classes approach in skill builder.
from ask_sdk_model.dialog import delegate_directive
from ask_sdk_model import Response
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
import logging
import ask_sdk_core.utils as ask_utils
import json
from ask_sdk_model.interfaces.alexa.presentation.apl import (
    RenderDocumentDirective)

import os
import boto3
import json
import datetime
import pytz

from habit_tracker_utils import get_active_streak, get_present_tense, get_phrase

from ask_sdk.standard import StandardSkillBuilder
from ask_sdk_dynamodb.adapter import DynamoDbAdapter
from ask_sdk_core.dispatch_components import AbstractRequestInterceptor
from ask_sdk_core.dispatch_components import AbstractResponseInterceptor

# For testing purposes, True in "live"
HABIT_TRACKING = True


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

'''
Misc Handlers, Custom Functionality

    - LaunchRequestHandler: On First Launch
    - YesHandler: Contextually Handles "Yes" responses
    - NoHandler: Contextually Handles "No" responses
    - PromptAddHandler: If no habits exist, this is the default handler to prompt user to add a habit

'''


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Code to get User's time zone, and personalize the greeting
        device_id = handler_input.request_envelope.context.system.device.device_id
        user_time_zone = ""
        greeting = ""

        try:
            user_preferences_client = handler_input.service_client_factory.get_ups_service()
            user_time_zone = user_preferences_client.get_system_time_zone(
                device_id)
        except Exception as e:
            user_time_zone = 'error.'
            logger.error(e)

        if user_time_zone == 'error':
            greeting = 'Hello.'
        else:
            # get the hour of the day or night in your customer's time zone
            hour = datetime.datetime.now(pytz.timezone(user_time_zone)).hour
            if 0 <= hour and hour <= 4:
                greeting = "Hi night-owl!"
            elif 5 <= hour and hour <= 11:
                greeting = "Good morning!"
            elif 12 <= hour and hour <= 17:
                greeting = "Good afternoon!"
            elif 17 <= hour and hour <= 23:
                greeting = "Good evening!"
            else:
                greeting = "Howdy partner!"

        # Instantiate Alexa Response and Visuals
        speak_output = ''
        title = ''
        subtitle = ''

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # If it's the first time the user's tried the app
        if session_attributes["visits"] == 0:

            # Explain the concept, and ask the User if they'd like to add a habit
            speak_output = f"{greeting} Welcome to 66 Days To A Better You. " \
                f"On average, it takes about 66 days to form a new " \
                f"habit. I can help keep track of these habits and " \
                f"try to keep you on track towards reaching your goals. " \
                f"Would you like to get started?"
            title = 'Say "yes."'
            subtitle = 'Start Tracking Your Habits!'

            # On yes response, Add a Habit (On no, cancel intent)
            session_attributes["on_yes"] = "AddHabitIntent"

        # If the User has visited before
        else:
            speak_output = f"{greeting} Welcome back to 66 Days To A Better You! "
            session_attributes["add_on_yes"] = False

            # If the user has active habits
            if session_attributes['habits']:

                # Ask the User what they'd like to do, and listen for response
                speak_output += f"You have active habits, what would you like me " \
                    f"to do? You can say things like Check off a Habit, Add a Habit, " \
                    f"Delete a Habit, Check Habit streaks, or Check Habit Names."
                title = 'Valid Commands:'
                subtitle = 'Check off, Add, Rename, Delete, or Check Streaks'

            # Otherwise if the User does not have any active habits
            else:

                # Ask the user if they'd like to add a habit
                speak_output += f"Looks like I'm not tracking any habits " \
                    f"for you at the moment, would you like me to add a habit " \
                    f"for you?"
                title = 'Say "yes."'
                subtitle = 'Start Tracking Your Habits!'

                # On yes response, Add a Habit (On no, cancel intent)
                session_attributes["on_yes"] = "AddHabitIntent"

        # increment the number of visits and save the session attributes so the
        # ResponseInterceptor will save it persistently.
        session_attributes["visits"] = session_attributes["visits"] + 1

        # ====================================================================
        # Add a visual with Alexa Layouts
        # ====================================================================
        # Import an Alexa Presentation Language (APL) template
        with open("./documents/APL_simple.json") as apl_doc:
            apl_simple = json.load(apl_doc)

            if ask_utils.get_supported_interfaces(handler_input).alexa_presentation_apl is not None:
                handler_input.response_builder.add_directive(
                    RenderDocumentDirective(
                        document=apl_simple,
                        datasources={
                            "myData": {
                                # ====================================================================
                                # Set a headline and subhead to display on the screen if there is one
                                # ====================================================================
                                "Title": title,
                                "Subtitle": subtitle,
                            }
                        }
                    )
                )

        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask(speak_output)
            .response
        )


class YesHandler(AbstractRequestHandler):
    """Handler for Contextually Handling Yes"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
            and ask_utils.is_intent_name("AMAZON.YesIntent")(handler_input)
        )

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # What did the user say "yes" to?
        next_intent = session_attributes["on_yes"]

        # Reset "yes" to head to help
        session_attributes["on_yes"] = "AMAZON.HelpIntent"

        # Route the User to the next intent
        updateIntent = {
            'name': next_intent,
            'confirmation_status': 'NONE',
            'slots': None
        }
        return (
            handler_input.response_builder
            .add_directive(delegate_directive.DelegateDirective(updated_intent=updateIntent))
            .response
        )


class NoHandler(AbstractRequestHandler):
    """Handler for Contextually Handling No"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
            and ask_utils.is_intent_name("AMAZON.NoIntent")(handler_input)
        )

    def handle(self, handler_input):

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # What did the user say "no" to?
        next_intent = session_attributes["on_yes"]

        # If the user said "no" to adding a habit, we should close the app
        if next_intent == "AddHabitIntent":

            updateIntent = {
                'name': "AMAZON.CancelIntent",
                'confirmation_status': 'NONE',
                'slots': None
            }

        # If the user said "no" to something else, we should route them to help
        else:

            updateIntent = {
                'name': "AMAZON.HelpIntent",
                'confirmation_status': 'NONE',
                'slots': None
            }

        return (
            handler_input.response_builder
            .add_directive(delegate_directive.DelegateDirective(updated_intent=updateIntent))
            .response
        )


class PromptAddHandler(AbstractRequestHandler):
    """Handler for prompting add habit if no habits exist"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # Handle if no habits exist
        return not session_attributes["habits"]

    def handle(self, handler_input):

        # Instantiate Alexa Response and Visuals
        speak_output = ''
        title = ''
        subtitle = ''

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # Ask the user if they'd like to add a habit
        speak_output = f"I'm sorry, it looks like you're not currently tracking any habits. " \
            f"Would you like to add a habit for me to track for you?"
        title = 'No Active Habits!'
        subtitle = 'Would you like to add a Habit for me to track?'

        # Listen for yes/no
        session_attributes["on_yes"] = "AddHabitIntent"

        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask(speak_output)
            .response
        )


'''
CREATE

    - AddHabitHandler
        Creates an entry for a habit

'''


class AddHabitHandler(AbstractRequestHandler):
    """Handler for Adding a Habit Name"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
            and ask_utils.is_intent_name("AddHabitIntent")(handler_input)
        )

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Instantiate Alexa Response and Visuals
        speak_output = ''
        title = ''
        subtitle = ''

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # Whether to hang for a Response (default no)
        listen_for_response = False

        # If User already has 3 habits, tell the user to delete or rename. No need to listen for response
        if len(session_attributes["habits"]) >= 3:
            speak_output = f"I'm sorry, you've reached your limit of 3 active habits to track. " \
                f"You can delete an existing habit to make room, or update an existing habit. " \
                f"What would you like to do?"
            title = 'Habit Limit Reached!'
            subtitle = 'Delete another habit to make room, or update an existing habit'

        # If User has less than 3 habits...
        else:

            # Check the verb of the habit the User said
            habit = ask_utils.request_util.get_slot(
                handler_input, "habit").value

            # Also pull the stuff around the verb
            sep = ask_utils.request_util.get_slot(handler_input, "sep").value
            quant = ask_utils.request_util.get_slot(
                handler_input, "quant").value
            obj = ask_utils.request_util.get_slot(
                handler_input, "object").value

            # Hamstring the full habit name
            full_habit_name = f"{habit}{' ' + sep if sep else ''}{' ' + quant if quant else ''}{' ' + obj if obj else ''}".rstrip()

            # If the verb of the habit already exists
            if habit in session_attributes["habits"]:

                # Tell the user that this habit already exists
                speak_output = f'Hm, it looks like a habit called {habit} already exists' \
                    f'Would you like to try another name?'
                title = f'"{habit}" already exists'
                subtitle = f"Let's try again..."

                # Ask to add a habit, and listen for yes/no
                session_attributes["on_yes"] = "AddHabitIntent"
                listen_for_response = True

            # If the habit doesn't already exist
            else:

                # Tell the user we were able to add the habit!
                speak_output = f'Okay, adding a habit called {full_habit_name}'
                title = f'Adding a habit called "{full_habit_name}"'
                subtitle = f'Please delete and re-create if this name is not correct'

                # Initiate habit streak and store optional language
                session_attributes["habits"][habit] = {}
                session_attributes["habits"][habit]["streak"] = []
                session_attributes["habits"][habit]["full_habit_name"] = full_habit_name

        # ====================================================================
        # Add a visual with Alexa Layouts
        # ====================================================================
        # Import an Alexa Presentation Language (APL) template
        with open("./documents/APL_simple.json") as apl_doc:
            apl_simple = json.load(apl_doc)
            if ask_utils.get_supported_interfaces(
                    handler_input).alexa_presentation_apl is not None:
                handler_input.response_builder.add_directive(
                    RenderDocumentDirective(
                        document=apl_simple,
                        datasources={
                            "myData": {
                                # ====================================================================
                                # Set a headline and subhead to display on the screen if there is one
                                # ====================================================================
                                "Title": title,
                                "Subtitle": subtitle,
                            }
                        }
                    )
                )

        if listen_for_response:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
            )

        else:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .response
            )


'''
READ

    - CheckHabitStreakHandler
        Reads out the current active streak for a single habit 
    - CheckAllHabitStreaksHandler
        Reads out the current active streak for all habits
    - CheckHabitNamesHandler
        Reads out the name for all active habits

'''


class CheckHabitStreakHandler(AbstractRequestHandler):
    """Handler for checking singular habit streak"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
            and ask_utils.is_intent_name("CheckHabitStreakIntent")(handler_input)
        )

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Instantiate Alexa Response and Visuals
        speak_output = ''
        title = ''
        subtitle = ''

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # Whether to hang for a Response (default no)
        listen_for_response = False

        # Get current date based on user's time zone (UTC default)
        device_id = handler_input.request_envelope.context.system.device.device_id

        user_time_zone = ""
        greeting = ""

        try:
            user_preferences_client = handler_input.service_client_factory.get_ups_service()
            user_time_zone = user_preferences_client.get_system_time_zone(
                device_id)
        # Use Pacific Time as default time zone
        except Exception as e:
            user_time_zone = pytz.Pacific
            logger.error(e)

        current_time = datetime.datetime.now(pytz.timezone(user_time_zone))
        current_date = datetime.date(
            current_time.year, current_time.month, current_time.day)

        # If the User does not have active habits
        if not session_attributes["habits"]:

            # Ask the user if they'd like to add a habit
            speak_output = f"I'm sorry, it looks like you're not currently tracking any habits. " \
                f"Would you like to add a habit for me to track for you?"
            title = 'No Active Habits!'
            subtitle = 'Would you like to add a Habit for me to track?'

            # Listen for yes/no
            session_attributes["on_yes"] = "AddHabitIntent"
            listen_for_response = True

        # If active habits...
        else:

            # Get the habit verb
            habit = ask_utils.request_util.get_slot(
                handler_input, "habit").value

            # Process the habit for multi-word, or past tense
            habit = get_present_tense(habit.split(" ")[0])

            # If habit does not exist
            if habit not in session_attributes["habits"]:

                # Ask the User to try another name
                speak_output = f"Hm, I'm not tracking a habit for {habit}. " \
                    f'Would you like to try another name?'
                title = f'No habit with verb "{habit}" is being tracked!'
                subtitle = f"Let's try again..."

                # Listen for yes/no
                session_attributes["on_yes"] = "CheckHabitStreakIntent"
                listen_for_response = True

            # If the habit does exist
            else:

                # Get the full habit name
                full_habit_name = session_attributes["habits"][habit]["full_habit_name"].capitalize(
                )

                # Get the streak
                streak = get_active_streak(
                    session_attributes["habits"][habit]["streak"], current_date.isoformat())

                # Get an appropriate phrase
                phrase = get_phrase(streak)

                speak_output += f"Your current streak for {full_habit_name} is {streak}. {phrase}"
                title += f'{full_habit_name}'
                subtitle = f"{streak} {'day' if streak==1 else 'days'}"

        # ====================================================================
        # Add a visual with Alexa Layouts
        # ====================================================================
        # Import an Alexa Presentation Language (APL) template
        with open("./documents/APL_simple.json") as apl_doc:
            apl_simple = json.load(apl_doc)
            if ask_utils.get_supported_interfaces(
                    handler_input).alexa_presentation_apl is not None:
                handler_input.response_builder.add_directive(
                    RenderDocumentDirective(
                        document=apl_simple,
                        datasources={
                            "myData": {
                                # ====================================================================
                                # Set a headline and subhead to display on the screen if there is one
                                # ====================================================================
                                "Title": title,
                                "Subtitle": subtitle,
                            }
                        }
                    )
                )

        if listen_for_response:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
            )

        else:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .response
            )


class CheckAllHabitStreaksHandler(AbstractRequestHandler):
    """Handler for checking all habit streaks"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
            and ask_utils.is_intent_name("CheckAllHabitStreaksIntent")(handler_input)
        )

    def handle(self, handler_input):
        """Handler for checking habit streaks"""
        # type: (HandlerInput) -> Response
        speak_output = ''
        title = ''
        subtitle = ''

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # Whether to hang for a Response
        listen_for_response = False

        # Get current date based on user's time zone (UTC default)
        device_id = handler_input.request_envelope.context.system.device.device_id

        user_time_zone = ""
        greeting = ""

        try:
            user_preferences_client = handler_input.service_client_factory.get_ups_service()
            user_time_zone = user_preferences_client.get_system_time_zone(
                device_id)
        # Use Pacific Time as default time zone
        except Exception as e:
            user_time_zone = pytz.Pacific
            logger.error(e)

        current_time = datetime.datetime.now(pytz.timezone(user_time_zone))
        current_date = datetime.date(
            current_time.year, current_time.month, current_time.day)

        # If no active habits
        if not session_attributes["habits"]:
            speak_output = f"I'm sorry, it looks like you're not currently tracking any habits. " \
                f"Would you like to add a habit for me to track for you?"
            title = 'No Active Habits!'
            subtitle = 'Would you like to add a Habit for me to track?'

            # Listen for yes/no
            session_attributes["on_yes"] = "AddHabitIntent"
            listen_for_response = True

        # If active habits...
        else:

            # For all habits
            habits = session_attributes["habits"].keys()
            title += f'Streaks for '

            # If there's only one habit, delegate dialog to CheckStreakHandler
            if len(habits) == 1:

                habit = list(habits)[0]

                # Get the full habit name
                full_habit_name = session_attributes["habits"][habit]["full_habit_name"].capitalize(
                )

                # Get the streak
                streak = get_active_streak(
                    session_attributes["habits"][habit]["streak"], current_date.isoformat())

                # get an encouragement based on the streak length
                phrase = get_phrase(streak)

                # Tell the User
                speak_output += f"Your current streak for {full_habit_name} is {streak}. {phrase}"
                title += f'{full_habit_name}'
                subtitle = f"{streak} {'day' if streak==1 else 'days'}"

            # Otherwise, iterate through all habits and announce as a list
            else:

                title = "Streaks:"

                for idx, habit in enumerate(habits):

                    # Get the full habit name
                    full_habit_name = session_attributes["habits"][habit]["full_habit_name"].capitalize(
                    )

                    # Get the streak
                    streak = get_active_streak(
                        session_attributes["habits"][habit]["streak"], current_date.isoformat())

                    # List the habit name and streak
                    speak_output += f"Your current streak for {full_habit_name} is {streak}"
                    subtitle += f"{full_habit_name}: {streak}"

                    if idx == len(habits) - 2:
                        speak_output += ', and '
                        subtitle += ', and '
                    elif idx <= len(habits) - 2:
                        speak_output += ', '
                        subtitle += ', '

        # ====================================================================
        # Add a visual with Alexa Layouts
        # ====================================================================
        # Import an Alexa Presentation Language (APL) template
        with open("./documents/APL_simple.json") as apl_doc:
            apl_simple = json.load(apl_doc)
            if ask_utils.get_supported_interfaces(
                    handler_input).alexa_presentation_apl is not None:
                handler_input.response_builder.add_directive(
                    RenderDocumentDirective(
                        document=apl_simple,
                        datasources={
                            "myData": {
                                # ====================================================================
                                # Set a headline and subhead to display on the screen if there is one
                                # ====================================================================
                                "Title": title,
                                "Subtitle": subtitle,
                            }
                        }
                    )
                )

        if listen_for_response:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
            )

        else:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .response
            )


class CheckHabitNamesHandler(AbstractRequestHandler):
    """Handler for checking all habit names"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool

        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
            and ask_utils.is_intent_name("CheckHabitNamesIntent")(handler_input)
        )

    def handle(self, handler_input):
        """Handler for checking habit streaks"""
        # type: (HandlerInput) -> Response
        speak_output = ''
        title = ''
        subtitle = ''

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # Whether to hang for a Response
        listen_for_response = False

        # Get current date based on user's time zone (UTC default)
        device_id = handler_input.request_envelope.context.system.device.device_id

        user_time_zone = ""
        greeting = ""

        try:
            user_preferences_client = handler_input.service_client_factory.get_ups_service()
            user_time_zone = user_preferences_client.get_system_time_zone(
                device_id)
        # Use Pacific Time as default time zone
        except Exception as e:
            user_time_zone = pytz.Pacific
            logger.error(e)

        current_time = datetime.datetime.now(pytz.timezone(user_time_zone))
        current_date = datetime.date(
            current_time.year, current_time.month, current_time.day)

        # If no active habits
        if not session_attributes["habits"]:
            speak_output = f"I'm sorry, it looks like you're not currently tracking any habits. " \
                f"Would you like to add a habit for me to track for you?"
            title = 'No Active Habits!'
            subtitle = 'Would you like to add a Habit for me to track?'

            # Listen for yes/no
            session_attributes["on_yes"] = "AddHabitIntent"
            listen_for_response = True

        # If active habits...
        else:

            # For all habits
            habits = session_attributes["habits"].keys()
            title += f'Your habits: '

            # If there's only one habit there's one format
            if len(habits) == 1:

                habit = list(habits)[0]

                # Get the full habit name
                full_habit_name = session_attributes["habits"][habit]["full_habit_name"].capitalize(
                )

                # Tell the User
                speak_output += f"You have one habit, {full_habit_name}"
                subtitle = f"{full_habit_name}"

            # Otherwise, iterate through all habits and announce as a list
            else:

                speak_output += f"You have {len(habits)} habits, named "

                for idx, habit in enumerate(habits):

                    # Get the full habit name
                    full_habit_name = session_attributes["habits"][habit]["full_habit_name"].capitalize(
                    )

                    # List the habit name and streak
                    speak_output += f"{full_habit_name}"
                    subtitle += f"{full_habit_name}"

                    if idx == len(habits) - 2:
                        speak_output += ', and '
                        subtitle += ', and '
                    elif idx <= len(habits) - 2:
                        speak_output += ', '
                        subtitle += ', '

        # ====================================================================
        # Add a visual with Alexa Layouts
        # ====================================================================
        # Import an Alexa Presentation Language (APL) template
        with open("./documents/APL_simple.json") as apl_doc:
            apl_simple = json.load(apl_doc)
            if ask_utils.get_supported_interfaces(
                    handler_input).alexa_presentation_apl is not None:
                handler_input.response_builder.add_directive(
                    RenderDocumentDirective(
                        document=apl_simple,
                        datasources={
                            "myData": {
                                # ====================================================================
                                # Set a headline and subhead to display on the screen if there is one
                                # ====================================================================
                                "Title": title,
                                "Subtitle": subtitle,
                            }
                        }
                    )
                )

        if listen_for_response:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
            )

        else:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .response
            )


'''
Update

    - UpdateHabitHandler
        Renames an active habit (without effecting the streak)
    - DidHabitHandler
        Adds todays timestamp to the habits active streak (if not already checked off)
    - UndoHabitHandler
        Un-checks the current day for a habit

'''


class UpdateHabitHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
            and ask_utils.is_intent_name("UpdateHabitIntent")(handler_input)
        )

    def handle(self, handler_input):

        # Instantiate Alexa Response and Visuals
        speak_output = "I'm sorry, for now I can't rename habits. If you'd like to rename a habit, please delete " \
            "the old habit and create a new habit. Unfortunately, the streak data cannot be saved"
        title = 'Rename not possible at the moment'
        subtitle = 'Please delete and create a new habit'

        # ====================================================================
        # Add a visual with Alexa Layouts
        # ====================================================================
        # Import an Alexa Presentation Language (APL) template
        with open("./documents/APL_simple.json") as apl_doc:
            apl_simple = json.load(apl_doc)
            if ask_utils.get_supported_interfaces(
                    handler_input).alexa_presentation_apl is not None:
                handler_input.response_builder.add_directive(
                    RenderDocumentDirective(
                        document=apl_simple,
                        datasources={
                            "myData": {
                                # ====================================================================
                                # Set a headline and subhead to display on the screen if there is one
                                # ====================================================================
                                "Title": title,
                                "Subtitle": subtitle,
                            }
                        }
                    )
                )

        return (
            handler_input.response_builder
            .speak(speak_output)
            .response
        )


''' FOR NOW, NOT IMPLEMENTED
class UpdateHabitHandler(AbstractRequestHandler):
    
    
    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
                and ask_utils.is_intent_name("UpdateHabitIntent")(handler_input)
        )
    
    def handle(self, handler_input):
        
        # Instantiate Alexa Response and Visuals
        speak_output = ''
        title = ''
        subtitle = ''
        
        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes
        
        # Whether to hang for a Response (default no)
        listen_for_response = False
        
        # If the User does not have active habits
        if not session_attributes["habits"]:
            
            # Ask the user if they'd like to add a habit
            speak_output = f"I'm sorry, it looks like you're not currently tracking any habits. " \
                    f"Would you like to add a habit for me to track for you?"
            title = 'No Active Habits!'
            subtitle = 'Would you like to add a Habit for me to track?'
            
            # Listen for yes/no
            session_attributes["on_yes"] = "AddHabitIntent"
            listen_for_response = True
        
        # If active habits...
        else:
            
            # Get the habit verb, and the replacement habit verb
            habit = ask_utils.request_util.get_slot(handler_input, "habit").value
            new_habit = ask_utils.request_util.get_slot(handler_input, "new_habit").value
            
            # Also pull the stuff around the verb for the new habit
            sep = ask_utils.request_util.get_slot(handler_input, "new_sep").value
            quant = ask_utils.request_util.get_slot(handler_input, "new_quant").value
            obj = ask_utils.request_util.get_slot(handler_input, "new_object").value
            
            # Process the old habit for multi-word, or past tense 
            habit = get_present_tense(habit.split(" ")[0])
            
            # Check if habit already exists
            if habit not in session_attributes["habits"]:
                
                # Ask the user if they'd like to try another name
                speak_output = f"Hm, I'm not tracking a habit named {habit}. " \
                    f'Would you like to try another name?'
                title = f'No habit named "{habit}" is being tracked!'
                subtitle = f"Let's try again..."
                
                # Listen for yes/no
                session_attributes["on_yes"] = "UpdateHabitIntent"
                listen_for_response = True
            
            # Now if it does, we can successfully change the name of the habit
            else:
                
                #Get the full habit names
                old_full_habit_name = session_attributes["habits"][habit]["full_habit_name"]
                
                # Hamstring the new full habit name
                new_full_habit_name = f"{habit}{' ' + sep if sep else ''}{' ' + quant if quant else ''}{' ' + obj if obj else ''}".rstrip()
                
                # Tell the User we're changing names
                speak_output = f'Okay, changing the name of your habit {old_full_habit_name} to {new_full_habit_name}'
                title = f'Changing your habit called "{old_full_habit_name}" to "{new_full_habit_name}"'
                subtitle = f'You can update the name as many times as you want without losing the streak!'
                
                # Change key name (Copy over data, then delete old key)
                session_attributes["habits"][new_habit] = {}
                session_attributes["habits"][new_habit]["streak"] = session_attributes["habits"][habit]["streak"]
                session_attributes["habits"][new_habit]["full_habit_name"] = new_full_habit_name
                
                if new_habit != habit:
                    del session_attributes["habits"][habit]
            
        #====================================================================
        # Add a visual with Alexa Layouts
        #====================================================================
        # Import an Alexa Presentation Language (APL) template
        with open("./documents/APL_simple.json") as apl_doc:
            apl_simple = json.load(apl_doc)
            if ask_utils.get_supported_interfaces(
                    handler_input).alexa_presentation_apl is not None:
                handler_input.response_builder.add_directive(
                    RenderDocumentDirective(
                        document=apl_simple,
                        datasources={
                            "myData": {
                                #====================================================================
                                # Set a headline and subhead to display on the screen if there is one
                                #====================================================================
                                "Title": title,
                                "Subtitle": subtitle,
                            }
                        }
                    )
                )
        
        if listen_for_response:

            return (
                handler_input.response_builder
                    .speak(speak_output)
                    .ask(speak_output)
                    .response
            )
            
        else:
            
            return (
                handler_input.response_builder
                    .speak(speak_output)
                    .response
            )
'''


class DidHabitHandler(AbstractRequestHandler):
    """Handler for Checking Off an existing habit"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
            and ask_utils.is_intent_name("DidHabitIntent")(handler_input)
        )

    def handle(self, handler_input):

        # Instantiate Alexa Response and Visuals
        speak_output = ''
        title = ''
        subtitle = ''

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # Whether to hang for a Response (default no)
        listen_for_response = False

        # Get current date based on user's time zone (UTC default)
        device_id = handler_input.request_envelope.context.system.device.device_id

        user_time_zone = ""
        greeting = ""

        try:
            user_preferences_client = handler_input.service_client_factory.get_ups_service()
            user_time_zone = user_preferences_client.get_system_time_zone(
                device_id)
        # Use Pacific Time as default time zone
        except Exception as e:
            user_time_zone = pytz.Pacific
            logger.error(e)

        current_time = datetime.datetime.now(pytz.timezone(user_time_zone))
        current_date = datetime.date(
            current_time.year, current_time.month, current_time.day)

        # If the User does not have active habits
        if not session_attributes["habits"]:

            # Ask the user if they'd like to add a habit
            speak_output = f"I'm sorry, it looks like you're not currently tracking any habits. " \
                f"Would you like to add a habit for me to track for you?"
            title = 'No Active Habits!'
            subtitle = 'Would you like to add a Habit for me to track?'

            # Listen for yes/no
            session_attributes["on_yes"] = "AddHabitIntent"
            listen_for_response = True

        else:

            # Get habit
            habit = ask_utils.request_util.get_slot(
                handler_input, "habit").value

            # Process the habit for multi-word, or past tense
            habit = get_present_tense(habit.split(" ")[0])

            # If habit does not exist
            if habit not in session_attributes["habits"]:

                speak_output = f"Hm, I'm not tracking a habit named {habit}. " \
                    f'Would you like to try another name?'
                title = f'No habit named "{habit}" is being tracked!'
                subtitle = f"Let's try again..."

                # Listen for yes/no
                session_attributes["on_yes"] = "DidHabitIntent"
                listen_for_response = True

            # If the habit does exist
            else:

                # Already checked off for today?
                if session_attributes["habits"][habit]["streak"] and session_attributes["habits"][habit]["streak"][-1] == current_date.isoformat():

                    # Tell the user it's already been checked off, no need to listen for a response
                    speak_output = f'You already checked this habit off for today! Come back tomorrow to continue your streak'
                    title = f'Habit already checked off today!'
                    subtitle = f'...'

                # If not checked off...
                else:

                    # Get full habit name
                    full_habit_name = session_attributes["habits"][habit]["full_habit_name"]

                    # Check it off, and maintain max length of 66 dates
                    if len(session_attributes["habits"][habit]["streak"]) <= 66:
                        session_attributes["habits"][habit]["streak"] += [
                            current_date.isoformat()]
                    else:
                        session_attributes["habits"][habit]["streak"].pop(0)
                        session_attributes["habits"][habit]["streak"] += [
                            current_date.isoformat()]

                    # Get the streak
                    active_streak = get_active_streak(
                        session_attributes["habits"][habit]["streak"], current_date.isoformat())

                    # Get an appropriate phrase
                    phrase = get_phrase(active_streak)

                    speak_output = f'Alright, checking off {full_habit_name}! Your streak is now ' \
                        f' {active_streak} days long. {phrase}'
                    title = f'Checking off {full_habit_name}!'
                    subtitle = f'Your streak is now {active_streak} days long!'

        # ====================================================================
        # Add a visual with Alexa Layouts
        # ====================================================================
        # Import an Alexa Presentation Language (APL) template
        with open("./documents/APL_simple.json") as apl_doc:
            apl_simple = json.load(apl_doc)
            if ask_utils.get_supported_interfaces(
                    handler_input).alexa_presentation_apl is not None:
                handler_input.response_builder.add_directive(
                    RenderDocumentDirective(
                        document=apl_simple,
                        datasources={
                            "myData": {
                                # ====================================================================
                                # Set a headline and subhead to display on the screen if there is one
                                # ====================================================================
                                "Title": title,
                                "Subtitle": subtitle,
                            }
                        }
                    )
                )

        if listen_for_response:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
            )

        else:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .response
            )


class UndoHabitHandler(AbstractRequestHandler):
    """Handler for unchecking an existing habit"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
            and ask_utils.is_intent_name("UndoHabitIntent")(handler_input)
        )

    def handle(self, handler_input):

        # Instantiate Alexa Response and Visuals
        speak_output = ''
        title = ''
        subtitle = ''

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # Whether to hang for a Response (default no)
        listen_for_response = False

        # Get current date based on user's time zone (UTC default)
        device_id = handler_input.request_envelope.context.system.device.device_id

        user_time_zone = ""
        greeting = ""

        try:
            user_preferences_client = handler_input.service_client_factory.get_ups_service()
            user_time_zone = user_preferences_client.get_system_time_zone(
                device_id)
        # Use Pacific Time as default time zone
        except Exception as e:
            user_time_zone = pytz.Pacific
            logger.error(e)

        current_time = datetime.datetime.now(pytz.timezone(user_time_zone))
        current_date = datetime.date(
            current_time.year, current_time.month, current_time.day)

        # If the User does not have active habits
        if not session_attributes["habits"]:

            # Ask the user if they'd like to add a habit
            speak_output = f"I'm sorry, it looks like you're not currently tracking any habits. " \
                f"Would you like to add a habit for me to track for you?"
            title = 'No Active Habits!'
            subtitle = 'Would you like to add a Habit for me to track?'

            # Listen for yes/no
            session_attributes["on_yes"] = "AddHabitIntent"
            listen_for_response = True

        else:

            # Get habit
            habit = ask_utils.request_util.get_slot(
                handler_input, "habit").value

            # Process the habit for multi-word, or past tense
            habit = get_present_tense(habit.split(" ")[0])

            # If habit does not exist
            if habit not in session_attributes["habits"]:

                speak_output = f"Hm, I'm not tracking a habit named {habit}. " \
                    f'Would you like to try another name?'
                title = f'No habit named "{habit}" is being tracked!'
                subtitle = f"Let's try again..."

                # Listen for yes/no
                session_attributes["on_yes"] = "UndoHabitIntent"
                listen_for_response = True

            # If the habit does exist
            else:

                # Already checked off for today?
                if session_attributes["habits"][habit]["streak"] and session_attributes["habits"][habit]["streak"][-1] == current_date.isoformat():

                    # Get the full habit name
                    full_habit_name = session_attributes["habits"][habit]["full_habit_name"]

                    # Pop the last element off
                    session_attributes["habits"][habit]["streak"].pop(-1)

                    speak_output = f'Alright, undoing your check off of {full_habit_name}. Come back and let me know when its done! '
                    title = f'Undoing check off of {full_habit_name}!'
                    subtitle = f'Come let me know when its done!'

                # If not checked off...
                else:

                    # Tell the user it's already been checked off, no need to listen for a response
                    speak_output = f'You havent checked this habit off today!'
                    title = f'Habit not checked off today!'
                    subtitle = f'...'

        # ====================================================================
        # Add a visual with Alexa Layouts
        # ====================================================================
        # Import an Alexa Presentation Language (APL) template
        with open("./documents/APL_simple.json") as apl_doc:
            apl_simple = json.load(apl_doc)
            if ask_utils.get_supported_interfaces(
                    handler_input).alexa_presentation_apl is not None:
                handler_input.response_builder.add_directive(
                    RenderDocumentDirective(
                        document=apl_simple,
                        datasources={
                            "myData": {
                                # ====================================================================
                                # Set a headline and subhead to display on the screen if there is one
                                # ====================================================================
                                "Title": title,
                                "Subtitle": subtitle,
                            }
                        }
                    )
                )

        if listen_for_response:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
            )

        else:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .response
            )


'''
Delete

    - DeleteHabitHandler
        Deletes an active habit, and all data associated with it

'''


class DeleteHabitHandler(AbstractRequestHandler):
    """Handler for Deleting an existing habit"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (
            ask_utils.is_request_type("IntentRequest")(handler_input)
            and ask_utils.is_intent_name("DeleteHabitIntent")(handler_input)
        )

    def handle(self, handler_input):

        # Instantiate Alexa Response and Visuals
        speak_output = ''
        title = ''
        subtitle = ''

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # Whether to hang for a Response (default no)
        listen_for_response = False

        # If the User does not have active habits
        if not session_attributes["habits"]:

            # Ask the user if they'd like to add a habit
            speak_output = f"I'm sorry, it looks like you're not currently tracking any habits. " \
                f"Would you like to add a habit for me to track for you?"
            title = 'No Active Habits!'
            subtitle = 'Would you like to add a Habit for me to track?'

            # Listen for yes/no
            session_attributes["on_yes"] = "AddHabitIntent"
            listen_for_response = True

        else:

            # Get the habit
            habit = ask_utils.request_util.get_slot(
                handler_input, "habit").value

            # Process the habit for multi-word, or past tense
            habit = get_present_tense(habit.split(" ")[0])

            # If habit does not exist
            if habit not in session_attributes["habits"]:

                speak_output = f"Hm, I'm not tracking a habit named {habit}. " \
                    f'Would you like to try another name?'
                title = f'No habit named "{habit}" is being tracked!'
                subtitle = f"Let's try again..."

                # Listen for yes/no
                session_attributes["on_yes"] = "DeleteHabitIntent"
                listen_for_response = True

            # If the habit does exist
            else:

                # Get the full habit name
                full_habit_name = session_attributes["habits"][habit]["full_habit_name"]

                # Notify the User the habit will be deleted
                speak_output = f'Okay, deleting your habit called {full_habit_name}'
                title = f'Deleting your habit called "{full_habit_name}"'
                subtitle = f'...'

                # Delete the habit information
                del session_attributes["habits"][habit]

        # ====================================================================
        # Add a visual with Alexa Layouts
        # ====================================================================
        # Import an Alexa Presentation Language (APL) template
        with open("./documents/APL_simple.json") as apl_doc:
            apl_simple = json.load(apl_doc)
            if ask_utils.get_supported_interfaces(
                    handler_input).alexa_presentation_apl is not None:
                handler_input.response_builder.add_directive(
                    RenderDocumentDirective(
                        document=apl_simple,
                        datasources={
                            "myData": {
                                # ====================================================================
                                # Set a headline and subhead to display on the screen if there is one
                                # ====================================================================
                                "Title": title,
                                "Subtitle": subtitle,
                            }
                        }
                    )
                )

        if listen_for_response:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
            )

        else:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .response
            )


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = ''
        title = ''
        subtitle = ''

        # Get session attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # Whether to hang for a Response
        listen_for_response = False

        # Check that a habit exists
        if not session_attributes["habits"]:
            speak_output = f"To get started, we'll need to add an active habit that I can track. " \
                f"Would you like me to add a habit to track for you?"
            title = "Say yes to get started"
            subtitle = "Let's add a habit to track!"
            session_attributes["on_yes"] = "AddHabitIntent"
            listen_for_response = True

        else:
            speak_output = f"You can say things like Check off a Habit, Add a Habit, " \
                f"Rename a Habit, Delete a Habit, or Check habit streaks."
            title = "Valid commands:"
            subtitle = "Check off, add, rename, delete, or check habit streaks!"
            session_attributes["on_yes"] = "AMAZON.HelpIntent"

        # ====================================================================
        # Add a visual with Alexa Layouts
        # ====================================================================
        # Import an Alexa Presentation Language (APL) template
        with open("./documents/APL_simple.json") as apl_doc:
            apl_simple = json.load(apl_doc)
            if ask_utils.get_supported_interfaces(
                    handler_input).alexa_presentation_apl is not None:
                handler_input.response_builder.add_directive(
                    RenderDocumentDirective(
                        document=apl_simple,
                        datasources={
                            "myData": {
                                # ====================================================================
                                # Set a headline and subhead to display on the screen if there is one
                                # ====================================================================
                                "Title": title,
                                "Subtitle": subtitle,
                            }
                        }
                    )
                )

        if listen_for_response:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
            )

        else:

            return (
                handler_input.response_builder
                .speak(speak_output)
                .response
            )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        speak_output = "Goodbye! You can come back anytime to keep tracking habits by saying 'Alexa, open 66 Days to a Better You"

        return (
            handler_input.response_builder
            .speak(speak_output)
            .response
        )


class FallbackIntentHandler(AbstractRequestHandler):
    """Single handler for Fallback Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In FallbackIntentHandler")
        speech = "Hmm, I'm not sure. You can say Help, or you can add, update, or check habits. What would you like to do?"
        reprompt = "I didn't catch that. What can I help you with?"

        return handler_input.response_builder.speak(speech).ask(reprompt).response


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response

        # Any cleanup logic goes here.

        return handler_input.response_builder.response


class IntentReflectorHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."

        return (
            handler_input.response_builder
            .speak(speak_output)
            # .ask("add a reprompt if you want to keep the session open for the user to respond")
            .response
        )


class LoadDataInterceptor(AbstractRequestInterceptor):
    """Check if user is invoking skill for first time and initialize preset."""

    def process(self, handler_input):
        # type: (HandlerInput) -> None
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        # ensure important variables are initialized so they're used more easily in handlers.
        # This makes sure they're ready to go and makes the handler code a little more readable
        if 'habits' not in persistent_attributes:
            persistent_attributes["habits"] = {}

        if 'habits' not in session_attributes:
            session_attributes["habits"] = {}

        if 'on_yes' not in session_attributes:
            session_attributes["on_yes"] = "AMAZON.HelpIntent"

        # if you're tracking past_celebs between sessions, use the persistent value
        # set the visits value (either 0 for new, or the persistent value)
        session_attributes["habits"] = persistent_attributes["habits"] if HABIT_TRACKING else session_attributes["habits"]
        session_attributes["visits"] = persistent_attributes["visits"] if 'visits' in persistent_attributes else 0


class SaveDataInterceptor(AbstractResponseInterceptor):
    """Save persistence attributes before sending response to user."""

    def process(self, handler_input, response):
        # type: (HandlerInput, Response) -> None
        persistent_attributes = handler_input.attributes_manager.persistent_attributes
        session_attributes = handler_input.attributes_manager.session_attributes

        persistent_attributes["habits"] = session_attributes["habits"] if HABIT_TRACKING else {
        }
        persistent_attributes["visits"] = session_attributes["visits"]

        handler_input.attributes_manager.save_persistent_attributes()


class LoggingResponseInterceptor(AbstractResponseInterceptor):
    """Log the alexa responses."""

    def process(self, handler_input, response):
        # type: (HandlerInput, Response) -> None
        logger.debug('----- RESPONSE -----')
        logger.debug("{}".format(response))


class LoggingRequestInterceptor(AbstractRequestInterceptor):
    """Log the alexa requests."""

    def process(self, handler_input):
        # type: (HandlerInput) -> None
        logger.debug('----- REQUEST -----')
        logger.debug("{}".format(
            handler_input.request_envelope.request))


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """

    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder
            .speak(speak_output)
            .ask(speak_output)
            .response
        )

# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.


sb = StandardSkillBuilder(
    table_name=os.environ.get("DYNAMODB_PERSISTENCE_TABLE_NAME"), auto_create_table=False)

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(YesHandler())
sb.add_request_handler(NoHandler())
sb.add_request_handler(AddHabitHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(PromptAddHandler())
sb.add_request_handler(DidHabitHandler())
sb.add_request_handler(UndoHabitHandler())
sb.add_request_handler(CheckHabitNamesHandler())
sb.add_request_handler(CheckHabitStreakHandler())
sb.add_request_handler(CheckAllHabitStreaksHandler())
sb.add_request_handler(UpdateHabitHandler())
sb.add_request_handler(DeleteHabitHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
# make sure IntentReflectorHandler is last so it doesn't override your custom intent handlers
sb.add_request_handler(IntentReflectorHandler())

sb.add_exception_handler(CatchAllExceptionHandler())

# Interceptors
sb.add_global_request_interceptor(LoadDataInterceptor())
sb.add_global_request_interceptor(LoggingRequestInterceptor())

sb.add_global_response_interceptor(SaveDataInterceptor())
sb.add_global_response_interceptor(LoggingResponseInterceptor())

lambda_handler = sb.lambda_handler()
