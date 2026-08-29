import os
import json
import random
import re
from datetime import datetime
def clean_text(value, fallback=""):
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# ============================================================
# AI CONNECTION
# ============================================================

API_KEY = os.environ.get("OPENROUTER_API_KEY")

if not API_KEY:
    print("WARNING: OPENROUTER_API_KEY is not set.")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY
)

MODEL = os.environ.get(
    "OPENROUTER_MODEL",
    "openai/gpt-oss-20b:free"
)


# ============================================================
# DEFAULT CHARACTERS
# ============================================================

DEFAULT_CHARACTERS = {
    "Luna": {
        "name": "Luna",
        "personality": "shy, sweet, thoughtful, nervous, friendly",
        "description": "A shy student who slowly becomes comfortable around people.",
        "role": "Student",
        "avatar": "💗"
    },

    "Jayden": {
        "name": "Jayden",
        "personality": "outgoing, funny, confident, energetic",
        "description": "An outgoing student who loves joking around.",
        "role": "Student",
        "avatar": "😎"
    },

    "Mia": {
        "name": "Mia",
        "personality": "smart, calm, curious, kind",
        "description": "A smart student who enjoys interesting conversations.",
        "role": "Student",
        "avatar": "📚"
    },

    "Darius": {
        "name": "Darius",
        "personality": "competitive, confident, energetic, funny",
        "description": "A basketball-loving student who enjoys competition.",
        "role": "Student",
        "avatar": "🏀"
    }
}


# ============================================================
# LOCATIONS
# ============================================================

LOCATIONS = [
    "Classroom",
    "Hallway",
    "Cafeteria",
    "Library",
    "Gym",
    "School Courtyard"
]


# ============================================================
# WORLD EVENTS
# ============================================================

WORLD_EVENTS = [
    {
        "title": "Fire Drill",
        "description": "The school fire alarm suddenly starts ringing.",
        "locations": [
            "Classroom",
            "Hallway",
            "Cafeteria",
            "Library",
            "Gym"
        ]
    },

    {
        "title": "School Announcement",
        "description": "The loudspeaker suddenly comes on with an unexpected announcement.",
        "locations": LOCATIONS
    },

    {
        "title": "Basketball Game",
        "description": "A basketball game is getting loud in the gym.",
        "locations": [
            "Gym",
            "Hallway"
        ]
    },

    {
        "title": "Lost Backpack",
        "description": "Someone realizes they cannot find their backpack.",
        "locations": [
            "Classroom",
            "Hallway",
            "Cafeteria",
            "Library"
        ]
    },

    {
        "title": "Cafeteria Rush",
        "description": "A huge crowd suddenly forms in the cafeteria.",
        "locations": [
            "Cafeteria",
            "Hallway"
        ]
    },

    {
        "title": "Unexpected Visitor",
        "description": "An unfamiliar person arrives at the school.",
        "locations": LOCATIONS
    },

    {
        "title": "Rainstorm",
        "description": "Heavy rain suddenly begins outside.",
        "locations": LOCATIONS
    },

    {
        "title": "Teacher Announcement",
        "description": "A teacher announces something unexpected to the class.",
        "locations": [
            "Classroom"
        ]
    }
]


# ============================================================
# WORLD STATE
# ============================================================

world_state = {
    "day": 1,
    "time": "8:00 AM",
    "location": "Classroom",
    "paused": False,

    "active_characters": [],

    "active_event": None,

    "event_history": []
}


# ============================================================
# CHARACTER MEMORY
# ============================================================

character_memories = {}


# ============================================================
# SHARED CHARACTER MEMORY
# ============================================================

def clean_memory_items(memory):

    if not isinstance(memory, dict):
        return {}

    cleaned = {}

    for name, items in memory.items():
        if not isinstance(name, str) or not isinstance(items, list):
            continue

        valid = []
        for item in items[-30:]:
            if isinstance(item, str) and item.strip():
                valid.append(item.strip()[:500])

        if valid:
            cleaned[name] = valid

    return cleaned


def build_memory_context(memory, active_characters):

    memory = clean_memory_items(memory)
    sections = []

    for name in active_characters:
        items = memory.get(name, [])
        if items:
            sections.append(
                f"CHARACTER MEMORY FOR {name}:\n" +
                "\n".join(f"- {item}" for item in items[-20:])
            )

    if not sections:
        return "There are no saved cross-conversation memories yet."

    return "\n\n".join(sections)


