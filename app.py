import os
import json
import random
import re
import threading
from datetime import datetime, timezone

from flask import Flask, render_template, request, jsonify
from openai import OpenAI


app = Flask(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

API_KEY = (
    os.getenv("OPENROUTER_API_KEY")
    or os.getenv("OPENAI_API_KEY")
)

# OpenRouter's free router automatically selects an
# available free model.
#
# You can override this with:
#
# OPENROUTER_MODEL=some/model
#
DEFAULT_MODELS = [
    "openrouter/free"
]

configured_model = os.getenv("OPENROUTER_MODEL")

if configured_model:
    MODELS = [configured_model]
else:
    MODELS = DEFAULT_MODELS


if API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY
    )
else:
    client = None


DATA_FILE = "school_world_data.json"

data_lock = threading.Lock()


# ============================================================
# HELPERS
# ============================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def clean_text(text):
    if text is None:
        return ""

    text = str(text)

    text = text.replace("\x00", "")

    text = re.sub(
        r"```(?:json|python|html|javascript)?",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = text.replace("```", "")

    return text.strip()


def trim_memory(items, limit=40):
    if not isinstance(items, list):
        return []

    if len(items) <= limit:
        return items

    return items[-limit:]


def safe_int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default


# ============================================================
# DEFAULT CHARACTERS
# ============================================================

DEFAULT_CHARACTERS = [
    {
        "id": "alex",
        "name": "Alex",
        "role": "Student",
        "personality": (
            "Friendly, curious, funny, energetic, "
            "and sometimes impulsive."
        ),
        "description": (
            "Alex likes meeting people and turning "
            "boring situations into something interesting."
        ),
        "traits": [
            "Friendly",
            "Curious",
            "Funny",
            "Impulsive"
        ],
        "memory": [],
        "conversation": []
    },

    {
        "id": "maya",
        "name": "Maya",
        "role": "Student",
        "personality": (
            "Intelligent, calm, observant, sarcastic, "
            "and independent."
        ),
        "description": (
            "Maya notices details other people miss "
            "and thinks before she speaks."
        ),
        "traits": [
            "Smart",
            "Calm",
            "Observant",
            "Sarcastic"
        ],
        "memory": [],
        "conversation": []
    },

    {
        "id": "jordan",
        "name": "Jordan",
        "role": "Student",
        "personality": (
            "Confident, competitive, outgoing, playful, "
            "and occasionally stubborn."
        ),
        "description": (
            "Jordan loves competition and enjoys "
            "challenging people."
        ),
        "traits": [
            "Confident",
            "Competitive",
            "Outgoing",
            "Stubborn"
        ],
        "memory": [],
        "conversation": []
    },

    {
        "id": "sam",
        "name": "Sam",
        "role": "Student",
        "personality": (
            "Quiet, creative, thoughtful, kind, "
            "and slightly mysterious."
        ),
        "description": (
            "Sam spends a lot of time drawing, "
            "reading, and observing the school."
        ),
        "traits": [
            "Creative",
            "Quiet",
            "Kind",
            "Thoughtful"
        ],
        "memory": [],
        "conversation": []
    }
]


# ============================================================
# LOCATIONS
# ============================================================

DEFAULT_LOCATIONS = [
    "Classroom",
    "Hallway",
    "Cafeteria",
    "Library",
    "Gym",
    "Courtyard",
    "Science Lab",
    "Computer Lab",
    "Front Office",
    "Auditorium",
    "Art Room",
    "Music Room",
    "Rooftop"
]


# ============================================================
# DIMENSION DIFFERENCES
# ============================================================

DIMENSION_DESCRIPTIONS = [
    "A world where the school developed differently.",
    "A world where different students became friends.",
    "A world where the school has a strange history.",
    "A world where ordinary events often become unusual.",
    "A world almost identical to Earth 1, except for small details.",
    "A world where one major event changed the school's future.",
    "A world where the school seems to remember visitors.",
    "A world where time inside the school behaves strangely.",
    "A world where certain students know about other Earths.",
    "A world where familiar places have unfamiliar purposes."
]


DIMENSION_HINTS = [
    "A student remembers an event that never happened on Earth 1.",
    "The school clock is exactly 17 minutes ahead.",
    "Someone claims they have met you before.",
    "A classroom contains an object that does not exist on Earth 1.",
    "You hear your own voice coming from an empty hallway.",
    "A mysterious symbol appears near the science lab.",
    "A student insists there is another version of this school.",
    "The school map contains a room that does not exist.",
    "A teacher mentions a student with the same name as someone from another Earth.",
    "A reflection briefly shows a different version of the school.",
    "A hallway seems longer than it should be.",
    "A book contains a description of events that have not happened yet.",
    "Someone seems strangely unsurprised by the idea of dimensions.",
    "A familiar object has a completely different history here.",
    "You notice a date that does not match the current year."
]


# ============================================================
# CREATE UNIVERSE
# ============================================================

def create_universe(number, name=None):

    if name is None:
        name = f"Earth {number}"

    is_first = number == 1

    characters = json.loads(
        json.dumps(DEFAULT_CHARACTERS)
    )

    if is_first:
        description = (
            "The original school world. "
            "Everything seems normal... for now."
        )

        hints = [
            "The school seems completely normal.",
            "There may be more to this world than first appears."
        ]

    else:
        description = random.choice(
            DIMENSION_DESCRIPTIONS
        )

        hints = [
            random.choice(DIMENSION_HINTS)
        ]

    return {
        "id": f"earth_{number}",
        "number": number,
        "name": name,

        "description": description,

        "characters": characters,

        "locations": list(DEFAULT_LOCATIONS),

        "player_location": "Classroom",

        "world_memory": [],

        "background_events": [],

        "hints": hints,

        "connections": [],

        "discovered": is_first,
        "visited": is_first,

        "events": [],

        "story": {
            "active": False,
            "story_id": random.randint(
                100000,
                999999
            ),
            "title": "",
            "theme": "",
            "current_node": "start",
            "history": [],
            "seen_nodes": ["start"],
            "ending": None,
            "tree": {}
        },

        "improvement": {
            "facts": [],
            "preferences": [],
            "successful_patterns": [],
            "relationship_notes": []
        }
    }


# ============================================================
# DEFAULT DATA
# ============================================================

def default_data():

    earth = create_universe(
        1,
        "Earth 1"
    )

    return {
        "world_id": random.randint(
            100000,
            999999
        ),

        "world_number": 1,

        "current_universe": "earth_1",

        "universes": {
            "earth_1": earth
        },

        "multiverse": {
            "id": random.randint(
                100000,
                999999
            ),

            "discovered_universes": [
                "earth_1"
            ],

            "visited_universes": [
                "earth_1"
            ],

            "events": [],

            "global_hints": [],

            "portal_history": []
        }
    }


# ============================================================
# DATA STORAGE
# ============================================================

def save_data(current_data=None):

    if current_data is None:
        current_data = data

    with data_lock:

        temp_file = DATA_FILE + ".tmp"

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                current_data,
                f,
                indent=2,
                ensure_ascii=False
            )

        os.replace(
            temp_file,
            DATA_FILE
        )


