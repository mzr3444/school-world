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

DEFAULT_MODELS = [
    "openai/gpt-oss-20b:free",
    "meta-llama/llama-3.3-8b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
    "qwen/qwen-2.5-72b-instruct:free"
]

configured_model = os.getenv("OPENROUTER_MODEL")

if configured_model:
    MODELS = [configured_model] + [
        model
        for model in DEFAULT_MODELS
        if model != configured_model
    ]
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
        "conversation": [],
        "location": "Hallway",
        "status": "Hanging around the hallway."
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
        "conversation": [],
        "location": "Library",
        "status": "Reading in the library."
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
        "conversation": [],
        "location": "Gym",
        "status": "Practicing in the gym."
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
        "conversation": [],
        "location": "Courtyard",
        "status": "Drawing in the courtyard."
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
# HELPERS
# ============================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", "")

    text = re.sub(
        r"```(?:json|python|html)?",
        "",
        text,
        flags=re.I
    )

    text = text.replace("```", "")

    return text.strip()


def trim_memory(items, limit=40):
    if len(items) <= limit:
        return items

    return items[-limit:]


def copy_defaults():
    return json.loads(
        json.dumps(DEFAULT_CHARACTERS)
    )


# ============================================================
# UNIVERSE CREATION
# ============================================================

def create_universe(number, name=None):
    if name is None:
        name = f"Earth {number}"

    characters = copy_defaults()

    return {
        "id": f"earth_{number}",
        "number": number,
        "name": name,
        "description": (
            "An alternate version of the school world."
        ),

        "characters": characters,

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
            "story_id": random.randint(
                100000,
                999999
            ),
            "title": "",
            "theme": "",
            "current_node": "start",
            "history": [],
            "seen_nodes": [],
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
        ) as file:
            json.dump(
                current_data,
                file,
                indent=2,
                ensure_ascii=False
            )

        os.replace(
            temp_file,
            DATA_FILE
        )


def repair_character(character):
    character.setdefault(
        "memory",
        []
    )

    character.setdefault(
        "conversation",
        []
    )

    character.setdefault(
        "traits",
        []
    )

    character.setdefault(
        "role",
        "Student"
    )

    character.setdefault(
        "personality",
        "Friendly and interesting."
    )

    character.setdefault(
        "description",
        ""
    )

    character.setdefault(
        "location",
        "Classroom"
    )

    character.setdefault(
        "status",
        "Going about their day."
    )

    return character


def repair_universe(universe):
    universe.setdefault(
        "description",
        "An alternate version of the school world."
    )

    universe.setdefault(
        "characters",
        copy_defaults()
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
        True
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
            "seen_nodes": [],
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

    for character in universe["characters"]:
        repair_character(character)

    return universe


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
        ) as file:
            loaded = json.load(file)

        # ----------------------------------------------------
        # Upgrade old single-world format.
        # ----------------------------------------------------

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

            upgraded["universes"][
                "earth_1"
            ] = earth

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
            {
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
        )

        for universe in loaded["universes"].values():
            repair_universe(universe)

        return loaded

    except Exception as error:
        print(
            "Data load failed:",
            error
        )

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

    universe = data["universes"][universe_id]

    repair_universe(universe)

    return universe


def find_character(character_id):
    universe = current_universe()

    for character in universe["characters"]:
        if character["id"] == character_id:
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

    universe["world_memory"].append(
        text
    )

    universe["world_memory"] = trim_memory(
        universe["world_memory"],
        80
    )