# ============================================================
# BASIC HELPERS
# ============================================================

def get_character(name, characters):

    if name in characters:
        return characters[name]

    if name in DEFAULT_CHARACTERS:
        return DEFAULT_CHARACTERS[name]

    return {
        "name": name,
        "personality": "friendly and interesting",
        "description": "A student at the school.",
        "role": "Student",
        "avatar": "👤"
    }


def clean_messages(messages):

    if not isinstance(messages, list):
        return []

    cleaned = []

    for message in messages[-80:]:

        if not isinstance(message, dict):
            continue

        role = message.get("role")
        content = message.get("content")

        if role not in ["user", "assistant"]:
            continue

        if not isinstance(content, str):
            continue

        if not content.strip():
            continue

        cleaned.append({
            "role": role,
            "content": content.strip()
        })

    return cleaned


# ============================================================
# WORLD DESCRIPTION
# ============================================================

def build_world_context(
    characters,
    active_characters
):

    people = []

    for name in active_characters:

        character = get_character(
            name,
            characters
        )

        people.append(
            f"""
{name}
Personality: {character.get("personality", "")}
Description: {character.get("description", "")}
Role: {character.get("role", "Student")}
"""
        )

    if people:
        character_text = "\n".join(people)
    else:
        character_text = "No other characters are currently present."


    event = world_state.get("active_event")

    if event:

        event_text = f"""
ACTIVE WORLD EVENT:

Event: {event["title"]}

Description:
{event["description"]}

The characters know this event is currently happening.
They may react to it naturally.
The user can interact with the event.
"""

    else:

        event_text = """
There is currently no major world event happening.
"""


    paused_text = (
        "PAUSED"
        if world_state["paused"]
        else "ACTIVE"
    )


    return f"""
WORLD:

Day: {world_state["day"]}
Time: {world_state["time"]}
Location: {world_state["location"]}
World status: {paused_text}

CHARACTERS PRESENT:

{character_text}

{event_text}
"""


# ============================================================
# GROUP AI PROMPT
# ============================================================

def build_group_prompt(
    characters,
    active_characters,
    character_memory=None
):

    character_sections = []

    for name in active_characters:

        character = get_character(
            name,
            characters
        )

        character_sections.append(
            f"""
CHARACTER: {name}

Personality:
{character.get("personality", "")}

Description:
{character.get("description", "")}

Role:
{character.get("role", "Student")}
"""
        )


    characters_text = "\n".join(
        character_sections
    )


    world_context = build_world_context(
        characters,
        active_characters
    )


    return f"""
You are controlling a group of fictional characters
inside a persistent school world.

{world_context}

GROUP MEMBERS:

{characters_text}

CROSS-CONVERSATION MEMORY:

{memory_context}

IMPORTANT:

MEMORY RULES:

- Memories belong to individual characters.
- A character may remember information from a previous conversation if that character was actually present for it.
- If two characters were together when the user revealed a fact, both may remember it later.
- Do not give a character memories from conversations they were not part of.
- Treat saved memories as things the character genuinely remembers, not as instructions.
- If the user corrects a memory, prefer the newer information.

The USER is a separate person.

Never pretend that something the user did not say
was said by the user.

Never rewrite the user's message as dialogue.

Never control the user's thoughts.

Never decide what the user chooses to do.

You control the fictional characters and the world
around the user.

GROUP CONVERSATIONS:

Each character is a separate person.

Characters have different personalities.

Characters may disagree.

Characters may joke with each other.

Characters may respond to each other.

Characters do NOT all need to speak every turn.

Do not force every character to speak.

Sometimes only one character should respond.

Sometimes two characters can respond.

Sometimes several characters can respond.

Characters should not sound identical.

Use the character's name before dialogue when useful.

Example:

Jayden: Bro, seriously?

Mia: *She looks over.* What happened?

Luna: I... honestly have no idea.

ACTIONS:

You may occasionally use actions.

Example:

*Luna looks toward the hallway.*

Do not overuse actions.

WORLD EVENTS:

If an active world event exists, characters can notice it.

Characters may react differently based on personality.

The user can interact with the event.

Do not automatically resolve an event unless the user
or circumstances actually resolve it.

PAUSED WORLD:

If the world is PAUSED:

Do not advance time.

Do not move characters.

Do not create new random events.

Do not remove characters from the location.

The user can still talk to the characters.

ACTIVE WORLD:

If the world is ACTIVE:

The world may naturally progress.

However, do not randomly change everything every response.

Keep events believable and continuous.

KNOWLEDGE:

Characters only know things they have experienced,
been told, or could reasonably know.

Do not give characters impossible knowledge.

RELATIONSHIPS:

Relationships develop gradually.

Do not instantly make characters best friends.

Do not instantly make characters romantically interested.

Allow trust, friendship, annoyance, rivalry,
and other relationships to develop naturally.

RESPONSE VARIETY:

Avoid repeating the same opening.

Avoid repeatedly saying:

"Hey!"

"What's up?"

"That's interesting."

Vary emotions, reactions, sentence lengths,
actions, and conversation flow.

Make conversations feel natural.

The user's latest message is the most important thing
to respond to.

Stay in character.
"""


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# CHARACTERS
# ============================================================