def load_data():

    if not os.path.exists(DATA_FILE):

        new_data = default_data()

        save_data(new_data)

        return new_data

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            loaded = json.load(f)

        # ----------------------------------------------------
        # Upgrade old single-world files
        # ----------------------------------------------------

        if "universes" not in loaded:

            old = loaded

            upgraded = default_data()

            upgraded["world_id"] = old.get(
                "world_id",
                random.randint(
                    100000,
                    999999
                )
            )

            upgraded["world_number"] = old.get(
                "world_number",
                1
            )

            earth = create_universe(
                1,
                "Earth 1"
            )

            for key in [
                "characters",
                "locations",
                "player_location",
                "world_memory",
                "background_events",
                "hints",
                "connections",
                "story",
                "improvement",
                "events"
            ]:

                if key in old:
                    earth[key] = old[key]

            upgraded["universes"]["earth_1"] = earth

            loaded = upgraded

        # ----------------------------------------------------
        # Make sure required structures exist
        # ----------------------------------------------------

        loaded.setdefault(
            "current_universe",
            "earth_1"
        )

        loaded.setdefault(
            "universes",
            {}
        )

        if "earth_1" not in loaded["universes"]:

            loaded["universes"]["earth_1"] = create_universe(
                1,
                "Earth 1"
            )

        loaded.setdefault(
            "multiverse",
            {}
        )

        multiverse = loaded["multiverse"]

        multiverse.setdefault(
            "id",
            random.randint(
                100000,
                999999
            )
        )

        multiverse.setdefault(
            "discovered_universes",
            ["earth_1"]
        )

        multiverse.setdefault(
            "visited_universes",
            ["earth_1"]
        )

        multiverse.setdefault(
            "events",
            []
        )

        multiverse.setdefault(
            "global_hints",
            []
        )

        multiverse.setdefault(
            "portal_history",
            []
        )

        # ----------------------------------------------------
        # Repair universes
        # ----------------------------------------------------

        for universe in loaded["universes"].values():

            universe.setdefault(
                "characters",
                json.loads(
                    json.dumps(DEFAULT_CHARACTERS)
                )
            )

            universe.setdefault(
                "locations",
                list(DEFAULT_LOCATIONS)
            )

            universe.setdefault(
                "player_location",
                "Classroom"
            )

            universe.setdefault(
                "world_memory",
                []
            )

            universe.setdefault(
                "background_events",
                []
            )

            universe.setdefault(
                "hints",
                []
            )

            universe.setdefault(
                "connections",
                []
            )

            universe.setdefault(
                "events",
                []
            )

            universe.setdefault(
                "discovered",
                False
            )

            universe.setdefault(
                "visited",
                False
            )

            universe.setdefault(
                "story",
                {
                    "active": False,
                    "story_id": random.randint(
                        100000,
                        999999
                    ),
                    "title": "",
                    "theme": "",
                    "current_node": "start",
                    "history": [],
                    "seen_nodes": ["start"],
                    "ending": None,
                    "tree": {}
                }
            )

            universe.setdefault(
                "improvement",
                {
                    "facts": [],
                    "preferences": [],
                    "successful_patterns": [],
                    "relationship_notes": []
                }
            )

        return loaded

    except Exception:

        new_data = default_data()

        save_data(new_data)

        return new_data


data = load_data()


# ============================================================
# CURRENT UNIVERSE
# ============================================================

def current_universe():

    universe_id = data.get(
        "current_universe",
        "earth_1"
    )

    if universe_id not in data["universes"]:

        universe_id = "earth_1"

        data["current_universe"] = universe_id

    return data["universes"][universe_id]


# ============================================================
# CHARACTER HELPERS
# ============================================================

def find_character(character_id):

    universe = current_universe()

    for character in universe.get(
        "characters",
        []
    ):

        if character.get("id") == character_id:
            return character

    return None


def remember(character, text):

    text = clean_text(text)

    if not text:
        return

    character.setdefault(
        "memory",
        []
    )

    character["memory"].append(text)

    character["memory"] = trim_memory(
        character["memory"],
        40
    )


def add_world_memory(text):

    text = clean_text(text)

    if not text:
        return

    universe = current_universe()

    universe.setdefault(
        "world_memory",
        []
    )

    universe["world_memory"].append(
        text
    )

    universe["world_memory"] = trim_memory(
        universe["world_memory"],
        60
    )


