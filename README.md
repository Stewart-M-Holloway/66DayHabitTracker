# 66 Day Habit Tracker

## Introduction

This is a skill I developed as a pet project after the Alexa Health and Wellness team was dissolved by the larger Alexa re-structure. It's not intended to be monetized or used for advertisement, simply a great way to practice and apply what I learned through Amazon and to demonstrate my capability to develop and deliver intuitive Software experiences.

Fundamentally, this is an Alexa CRUD app- The user can instantiate persistent habits (CREATE), continually track that they've completed those habits (UPDATE), check the status of their streaks (READ), and remove habits they no longer want to track (DELETE). I discuss the deep technical aspects, and some engineering to make a more intuitive experience, below...

## Some Context on Alexa Skills

### VUIs

Alexa experiences are referred to as VUIs, Verbal User Interfaces, and are accessed differently than traditional GUIs or web apps. User input is abstracted to user "utterances", which drives how the Alexa API triages towards back-end applications and then returns verbal prompts to the User. In many ways, however, the back-end is essentially a traditional web application.

### API Layers

After the very first layer of interaction, a user utterance will either explicitly be triaged to your skill, or in some cases the Alexa interface can infer that your skill is the one to be accessed by a given User utterance. After this, the input is parsed and tokenized, and Alexa will package the information and send it to _your_ skill as a request, which it better be ready to handle. Alexa interacts with your skill via HTTP over SSL/TLS, sending POST requests in a JSON body, and expecting an appropriate JSON-formatted response.

After successfully (or unsuccessfully) handling the request from the Alexa service, your skill must send a response payload conforming to the Alexa API.

Alexa Response/Request Doc: https://developer.amazon.com/en-US/docs/alexa/custom-skills/request-and-response-json-reference.html

    {
    "version": "1.0",
    "session": {
        "new": true,
        "sessionId": "amzn1.echo-api.session.[unique-value-here]",
        "application": {
        "applicationId": "amzn1.ask.skill.[unique-value-here]"
        },
        "attributes": {
        "key": "string value"
        },
        "user": {
        "userId": "amzn1.ask.account.[unique-value-here]",
        "accessToken": "Atza|AAAAAAAA...",
        "permissions": {
            "consentToken": "ZZZZZZZ..."
        }
        }
    },
    "context": {
        "System": {
        "device": {
            "deviceId": "string",
            "supportedInterfaces": {
            "AudioPlayer": {}
            },
            "persistentEndpointId" : "amzn1.alexa.endpoint.[unique-value-here]"
        },
        "application": {
            "applicationId": "amzn1.ask.skill.[unique-value-here]"
        },
        "user": {
            "userId": "amzn1.ask.account.[unique-value-here]",
            "accessToken": "Atza|AAAAAAAA...",
            "permissions": {
            "consentToken": "ZZZZZZZ..."
            }
        },
        "person": {
            "personId": "amzn1.ask.person.[unique-value-here]",
            "accessToken": "Atza|BBBBBBB..."
        },
        "unit": {
            "unitId": "amzn1.ask.unit.[unique-value-here]",
            "persistentUnitId" : "amzn1.alexa.unit.did.[unique-value-here]"
        },
        "apiEndpoint": "https://api.amazonalexa.com",
        "apiAccessToken": "AxThk..."
        },
        "AudioPlayer": {
        "playerActivity": "PLAYING",
        "token": "audioplayer-token",
        "offsetInMilliseconds": 0
        }
    },
    "request": {}

}

### Skill Architecture

Consider the following abstraction:

![alt text](assets\images\alexa-skill-architecture.png)

It's very typical for a serverless microservice (AWS Lambda) to operate on the incoming request. Because lambda is stateless, it becomes necessary to define the interactions and API calls between various AWS staples like IAM, DynamoDB, S3, etc... The developer has considerable freedom to be inventive about the way they handle app behavior, although there are some best practices to ensure the user experiences a smooth verbal interactions with Alexa. There are also distinct APIs that define payloads you may send to DynamoDB/S3, etc., but the python middle layer can abstract the building of these request/response managements to speed development.

## Habit Tracker Functionality (Architecture and CRUD)

### High Level Architecture View

![alt text](assets\charts\high_level_architecture.png)

### Utterance Model

When a User speaks to your skill, you essentially need two bits of information: First, what part of your application logic should handle this utterance? Second, what additional information did the User provide that would help this logic determine what to do?

For most intents, we parse for a purpose (i.e. Create or Delete), and a habit (i.e. swim 10 laps.). The habit is further subdivided to allow for extra info collection, although the habit (verb) is the most important token as it will be the key through which we will access the habit.

![alt text](assets\charts\utterance_diagram.png)

### Persistence Layer