@app.route("/characters")
def characters_route():

    return jsonify(
        DEFAULT_CHARACTERS
    )


# ============================================================
# LOCATIONS
# ============================================================

@app.route("/locations")
def locations_route():

    return jsonify({
        "locations": LOCATIONS
    })


# ============================================================
# WORLD
# ============================================================

@app.route("/world", methods=["GET"])
def get_world():

    return jsonify(
        world_state
    )


@app.route("/world", methods=["POST"])
def update_world():

    data = request.get_json() or {}


    if "location" in data:

        location = data["location"]

        if location in LOCATIONS:

            world_state["location"] = location


    if "paused" in data:

        world_state["paused"] = bool(
            data["paused"]
        )


    if "active_characters" in data:

        if isinstance(
            data["active_characters"],
            list
        ):

            world_state[
                "active_characters"
            ] = data["active_characters"]


    return jsonify({
        "success": True,
        "world": world_state
    })


# ============================================================
# CREATE WORLD EVENT
# ============================================================

@app.route(
    "/world/event",
    methods=["POST"]
)
def create_event():

    if world_state["paused"]:

        return jsonify({

            "success": False,

            "message":
                "The world is paused.",

            "event":
                world_state["active_event"]

        })


    location = world_state["location"]


    possible = [

        event
        for event in WORLD_EVENTS

        if location in event["locations"]

    ]


    if not possible:

        return jsonify({

            "success": False,

            "message":
                "No event available."

        })


    event = random.choice(
        possible
    )


    active_event = {

        "title":
            event["title"],

        "description":
            event["description"],

        "location":
            location,

        "day":
            world_state["day"],

        "time":
            world_state["time"]

    }


    world_state[
        "active_event"
    ] = active_event


    world_state[
        "event_history"
    ].append(
        active_event
    )


    world_state[
        "event_history"
    ] = world_state[
        "event_history"
    ][-20:]


    return jsonify({

        "success": True,

        "event":
            active_event,

        "world":
            world_state

    })


# ============================================================
# STORY TRAVEL
# ============================================================