def add_improvement(text):

    text = clean_text(text)

    if not text:
        return

    universe = current_universe()

    improvement = universe.setdefault(
        "improvement",
        {}
    )

    facts = improvement.setdefault(
        "facts",
        []
    )

    if text not in facts:

        facts.append(text)

    improvement["facts"] = trim_memory(
        facts,
        50
    )


# ============================================================
# AI
# ============================================================

def call_ai(
    system_prompt,
    messages=None,
    temperature=0.8,
    max_tokens=700
):

    if messages is None:
        messages = []

    if not client:

        return (
            "AI_ERROR: OPENROUTER_API_KEY "
            "is not configured."
        )

    errors = []

    for model in MODELS:

        try:

            response = client.chat.completions.create(

                model=model,

                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    }
                ] + messages,

                temperature=temperature,

                max_tokens=max_tokens
            )

            if not response.choices:
                continue

            result = response.choices[
                0
            ].message.content

            if result:

                return clean_text(result)

        except Exception as e:

            errors.append(
                f"{model}: {str(e)}"
            )

            continue

    return (
        "AI_ERROR: All configured models failed. "
        + " | ".join(errors)
    )


# ============================================================
# AI JSON
# ============================================================

def safe_json_from_ai(text):

    text = clean_text(text)

    try:

        return json.loads(text)

    except Exception:
        pass

    # Look for a JSON object inside the response.

    start = text.find("{")
    end = text.rfind("}")

    if (
        start != -1
        and end != -1
        and end > start
    ):

        possible = text[
            start:end + 1
        ]

        try:

            return json.loads(
                possible
            )

        except Exception:
            pass

    # Try an array too.

    start = text.find("[")
    end = text.rfind("]")

    if (
        start != -1
        and end != -1
        and end > start
    ):

        possible = text[
            start:end + 1
        ]

        try:

            return json.loads(
                possible
            )

        except Exception:
            pass

    return None


# ============================================================
# HOME
# ============================================================

@app.route(
    "/",
    methods=["GET", "HEAD"]
)
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# WORLD
# ============================================================

@app.route(
    "/world",
    methods=["GET"]
)
def get_world():

    universe = current_universe()

    # IMPORTANT:
    #
    # The frontend expects characters,
    # locations, location, events, etc.
    # directly on the returned object.
    #
    # We provide BOTH the universe object
    # and the convenient direct fields.

    return jsonify({

        "world_id": data.get(
            "world_id"
        ),

        "world_number": data.get(
            "world_number",
            1
        ),

        "current_universe": data.get(
            "current_universe",
            "earth_1"
        ),

        "universe": universe,

        "id": universe.get(
            "id"
        ),

        "name": universe.get(
            "name"
        ),

        "description": universe.get(
            "description",
            ""
        ),

        "characters": universe.get(
            "characters",
            []
        ),

        "locations": universe.get(
            "locations",
            []
        ),

        "location": universe.get(
            "player_location",
            "Classroom"
        ),

        "player_location": universe.get(
            "player_location",
            "Classroom"
        ),

        "world_memory": universe.get(
            "world_memory",
            []
        ),

        "background_events": universe.get(
            "background_events",
            []
        ),

        "hints": universe.get(
            "hints",
            []
        ),

        "events": universe.get(
            "events",
            []
        ),

        "connections": universe.get(
            "connections",
            []
        ),

        "story": universe.get(
            "story",
            {}
        ),

        "improvement": universe.get(
            "improvement",
            {}
        ),

        "multiverse": data.get(
            "multiverse",
            {}
        )
    })


# ============================================================
# CHARACTER CHAT
# ============================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    body = request.get_json(
        silent=True
    ) or {}

    character_id = body.get(
        "character_id"
    )

    message = clean_text(
        body.get("message")
    )

    if not character_id or not message:

        return jsonify({
            "error": (
                "character_id and message "
                "are required"
            )
        }), 400

    character = find_character(
        character_id
    )

    if not character:

        return jsonify({
            "error": "Character not found."
        }), 404

    universe = current_universe()

    remember(
        character,
        f"Player said: {message}"
    )

    recent = character.get(
        "conversation",
        []
    )[-18:]

    messages = []

    for item in recent:

        messages.append({
            "role": item.get(
                "role",
                "user"
            ),
            "content": item.get(
                "content",
                ""
            )
        })

    messages.append({
        "role": "user",
        "content": message
    })

    other_characters = []

    for c in universe.get(
        "characters",
        []
    ):

        if c["id"] != character["id"]:

            other_characters.append({

                "name": c["name"],

                "role": c["role"],

                "personality": c["personality"]
            })

    system_prompt = f"""
You are {character["name"]}, a person inside a
living school simulation.

You are NOT an AI and should never describe yourself
as an AI, chatbot, language model, or assistant.

UNIVERSE:
{universe["name"]}

UNIVERSE DESCRIPTION:
{universe.get("description", "")}

ROLE:
{character["role"]}

PERSONALITY:
{character["personality"]}

DESCRIPTION:
{character["description"]}

TRAITS:
{", ".join(character.get("traits", []))}

CURRENT PLAYER LOCATION:
{universe.get("player_location", "Classroom")}

CHARACTER MEMORY:
{json.dumps(character.get("memory", [])[-25:], ensure_ascii=False)}

WORLD MEMORY:
{json.dumps(universe.get("world_memory", [])[-25:], ensure_ascii=False)}

DIMENSION HINTS:
{json.dumps(universe.get("hints", [])[-10:], ensure_ascii=False)}

OTHER CHARACTERS:
{json.dumps(other_characters, ensure_ascii=False)}

RULES:

1. Stay completely in character.
2. Remember important previous conversations.
3. Give natural medium-length responses.
4. Usually answer with several sentences.
5. Do not make every answer enormous.
6. Do not constantly agree with the player.
7. Have opinions and emotions.
8. Never control the player's actions.
9. Do not decide what the player says, thinks, or does.
10. Know the school locations.
11. You may talk about other students.
12. You may joke, disagree, become curious,
    suspicious, excited, or annoyed.
13. Do not randomly reveal every multiverse secret.
14. The multiverse exists, but characters should
    only know what makes sense for them.
15. Do not turn every conversation into a
    multiverse conversation.
16. Remember that this is {universe["name"]}.
17. Treat the current location naturally.
18. Keep the conversation feeling like a real person.
"""

    answer = call_ai(
        system_prompt,
        messages,
        temperature=0.82,
        max_tokens=650
    )

    if answer.startswith(
        "AI_ERROR:"
    ):

        return jsonify({
            "error": answer
        }), 500

    character.setdefault(
        "conversation",
        []
    )

    character["conversation"].append({

        "role": "user",

        "content": message,

        "time": utc_now()
    })

    character["conversation"].append({

        "role": "assistant",

        "content": answer,

        "time": utc_now()
    })

    character["conversation"] = trim_memory(
        character["conversation"],
        70
    )

    if len(message) > 20:

        add_improvement(
            f"Player communication pattern: "
            f"{message[:180]}"
        )

    save_data()

    return jsonify({

        "reply": answer,

        "character": character,

        "universe": universe["name"],

        "location": universe[
            "player_location"
        ]
    })


