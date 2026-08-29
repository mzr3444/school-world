````python
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

API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")

DEFAULT_MODELS = [
    "openai/gpt-oss-20b:free",
    "meta-llama/llama-3.3-8b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
    "qwen/qwen-2.5-72b-instruct:free"
]

configured_model = os.getenv("OPENROUTER_MODEL")

if configured_model:
    MODELS = [configured_model] + [
        m for m in DEFAULT_MODELS
        if m != configured_model
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
        "personality": "Friendly, curious, funny, energetic, and sometimes impulsive.",
        "description": "Alex likes meeting people and turning boring situations into something interesting.",
        "traits": ["Friendly", "Curious", "Funny", "Impulsive"],
        "memory": [],
        "conversation": []
    },
    {
        "id": "maya",
        "name": "Maya",
        "role": "Student",
        "personality": "Intelligent, calm, observant, sarcastic, and independent.",
        "description": "Maya notices details other people miss and thinks before she speaks.",
        "traits": ["Smart", "Calm", "Observant", "Sarcastic"],
        "memory": [],
        "conversation": []
    },
    {
        "id": "jordan",
        "name": "Jordan",
        "role": "Student",
        "personality": "Confident, competitive, outgoing, playful, and occasionally stubborn.",
        "description": "Jordan loves competition and enjoys challenging people.",
        "traits": ["Confident", "Competitive", "Outgoing", "Stubborn"],
        "memory": [],
        "conversation": []
    },
    {
        "id": "sam",
        "name": "Sam",
        "role": "Student",
        "personality": "Quiet, creative, thoughtful, kind, and slightly mysterious.",
        "description": "Sam spends a lot of time drawing, reading, and observing the school.",
        "traits": ["Creative", "Quiet", "Kind", "Thoughtful"],
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
    "A world almost identical to Earth 1, except small details keep changing.",
    "A world where the school developed a strange history.",
    "A world where different students became friends.",
    "A world where ordinary school events frequently become unusual.",
    "A world where one major event changed the school's future.",
    "A world where the school has secrets that nobody on Earth 1 knows about.",
    "A world where familiar people remember things that never happened.",
    "A world where the school seems normal during the day but strange things happen after hours."
]


DIMENSION_HINTS = [
    "A classroom clock is showing a time that does not exist.",
    "Someone remembers seeing you before you arrived in this universe.",
    "A familiar student seems to know something about another Earth.",
    "A strange symbol keeps appearing in different locations.",
    "A reflection briefly shows a different version of the school.",
    "A school announcement mentions a student nobody remembers.",
    "A book contains a map of a school that looks almost identical to this one.",
    "A hallway briefly changes before returning to normal.",
    "Someone claims they have already visited another dimension.",
    "A strange object appears in two places at once."
]