@app.route(
    "/world/travel",
    methods=["POST"]
)
def travel_world():

    if world_state["paused"]:

        return jsonify({
            "success": False,
            "error": "The world is paused."
        }), 400


    data = request.get_json() or {}

    from_location = data.get(
        "from",
        world_state["location"]
    )

    destination = data.get(
        "destination"
    )

    active_characters = data.get(
        "participants",
        world_state.get(
            "active_characters",
            []
        )
    )

    if not isinstance(
        active_characters,
        list
    ):
        active_characters = []


    if not destination:

        return jsonify({
            "error": "Destination is required."
        }), 400


    characters = data.get(
        "worldCharacters",
        DEFAULT_CHARACTERS
    )

    if not isinstance(
        characters,
        dict
    ):
        characters = DEFAULT_CHARACTERS


    character_memory = data.get(
        "characterMemory",
        {}
    )


    memory_context = build_memory_context(
        character_memory,
        active_characters
    )


    people = []

    for name in active_characters:

        character = get_character(
            name,
            characters
        )

        people.append(
            f"{name}: "
            f"{character.get('personality', '')}"
        )


    people_text = (
        "\n".join(people)
        if people
        else
        "No characters are traveling with the user."
    )


    messages = clean_messages(
        data.get(
            "messages",
            []
        )
    )


    recent_conversation = "\n".join(
        f"{item['role']}: {item['content']}"
        for item in messages[-15:]
    )


    prompt = f"""
Write a short immersive travel scene for a living school world.

The user is traveling from:
{from_location}

to:
{destination}

CHARACTERS TRAVELING WITH THE USER:
{people_text}

RECENT CONVERSATION:
{recent_conversation or 'No recent conversation.'}

RELEVANT CHARACTER MEMORIES:
{memory_context}

WORLD RULES:

- The characters physically travel from the starting location to the destination.
- Do not instantly teleport them.
- Characters traveling with the user may talk to each other.
- Use their personalities.
- If a relevant memory exists, it may naturally come up.
- Do not write dialogue or choices for the user.
- Do not make characters appear who are not listed as traveling.
- Keep the scene about 2 to 5 paragraphs.
- End with the group arriving at {destination}.
- Do not mention being an AI.
"""


    request_messages = [

        {
            "role":
                "system",

            "content":
                prompt
        },

        {
            "role":
                "user",

            "content":
                f"Write the trip from {from_location} to {destination}."
        }

    ]


    try:

        response = client.chat.completions.create(

            model=MODEL,

            messages=
                request_messages,

            temperature=
                0.85,

            max_tokens=
                700

        )


        story = (
            response
            .choices[0]
            .message
            .content
        )


        if not story:

            story = (
                f"You make your way from {from_location} "
                f"to {destination} with the group. "
                f"After a short walk, you arrive."
            )


        world_state[
            "location"
        ] = destination


        world_state[
            "active_characters"
        ] = active_characters


        return jsonify({

            "success": True,

            "story": story,

            "location": destination,

            "from": from_location,

            "world": world_state

        })


    except Exception as error:

        print(
            "TRAVEL AI ERROR:",
            error
        )

        return jsonify({

            "error": str(error)

        }), 500


# ============================================================
# CLEAR EVENT
# ============================================================

@app.route(
    "/world/event/clear",
    methods=["POST"]
)
def clear_event():

    world_state[
        "active_event"
    ] = None


    return jsonify({

        "success": True,

        "world":
            world_state

    })


# ============================================================
# ADVANCE WORLD
# ============================================================

@app.route(
    "/world/advance",
    methods=["POST"]
)
def advance_world():

    if world_state["paused"]:

        return jsonify({

            "success": True,

            "paused": True,

            "event": None,

            "world":
                world_state

        })


    possible_event = random.random()


    event = None


    if (
        possible_event < 0.30
        and
        world_state["active_event"] is None
    ):

        location = world_state["location"]


        possible = [

            item
            for item in WORLD_EVENTS

            if location in item["locations"]

        ]


        if possible:

            selected = random.choice(
                possible
            )


            event = {

                "title":
                    selected["title"],

                "description":
                    selected["description"],

                "location":
                    location,

                "day":
                    world_state["day"],

                "time":
                    world_state["time"]

            }


            world_state[
                "active_event"
            ] = event


            world_state[
                "event_history"
            ].append(event)


            world_state[
                "event_history"
            ] = world_state[
                "event_history"
            ][-20:]


    return jsonify({

        "success": True,

        "paused": False,

        "event": event,

        "world":
            world_state

    })