# ============================================================
# RESET CHARACTER CONVERSATION
# ============================================================

@app.route(
    "/conversation/reset",
    methods=["POST"]
)
def reset_conversation():

    body = request.get_json(
        silent=True
    ) or {}

    character_id = body.get(
        "character_id"
    )

    character = find_character(
        character_id
    )

    if not character:

        return jsonify({
            "error": "Character not found."
        }), 404

    character["conversation"] = []

    save_data()

    return jsonify({

        "success": True,

        "message": (
            f"Conversation with "
            f"{character['name']} was reset."
        )
    })


# ============================================================
# NEW CONVERSATION
# ============================================================

@app.route(
    "/conversation/new",
    methods=["POST"]
)
def new_text():

    return jsonify({
        "success": True,
        "message": "New conversation started."
    })


# ============================================================
# CREATE CHARACTER
# ============================================================

@app.route(
    "/characters/create",
    methods=["POST"]
)
def create_character():

    body = request.get_json(
        silent=True
    ) or {}

    name = clean_text(
        body.get("name")
    )

    role = clean_text(
        body.get("role")
    ) or "Student"

    personality = clean_text(
        body.get("personality")
    )

    description = clean_text(
        body.get("description")
    )

    traits = body.get(
        "traits",
        []
    )

    if not name:

        return jsonify({
            "error": "Character name is required."
        }), 400

    if not personality:

        return jsonify({
            "error": (
                "Character personality "
                "is required."
            )
        }), 400

    if not isinstance(
        traits,
        list
    ):

        traits = []

    character_id = (
        re.sub(
            r"[^a-z0-9]+",
            "-",
            name.lower()
        ).strip("-")
        + "-"
        + str(
            random.randint(
                1000,
                9999
            )
        )
    )

    character = {

        "id": character_id,

        "name": name,

        "role": role,

        "personality": personality,

        "description": (
            description
            or f"{name} is a "
            f"{role.lower()} at the school."
        ),

        "traits": [
            clean_text(x)
            for x in traits
            if clean_text(x)
        ],

        "memory": [],

        "conversation": []
    }

    universe = current_universe()

    universe[
        "characters"
    ].append(
        character
    )

    save_data()

    return jsonify({

        "success": True,

        "character": character
    })


# ============================================================
# LOCATION TRAVEL
# ============================================================

@app.route(
    "/world/travel",
    methods=["POST"]
)
def travel():

    body = request.get_json(
        silent=True
    ) or {}

    location = clean_text(
        body.get("location")
    )

    universe = current_universe()

    if location not in universe[
        "locations"
    ]:

        return jsonify({
            "error": "Unknown location."
        }), 400

    old_location = universe[
        "player_location"
    ]

    universe[
        "player_location"
    ] = location

    add_world_memory(
        f"Player traveled from "
        f"{old_location} to {location}."
    )

    save_data()

    return jsonify({

        "success": True,

        "location": location,

        "old_location": old_location,

        "universe": universe["name"]
    })


# ============================================================
# BACKGROUND WORLD EVENTS
# ============================================================

@app.route(
    "/world/advance",
    methods=["POST"]
)
def world_advance():

    universe = current_universe()

    if len(
        universe.get(
            "characters",
            []
        )
    ) < 2:

        return jsonify({
            "event": (
                "There are not enough "
                "characters."
            )
        })

    first, second = random.sample(
        universe["characters"],
        2
    )

    location = random.choice(
        universe["locations"]
    )

    system_prompt = f"""
Generate a background interaction between
two school characters.

UNIVERSE:
{universe["name"]}

CHARACTER A:
{first["name"]}
{first["personality"]}

CHARACTER B:
{second["name"]}
{second["personality"]}

LOCATION:
{location}

Create a natural school event.

It can involve:

- joking
- studying
- gossip
- disagreement
- helping
- competition
- an ordinary school moment
- discovering something
- discussing another student

Do not make every event dramatic.

Keep it 3-7 sentences.

Do not control the player.
"""

    event_text = call_ai(
        system_prompt,
        [],
        temperature=0.9,
        max_tokens=350
    )

    if event_text.startswith(
        "AI_ERROR:"
    ):

        return jsonify({
            "error": event_text
        }), 500

    background = {

        "characters": [
            first["name"],
            second["name"]
        ],

        "location": location,

        "event": event_text,

        "time": utc_now()
    }

    universe[
        "background_events"
    ].append(
        background
    )

    universe[
        "background_events"
    ] = trim_memory(
        universe["background_events"],
        50
    )

    remember(
        first,
        f"{second['name']} and I interacted "
        f"at {location}: {event_text[:180]}"
    )

    remember(
        second,
        f"I interacted with "
        f"{first['name']} at {location}: "
        f"{event_text[:180]}"
    )

    add_world_memory(
        f"{first['name']} and "
        f"{second['name']} interacted "
        f"at {location}."
    )

    save_data()

    return jsonify({

        "success": True,

        "event": background
    })