# ============================================================
# UNIVERSE CREATION
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
# STORAGE
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
                "story",
                "improvement",
                "events",
                "hints",
                "connections"
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

        # Upgrade every universe.
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
                universe["number"] == 1
            )

            universe.setdefault(
                "visited",
                universe["number"] == 1
            )

            universe.setdefault(
                "story",
                {
                    "active": False,
                    "story_id": random.randint(100000, 999999),
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
# HELPERS
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


def add_hint(
    universe,
    hint
):

    hint = clean_text(hint)

    if not hint:
        return

    universe.setdefault(
        "hints",
        []
    )

    if hint not in universe["hints"]:

        universe["hints"].append(
            hint
        )

    universe["hints"] = trim_memory(
        universe["hints"],
        40
    )

    data["multiverse"].setdefault(
        "global_hints",
        []
    )

    data["multiverse"]["global_hints"].append({
        "universe": universe["name"],
        "hint": hint,
        "time": datetime.utcnow().isoformat()
    })

    data["multiverse"]["global_hints"] = trim_memory(
        data["multiverse"]["global_hints"],
        100
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

            result = response.choices[0].message.content

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


def safe_json_from_ai(text):

    text = clean_text(text)

    try:
        return json.loads(text)

    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:

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

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# WORLD
# ============================================================

@app.route("/world")
def get_world():

    universe = current_universe()

    return jsonify({

        "world_id":
            data["world_id"],

        "world_number":
            data["world_number"],

        "current_universe":
            data["current_universe"],

        # IMPORTANT:
        # These are returned directly so the frontend
        # can actually see them.

        "universe":
            universe,

        "characters":
            universe["characters"],

        "locations":
            universe["locations"],

        "location":
            universe["player_location"],

        "background_events":
            universe["background_events"][-20:],

        "events":
            universe["events"][-20:],

        "hints":
            universe["hints"][-20:],

        "multiverse":
            data["multiverse"]
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
            "error":
                "character_id and message are required"
        }), 400

    character = find_character(
        character_id
    )

    if not character:

        return jsonify({
            "error":
                "Character not found"
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
            "role":
                item["role"],

            "content":
                item["content"]
        })

    messages.append({
        "role":
            "user",

        "content":
            message
    })

    other_characters = [

        {
            "name":
                c["name"],

            "role":
                c["role"],

            "personality":
                c["personality"]
        }

        for c in universe["characters"]

        if c["id"] != character["id"]
    ]

    system_prompt = f"""
You are {character["name"]}, a person inside a living school simulation.

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

PLAYER LOCATION:
{universe["player_location"]}

CHARACTER MEMORY:
{json.dumps(character.get("memory", [])[-25:], ensure_ascii=False)}

WORLD MEMORY:
{json.dumps(universe.get("world_memory", [])[-25:], ensure_ascii=False)}

RECENT MULTIVERSAL HINTS:
{json.dumps(universe.get("hints", [])[-10:], ensure_ascii=False)}

OTHER CHARACTERS:
{json.dumps(other_characters, ensure_ascii=False)}

RULES:

1. Stay completely in character.
2. Remember important previous conversations.
3. Give natural medium-length responses.
4. Do not constantly agree with the player.
5. Have your own opinions.
6. Never control the player's actions.
7. Do not automatically follow the player.
8. Do not randomly mention the multiverse.
9. If the player asks about strange events, react naturally.
10. Characters can notice and discuss events.
11. Characters can disagree with each other.
12. Characters can form friendships and rivalries.
13. Do not describe yourself as an AI.
14. The school is a living world.
15. This universe may be different from other universes.
16. Do not reveal every mystery immediately.
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
            "error":
                answer
        }), 500

    character.setdefault(
        "conversation",
        []
    )

    character["conversation"].append({

        "role":
            "user",

        "content":
            message,

        "time":
            datetime.utcnow().isoformat()
    })

    character["conversation"].append({

        "role":
            "assistant",

        "content":
            answer,

        "time":
            datetime.utcnow().isoformat()
    })

    character["conversation"] = trim_memory(
        character["conversation"],
        70
    )

    if len(message) > 20:

        add_improvement(
            f"Player communication pattern: {message[:180]}"
        )

    save_data()

    return jsonify({

        "reply":
            answer,

        "character":
            character,

        "universe":
            universe["name"],

        "location":
            universe["player_location"]
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
            "error":
                "Character not found"
        }), 404

    character["conversation"] = []

    save_data()

    return jsonify({
        "success":
            True
    })


@app.route(
    "/conversation/new",
    methods=["POST"]
)
def new_text():

    return jsonify({
        "success":
            True
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
            "error":
                "Character name is required."
        }), 400

    if not personality:

        return jsonify({
            "error":
                "Character personality is required."
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

        "id":
            character_id,

        "name":
            name,

        "role":
            role,

        "personality":
            personality,

        "description":
            description or
            f"{name} is a {role.lower()} at the school.",

        "traits":
            [
                clean_text(x)
                for x in traits
                if clean_text(x)
            ],

        "memory":
            [],

        "conversation":
            []
    }

    universe = current_universe()

    universe["characters"].append(
        character
    )

    save_data()

    return jsonify({

        "success":
            True,

        "character":
            character
    })


# ============================================================
# SCHOOL TRAVEL
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
            "error":
                "Unknown location."
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

        "success":
            True,

        "location":
            location,

        "universe":
            universe["name"]
    })


# ============================================================
# BACKGROUND EVENTS
# ============================================================

@app.route(
    "/world/advance",
    methods=["POST"]
)
def world_advance():

    universe = current_universe()

    if len(universe["characters"]) < 2:

        return jsonify({
            "event":
                "There are not enough characters."
        })

    first, second = random.sample(
        universe["characters"],
        2
    )

    location = random.choice(
        universe["locations"]
    )

    system_prompt = f"""
Generate a natural background interaction.

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

Create a school interaction.

It could involve:
- joking
- studying
- gossip
- disagreement
- helping
- competition
- friendship
- an ordinary school moment

Do not make every event dramatic.

Write 3-7 sentences.
"""

    event = call_ai(
        system_prompt,
        [],
        temperature=0.9,
        max_tokens=350
    )

    if event.startswith(
        "AI_ERROR:"
    ):

        return jsonify({
            "error":
                event
        }), 500

    background = {

        "characters":
            [
                first["name"],
                second["name"]
            ],

        "location":
            location,

        "event":
            event,

        "time":
            datetime.utcnow().isoformat()
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
        f"{second['name']} and I interacted at {location}: {event[:180]}"
    )

    remember(
        second,
        f"I interacted with {first['name']} at {location}: {event[:180]}"
    )

    add_world_memory(
        f"{first['name']} and {second['name']} interacted at {location}."
    )

    save_data()

    return jsonify({

        "success":
            True,

        "event":
            background
    })


# ============================================================
# MULTIVERSE EVENT
# ============================================================

def generate_multiversal_event():

    universe = current_universe()

    event_type = random.choice(
        [
            "A reflection shows another Earth.",
            "A student receives a message from another universe.",
            "A classroom object changes into an alternate version.",
            "A hallway briefly changes.",
            "A student remembers something that never happened.",
            "A mysterious symbol appears.",
            "A portal distortion appears.",
            "Someone seems to have memories from another Earth.",
            "Two versions of the same object appear.",
            "A strange sound comes from another universe."
        ]
    )

    prompt = f"""
Create a mysterious multiversal event.

CURRENT UNIVERSE:
{universe["name"]}

CURRENT LOCATION:
{universe["player_location"]}

EVENT TYPE:
{event_type}

KNOWN UNIVERSES:
{json.dumps(data["multiverse"]["discovered_universes"])}

CHARACTERS:
{json.dumps([
    {
        "name": c["name"],
        "personality": c["personality"]
    }
    for c in universe["characters"]
], ensure_ascii=False)}

Return ONLY JSON.

{{
    "title": "short title",
    "description": "what happens",
    "hint": "small clue toward another dimension",
    "portal_available": false,
    "target_universe": null
}}

Rules:

- Keep the mystery interesting.
- Do not explain everything.
- The player should be able to investigate.
- Sometimes a portal should become available.
- A portal should NOT appear every time.
- target_universe must be an integer if portal_available is true.
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

            "title":
                "A Strange Distortion",

            "description":
                event_type,

            "hint":
                random.choice(
                    DIMENSION_HINTS
                ),

            "portal_available":
                random.random() < 0.2,

            "target_universe":
                None
        }

    portal_available = bool(
        parsed.get(
            "portal_available",
            False
        )
    )

    target = parsed.get(
        "target_universe"
    )

    # If AI says portal but no target exists,
    # create a new dimension automatically.

    if portal_available:

        if not isinstance(
            target,
            int
        ):

            existing_numbers = [
                u["number"]
                for u in data["universes"].values()
            ]

            target = max(
                existing_numbers,
                default=1
            ) + 1

            create_dimension(
                target
            )

        elif f"earth_{target}" not in data["universes"]:

            create_dimension(
                target
            )

    event = {

        "id":
            random.randint(
                100000,
                999999
            ),

        "universe":
            universe["name"],

        "universe_id":
            universe["id"],

        "location":
            universe["player_location"],

        "title":
            clean_text(
                parsed.get(
                    "title",
                    "Multiversal Event"
                )
            ),

        "description":
            clean_text(
                parsed.get(
                    "description",
                    event_type
                )
            ),

        "hint":
            clean_text(
                parsed.get(
                    "hint",
                    random.choice(
                        DIMENSION_HINTS
                    )
                )
            ),

        "portal_available":
            portal_available,

        "target_universe":
            target if portal_available else None,

        "time":
            datetime.utcnow().isoformat()
    }

    universe["events"].append(
        event
    )

    universe["events"] = trim_memory(
        universe["events"],
        50
    )

    if event["hint"]:

        add_hint(
            universe,
            event["hint"]
        )

    data["multiverse"]["events"].append(
        event
    )

    data["multiverse"]["events"] = trim_memory(
        data["multiverse"]["events"],
        100
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

        "success":
            True,

        "event":
            event
    })


# ============================================================
# CREATE DIMENSION
# ============================================================

def create_dimension(number):

    universe_id = f"earth_{number}"

    if universe_id in data["universes"]:

        return data["universes"][universe_id]

    universe = create_universe(
        number,
        f"Earth {number}"
    )

    universe["description"] = random.choice(
        DIMENSION_DESCRIPTIONS
    )

    # Every dimension begins with at least one mystery.
    add_hint(
        universe,
        random.choice(
            DIMENSION_HINTS
        )
    )

    universe["discovered"] = True

    data["universes"][universe_id] = universe

    if universe_id not in data["multiverse"]["discovered_universes"]:

        data["multiverse"][
            "discovered_universes"
        ].append(
            universe_id
        )

    return universe


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

        u["number"]

        for u in data["universes"].values()
    ]

    if requested_number:

        try:

            requested_number = int(
                requested_number
            )

        except Exception:

            requested_number = None

    if not requested_number:

        requested_number = max(
            existing_numbers,
            default=0
        ) + 1

    universe_id = f"earth_{requested_number}"

    if universe_id in data["universes"]:

        return jsonify({

            "success":
                True,

            "universe":
                data["universes"][universe_id],

            "already_exists":
                True
        })

    universe = create_dimension(
        requested_number
    )

    save_data()

    return jsonify({

        "success":
            True,

        "universe":
            universe
    })