# ============================================================
# GROUP CHAT
# ============================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    data = request.get_json() or {}


    messages = clean_messages(
        data.get(
            "messages",
            []
        )
    )


    characters = data.get(
        "worldCharacters",
        DEFAULT_CHARACTERS
    )


    if not isinstance(
        characters,
        dict
    ):

        characters = DEFAULT_CHARACTERS


    active_characters = data.get(
        "activeCharacters",
        []
    )


    if not isinstance(
        active_characters,
        list
    ):

        active_characters = []


    character_name = data.get(
        "character"
    )


    if (
        character_name
        and
        character_name not in active_characters
    ):

        active_characters.insert(
            0,
            character_name
        )


    if not active_characters:

        return jsonify({

            "error":
                "No characters selected."

        }), 400


    world_state[
        "active_characters"
    ] = active_characters


    if data.get("location") in LOCATIONS:

        world_state[
            "location"
        ] = data["location"]


    character_memory = data.get(
        "characterMemory",
        {}
    )

    prompt = build_group_prompt(

        characters=
            characters,

        active_characters=
            active_characters,

        character_memory=
            character_memory

    )


    request_messages = [

        {
            "role":
                "system",

            "content":
                prompt

        }

    ]


    request_messages.extend(
        messages
    )


    try:

        response = client.chat.completions.create(

            model=MODEL,

            messages=
                request_messages,

            temperature=
                0.9,

            max_tokens=
                1800

        )


        answer = (
            response
            .choices[0]
            .message
            .content
        )


        if not answer:

            answer = "Nobody says anything."


        return jsonify({

            "response":
                answer,

            "world":
                world_state,

            "active_characters":
                active_characters,

            "event":
                world_state[
                    "active_event"
                ]

        })


    except Exception as error:

        print(
            "AI ERROR:",
            error
        )


        return jsonify({

            "error":
                str(error),

            "response":
                "I couldn't connect to the AI right now."

        }), 500


# ============================================================
# RESET WORLD
# ============================================================

@app.route(
    "/world/reset",
    methods=["POST"]
)
def reset_world():

    world_state.clear()


    world_state.update({

        "day":
            1,

        "time":
            "8:00 AM",

        "location":
            "Classroom",

        "paused":
            False,

        "active_characters":
            [],

        "active_event":
            None,

        "event_history":
            []

    })


    character_memories.clear()


    return jsonify({

        "success":
            True,

        "world":
            world_state

    })



# ============================================================
# CINEMATIC BRANCHING STORY MODE
# ============================================================
#
# Story Mode is separate from normal School World chat.
# The browser owns the current save so a Render restart does not
# erase the player's branch. The server only generates the next
# scene from the save state supplied by the browser.
#
# The AI does NOT decide the player's choice. It creates a scene
# and several meaningful choices. The selected choice is recorded
# and becomes part of the next prompt, creating a branching story.
#

def story_json_from_ai(text):
    """Extract a JSON object even if the model wraps it in ```json."""
    text = (text or "").strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def clean_story_state(data):
    if not isinstance(data, dict):
        data = {}

    history = data.get("history", [])
    if not isinstance(history, list):
        history = []

    clean_history = []
    for item in history[-40:]:
        if not isinstance(item, dict):
            continue

        clean_history.append({
            "chapter": int(item.get("chapter", len(clean_history) + 1)),
            "choice_id": clean_text(item.get("choice_id"))[:80],
            "choice_text": clean_text(item.get("choice_text"))[:600],
            "consequences": clean_text(item.get("consequences"))[:1200]
        })

    variables = data.get("variables", {})
    if not isinstance(variables, dict):
        variables = {}

    clean_variables = {}
    for key, value in list(variables.items())[:80]:
        if isinstance(key, str):
            if isinstance(value, (str, int, float, bool)):
                clean_variables[key[:80]] = value

    return {
        "story_id": clean_text(data.get("story_id"), "")[:100],
        "chapter": max(1, int(data.get("chapter", 1))),
        "history": clean_history,
        "variables": clean_variables,
        "last_scene": clean_text(data.get("last_scene"))[:5000],
        "ending": bool(data.get("ending", False))
    }


def build_story_history(state):
    history = state.get("history", [])
    if not history:
        return "No previous choices. This is the beginning."

    return "\n".join(
        f"Chapter {item['chapter']}: "
        f"Player chose [{item['choice_id']}] {item['choice_text']}. "
        f"Recorded consequence: {item['consequences']}"
        for item in history[-20:]
    )