# ============================================================
# MULTIVERSE EVENT TYPES
# ============================================================

MULTIVERSE_EVENT_TYPES = [

    "A strange reflection briefly shows another Earth.",

    "A character receives a message from someone who should not exist.",

    "A classroom object suddenly changes into a different version.",

    "A hallway briefly looks different before returning to normal.",

    "A student remembers an event that never happened in this universe.",

    "A mysterious symbol appears somewhere in the school.",

    "A portal-like distortion appears for a few seconds.",

    "A familiar student behaves as though they came from another Earth.",

    "Two versions of the same object appear at once.",

    "A strange sound seems to come from another universe.",

    "A clock displays a time that does not exist.",

    "Someone sees a second version of themselves.",

    "A doorway appears where there was previously a wall.",

    "A school announcement mentions another dimension.",

    "A mysterious note appears with coordinates to another Earth."
]


# ============================================================
# GENERATE MULTIVERSE EVENT
# ============================================================

def generate_multiversal_event():

    universe = current_universe()

    event_type = random.choice(
        MULTIVERSE_EVENT_TYPES
    )

    discovered = data[
        "multiverse"
    ].get(
        "discovered_universes",
        ["earth_1"]
    )

    prompt = f"""
Generate a multiversal event for a
school simulation.

CURRENT UNIVERSE:
{universe["name"]}

CURRENT LOCATION:
{universe["player_location"]}

CURRENT UNIVERSE DESCRIPTION:
{universe.get("description", "")}

EVENT TYPE:
{event_type}

KNOWN UNIVERSES:
{json.dumps(discovered)}

CURRENT CHARACTERS:
{json.dumps(
    [
        {
            "name": c["name"],
            "personality": c["personality"]
        }
        for c in universe.get(
            "characters",
            []
        )
    ],
    ensure_ascii=False
)}

The event should feel mysterious and interesting.

Do not immediately explain everything.

It should include:

1. What happens.
2. What the player can observe.
3. A clue about another universe.
4. Whether a portal is accessible.

IMPORTANT:

If you set portal_available to true,
target_universe MUST be an existing discovered
universe ID such as "earth_2".

Return ONLY valid JSON:

{{
    "title": "event title",
    "description": "event description",
    "hint": "clue toward another universe",
    "portal_available": false,
    "target_universe": null
}}
"""

    result = call_ai(
        prompt,
        [],
        temperature=1.0,
        max_tokens=600
    )

    parsed = safe_json_from_ai(
        result
    )

    if not parsed:

        parsed = {

            "title": "A Strange Distortion",

            "description": event_type,

            "hint": random.choice(
                DIMENSION_HINTS
            ),

            "portal_available": False,

            "target_universe": None
        }

    target = parsed.get(
        "target_universe"
    )

    if target:

        target = str(target)

        if target not in data[
            "universes"
        ]:

            target = None

        elif not data[
            "universes"
        ][target].get(
            "discovered",
            False
        ):

            target = None

    portal_available = bool(
        parsed.get(
            "portal_available",
            False
        )
    )

    if not target:
        portal_available = False

    event = {

        "id": random.randint(
            100000,
            999999
        ),

        "universe": universe["name"],

        "universe_id": universe["id"],

        "location": universe[
            "player_location"
        ],

        "title": clean_text(
            parsed.get(
                "title",
                "Multiversal Event"
            )
        ),

        "description": clean_text(
            parsed.get(
                "description",
                event_type
            )
        ),

        "hint": clean_text(
            parsed.get(
                "hint",
                random.choice(
                    DIMENSION_HINTS
                )
            )
        ),

        "portal_available": portal_available,

        "target_universe": target,

        "time": utc_now()
    }

    universe[
        "events"
    ].append(
        event
    )

    universe[
        "events"
    ] = trim_memory(
        universe["events"],
        50
    )

    # --------------------------------------------------------
    # Store hint in current universe
    # --------------------------------------------------------

    if event["hint"]:

        universe[
            "hints"
        ].append(
            event["hint"]
        )

        universe[
            "hints"
        ] = trim_memory(
            universe["hints"],
            30
        )

        data[
            "multiverse"
        ][
            "global_hints"
        ].append({

            "universe": universe["name"],

            "universe_id": universe["id"],

            "hint": event["hint"],

            "time": utc_now()
        })

        data[
            "multiverse"
        ][
            "global_hints"
        ] = trim_memory(
            data[
                "multiverse"
            ][
                "global_hints"
            ],
            100
        )

    # --------------------------------------------------------
    # Global event history
    # --------------------------------------------------------

    data[
        "multiverse"
    ][
        "events"
    ].append(
        event
    )

    data[
        "multiverse"
    ][
        "events"
    ] = trim_memory(
        data[
            "multiverse"
        ][
            "events"
        ],
        100
    )

    # --------------------------------------------------------
    # If portal is available, create a connection
    # --------------------------------------------------------

    if (
        portal_available
        and target
    ):

        connection = {
            "from": universe["id"],
            "to": target
        }

        if connection not in universe[
            "connections"
        ]:

            universe[
                "connections"
            ].append(
                connection
            )

    add_world_memory(
        f"Multiversal event: "
        f"{event['title']}"
    )

    save_data()

    return event