# ============================================================
# MULTIVERSE MAP
# ============================================================

@app.route(
    "/multiverse"
)
def get_multiverse():

    universes = []

    for universe in data["universes"].values():

        universes.append({

            "id":
                universe["id"],

            "number":
                universe["number"],

            "name":
                universe["name"],

            "description":
                universe.get(
                    "description",
                    ""
                ),

            "discovered":
                universe.get(
                    "discovered",
                    False
                ),

            "visited":
                universe.get(
                    "visited",
                    False
                ),

            "hints":
                universe.get(
                    "hints",
                    []
                )[-10:],

            "connections":
                universe.get(
                    "connections",
                    []
                )
        })

    universes.sort(
        key=lambda x: x["number"]
    )

    return jsonify({

        "current_universe":
            data["current_universe"],

        "universes":
            universes,

        "events":
            data["multiverse"]["events"][-30:],

        "global_hints":
            data["multiverse"]["global_hints"][-50:],

        "portal_history":
            data["multiverse"]["portal_history"][-30:]
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

    if target not in data["universes"]:

        return jsonify({

            "error":
                "That dimension has not been discovered."
        }), 404

    target_universe = data[
        "universes"
    ][target]

    if not target_universe.get(
        "discovered",
        False
    ):

        return jsonify({

            "error":
                "That dimension has not been discovered yet."
        }), 403

    old = data[
        "current_universe"
    ]

    if old == target:

        return jsonify({

            "success":
                True,

            "message":
                "You are already there.",

            "universe":
                target_universe
        })

    old_universe = data[
        "universes"
    ].get(old)

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

    portal_record = {

        "from":
            old,

        "to":
            target,

        "time":
            datetime.utcnow().isoformat()
    }

    data[
        "multiverse"
    ][
        "portal_history"
    ].append(
        portal_record
    )

    if old_universe:

        connection = {

            "from":
                old,

            "to":
                target
        }

        if connection not in old_universe[
            "connections"
        ]:

            old_universe[
                "connections"
            ].append(
                connection
            )

    # Give the player a clue after arriving.
    if random.random() < 0.75:

        add_hint(
            target_universe,
            random.choice(
                DIMENSION_HINTS
            )
        )

    save_data()

    return jsonify({

        "success":
            True,

        "from":
            old,

        "to":
            target,

        "universe":
            target_universe
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
    "An ordinary day slowly turns into something nobody expected.",
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
- Choices actually change future events.
- Exactly four choices at every non-ending node.
- Choices are A, B, C, D.
- Include normal school moments.
- Characters act according to personality.
- Story feels continuous.
- Every story should be different.

Return ONLY valid JSON.

Use:

{{
  "title": "story title",
  "theme": "theme",
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


@app.route(
    "/story/start",
    methods=["POST"]
)
def story_start():

    story = generate_story()

    if not story:

        return jsonify({

            "error":
                "Story generation failed. Check your API key and models."
        }), 500

    universe = current_universe()

    data_story = {

        "active":
            True,

        "story_id":
            random.randint(
                100000,
                999999
            ),

        "title":
            story.get(
                "title",
                "Untitled Story"
            ),

        "theme":
            story.get(
                "theme",
                ""
            ),

        "current_node":
            story.get(
                "start",
                "start"
            ),

        "history":
            [],

        "seen_nodes":
            [
                story.get(
                    "start",
                    "start"
                )
            ],

        "ending":
            None,

        "tree":
            story
    }

    universe["story"] = data_story

    add_world_memory(
        f"Story started: {data_story['title']}"
    )

    save_data()

    return jsonify({

        "success":
            True,

        "story":
            data_story
    })


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

    story_state = universe[
        "story"
    ]

    if not story_state[
        "active"
    ]:

        return jsonify({
            "error":
                "No active story."
        }), 400

    story = story_state[
        "tree"
    ]

    current_id = story_state[
        "current_node"
    ]

    node = story.get(
        "nodes",
        {}
    ).get(
        current_id
    )

    if not node:

        return jsonify({
            "error":
                "Story node not found."
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
            "error":
                "Invalid choice."
        }), 400

    next_id = choice.get(
        "next"
    )

    story_state[
        "history"
    ].append({

        "node":
            current_id,

        "choice":
            choice_id,

        "choice_text":
            choice.get(
                "text",
                ""
            ),

        "next":
            next_id
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
            f"Story ended: {ending.get('title', 'Unknown ending')}"
        )

    save_data()

    return jsonify({

        "success":
            True,

        "current_node":
            next_id,

        "ending":
            ending,

        "story":
            story_state
    })


@app.route(
    "/story/tree"
)
def story_tree():

    universe = current_universe()

    story = universe[
        "story"
    ]

    return jsonify({

        "title":
            story["title"],

        "tree":
            story["tree"],

        "seen_nodes":
            story["seen_nodes"],

        "history":
            story["history"],

        "ending":
            story["ending"],

        "active":
            story["active"],

        "current_node":
            story["current_node"]
    })


# ============================================================
# STORY REPLAY
# ============================================================

@app.route(
    "/story/replay",
    methods=["POST"]
)
def replay_story():

    universe = current_universe()

    old_story = universe.get(
        "story",
        {}
    )

    if not old_story.get(
        "tree"
    ):

        return jsonify({

            "error":
                "There is no story to replay."
        }), 400

    tree = old_story[
        "tree"
    ]

    start = tree.get(
        "start",
        "start"
    )

    universe[
        "story"
    ] = {

        "active":
            True,

        "story_id":
            random.randint(
                100000,
                999999
            ),

        "title":
            tree.get(
                "title",
                "Story"
            ),

        "theme":
            tree.get(
                "theme",
                ""
            ),

        "current_node":
            start,

        "history":
            [],

        "seen_nodes":
            [start],

        "ending":
            None,

        "tree":
            tree
    }

    save_data()

    return jsonify({

        "success":
            True,

        "story":
            universe["story"]
    })


# ============================================================
# IMPROVEMENT
# ============================================================

@app.route(
    "/improvement"
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
            "error":
                "Lesson is required."
        }), 400

    add_improvement(
        lesson
    )

    save_data()

    return jsonify({

        "success":
            True,

        "improvement":
            current_universe()[
                "improvement"
            ]
    })


# ============================================================
# RESET EVERYTHING
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

        "success":
            True,

        "world_number":
            data["world_number"],

        "world_id":
            data["world_id"],

        "message":
            "A completely new multiverse was created."
    })


# ============================================================
# HEALTH
# ============================================================

@app.route(
    "/health"
)
def health():

    return jsonify({

        "status":
            "ok",

        "ai_configured":
            bool(API_KEY),

        "models":
            MODELS,

        "current_universe":
            data["current_universe"],

        "universe_count":
            len(data["universes"]),

        "world":
            data["world_number"]
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
````