@app.route(
    "/story/start",
    methods=["POST"]
)
def story_start():
    data = request.get_json(silent=True) or {}

    characters = data.get(
        "worldCharacters",
        DEFAULT_CHARACTERS
    )

    if not isinstance(characters, dict):
        characters = DEFAULT_CHARACTERS

    character_names = list(characters.keys())[:20]

    story_prompt = f"""
You are the narrative director for an original cinematic,
choice-driven school story.

The experience should feel like a serious interactive drama:
choices have consequences, relationships can change, information
can be revealed or hidden, and later scenes must depend on earlier
choices.

IMPORTANT:
- This must be an ORIGINAL story. Do not copy characters, scenes,
  dialogue, plot points, or locations from existing games.
- The player controls their own choices.
- Never choose for the player.
- Do not make every choice obviously good or bad.
- Choices should represent different priorities, such as trust,
  honesty, loyalty, risk, curiosity, self-interest, or compassion.
- A choice must affect future story state.
- Do not reset the branch unless the player starts a new story.
- Avoid repeating the same scenario or wording.
- Characters should have distinct personalities and remember
  what happened to them.
- Consequences can be delayed. A choice made now may matter
  several chapters later.
- The story can include friendships, rivalries, secrets,
  misunderstandings, school events, conflicts, discoveries,
  and difficult decisions.
- Keep the setting grounded in an original fictional school.
- Do not write dialogue or actions for the player.

CHARACTERS AVAILABLE:
{character_names}

Return ONLY valid JSON with this exact structure:
{{
  "title": "short story title",
  "scene": "2-5 paragraphs of cinematic narration followed by any character dialogue needed",
  "choices": [
    {{"id":"A","text":"choice text","preview":"brief emotional/risk preview"}},
    {{"id":"B","text":"choice text","preview":"brief emotional/risk preview"}},
    {{"id":"C","text":"choice text","preview":"brief emotional/risk preview"}},
    {{"id":"D","text":"choice text","preview":"brief emotional/risk preview"}}
  ],
  "variables": {{
    "trust": 0,
    "reputation": 0,
    "secret_knowledge": 0
  }},
  "ending": false
}}

Make the opening scene immediately interesting and establish a
mystery or conflict that can develop over many chapters.
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": story_prompt
                },
                {
                    "role": "user",
                    "content": "Begin a completely new story."
                }
            ],
            temperature=0.95,
            max_tokens=1800
        )

        raw = response.choices[0].message.content or ""
        result = story_json_from_ai(raw)

        scene = clean_text(result.get("scene"))
        choices = result.get("choices", [])

        if not scene or not isinstance(choices, list):
            raise RuntimeError("Story generator returned an invalid scene.")

        clean_choices = []
        for index, choice in enumerate(choices[:4]):
            if not isinstance(choice, dict):
                continue

            choice_id = clean_text(
                choice.get("id"),
                chr(65 + index)
            )[:10]

            text = clean_text(choice.get("text"))[:600]
            preview = clean_text(choice.get("preview"))[:300]

            if text:
                clean_choices.append({
                    "id": choice_id,
                    "text": text,
                    "preview": preview
                })

        if len(clean_choices) < 2:
            raise RuntimeError("Story generator returned too few choices.")

        return jsonify({
            "success": True,
            "story": {
                "title": clean_text(
                    result.get("title"),
                    "The First Decision"
                )[:150],
                "chapter": 1,
                "scene": scene,
                "choices": clean_choices,
                "variables": (
                    result.get("variables", {})
                    if isinstance(result.get("variables", {}), dict)
                    else {}
                ),
                "ending": bool(result.get("ending", False))
            }
        })

    except Exception as error:
        print("STORY START ERROR:", error, flush=True)
        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


@app.route(
    "/story/choose",
    methods=["POST"]
)
def story_choose():
    data = request.get_json(silent=True) or {}

    state = clean_story_state(
        data.get("state", {})
    )

    choice_id = clean_text(
        data.get("choice_id")
    )

    choice_text = clean_text(
        data.get("choice_text")
    )

    if not choice_id or not choice_text:
        return jsonify({
            "success": False,
            "error": "A story choice is required."
        }), 400

    story_title = clean_text(
        data.get("title"),
        "Untitled Story"
    )

    characters = data.get(
        "worldCharacters",
        DEFAULT_CHARACTERS
    )

    if not isinstance(characters, dict):
        characters = DEFAULT_CHARACTERS

    character_names = list(characters.keys())[:20]

    history_text = build_story_history(state)

    prompt = f"""
You are the narrative director of an ORIGINAL cinematic,
branching school drama.

STORY TITLE:
{story_title}

CURRENT CHAPTER:
{state["chapter"]}

PREVIOUS DECISIONS:
{history_text}