# ============================================================
# MULTIVERSE EVENT ROUTE
# ============================================================

@app.route(
    "/multiverse/event",
    methods=["POST"]
)
def multiverse_event():

    event = generate_multiversal_event()

    return jsonify({

        "success": True,

        "event": event
    })


# ============================================================
# CREATE NEW UNIVERSE
# ============================================================

@app.route(
    "/multiverse/create",
    methods=["POST"]
)
def create_universe_route():

    body = request.get_json(
        silent=True
    ) or {}

    requested_number = safe_int(
        body.get("number")
    )

    existing_numbers = []

    for universe in data[
        "universes"
    ].values():

        number = safe_int(
            universe.get("number")
        )

        if number is not None:

            existing_numbers.append(
                number
            )

    if not requested_number:

        requested_number = (
            max(
                existing_numbers,
                default=0
            )
            + 1
        )

    if requested_number < 1:

        requested_number = 1

    universe_id = (
        f"earth_{requested_number}"
    )

    # --------------------------------------------------------
    # Already exists
    # --------------------------------------------------------

    if universe_id in data[
        "universes"
    ]:

        existing = data[
            "universes"
        ][universe_id]

        existing["discovered"] = True

        return jsonify({

            "success": True,

            "universe": existing,

            "already_exists": True
        })

    # --------------------------------------------------------
    # Create universe
    # --------------------------------------------------------

    universe = create_universe(
        requested_number,
        f"Earth {requested_number}"
    )

    universe["discovered"] = True

    universe["visited"] = False

    # Add multiple clues.

    extra_hints = random.sample(
        DIMENSION_HINTS,
        min(
            3,
            len(DIMENSION_HINTS)
        )
    )

    universe["hints"].extend(
        extra_hints
    )

    # Give the new universe a unique
    # initial multiverse event.

    universe["events"].append({

        "id": random.randint(
            100000,
            999999
        ),

        "universe": universe["name"],

        "universe_id": universe["id"],

        "location": "Classroom",

        "title": "A New Dimension",

        "description": (
            f"You have discovered "
            f"{universe['name']}. "
            f"It looks familiar, but something "
            f"about it feels different."
        ),

        "hint": universe["hints"][0],

        "portal_available": True,

        "target_universe": universe["id"],

        "time": utc_now()
    })

    data[
        "universes"
    ][universe_id] = universe

    if universe_id not in data[
        "multiverse"
    ][
        "discovered_universes"
    ]:

        data[
            "multiverse"
        ][
            "discovered_universes"
        ].append(
            universe_id
        )

    # --------------------------------------------------------
    # Connect new universe to current universe
    # --------------------------------------------------------

    current = current_universe()

    connection = {

        "from": current["id"],

        "to": universe["id"]
    }

    if connection not in current[
        "connections"
    ]:

        current[
            "connections"
        ].append(
            connection
        )

    reverse_connection = {

        "from": universe["id"],

        "to": current["id"]
    }

    if reverse_connection not in universe[
        "connections"
    ]:

        universe[
            "connections"
        ].append(
            reverse_connection
        )

    save_data()

    return jsonify({

        "success": True,

        "universe": universe,

        "already_exists": False
    })


# ============================================================
# MULTIVERSE MAP
# ============================================================

@app.route(
    "/multiverse",
    methods=["GET"]
)
def get_multiverse():

    universes = []

    for universe in data[
        "universes"
    ].values():

        universes.append({

            "id": universe["id"],

            "number": universe["number"],

            "name": universe["name"],

            "description": universe.get(
                "description",
                ""
            ),

            "discovered": universe.get(
                "discovered",
                False
            ),

            "visited": universe.get(
                "visited",
                False
            ),

            "hints": universe.get(
                "hints",
                []
            )[-10:],

            "connections": universe.get(
                "connections",
                []
            ),

            "location": universe.get(
                "player_location",
                "Classroom"
            ),

            "character_count": len(
                universe.get(
                    "characters",
                    []
                )
            ),

            "event_count": len(
                universe.get(
                    "events",
                    []
                )
            )
        })

    universes.sort(
        key=lambda x: x["number"]
    )

    return jsonify({

        "current_universe": data[
            "current_universe"
        ],

        "current": data[
            "universes"
        ][
            data["current_universe"]
        ],

        "universes": universes,

        "events": data[
            "multiverse"
        ][
            "events"
        ][-30:],

        "global_hints": data[
            "multiverse"
        ][
            "global_hints"
        ][-50:],

        "portal_history": data[
            "multiverse"
        ][
            "portal_history"
        ][-30:]
    })


# ============================================================
# TRAVEL BETWEEN DIMENSIONS
# ============================================================

