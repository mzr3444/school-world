import os
import json
import random
import re
import threading
from datetime import datetime

from flask import Flask, render_template, request, jsonify
from openai import OpenAI


# ============================================================
# APP
# ============================================================

app = Flask(__name__)

DATA_FILE = "school_world_data.json"
data_lock = threading.Lock()


# ============================================================
# OPENROUTER
# ============================================================

API_KEY = (
    os.getenv("OPENROUTER_API_KEY")
    or os.getenv("OPENAI_API_KEY")
)

# openrouter/free automatically chooses an available free model.
# You can override it with OPENROUTER_MODEL.
MODELS = [
    os.getenv("OPENROUTER_MODEL", "openrouter/free"),
    "openai/gpt-oss-20b:free",
]

# Remove duplicates while keeping order.
MODELS = list(dict.fromkeys(MODELS))


if API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY
    )
else:
    client = None


# ============================================================
# DEFAULT CHARACTERS
# ============================================================

DEFAULT_CHARACTERS = [
    {
        "id": "alex",
        "name": "Alex",
        "role": "Student",
        "personality": (
            "Friendly, curious, funny, energetic, and sometimes impulsive."
        ),
        "description": (
            "Alex likes meeting people and turning boring situations "
            "into something interesting."
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
            "Intelligent, calm, observant, sarcastic, and independent."
        ),
        "description": (
            "Maya notices details other people miss and thinks "
            "before she speaks."
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
            "Confident, competitive, outgoing, playful, and occasionally stubborn."
        ),
        "description": (
            "Jordan loves competition and enjoys challenging people."
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
            "Quiet, creative, thoughtful, kind, and slightly mysterious."
        ),
        "description": (
            "Sam spends a lot of time drawing, reading, and observing the school."
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


DEFAULT_LOCATIONS = [
    "Classroom",
    "Hallway",
    "Cafeteria",
    "Library",
    "Gym",
    "Courtyard",
    "Science Lab",
    "Computer Lab",
    "Front Office"
]


# ============================================================
# DIMENSION DESCRIPTIONS
# ============================================================

DIMENSION_DESCRIPTIONS = [
    (
        "A world that looks almost identical to Earth 1, "
        "but small details are strangely different."
    ),
    (
        "A world where the school developed very differently "
        "and old decisions changed its history."
    ),
    (
        "A world where unusual things happen more often "
        "than they should."
    ),
    (
        "A world where several students remember different "
        "versions of the same events."
    ),
    (
        "A world with a strange history surrounding the school."
    ),
    (
        "A world where one important event changed the "
        "future of the entire school."
    ),
    (
        "A world that seems normal until you start noticing "
        "the details."
    ),
    (
        "A world where the boundary between dimensions "
        "has become unusually weak."
    )
]


# ============================================================
# MULTIVERSE HINTS
# ============================================================

DIMENSION_HINTS = [
    "A clock shows a time that does not exist on your world.",
    "You notice handwriting that looks exactly like yours.",
    "Someone mentions a student who does not exist here.",
    "A familiar hallway has a door that should not be there.",
    "A reflection moves a fraction of a second too late.",
    "A classroom poster has a completely different school name.",
    "A student remembers a conversation you never had.",
    "A book contains a photograph of a different version of the school.",
    "A strange symbol appears near the edge of a classroom desk.",
    "The lights flicker and the hallway briefly looks unfamiliar.",
    "A teacher says something happened yesterday that never happened.",
    "You hear your own voice coming from an empty room.",
    "A familiar object has a different color and different markings.",
    "A locker contains a note addressed to someone from another Earth."
]


MULTIVERSE_EVENT_TYPES = [
    "strange reflection",
    "impossible message",
    "alternate object",
    "hallway distortion",
    "memory contradiction",
    "mysterious symbol",
    "temporary portal",
    "alternate student",
    "duplicate object",
    "sound from another dimension"
]


# ============================================================
# BASIC HELPERS
# ============================================================

def now():
    return datetime.utcnow().isoformat()


def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", "")

    text = re.sub(
        r"```(?:json|python|html|javascript)?",
        "",
        text,
        flags=re.I
    )

    text = text.replace("```", "")

    return text.strip()


def trim_list(items, limit):
    if not isinstance(items, list):
        return []

    if len(items) <= limit:
        return items

    return items[-limit:]


def safe_json_from_ai(text):
    text = clean_text(text)

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        try:
            return json.loads(
                text[start:end + 1]
            )
        except Exception:
            pass

    return None


# ============================================================
# CHARACTER HELPERS
# ============================================================

def copy_default_characters():
    return json.loads(
        json.dumps(DEFAULT_CHARACTERS)
    )


def find_character(character_id):
    universe = current_universe()

    for character in universe.get("characters", []):
        if character.get("id") == character_id:
            return character

    return None


def remember(character, text):
    text = clean_text(text)

    if not text:
        return

    character.setdefault("memory", [])
    character["memory"].append(text)
    character["memory"] = trim_list(
        character["memory"],
        50
    )


def add_world_memory(text):
    universe = current_universe()

    text = clean_text(text)

    if not text:
        return

    universe.setdefault(
        "world_memory",
        []
    )

    universe["world_memory"].append(text)

    universe["world_memory"] = trim_list(
        universe["world_memory"],
        100
    )


# ============================================================
# UNIVERSES
# ============================================================

def create_universe(number, name=None):
    if name is None:
        name = f"Earth {number}"

    return {
        "id": f"earth_{number}",
        "number": number,
        "name": name,

        "description": (
            "An alternate version of the school world."
        ),

        "characters": copy_default_characters(),

        "locations": list(DEFAULT_LOCATIONS),

        "player_location": "Classroom",

        "world_memory": [],

        "background_events": [],

        "events": [],

        "hints": [],

        "connections": [],

        "discovered": number == 1,

        "visited": number == 1,

        "story": {
            "active": False,
            "story_id": random.randint(100000, 999999),
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
# SAVE / LOAD
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

    except Exception:
        new_data = default_data()
        save_data(new_data)
        return new_data

    # --------------------------------------------------------
    # Upgrade old save files.
    # --------------------------------------------------------

    if not isinstance(loaded, dict):
        loaded = default_data()

    if "universes" not in loaded:
        old = loaded

        upgraded = default_data()

        upgraded["world_id"] = old.get(
            "world_id",
            random.randint(100000, 999999)
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
            "events",
            "hints",
            "connections",
            "story",
            "improvement"
        ]:
            if key in old:
                earth[key] = old[key]

        upgraded["universes"]["earth_1"] = earth

        loaded = upgraded

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
        random.randint(100000, 999999)
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

    # Make sure every universe has newer fields.
    for universe in loaded["universes"].values():

        universe.setdefault(
            "locations",
            list(DEFAULT_LOCATIONS)
        )

        universe.setdefault(
            "characters",
            copy_default_characters()
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
            "events",
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
            "discovered",
            universe.get("number") == 1
        )

        universe.setdefault(
            "visited",
            universe.get("number") == 1
        )

        universe.setdefault(
            "description",
            "An alternate version of the school world."
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


data = load_data()


# ============================================================
# CURRENT UNIVERSE
# ============================================================

def current_universe():
    universe_id = data.get(
        "current_universe",
        "earth_1"
    )

    if universe_id not in data.get(
        "universes",
        {}
    ):
        universe_id = "earth_1"

        data["current_universe"] = (
            universe_id
        )

    return data["universes"][universe_id]


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
            "AI_ERROR: OPENROUTER_API_KEY is not configured."
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

            result = response.choices[0].message.content

            if result:
                return clean_text(result)

        except Exception as e:
            errors.append(
                f"{model}: {str(e)}"
            )

    return (
        "AI_ERROR: All configured models failed. "
        + " | ".join(errors)
    )


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET", "HEAD"])
def home():
    return render_template("index.html")


# ============================================================
# WORLD
# ============================================================

@app.route("/world", methods=["GET"])
def get_world():
    universe = current_universe()

    # IMPORTANT:
    # This is flattened so your existing HTML can use:
    # world.characters
    # world.locations
    # world.location
    # world.background_events
    #
    # This was one of the problems in the previous version.

    return jsonify({
        "world_id": data["world_id"],
        "world_number": data["world_number"],

        "current_universe": data["current_universe"],

        "universe": universe,

        "universe_id": universe["id"],
        "universe_number": universe["number"],
        "universe_name": universe["name"],
        "universe_description": universe["description"],

        "characters": universe["characters"],

        "locations": universe["locations"],

        "location": universe["player_location"],

        "player_location": universe["player_location"],

        "world_memory": universe["world_memory"],

        "background_events": universe["background_events"],

        "events": universe["events"],

        "hints": universe["hints"],

        "connections": universe["connections"],

        "story": universe["story"],

        "improvement": universe["improvement"],

        "multiverse": data["multiverse"]
    })


# ============================================================
# CHARACTER CHAT
# ============================================================

@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(
        silent=True
    ) or {}

    character_id = clean_text(
        body.get("character_id")
    )

    message = clean_text(
        body.get("message")
    )

    if not character_id or not message:
        return jsonify({
            "error": (
                "character_id and message are required."
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
    )[-20:]

    messages = []

    for item in recent:
        role = item.get(
            "role",
            "user"
        )

        content = item.get(
            "content",
            ""
        )

        if role not in [
            "user",
            "assistant"
        ]:
            continue

        messages.append({
            "role": role,
            "content": content
        })

    messages.append({
        "role": "user",
        "content": message
    })

    other_characters = []

    for c in universe["characters"]:

        if c["id"] == character["id"]:
            continue

        other_characters.append({
            "name": c["name"],
            "role": c["role"],
            "personality": c["personality"]
        })

    recent_events = (
        universe.get(
            "events",
            []
        )[-10:]
    )

    system_prompt = f"""
You are {character["name"]}, a real person inside a living school simulation.

UNIVERSE:
{universe["name"]}

UNIVERSE DESCRIPTION:
{universe["description"]}

ROLE:
{character["role"]}

PERSONALITY:
{character["personality"]}

DESCRIPTION:
{character["description"]}

TRAITS:
{", ".join(character.get("traits", []))}

CURRENT PLAYER LOCATION:
{universe["player_location"]}

YOUR MEMORY:
{json.dumps(character.get("memory", [])[-30:], ensure_ascii=False)}

WORLD MEMORY:
{json.dumps(universe.get("world_memory", [])[-30:], ensure_ascii=False)}

RECENT MULTIVERSAL EVENTS:
{json.dumps(recent_events, ensure_ascii=False)}

OTHER CHARACTERS:
{json.dumps(other_characters, ensure_ascii=False)}

RULES:

1. Stay completely in character.
2. Talk naturally.
3. Have your own opinions.
4. You can disagree with the player.
5. You can joke, get annoyed, become excited,
   become suspicious, or become curious.
6. Never control the player's actions.
7. Do not automatically follow the player when they travel.
8. Characters have their own lives.
9. React naturally if a multiversal event has happened.
10. Do not constantly talk about dimensions.
11. Do not randomly reveal secrets.
12. Remember previous conversations.
13. Keep responses medium length.
14. Usually use 2-5 short paragraphs.
15. Do not describe yourself as an AI.
16. You know the school and its locations.
17. The universe may be different from other universes.
18. Do not assume the player knows everything.
19. If the player mentions something strange,
    react according to your personality.
20. You may reference other students when appropriate.
"""

    answer = call_ai(
        system_prompt,
        messages,
        temperature=0.85,
        max_tokens=650
    )

    if answer.startswith("AI_ERROR:"):
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
        "time": now()
    })

    character["conversation"].append({
        "role": "assistant",
        "content": answer,
        "time": now()
    })

    character["conversation"] = trim_list(
        character["conversation"],
        80
    )

    save_data()

    return jsonify({
        "reply": answer,
        "character": character,
        "universe": universe["name"],
        "location": universe["player_location"]
    })


# ============================================================
# RESET CHARACTER CONVERSATION
# ============================================================

@app.route("/conversation/reset", methods=["POST"])
def reset_conversation():
    body = request.get_json(
        silent=True
    ) or {}

    character_id = clean_text(
        body.get("character_id")
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
            f"Conversation with {character['name']} reset."
        )
    })


@app.route("/conversation/new", methods=["POST"])
def new_conversation():
    return jsonify({
        "success": True,
        "message": "New conversation started."
    })


# ============================================================
# CREATE CHARACTER
# ============================================================

@app.route("/characters/create", methods=["POST"])
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
            "error": "Character personality is required."
        }), 400

    if not isinstance(traits, list):
        traits = []

    character_id = (
        re.sub(
            r"[^a-z0-9]+",
            "-",
            name.lower()
        ).strip("-")
        + "-"
        + str(random.randint(1000, 9999))
    )

    character = {
        "id": character_id,
        "name": name,
        "role": role,
        "personality": personality,
        "description": (
            description
            or f"{name} is a {role.lower()} at the school."
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

    universe["characters"].append(
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

@app.route("/world/travel", methods=["POST"])
def travel_location():
    body = request.get_json(
        silent=True
    ) or {}

    location = clean_text(
        body.get("location")
    )

    universe = current_universe()

    if location not in universe["locations"]:
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
        f"Player traveled from {old_location} to {location}."
    )

    save_data()

    return jsonify({
        "success": True,
        "location": location,
        "universe": universe["name"]
    })


# ============================================================
# BACKGROUND WORLD EVENTS
# ============================================================

@app.route("/world/advance", methods=["POST"])
def world_advance():
    universe = current_universe()

    if len(universe["characters"]) < 2:
        return jsonify({
            "event": None,
            "message": "Not enough characters."
        })

    first, second = random.sample(
        universe["characters"],
        2
    )

    location = random.choice(
        universe["locations"]
    )

    # If AI isn't available, still make the world work.
    if client:

        prompt = f"""
Create a short natural background interaction between two
school students.

Student A:
{first["name"]}
{first["personality"]}

Student B:
{second["name"]}
{second["personality"]}

Location:
{location}

Universe:
{universe["name"]}

Possible event types:
- joking
- studying
- gossip
- disagreement
- helping
- competition
- ordinary school moment
- discovering something

Do not make every event dramatic.

Write 3-6 sentences.
Do not control the player.
"""

        event_text = call_ai(
            prompt,
            [],
            temperature=0.9,
            max_tokens=350
        )

    else:

        event_text = (
            f"{first['name']} and {second['name']} "
            f"were talking in the {location}. "
            f"They seemed caught up in their own conversation."
        )

    if event_text.startswith("AI_ERROR:"):
        event_text = (
            f"{first['name']} and {second['name']} "
            f"were talking in the {location}. "
            f"Something about their conversation seemed interesting."
        )

    event = {
        "characters": [
            first["name"],
            second["name"]
        ],

        "location": location,

        "event": event_text,

        "time": now()
    }

    universe["background_events"].append(
        event
    )

    universe["background_events"] = trim_list(
        universe["background_events"],
        60
    )

    remember(
        first,
        f"I interacted with {second['name']} at {location}."
    )

    remember(
        second,
        f"I interacted with {first['name']} at {location}."
    )

    add_world_memory(
        f"{first['name']} and {second['name']} "
        f"had an interaction at {location}."
    )

    save_data()

    return jsonify({
        "success": True,
        "event": event
    })


# ============================================================
# CREATE A NEW DIMENSION
# ============================================================

def create_dimension(number):
    universe = create_universe(
        number,
        f"Earth {number}"
    )

    universe["description"] = random.choice(
        DIMENSION_DESCRIPTIONS
    )

    universe["discovered"] = True

    # Give the dimension a few unique hints.
    universe["hints"] = random.sample(
        DIMENSION_HINTS,
        min(3, len(DIMENSION_HINTS))
    )

    # Make a few character details slightly different.
    alternate_details = [
        "seems unusually familiar",
        "has a different favorite subject",
        "has been asking strange questions",
        "seems to remember something differently",
        "has recently noticed strange events"
    ]

    for character in universe["characters"]:
        character["alternate_detail"] = random.choice(
            alternate_details
        )

    return universe


@app.route("/multiverse/create", methods=["POST"])
def create_universe_route():
    body = request.get_json(
        silent=True
    ) or {}

    requested_number = body.get(
        "number"
    )

    existing_numbers = [
        u.get("number", 0)
        for u in data["universes"].values()
    ]

    if requested_number is not None:
        try:
            requested_number = int(
                requested_number
            )
        except Exception:
            requested_number = None

    if not requested_number:
        requested_number = (
            max(
                existing_numbers,
                default=0
            )
            + 1
        )

    universe_id = (
        f"earth_{requested_number}"
    )

    if universe_id in data["universes"]:
        return jsonify({
            "success": True,
            "already_exists": True,
            "universe": data["universes"][universe_id]
        })

    universe = create_dimension(
        requested_number
    )

    data["universes"][universe_id] = universe

    if universe_id not in data["multiverse"]["discovered_universes"]:
        data["multiverse"]["discovered_universes"].append(
            universe_id
        )

    save_data()

    return jsonify({
        "success": True,
        "universe": universe
    })


# ============================================================
# MULTIVERSE EVENTS
# ============================================================

def generate_multiversal_event():
    universe = current_universe()

    event_type = random.choice(
        MULTIVERSE_EVENT_TYPES
    )

    # Occasionally create a new dimension.
    should_create_dimension = (
        random.random() < 0.45
    )

    target_universe = None

    if should_create_dimension:

        existing_numbers = [
            u.get("number", 0)
            for u in data["universes"].values()
        ]

        next_number = (
            max(
                existing_numbers,
                default=0
            )
            + 1
        )

        new_universe_id = (
            f"earth_{next_number}"
        )

        new_universe = create_dimension(
            next_number
        )

        # New dimension exists but is only discovered
        # through this event.
        data["universes"][
            new_universe_id
        ] = new_universe

        target_universe = new_universe_id

        if new_universe_id not in data["multiverse"]["discovered_universes"]:
            data["multiverse"]["discovered_universes"].append(
                new_universe_id
            )

    else:

        known = [
            uid
            for uid in data["multiverse"].get(
                "discovered_universes",
                []
            )
            if uid != universe["id"]
        ]

        if known:
            target_universe = random.choice(
                known
            )

    # --------------------------------------------------------
    # Generate event with AI if possible.
    # --------------------------------------------------------

    if client:

        target_name = (
            data["universes"][target_universe]["name"]
            if target_universe
            else "an unknown dimension"
        )

        prompt = f"""
Create a mysterious multiversal event in a school simulation.

Current universe:
{universe["name"]}

Current location:
{universe["player_location"]}

Event type:
{event_type}

Possible connected universe:
{target_name}

Characters:
{json.dumps([
    {
        "name": c["name"],
        "personality": c["personality"]
    }
    for c in universe["characters"]
], ensure_ascii=False)}

The event should:
- feel mysterious
- be interesting but not ridiculous
- give the player a clue
- avoid explaining everything
- allow characters to notice/react to it
- potentially reveal that another dimension exists

Return ONLY JSON:

{{
    "title": "short title",
    "description": "what happens",
    "hint": "small clue about another dimension",
    "portal_available": true
}}
"""

        result = call_ai(
            prompt,
            [],
            temperature=1.0,
            max_tokens=500
        )

        parsed = safe_json_from_ai(
            result
        )

    else:
        parsed = None

    if not parsed:
        parsed = {
            "title": "A Strange Distortion",
            "description": (
                f"A strange {event_type} occurs in the "
                f"{universe['player_location']}. "
                f"For a moment, something about the school "
                f"looks completely different."
            ),
            "hint": random.choice(
                DIMENSION_HINTS
            ),
            "portal_available": bool(
                target_universe
            )
        }

    hint = clean_text(
        parsed.get(
            "hint",
            random.choice(DIMENSION_HINTS)
        )
    )

    event = {
        "id": random.randint(
            100000,
            999999
        ),

        "universe": universe["name"],

        "universe_id": universe["id"],

        "location": universe["player_location"],

        "title": clean_text(
            parsed.get(
                "title",
                "Multiversal Event"
            )
        ),

        "description": clean_text(
            parsed.get(
                "description",
                ""
            )
        ),

        "hint": hint,

        "portal_available": bool(
            parsed.get(
                "portal_available",
                False
            )
        ) and bool(target_universe),

        "target_universe": target_universe,

        "time": now()
    }

    universe["events"].append(
        event
    )

    universe["events"] = trim_list(
        universe["events"],
        70
    )

    # Store hint.
    if hint:

        universe["hints"].append(
            hint
        )

        universe["hints"] = trim_list(
            universe["hints"],
            40
        )

        data["multiverse"]["global_hints"].append({
            "universe": universe["name"],
            "universe_id": universe["id"],
            "hint": hint,
            "time": now()
        })

        data["multiverse"]["global_hints"] = trim_list(
            data["multiverse"]["global_hints"],
            150
        )

    data["multiverse"]["events"].append(
        event
    )

    data["multiverse"]["events"] = trim_list(
        data["multiverse"]["events"],
        150
    )

    # --------------------------------------------------------
    # Make characters remember the event.
    # --------------------------------------------------------

    for character in universe["characters"]:

        remember(
            character,
            (
                f"I witnessed a strange multiversal event: "
                f"{event['title']}. "
                f"{event['description'][:200]}"
            )
        )

    add_world_memory(
        f"Multiversal event: {event['title']}"
    )

    save_data()

    return event


@app.route("/multiverse/event", methods=["POST"])
def multiverse_event():
    event = generate_multiversal_event()

    return jsonify({
        "success": True,
        "event": event
    })


# ============================================================
# MULTIVERSE MAP
# ============================================================

@app.route("/multiverse", methods=["GET"])
def get_multiverse():
    universes = []

    for universe in data["universes"].values():

        universes.append({
            "id": universe["id"],
            "number": universe["number"],
            "name": universe["name"],
            "description": universe["description"],
            "discovered": universe["discovered"],
            "visited": universe["visited"],
            "hints": universe.get(
                "hints",
                []
            )[-10:],
            "connections": universe.get(
                "connections",
                []
            )
        })

    universes.sort(
        key=lambda x: x["number"]
    )

    return jsonify({
        "current_universe": data["current_universe"],

        "universes": universes,

        "events": data["multiverse"]["events"][-40:],

        "global_hints": data["multiverse"]["global_hints"][-60:],

        "portal_history": data["multiverse"]["portal_history"][-40:]
    })


# ============================================================
# TRAVEL BETWEEN DIMENSIONS
# ============================================================

@app.route("/multiverse/travel", methods=["POST"])
def travel_universe():
    body = request.get_json(
        silent=True
    ) or {}

    target = clean_text(
        body.get("universe")
    )

    if not target:
        return jsonify({
            "error": "No universe was selected."
        }), 400

    if target not in data["universes"]:
        return jsonify({
            "error": (
                "That dimension has not been discovered yet."
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
                "That dimension has not been discovered yet."
            )
        }), 403

    old = data["current_universe"]

    if old == target:
        return jsonify({
            "success": True,
            "message": (
                "You are already in that dimension."
            ),
            "from": old,
            "to": target,
            "universe": target_universe
        })

    old_universe = data[
        "universes"
    ].get(old)

    # --------------------------------------------------------
    # Record connection in both directions.
    # --------------------------------------------------------

    connection_forward = {
        "from": old,
        "to": target
    }

    connection_back = {
        "from": target,
        "to": old
    }

    if old_universe is not None:

        old_universe.setdefault(
            "connections",
            []
        )

        if connection_forward not in old_universe["connections"]:
            old_universe["connections"].append(
                connection_forward
            )

    target_universe.setdefault(
        "connections",
        []
    )

    if connection_back not in target_universe["connections"]:
        target_universe["connections"].append(
            connection_back
        )

    # --------------------------------------------------------
    # Travel.
    # --------------------------------------------------------

    data["current_universe"] = target

    target_universe["visited"] = True

    if target not in data["multiverse"]["visited_universes"]:
        data["multiverse"]["visited_universes"].append(
            target
        )

    portal_event = {
        "from": old,
        "to": target,
        "from_name": (
            old_universe["name"]
            if old_universe
            else old
        ),
        "to_name": target_universe["name"],
        "time": now()
    }

    data["multiverse"]["portal_history"].append(
        portal_event
    )

    data["multiverse"]["portal_history"] = trim_list(
        data["multiverse"]["portal_history"],
        100
    )

    # Give the player a hint immediately upon arrival.
    arrival_hint = random.choice(
        DIMENSION_HINTS
    )

    target_universe["hints"].append(
        arrival_hint
    )

    target_universe["hints"] = trim_list(
        target_universe["hints"],
        40
    )

    add_world_memory(
        f"Player traveled from {old} to {target}."
    )

    save_data()

    return jsonify({
        "success": True,

        "from": old,

        "to": target,

        "universe": target_universe,

        "arrival_hint": arrival_hint
    })


# ============================================================
# STORY MODE
# ============================================================

STORY_THEMES = [
    "A mysterious event happens at school.",
    "A strange discovery changes an ordinary school day.",
    "A friendship begins to fall apart.",
    "A hidden secret about the school is discovered.",
    "A competition becomes much more serious than expected.",
    "An ordinary day slowly turns into something unexpected.",
    "A strange object is discovered inside the school.",
    "A school event goes completely wrong.",
    "A rumor spreads through the school.",
    "A multiversal mystery begins inside an ordinary classroom."
]


def fallback_story():
    """
    Used if AI story generation fails.
    This means Story Mode can still work.
    """

    return {
        "title": "The Strange Door",

        "theme": (
            "A mysterious door appears in the school."
        ),

        "start": "start",

        "nodes": {

            "start": {
                "title": "The Door",
                "text": (
                    "The school day seems normal until you notice "
                    "a door at the end of the hallway that you've "
                    "never seen before."
                ),
                "choices": [
                    {
                        "id": "A",
                        "text": "Open the door.",
                        "next": "door"
                    },
                    {
                        "id": "B",
                        "text": "Ask Maya about it.",
                        "next": "maya"
                    },
                    {
                        "id": "C",
                        "text": "Look for a teacher.",
                        "next": "teacher"
                    },
                    {
                        "id": "D",
                        "text": "Walk away.",
                        "next": "away"
                    }
                ]
            },

            "door": {
                "title": "Another Hallway",
                "text": (
                    "Behind the door is a hallway that looks almost "
                    "exactly like your school, except everything is "
                    "slightly different."
                ),
                "choices": [
                    {
                        "id": "A",
                        "text": "Walk deeper inside.",
                        "next": "ending_explorer"
                    },
                    {
                        "id": "B",
                        "text": "Go back.",
                        "next": "ending_safe"
                    },
                    {
                        "id": "C",
                        "text": "Call out.",
                        "next": "ending_echo"
                    },
                    {
                        "id": "D",
                        "text": "Search for another door.",
                        "next": "ending_lost"
                    }
                ]
            },

            "maya": {
                "title": "Maya Notices",
                "text": (
                    "Maya studies the door carefully. She says the "
                    "lock looks newer than the rest of the hallway."
                ),
                "choices": [
                    {
                        "id": "A",
                        "text": "Open it with Maya.",
                        "next": "door"
                    },
                    {
                        "id": "B",
                        "text": "Leave it alone.",
                        "next": "ending_safe"
                    },
                    {
                        "id": "C",
                        "text": "Search the hallway.",
                        "next": "ending_clue"
                    },
                    {
                        "id": "D",
                        "text": "Tell Jordan.",
                        "next": "ending_competition"
                    }
                ]
            },

            "teacher": {
                "title": "The Teacher",
                "text": (
                    "The teacher looks confused when you mention "
                    "the door. They insist that there has never "
                    "been a door there."
                ),
                "choices": [
                    {
                        "id": "A",
                        "text": "Show them.",
                        "next": "ending_clue"
                    },
                    {
                        "id": "B",
                        "text": "Keep investigating.",
                        "next": "door"
                    },
                    {
                        "id": "C",
                        "text": "Believe them.",
                        "next": "ending_safe"
                    },
                    {
                        "id": "D",
                        "text": "Ask another student.",
                        "next": "ending_echo"
                    }
                ]
            },

            "away": {
                "title": "Pretending Nothing Happened",
                "text": (
                    "You walk away. For the rest of the day, "
                    "you keep wondering whether the door was real."
                ),
                "choices": [
                    {
                        "id": "A",
                        "text": "Return after school.",
                        "next": "door"
                    },
                    {
                        "id": "B",
                        "text": "Forget about it.",
                        "next": "ending_safe"
                    },
                    {
                        "id": "C",
                        "text": "Tell someone.",
                        "next": "ending_clue"
                    },
                    {
                        "id": "D",
                        "text": "Investigate tomorrow.",
                        "next": "ending_echo"
                    }
                ]
            }
        },

        "endings": [

            {
                "id": "ending_explorer",
                "title": "The Explorer",
                "text": (
                    "You step into the alternate school and realize "
                    "you may have discovered another dimension."
                )
            },

            {
                "id": "ending_safe",
                "title": "The Safe Choice",
                "text": (
                    "You decide that some mysteries are better left alone."
                )
            },

            {
                "id": "ending_echo",
                "title": "The Echo",
                "text": (
                    "Your voice comes back from somewhere that "
                    "should not exist."
                )
            },

            {
                "id": "ending_lost",
                "title": "Lost Between Worlds",
                "text": (
                    "The hallway changes around you. "
                    "You can no longer tell which school is yours."
                )
            },

            {
                "id": "ending_clue",
                "title": "The First Clue",
                "text": (
                    "You discover a symbol that appears to be "
                    "connected to another universe."
                )
            },

            {
                "id": "ending_competition",
                "title": "A Race Between Worlds",
                "text": (
                    "Jordan turns the discovery into a competition, "
                    "and suddenly everyone wants to know what's behind "
                    "the door."
                )
            }
        ]
    }


def generate_story():
    universe = current_universe()

    theme = random.choice(
        STORY_THEMES
    )

    if not client:
        return fallback_story()

    story_system = f"""
Create a branching interactive school story.

UNIVERSE:
{universe["name"]}

UNIVERSE DESCRIPTION:
{universe["description"]}

THEME:
{theme}

CHARACTERS:
{json.dumps([
    {
        "name": c["name"],
        "role": c["role"],
        "personality": c["personality"]
    }
    for c in universe["characters"]
], ensure_ascii=False)}

Requirements:

- At least 5 endings.
- 15-24 meaningful story nodes if possible.
- Exactly four choices at every normal node.
- Choices must change future events.
- Some choices should create different branches.
- Characters must behave according to personality.
- Include normal school moments.
- The player controls only themselves.
- Do not force the player's actions.
- The story should feel continuous.
- Do not copy an existing copyrighted story.
- A multiverse mystery is allowed but should not dominate every scene.

Return ONLY valid JSON.

Structure:

{{
  "title": "story title",
  "theme": "story theme",
  "start": "start",
  "nodes": {{
    "start": {{
      "title": "Scene title",
      "text": "Scene description",
      "choices": [
        {{"id":"A","text":"Choice A","next":"node_id"}},
        {{"id":"B","text":"Choice B","next":"node_id"}},
        {{"id":"C","text":"Choice C","next":"node_id"}},
        {{"id":"D","text":"Choice D","next":"node_id"}}
      ]
    }}
  }},
  "endings": [
    {{
      "id":"ending_1",
      "title":"Ending title",
      "text":"Ending description"
    }}
  ]
}}

Every next value must point to a real node or ending.
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
        return fallback_story()

    if "nodes" not in parsed:
        return fallback_story()

    if "endings" not in parsed:
        parsed["endings"] = []

    return parsed


# ============================================================
# START STORY
# ============================================================

@app.route("/story/start", methods=["POST"])
def story_start():
    story = generate_story()

    if not story:
        return jsonify({
            "error": "Unable to create story."
        }), 500

    universe = current_universe()

    start_id = story.get(
        "start",
        "start"
    )

    universe["story"] = {
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

        "current_node": start_id,

        "history": [],

        "seen_nodes": [
            start_id
        ],

        "ending": None,

        "tree": story
    }

    add_world_memory(
        f"Story started: {universe['story']['title']}"
    )

    save_data()

    return jsonify({
        "success": True,
        "story": universe["story"]
    })


# ============================================================
# STORY CHOICE
# ============================================================

@app.route("/story/choose", methods=["POST"])
def story_choose():
    body = request.get_json(
        silent=True
    ) or {}

    choice_id = clean_text(
        body.get("choice")
    ).upper()

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

        if clean_text(
            item.get("id")
        ).upper() == choice_id:

            choice = item
            break

    if not choice:
        return jsonify({
            "error": "Invalid choice."
        }), 400

    next_id = clean_text(
        choice.get("next")
    )

    story_state["history"].append({
        "node": current_id,
        "choice": choice_id,
        "choice_text": choice.get(
            "text",
            ""
        ),
        "next": next_id,
        "time": now()
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

        if item.get("id") == next_id:
            ending = item
            break

    if ending:

        story_state["ending"] = ending

        story_state["active"] = False

        add_world_memory(
            "Story ended: "
            + clean_text(
                ending.get(
                    "title",
                    "Unknown ending"
                )
            )
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

@app.route("/story/tree", methods=["GET"])
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
        ),

        "current_node": story.get(
            "current_node",
            "start"
        )
    })


# ============================================================
# STORY REPLAY
# ============================================================

@app.route("/story/replay", methods=["POST"])
def story_replay():
    story = generate_story()

    if not story:
        return jsonify({
            "error": "Unable to generate a new story."
        }), 500

    universe = current_universe()

    start_id = story.get(
        "start",
        "start"
    )

    universe["story"] = {
        "active": True,

        "story_id": random.randint(
            100000,
            999999
        ),

        "title": story.get(
            "title",
            "New Story"
        ),

        "theme": story.get(
            "theme",
            ""
        ),

        "current_node": start_id,

        "history": [],

        "seen_nodes": [
            start_id
        ],

        "ending": None,

        "tree": story
    }

    add_world_memory(
        f"Story replayed: {universe['story']['title']}"
    )

    save_data()

    return jsonify({
        "success": True,
        "story": universe["story"]
    })


# ============================================================
# IMPROVEMENT
# ============================================================

@app.route("/improvement", methods=["GET"])
def get_improvement():
    return jsonify(
        current_universe().get(
            "improvement",
            {}
        )
    )


@app.route("/improvement/learn", methods=["POST"])
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

    universe = current_universe()

    improvement = universe.setdefault(
        "improvement",
        {}
    )

    facts = improvement.setdefault(
        "facts",
        []
    )

    if lesson not in facts:
        facts.append(
            lesson
        )

    improvement["facts"] = trim_list(
        facts,
        100
    )

    save_data()

    return jsonify({
        "success": True,
        "improvement": improvement
    })


# ============================================================
# WORLD RESET
# ============================================================

@app.route("/world/reset", methods=["POST"])
def reset_world():
    global data

    old_number = data.get(
        "world_number",
        1
    )

    new_data = default_data()

    new_data["world_number"] = (
        old_number + 1
    )

    new_data["world_id"] = random.randint(
        100000,
        999999
    )

    new_data["multiverse"]["id"] = random.randint(
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

        "current_universe": data[
            "current_universe"
        ],

        "message": (
            "A completely new multiverse was created."
        )
    })


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
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

        "world": data[
            "world_number"
        ]
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