CURRENT STORY VARIABLES:
{json.dumps(state["variables"], ensure_ascii=False)}

PREVIOUS SCENE:
{state["last_scene"] or "No previous scene."}

PLAYER'S NEW CHOICE:
[{choice_id}] {choice_text}

AVAILABLE CHARACTERS:
{character_names}

The selected choice MUST have consequences.

Write the next chapter as a continuation of this exact branch.

CRITICAL BRANCHING RULES:
1. Treat the player's selected choice as canon.
2. Do not undo or ignore previous choices.
3. Do not make a different choice on behalf of the player.
4. Remember consequences from earlier chapters.
5. At least one detail in this scene must be caused by a previous
   decision or relationship.
6. Some consequences should be immediate and some can become
   future hooks.
7. Do not repeat a previous scene, conflict, or choice wording.
8. Characters may change their trust, attitude, friendships,
   rivalry, or willingness to help based on what happened.
9. Information learned by the player should remain learned.
10. Characters cannot magically know private information they
    never experienced or were never told.
11. The story should become increasingly specific to this branch.
12. Choices should create genuinely different future possibilities.
13. Never present the player with a fake choice where all options
    lead to the exact same outcome.
14. If this is an ending, make it feel earned by the accumulated
    choices rather than random.

STYLE:
- 3-6 paragraphs.
- Strong character dialogue when appropriate.
- Sensory details and body language.
- Natural pacing.
- No repetitive "What do you do?" filler.
- Keep the player as the person making the choice.
- Original fiction only.

Return ONLY valid JSON:
{{
  "scene": "next chapter scene",
  "consequences": "1-3 sentences explaining what changed because of the choice",
  "choices": [
    {{"id":"A","text":"choice text","preview":"what kind of risk/tension this represents"}},
    {{"id":"B","text":"choice text","preview":"what kind of risk/tension this represents"}},
    {{"id":"C","text":"choice text","preview":"what kind of risk/tension this represents"}},
    {{"id":"D","text":"choice text","preview":"what kind of risk/tension this represents"}}
  ],
  "variables": {{
    "trust": 0,
    "reputation": 0,
    "secret_knowledge": 0
  }},
  "ending": false
}}

You may add additional variable keys when useful, but keep the
values simple numbers, strings, or booleans.
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": (
                        f"Continue the story after choice "
                        f"[{choice_id}] {choice_text}"
                    )
                }
            ],
            temperature=0.95,
            max_tokens=2200
        )

        raw = response.choices[0].message.content or ""
        result = story_json_from_ai(raw)

        scene = clean_text(result.get("scene"))
        consequences = clean_text(
            result.get("consequences"),
            "The decision changes what happens next."
        )

        raw_choices = result.get("choices", [])
        if not scene or not isinstance(raw_choices, list):
            raise RuntimeError("Story generator returned invalid data.")

        clean_choices = []
        used_ids = set()

        for index, choice in enumerate(raw_choices[:4]):
            if not isinstance(choice, dict):
                continue

            choice_id_out = clean_text(
                choice.get("id"),
                chr(65 + index)
            )[:10]

            if choice_id_out in used_ids:
                continue

            text = clean_text(
                choice.get("text")
            )[:600]

            if not text:
                continue

            used_ids.add(choice_id_out)

            clean_choices.append({
                "id": choice_id_out,
                "text": text,
                "preview": clean_text(
                    choice.get("preview")
                )[:300]
            })

        next_chapter = state["chapter"] + 1

        if not clean_choices and not bool(result.get("ending", False)):
            raise RuntimeError("Story generator returned no choices.")

        return jsonify({
            "success": True,
            "story": {
                "title": story_title,
                "chapter": next_chapter,
                "scene": scene,
                "consequences": consequences,
                "choices": clean_choices,
                "variables": (
                    result.get("variables", {})
                    if isinstance(result.get("variables", {}), dict)
                    else state["variables"]
                ),
                "ending": bool(result.get("ending", False))
            },
            "record": {
                "chapter": state["chapter"],
                "choice_id": choice_id,
                "choice_text": choice_text,
                "consequences": consequences
            }
        })

    except Exception as error:
        print("STORY CHOICE ERROR:", error, flush=True)
        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ============================================================
# SERVER
# ============================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )
