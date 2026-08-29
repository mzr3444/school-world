import os
import json
import random
import re
import threading
from datetime import datetime

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

# You can override this with:
#
# OPENROUTER_MODEL="your/model"
#
# The important part is that the model slug must currently
# exist on OpenRouter and support your account.
#
# We intentionally removed the broken old :free models.
DEFAULT_MODELS = [
    "openai/gpt-oss-20b",
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
            "Sam spends a lot of time drawing, reading, "
            "and observing the school."
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
    "Front Office"
]


# ============================================================
# UNIVERSE THEMES
# ============================================================

UNIVERSE_THEMES = [
    {
        "name": "The Almost Normal Earth",
        "description": (
            "This universe looks almost exactly like Earth 1, "
            "but tiny details seem wrong."
        )
    },

    {
        "name": "The Future Earth",
        "description": (
            "The school exists in a futuristic version "
            "of the world. Technology is everywhere."
        )
    },

    {
        "name": "The Strange School",
        "description": (
            "The school looks normal from outside, "
            "but strange things happen inside."
        )
    },

    {
        "name": "The Opposite Earth",
        "description": (
            "Many familiar people have personalities "
            "that are almost completely opposite."
        )
    },

    {
        "name": "The Abandoned Earth",
        "description": (
            "The school appears to have been abandoned, "
            "but signs suggest someone is still there."
        )
    },

    {
        "name": "The Perfect Earth",
        "description": (
            "Everything at this school seems perfect. "
            "Almost too perfect."
        )
    },

    {
        "name": "The Glitched Earth",
        "description": (
            "Reality occasionally behaves incorrectly. "
            "Objects, rooms, and memories can change."
        )
    },

    {
        "name": "The Hidden Earth",
        "description": (
            "This universe contains clues suggesting "
            "someone has been secretly observing other dimensions."
        )
    }
]


# ============================================================
# CREATE UNIVERSE
# ============================================================

def create_universe(number, name=None):

    if name is None:
        name = f"Earth {number}"

    if number == 1:
        description = (
            "The original school universe. "
            "Everything appears normal."
        )
    else:
        theme = random.choice(UNIVERSE_THEMES)
        description = theme["description"]

    return {
        "id": f"earth_{number}",
        "number": number,
        "name": name,
        "description": description,

        "characters": json.loads(
            json.dumps(DEFAULT_CHARACTERS)
        ),

        "locations": list(DEFAULT_LOCATIONS),

        "player_location": "Classroom",

        "world_memory": [],

        "background_events": [],

        "events": [],

        "hints": [],

        "connections": [],

        "discovered": number == 1,

        "visited": number == 1,

        "dimension_stability": random.randint(
            60,
            100
        ),

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
        # Upgrade older save files
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

            loaded["universes"][
                "earth_1"
            ] = create_universe(
                1,
                "Earth 1"
            )

        loaded.setdefault(
            "multiverse",
            {}
        )

        loaded["multiverse"].setdefault(
            "id",
            random.randint(
                100000,
                999999
            )
        )

        loaded["multiverse"].setdefault(
            "discovered_universes",
            ["earth_1"]
        )

        loaded["multiverse"].setdefault(
            "visited_universes",
            ["earth_1"]
        )

        loaded["multiverse"].setdefault(
            "events",
            []
        )

        loaded["multiverse"].setdefault(
            "global_hints",
            []
        )

        loaded["multiverse"].setdefault(
            "portal_history",
            []
        )

        # Upgrade each universe.
        for universe in loaded["universes"].values():

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
                "dimension_stability",
                random.randint(
                    60,
                    100
                )
            )

            universe.setdefault(
                "discovered",
                False
            )

            universe.setdefault(
                "visited",
                False
            )

        return loaded

    except Exception as e:

        print(
            "SAVE FILE ERROR:",
            e
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

    return data["universes"][universe_id]


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text)

    text = text.replace(
        "\x00",
        ""
    )

    text = re.sub(
        r"```(?:json|python|html)?",
        "",
        text,
        flags=re.I
    )

    text = text.replace(
        "```",
        ""
    )

    return text.strip()


def trim_memory(
    items,
    limit=40
):

    if len(items) <= limit:
        return items

    return items[-limit:]


# ============================================================
# CHARACTER HELPERS
# ============================================================

def find_character(character_id):

    universe = current_universe()

    for character in universe["characters"]:

        if character["id"] == character_id:
            return character

    return None


def remember(
    character,
    text
):

    text = clean_text(text)

    if not text:
        return

    character.setdefault(
        "memory",
        []
    )

    character["memory"].append(
        text
    )

    character["memory"] = trim_memory(
        character["memory"],
        40
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
        60
    )


def add_improvement(text):

    universe = current_universe()

    text = clean_text(text)

    if not text:
        return

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
            "AI_ERROR: "
            "OPENROUTER_API_KEY is not configured."
        )

    errors = []

    for model in MODELS:

        try:

            print(
                f"Trying AI model: {model}"
            )

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

            result = (
                response
                .choices[0]
                .message
                .content
            )

            if result:

                return clean_text(
                    result
                )

        except Exception as e:

            error = str(e)

            print(
                f"Model failed: {model}"
            )

            print(error)

            errors.append(
                f"{model}: {error}"
            )

    return (
        "AI_ERROR: All configured models failed. "
        + " | ".join(errors)
    )


# ============================================================
# JSON AI PARSER
# ============================================================

def safe_json_from_ai(text):

    text = clean_text(text)

    try:

        return json.loads(
            text
        )

    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if (
        start != -1
        and end != -1
        and end > start )
   