This application uses AWS DynamoDB to store persistent information about each user, such as habits, ongoing habit streaks, visits, etc. The structure of this data store is describe in this figure:

![alt text](assets\charts\persistence_model.png)

Notice that for simplicity and robustness, the key to access data about a certain habit involves _only_ the undercase and present tense form of a verb. I.e., the full habit may be "Swim 10 laps", but the key to access this will be "swim". This makes Verbal interaction with a database much more reliable.

### Utilities

There are a few quality-of-life functions necessary for this application to work. They are located in the habit_tracker_utils.py. They are:

#### get_active_streak(List: str) \*\*datetime iso strings

The logic for determining how long an active streak has been occurring on a given habit, using an input of a list of chronologic datetimes in ISO format (which is store-able by DynamoDB)

#### get_present_tense(str verb)

Since users may try to reference a habit with some other tense of the verb (imagine a user saying, "I swam laps today" to reference a habit called "Swim 10 laps"), we must be able to translate an input phrase to it's present tense form. This helper function uses a json reference file as a map from all tenses of the 1000 most common english verbs, to their present tenses. If the present tense form cannot be found, just returns the original verb

#### get_phrase(int streak_length)

To avoid repetitive encouragements from Alexa, we can actually randomly select from a pool of encouraging phrases. Based on the length of the streak, we may provide different phrases. Early on we may say to "keep it up", but later on around day 60 we may say "almost there!"

In addition to these, we also have "interceptors" for both saving and loading data. This is how the cache and persistent storage talk to eachother. Each time the cache data is modified, it must save that into persistent storage on the AWS DynamoDB backend to ensure that the User's interactions with their habits are recorded between sessions. These interceptors are triggered before and after each handler executes. Our lambda handling service can provide the typical RESTful API interactions with DynamoDB backend through these intercept handlers

![alt text](assets\charts\cache_to_persist.png)

### CREATE

There is only one handler for "Create", which is "AddHabitHandler". This is achieved simply by parsing for the habit tokens, and then instantiating a key (lower case verb) within the "habits" data structure with an empty list as "streak" and the peripheral tokens within "full_habit_name".

![alt text](assets\charts\add_habit.png)

### READ

There are 3 ways to read the user's habit and habit status:

1. Check individual habit streak
2. Check all habit streaks
3. Check habit names

This is achieved very simply by reading habit information from persistent storage, formatting it for speech and display output, and then building the response. If we cannot find a habit for the individual check intent, we reply that "I'm not tracking a habit called {habit}, would you like to try another name?"

![alt text](assets\charts\read_habit.png)

### UPDATE

2 Methods of updating the database

1. Did Habit
2. Undo Habit

We achieve this by checking for the existence of the habit, and then either appending the current date or popping the last date added to the "streak" list. We of course check to see if the habit has or has not already been checked off on a given day, and handle the request appropriately.

Diagram omitted - see "AddHabit" for workflow

### DELETE

Just 1 method of deleting a habit- we check to see if the habit exists, and then delete the key for that habit if it does. We also ask for confirmation, as deleting a habit is irreversible and removes all streak content thus far (don't want this to be accidental).

Diagram omitted - see "AddHabit" for workflow

## Testing

There is a testing strategy here, but it is not as robust as it should be fore a professional or monetized application. I do describe how I would set up testing and CI/CD for a more professional app.

### Unit Testing

There are test packages outlining how to test utility packages around the lambda function. There is also placeholder for unit testing of the lambda function itself, but in order to fully test lambda functions locally, it becomes necessary to mock relatively complex "intent" structures, which is not in the scope of a personal pet project.

### Integration Testing

Integration testing is the main vehicle for testing of this application and is done through the Alexa Developer Console, which allows for convenient interaction with the skill by typing utterances and receiving output.

### Ideal Testing Scenario (If this was professional)

![alt text](assets\charts\testing_pipeline.png)

Typically we'd split our testing stages into an automated pipeline. Early on, we test very simple things locally i.e. baseline functionality and successful builds. Then we can promote to alpha, and perform some base-level integration testing (response/request handling/business logic). In the beta to gamma stage, we can start to load test at our anticipated prod traffic levels, to ensure decent performance. Finally, after the gamma stage, we can verify voice or visual content before we promote to prod. Even in prod, we we will continuously poll our application with a synthetic canary, so that we can find failures before customers experience them.

This would be an automated pipeline, where lambda versions and cloud constructs could automatically be approved by passing gate tests between stages. There would also be rollback functionality in case failures aren't experienced until hitting prod. This would lower the operational load of developers and allow for a full CI/CD experience.

## Future Work

There are a few features I would have loved to include given more time. Here's a list

- Ability to rename habits without losing streak progress
- Ability to check off days in the past (i.e. I swam yesterday)
- More flexible habit naming
- Archiving of completed habits