@app.route(
    "/multiverse/travel",
    methods=["POST"]
)
def travel_universe():

    body = request.get_json(
        silent=True
    ) or {}

    target = clean_text(
        body.get("universe")
    )

    if not target:

        return jsonify({
            "error": (
                "A universe ID is required."
            )
        }), 400

    if target not in data[
        "universes"
    ]:

        return jsonify({
            "error": (
                "That universe has not "
                "been discovered."
            )
        }), 404

    target_universe = data[
        "universes"
    ][target]

    if not target_universe.get(
        "discovered",
        False
    ):

        return jsonify({
            "error": (
                "That universe has not "
                "been discovered yet."
            )
        }), 403

    old = data[
        "current_universe"
    ]

    if old == target:

        return jsonify({

            "success": True,

            "message": (
                "You are already in "
                "that universe."
            ),

            "universe": target_universe
        })

    old_universe = data[
        "universes"
    ].get(old)

    # --------------------------------------------------------
    # Switch universe
    # --------------------------------------------------------

    data[
        "current_universe"
    ] = target

    target_universe[
        "visited"
    ] = True

    if target not in data[
        "multiverse"
    ][
        "visited_universes"
    ]:

        data[
            "multiverse"
        ][
            "visited_universes"
        ].append(
            target
        )

    # --------------------------------------------------------
    # Portal history
    # --------------------------------------------------------

    portal_entry = {

        "from": old,

        "to": target,

        "time": utc_now()
    }

    data[
        "multiverse"
    ][
        "portal_history"
    ].append(
        portal_entry
    )

    data[
        "multiverse"
    ][
        "portal_history"
    ] = trim_memory(
        data[
            "multiverse"
        ][
            "portal_history"
        ],
        100
    )

    # --------------------------------------------------------
    # Create two-way connection
    # --------------------------------------------------------

    if old_universe:

        connection = {

            "from": old,

            "to": target
        }

        if connection not in old_universe[
            "connections"
        ]:

            old_universe[
                "connections"
            ].append(
                connection
            )

    reverse_connection = {

        "from": target,

        "to": old
    }

    if reverse_connection not in target_universe[
        "connections"
    ]:

        target_universe[
            "connections"
        ].append(
            reverse_connection
        )

    add_world_memory(
        f"Player arrived from "
        f"{old}."
    )

    save_data()

    return jsonify({

        "success": True,

        "from": old,

        "to": target,

        "universe": target_universe
    })


# ============================================================
# STORY THEMES
# ============================================================

STORY_THEMES = [

    "A mysterious event happens at school.",

    "A strange discovery changes an ordinary school day.",

    "A friendship begins to fall apart.",

    "A hidden secret about the school is discovered.",

    "A competition becomes much more serious than expected.",

    "An ordinary day slowly turns into something nobody expected.",

    "A strange object is discovered inside the school.",

    "A school event goes completely wrong.",

    "A rumor spreads through the school.",

    "A multiversal mystery begins inside an ordinary classroom.",

    "A student discovers something impossible about the school.",

    "A strange visitor arrives from another dimension."
]


# ============================================================
# GENERATE STORY
# ============================================================

def generate_story():

    universe = current_universe()

    theme = random.choice(
        STORY_THEMES
    )

    story_system = f"""
Create a branching interactive school story.

UNIVERSE:
{universe["name"]}

UNIVERSE DESCRIPTION:
{universe.get("description", "")}

THEME:
{theme}

CHARACTERS:
{json.dumps(
    [
        {
            "name": c["name"],
            "role": c["role"],
            "personality": c["personality"]
        }
        for c in universe.get(
            "characters",
            []
        )
    ],
    ensure_ascii=False
)}

Requirements:

- 5 major endings minimum.
- 15-24 meaningful story nodes.
- Choices must actually change future events.
- Choices can affect relationships, trust,
  information, locations, opportunities,
  and future decisions.
- Some branches should remain separate.
- Some choices should unlock later choices.
- Exactly four choices at every non-ending node.
- Choices are A, B, C, D.
- Include ordinary school moments between
  major events.
- Characters must behave according
  to their personalities.
- The story must feel continuous.
- Every story should be different.
- The player should not know the correct ending.
- Do not copy copyrighted game plots.

Return ONLY valid JSON.

Use this structure:

{{
  "title": "story title",
  "theme": "story theme",
  "start": "start",

  "nodes": {{

    "start": {{
      "title": "Scene title",
      "text": "Scene description",

      "choices": [
        {{
          "id": "A",
          "text": "Choice A",
          "next": "node_id"
        }},
        {{
          "id": "B",
          "text": "Choice B",
          "next": "node_id"
        }},
        {{
          "id": "C",
          "text": "Choice C",
          "next": "node_id"
        }},
        {{
          "id": "D",
          "text": "Choice D",
          "next": "node_id"
        }}
      ]
    }}

  }},

  "endings": [
    {{
      "id": "ending_1",
      "title": "Ending title",
      "text": "Ending description"
    }}
  ]
}}

Every next value must point to a real node
or a real ending.

Make the story complete.
"""

    response = call_ai(
        story_system,
        [],
        temperature=1.0,
        max_tokens=7000
    )

    parsed = safe_json_from_ai(
        response
    )

    if not parsed:

        return None

    if "nodes" not in parsed:

        return None

    parsed.setdefault(
        "endings",
        []
    )

    return parsed


# ============================================================
# STORY START
# ============================================================

@app.route(
    "/story/start",
    methods=["POST"]
)
def story_start():

    story = generate_story()

    if not story:

        return jsonify({
            "error": (
                "Story generation failed. "
                "Check your API key and "
                "available OpenRouter models."
            )
        }), 500

    universe = current_universe()

    start_node = story.get(
        "start",
        "start"
    )

    data_story = {

        "active": True,

        "story_id": random.randint(
            100000,
            999999
        ),

        "title": story.get(
            "title",
            "Untitled Story"
        ),

        "theme": story.get(
            "theme",
            ""
        ),

        "current_node": start_node,

        "history": [],

        "seen_nodes": [
            start_node
        ],

        "ending": None,

        "tree": story
    }

    universe[
        "story"
    ] = data_story

    add_world_memory(
        f"Story started: "
        f"{data_story['title']}"
    )

    save_data()

    return jsonify({

        "success": True,

        "story": data_story
    })