def add_improvement(text):
    universe = current_universe()

    text = clean_text(text)

    if not text:
        return

    improvements = universe.setdefault(
        "improvement",
        {}
    )

    facts = improvements.setdefault(
        "facts",
        []
    )

    if text not in facts:
        facts.append(text)

    improvements["facts"] = trim_memory(
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

            result = response.choices[
                0
            ].message.content

            if result:
                return clean_text(result)

        except Exception as error:
            errors.append(
                f"{model}: {str(error)}"
            )

            continue

    return (
        "AI_ERROR: All configured models failed. "
        + " | ".join(errors)
    )


def safe_json_from_ai(text):
    text = clean_text(text)

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if (
        start != -1
        and end != -1
        and end > start
    ):
        try:
            return json.loads(
                text[start:end + 1]
            )
        except Exception:
            pass

    return None


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET", "HEAD"])
def home():
    return render_template(
        "index.html"
    )


# ============================================================
# WORLD
# ============================================================

@app.route("/world", methods=["GET"])
def get_world():
    universe = current_universe()

    return jsonify({
        "world_id": data["world_id"],
        "world_number": data["world_number"],
        "current_universe": data["current_universe"],
        "universe": universe,
        "multiverse": data["multiverse"]
    })


# ============================================================
# CHAT
# ============================================================

@app.route("/chat", methods=["POST"])
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
                "are required."
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
        messages.append({
            "role": item["role"],
            "content": item["content"]
        })

    messages.append({
        "role": "user",
        "content": message
    })

    other_characters = [
        {
            "name": c["name"],
            "role": c["role"],
            "personality": c["personality"],
            "location": c.get(
                "location",
                "Unknown"
            ),
            "status": c.get(
                "status",
                ""
            )
        }
        for c in universe["characters"]
        if c["id"] != character["id"]
    ]

    system_prompt = f"""
You are {character["name"]}, a real person inside a
living school simulation.

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

YOUR CURRENT LOCATION:
{character.get("location", "Unknown")}

YOUR CURRENT STATUS:
{character.get("status", "")}

PLAYER LOCATION:
{universe["player_location"]}

CHARACTER MEMORY:
{json.dumps(character.get("memory", [])[-30:], ensure_ascii=False)}

WORLD MEMORY:
{json.dumps(universe.get("world_memory", [])[-30:], ensure_ascii=False)}

OTHER CHARACTERS:
{json.dumps(other_characters, ensure_ascii=False)}

IMPORTANT RULES:

1. Stay completely in character.
2. Remember important previous conversations.
3. Give natural medium-length responses.
4. Do not constantly agree with the player.
5. Have your own opinions and emotions.
6. Never control the player's actions.
7. Do not automatically follow the player.
8. Characters have their own locations and lives.
9. If the player travels somewhere, do not pretend you
   traveled with them unless the story specifically says so.
10. You know the school and its locations.
11. You may talk about other students.
12. You may disagree, joke, gossip, become curious,
    annoyed, excited, suspicious, or surprised.
13. Do not describe yourself as an AI or chatbot.
14. This is {universe["name"]}.
15. Alternate universes exist, but do not constantly
    bring them up.
16. React naturally to recent world events when relevant.
17. Do not make every conversation dramatic.
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
        "time": now_iso()
    })

    character["conversation"].append({
        "role": "assistant",
        "content": answer,
        "time": now_iso()
    })

    character["conversation"] = trim_memory(
        character["conversation"],
        80
    )

    if len(message) > 20:
        add_improvement(
            "Player communication pattern: "
            + message[:180]
        )

    save_data()

    return jsonify({
        "reply": answer,
        "character": character,
        "universe": universe["name"],
        "location": universe["player_location"]
    })


# ============================================================
# RESET CONVERSATION
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


@app.route(
    "/conversation/new",
    methods=["POST"]
)
def new_text():
    return jsonify({
        "success": True
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
            or f"{name} is a {role.lower()}."
        ),
        "traits": [
            clean_text(x)
            for x in traits
            if clean_text(x)
        ],
        "memory": [],
        "conversation": [],
        "location": random.choice(
            DEFAULT_LOCATIONS
        ),
        "status": (
            "Getting settled into "
            "the school."
        )
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
# TRAVEL INSIDE SCHOOL
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
        f"Player traveled from "
        f"{old_location} to {location}."
    )

    save_data()

    return jsonify({
        "success": True,
        "location": location
    })


# ============================================================
# BACKGROUND WORLD ACTIVITY
# ============================================================

def generate_background_event():
    universe = current_universe()

    if len(universe["characters"]) < 2:
        return None

    first, second = random.sample(
        universe["characters"],
        2
    )

    location = random.choice(
        universe["locations"]
    )

    system_prompt = f"""
Generate a natural background school interaction.

UNIVERSE:
{universe["name"]}

CHARACTER A:
Name: {first["name"]}
Personality: {first["personality"]}
Current location: {first.get("location", "Unknown")}

CHARACTER B:
Name: {second["name"]}
Personality: {second["personality"]}
Current location: {second.get("location", "Unknown")}

LOCATION OF EVENT:
{location}

Generate something that could naturally happen
during a normal school day.

Possible events:
- joking
- studying
- gossip
- disagreement
- helping
- competition
- awkward moment
- lunch
- class
- club activity
- discovering something
- talking about another student
- ordinary school behavior

Do not make every event dramatic.

Return ONLY JSON:

{{
    "summary": "short event description",
    "reaction_a": "how character A feels",
    "reaction_b": "how character B feels"
}}
"""

    response = call_ai(
        system_prompt,
        [],
        temperature=0.95,
        max_tokens=400
    )

    parsed = safe_json_from_ai(
        response
    )

    if not parsed:
        parsed = {
            "summary": (
                f"{first['name']} and "
                f"{second['name']} had a "
                f"normal conversation."
            ),
            "reaction_a": "They seem fine.",
            "reaction_b": "They seem fine."
        }

    event = {
        "id": random.randint(
            100000,
            999999
        ),
        "type": "background",
        "characters": [
            first["name"],
            second["name"]
        ],
        "character_ids": [
            first["id"],
            second["id"]
        ],
        "location": location,
        "event": clean_text(
            parsed.get(
                "summary",
                ""
            )
        ),
        "time": now_iso()
    }

    universe["background_events"].append(
        event
    )

    universe["background_events"] = trim_memory(
        universe["background_events"],
        60
    )

    remember(
        first,
        (
            f"{second['name']} and I "
            f"interacted at {location}: "
            f"{event['event']}"
        )
    )

    remember(
        second,
        (
            f"I interacted with "
            f"{first['name']} at {location}: "
            f"{event['event']}"
        )
    )

    add_world_memory(
        f"{first['name']} and "
        f"{second['name']} interacted "
        f"at {location}."
    )

    save_data()

    return event


@app.route(
    "/world/advance",
    methods=["POST"]
)
def world_advance():
    event = generate_background_event()

    if not event:
        return jsonify({
            "error": (
                "There are not enough "
                "characters."
            )
        }), 400

    return jsonify({
        "success": True,
        "event": event
    })


# ============================================================
# CHARACTER REACTION TO WORLD EVENT
# ============================================================

@app.route(
    "/world/react",
    methods=["POST"]
)
def world_react():
    body = request.get_json(
        silent=True
    ) or {}

    event_text = clean_text(
        body.get("event")
    )

    if not event_text:
        return jsonify({
            "error": "Event is required."
        }), 400

    universe = current_universe()

    reactions = []

    for character in universe["characters"]:
        system_prompt = f"""
You are {character["name"]}.

Personality:
{character["personality"]}

Traits:
{", ".join(character.get("traits", []))}

Location:
{character.get("location", "Unknown")}

A school event just happened:

{event_text}

Give a short natural reaction from this character.

Do not control the player.

Return ONLY the character's reaction.
"""

        reaction = call_ai(
            system_prompt,
            [],
            temperature=0.9,
            max_tokens=180
        )

        if reaction.startswith(
            "AI_ERROR:"
        ):
            continue

        remember(
            character,
            (
                f"I experienced this "
                f"world event: {event_text}. "
                f"My reaction: {reaction}"
            )
        )

        reactions.append({
            "character_id": character["id"],
            "name": character["name"],
            "reaction": reaction
        })

    save_data()

    return jsonify({
        "success": True,
        "reactions": reactions
    })


# ============================================================
# MULTIVERSE EVENT
# ============================================================

MULTIVERSE_EVENT_TYPES = [
    "A strange reflection briefly shows another Earth.",
    "A character receives a message from someone who should not exist.",
    "A classroom object suddenly changes into a different version.",
    "A hallway briefly looks different before returning to normal.",
    "A student remembers an event that never happened.",
    "A mysterious symbol appears somewhere in the school.",
    "A portal-like distortion appears for a few seconds.",
    "A familiar student behaves as if they came from another Earth.",
    "Two versions of the same object appear at once.",
    "A strange sound seems to come from another universe."
]


def generate_multiversal_event():
    universe = current_universe()

    event_type = random.choice(
        MULTIVERSE_EVENT_TYPES
    )

    known = data["multiverse"].get(
        "discovered_universes",
        ["earth_1"]
    )

    prompt = f"""
Generate a mysterious multiverse event.

CURRENT UNIVERSE:
{universe["name"]}

CURRENT LOCATION:
{universe["player_location"]}

EVENT TYPE:
{event_type}

KNOWN UNIVERSES:
{known}

The event should feel mysterious.

Do not explain everything immediately.

Return ONLY JSON:

{{
    "title": "event title",
    "description": "what happens",
    "hint": "a clue about another universe",
    "portal_available": false,
    "target_universe": null
}}

If a portal is available, target_universe must be
an integer.
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

    if not parsed:
        parsed = {
            "title": "A Strange Distortion",
            "description": event_type,
            "hint": (
                "Something about this world "
                "feels different."
            ),
            "portal_available": False,
            "target_universe": None
        }

    event = {
        "id": random.randint(
            100000,
            999999
        ),
        "type": "multiverse",
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
        "hint": clean_text(
            parsed.get(
                "hint",
                ""
            )
        ),
        "portal_available": bool(
            parsed.get(
                "portal_available",
                False
            )
        ),
        "target_universe": parsed.get(
            "target_universe"
        ),
        "time": now_iso()
    }

    universe["events"].append(
        event
    )

    universe["events"] = trim_memory(
        universe["events"],
        60
    )

    if event["hint"]:
        universe["hints"].append(
            event["hint"]
        )

        universe["hints"] = trim_memory(
            universe["hints"],
            40
        )

        data["multiverse"][
            "global_hints"
        ].append({
            "universe": universe["name"],
            "hint": event["hint"],
            "time": now_iso()
        })

        data["multiverse"][
            "global_hints"
        ] = trim_memory(
            data["multiverse"][
                "global_hints"
            ],
            100
        )

    data["multiverse"]["events"].append(
        event
    )

    data["multiverse"]["events"] = trim_memory(
        data["multiverse"]["events"],
        120
    )

    save_data()

    return event


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
# CREATE UNIVERSE
# ============================================================

@app.route(
    "/multiverse/create",
    methods=["POST"]
)
def create_universe_route():
    body = request.get_json(
        silent=True
    ) or {}

    requested_number = body.get(
        "number"
    )

    existing_numbers = [
        universe["number"]
        for universe in data["universes"].values()
    ]

    if requested_number:
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
            ) + 1
        )

    if requested_number < 1:
        requested_number = 1

    universe_id = (
        f"earth_{requested_number}"
    )

    if universe_id in data["universes"]:
        return jsonify({
            "success": True,
            "already_exists": True,
            "universe": data["universes"][
                universe_id
            ]
        })

    universe = create_universe(
        requested_number,
        f"Earth {requested_number}"
    )

    universe["description"] = random.choice([
        "A world where the school developed differently.",
        "A world where different students became friends.",
        "A world where the school has a strange history.",
        "A world where ordinary events often become unusual.",
        "A world almost identical to Earth 1 except for small details.",
        "A world where one major event changed the school's future."
    ])

    # Give the new universe small differences.
    random.shuffle(
        universe["characters"]
    )

    for character in universe["characters"]:
        character["memory"] = []
        character["conversation"] = []
        character["location"] = random.choice(
            universe["locations"]
        )

    universe["discovered"] = True
    universe["visited"] = False

    data["universes"][
        universe_id
    ] = universe

    if universe_id not in data["multiverse"][
        "discovered_universes"
    ]:
        data["multiverse"][
            "discovered_universes"
        ].append(
            universe_id
        )

    save_data()

    return jsonify({
        "success": True,
        "universe": universe
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

    for universe in data["universes"].values():
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
            "player_location": universe.get(
                "player_location",
                "Classroom"
            ),
            "character_count": len(
                universe.get(
                    "characters",
                    []
                )
            ),
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
        key=lambda item: item["number"]
    )

    return jsonify({
        "current_universe": data[
            "current_universe"
        ],
        "universes": universes,
        "events": data["multiverse"][
            "events"
        ][-30:],
        "global_hints": data["multiverse"][
            "global_hints"
        ][-50:],
        "portal_history": data["multiverse"][
            "portal_history"
        ][-30:]
    })


# ============================================================
# TRAVEL BETWEEN UNIVERSES
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

    if target not in data["universes"]:
        return jsonify({
            "error": (
                "That universe has "
                "not been discovered."
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
                "That universe has "
                "not been discovered yet."
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

    data[
        "current_universe"
    ] = target

    target_universe["visited"] = True

    if target not in data[
        "multiverse"
    ]["visited_universes"]:
        data[
            "multiverse"
        ]["visited_universes"].append(
            target
        )

    data[
        "multiverse"
    ]["portal_history"].append({
        "from": old,
        "to": target,
        "time": now_iso()
    })

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

    connection_back = {
        "from": target,
        "to": old
    }

    if connection_back not in target_universe[
        "connections"
    ]:
        target_universe[
            "connections"
        ].append(
            connection_back
        )

    add_world_memory(
        f"Player arrived from another universe: "
        f"{target_universe['name']}."
    )

    save_data()

    return jsonify({
        "success": True,
        "from": old,
        "to": target,
        "universe": target_universe
    })


# ============================================================
# STORY GENERATION
# ============================================================

STORY_THEMES = [
    "A mysterious event happens at school.",
    "A strange discovery changes an ordinary school day.",
    "A friendship begins to fall apart.",
    "A hidden secret about the school is discovered.",
    "A competition becomes much more serious than expected.",
    "An ordinary day slowly becomes unexpected.",
    "A strange object is discovered inside the school.",
    "A school event goes completely wrong.",
    "A rumor spreads through the school.",
    "A multiversal mystery begins inside an ordinary classroom."
]


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
{json.dumps([
    {
        "name": c["name"],
        "role": c["role"],
        "personality": c["personality"]
    }
    for c in universe["characters"]
], ensure_ascii=False)}

Requirements:

- 5 major endings minimum.
- 15-24 meaningful story nodes.
- Choices must actually change future events.
- Choices affect relationships, information,
  locations, opportunities, and decisions.
- Some branches remain separate.
- Some choices lock or unlock later choices.
- Exactly four choices at every non-ending node.
- Choices are A, B, C, D.
- Include ordinary school moments.
- Characters behave according to personality.
- The story feels continuous.
- Every story is different.
- Do not reveal the correct ending.
- Do not copy copyrighted game plots.

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
                "Check your API key, credits, "
                "and available models."
            )
        }), 500

    universe = current_universe()

    start_id = story.get(
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
        "current_node": start_id,
        "history": [],
        "seen_nodes": [
            start_id
        ],
        "ending": None,
        "tree": story
    }

    universe["story"] = data_story

    add_world_memory(
        "Story started: "
        + data_story["title"]
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
    ).upper()

    universe = current_universe()
    story_state = universe["story"]

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

    story_state["history"].append({
        "node": current_id,
        "choice": choice_id,
        "choice_text": choice.get(
            "text",
            ""
        ),
        "next": next_id,
        "time": now_iso()
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
            "Story ended: "
            + ending.get(
                "title",
                "Unknown ending"
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
        "tree"
    )

    if not tree:
        return jsonify({
            "error": (
                "There is no story "
                "to replay."
            )
        }), 400

    start_id = tree.get(
        "start",
        "start"
    )

    universe["story"] = {
        "active": True,
        "story_id": random.randint(
            100000,
            999999
        ),
        "title": old_story.get(
            "title",
            tree.get(
                "title",
                "Story Mode"
            )
        ),
        "theme": old_story.get(
            "theme",
            tree.get(
                "theme",
                ""
            )
        ),
        "current_node": start_id,
        "history": [],
        "seen_nodes": [
            start_id
        ],
        "ending": None,
        "tree": tree
    }

    save_data()

    return jsonify({
        "success": True,
        "story": universe["story"]
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
# IMPROVEMENT
# ============================================================

@app.route(
    "/improvement",
    methods=["GET"]
)
def get_improvement():
    return jsonify(
        current_universe()[
            "improvement"
        ]
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
        "improvement": current_universe()[
            "improvement"
        ]
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
        "message": (
            "A completely new multiverse "
            "was created."
        )
    })


# ============================================================
# HEALTH
# ============================================================

@app.route(
    "/health",
    methods=["GET"]
)
def health():
    return jsonify({
        "status": "ok",
        "ai_configured": bool(API_KEY),
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