# ============================================================
# STORY CHOICE
# ============================================================

@app.route(
    "/story/choose",
    methods=["POST"]
)
def story_choose():

    body = request.get_json(
        silent=True
    ) or {}

    choice_id = clean_text(
        body.get("choice")
    )

    universe = current_universe()

    story_state = universe.get(
        "story",
        {}
    )

    if not story_state.get(
        "active",
        False
    ):

        return jsonify({
            "error": "No active story."
        }), 400

    story = story_state.get(
        "tree",
        {}
    )

    current_id = story_state.get(
        "current_node"
    )

    node = story.get(
        "nodes",
        {}
    ).get(
        current_id
    )

    if not node:

        return jsonify({
            "error": "Story node not found."
        }), 404

    choice = None

    for item in node.get(
        "choices",
        []
    ):

        if item.get(
            "id"
        ) == choice_id:

            choice = item

            break

    if not choice:

        return jsonify({
            "error": "Invalid choice."
        }), 400

    next_id = choice.get(
        "next"
    )

    if not next_id:

        return jsonify({
            "error": (
                "This story choice "
                "has no destination."
            )
        }), 500

    story_state[
        "history"
    ].append({

        "node": current_id,

        "choice": choice_id,

        "choice_text": choice.get(
            "text",
            ""
        ),

        "next": next_id,

        "time": utc_now()
    })

    story_state[
        "current_node"
    ] = next_id

    if next_id not in story_state[
        "seen_nodes"
    ]:

        story_state[
            "seen_nodes"
        ].append(
            next_id
        )

    ending = None

    for item in story.get(
        "endings",
        []
    ):

        if item.get(
            "id"
        ) == next_id:

            ending = item

            break

    if ending:

        story_state[
            "ending"
        ] = ending

        story_state[
            "active"
        ] = False

        add_world_memory(
            f"Story ended: "
            f"{ending.get('title', 'Unknown ending')}"
        )

    save_data()

    return jsonify({

        "success": True,

        "current_node": next_id,

        "ending": ending,

        "story": story_state
    })


# ============================================================
# STORY TREE
# ============================================================

@app.route(
    "/story/tree",
    methods=["GET"]
)
def story_tree():

    universe = current_universe()

    story = universe.get(
        "story",
        {}
    )

    return jsonify({

        "title": story.get(
            "title",
            ""
        ),

        "theme": story.get(
            "theme",
            ""
        ),

        "current_node": story.get(
            "current_node",
            "start"
        ),

        "tree": story.get(
            "tree",
            {}
        ),

        "seen_nodes": story.get(
            "seen_nodes",
            []
        ),

        "history": story.get(
            "history",
            []
        ),

        "ending": story.get(
            "ending"
        ),

        "active": story.get(
            "active",
            False
        )
    })


# ============================================================
# STORY REPLAY
# ============================================================

@app.route(
    "/story/replay",
    methods=["POST"]
)
def story_replay():

    universe = current_universe()

    old_story = universe.get(
        "story",
        {}
    )

    tree = old_story.get(
        "tree",
        {}
    )

    if not tree or not tree.get(
        "nodes"
    ):

        return jsonify({
            "error": (
                "There is no story "
                "to replay."
            )
        }), 400

    start_node = tree.get(
        "start",
        "start"
    )

    universe[
        "story"
    ] = {

        "active": True,

        "story_id": random.randint(
            100000,
            999999
        ),

        "title": tree.get(
            "title",
            "Untitled Story"
        ),

        "theme": tree.get(
            "theme",
            ""
        ),

        "current_node": start_node,

        "history": [],

        "seen_nodes": [
            start_node
        ],

        "ending": None,

        "tree": tree
    }

    save_data()

    return jsonify({

        "success": True,

        "story": universe[
            "story"
        ]
    })


# ============================================================
# IMPROVEMENT
# ============================================================

@app.route(
    "/improvement",
    methods=["GET"]
)
def get_improvement():

    return jsonify(
        current_universe().get(
            "improvement",
            {}
        )
    )


@app.route(
    "/improvement/learn",
    methods=["POST"]
)
def improvement_learn():

    body = request.get_json(
        silent=True
    ) or {}

    lesson = clean_text(
        body.get("lesson")
    )

    if not lesson:

        return jsonify({
            "error": "Lesson is required."
        }), 400

    add_improvement(
        lesson
    )

    save_data()

    return jsonify({

        "success": True,

        "improvement": current_universe().get(
            "improvement",
            {}
        )
    })


# ============================================================
# WORLD RESET
# ============================================================

@app.route(
    "/world/reset",
    methods=["POST"]
)
def reset_world():

    global data

    old_number = data.get(
        "world_number",
        1
    )

    new_data = default_data()

    new_data[
        "world_number"
    ] = old_number + 1

    new_data[
        "world_id"
    ] = random.randint(
        100000,
        999999
    )

    new_data[
        "multiverse"
    ][
        "id"
    ] = random.randint(
        100000,
        999999
    )

    data = new_data

    save_data()

    return jsonify({

        "success": True,

        "world_number": data[
            "world_number"
        ],

        "world_id": data[
            "world_id"
        ],

        "message": (
            "A completely new multiverse "
            "was created. Previous memories, "
            "stories, characters, events, "
            "and discoveries were reset."
        )
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return jsonify({

        "status": "ok",

        "ai_configured": bool(
            API_KEY
        ),

        "models": MODELS,

        "current_universe": data[
            "current_universe"
        ],

        "universe_count": len(
            data["universes"]
        ),

        "world": data.get(
            "world_number",
            1
        )
    })


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "5000"
        )
    )

    app.run(

        host="0.0.0.0",

        port=port,

        debug=False
    )
