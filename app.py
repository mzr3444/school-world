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
# CONFIG
# ============================================================

API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b")

client = None

if API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY
    )

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
        "description": "Maya notices details other people miss and usually thinks before speaking.",
        "traits": ["Smart", "Calm", "Observant", "Sarcastic"],
        "memory": [],
        "conversation": []
    },
    {
        "id": "jordan",
        "name": "Jordan",
        "role": "Student",
        "personality": "Confident, competitive, outgoing, playful, and stubborn.",
        "description": "Jordan loves competition and enjoys challenging people.",
        "traits": ["Confident", "Competitive", "Outgoing", "Stubborn"],
        "memory": [],
        "conversation": []
    },
    {
        "id": "sam",
        "name": "Sam",
        "role": "Student",
        "personality": "Quiet, creative, thoughtful, kind, and mysterious.",
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
# DATA
# ============================================================

def new_story_state():
    return {
        "active": False,
        "story_id": random.randint(100000, 999999),
        "title": "",
        "theme": "",
        "current_node": "start",
        "history": [],
        "seen_nodes": [],
        "ending": None,
        "tree": {}
    }


def default_data():
    return {
        "world_id": random.randint(100000, 999999),
        "world_number": 1,
        "player_location": "Classroom",
        "characters": json.loads(json.dumps(DEFAULT_CHARACTERS)),
        "locations": DEFAULT_LOCATIONS.copy(),
        "world_memory": [],
        "background_events": [],
        "story": new_story_state(),
        "improvement": {
            "facts": [],
            "preferences": [],
            "successful_patterns": [],
            "relationship_notes": []
        }
    }


def save_data(current_data=None):
    if current_data is None:
        current_data = data

    with data_lock:
        temp_file = DATA_FILE + ".tmp"

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(
                current_data,
                f,
                indent=2,
                ensure_ascii=False
            )

        os.replace(temp_file, DATA_FILE)


def load_data():
    if not os.path.exists(DATA_FILE):
        fresh = default_data()
        save_data(fresh)
        return fresh

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        base = default_data()

        for key, value in base.items():
            if key not in loaded:
                loaded[key] = value

        if "story" not in loaded:
            loaded["story"] = new_story_state()

        if "improvement" not in loaded:
            loaded["improvement"] = base["improvement"]

        return loaded

    except Exception:
        fresh = default_data()
        save_data(fresh)
        return fresh


data = load_data()


# ============================================================
# HELPERS
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", "")
    text = re.sub(
        r"```(?:json|python|html)?",
        "",
        text,
        flags=re.IGNORECASE
    )
    text = text.replace("```", "")

    return text.strip()


def find_character(character_id):
    for character in data["characters"]:
        if character["id"] == character_id:
            return character
    return None


def trim(items, limit):
    if len(items) <= limit:
        return items

    return items[-limit:]


def remember(character, text):
    text = clean_text(text)

    if not text:
        return

    character.setdefault("memory", [])
    character["memory"].append(text)
    character["memory"] = trim(character["memory"], 40)


def add_world_memory(text):
    text = clean_text(text)

    if not text:
        return

    data.setdefault("world_memory", [])
    data["world_memory"].append(text)
    data["world_memory"] = trim(data["world_memory"], 60)


def add_improvement(text):
    text = clean_text(text)

    if not text:
        return

    facts = data["improvement"].setdefault("facts", [])

    if text not in facts:
        facts.append(text)

    data["improvement"]["facts"] = trim(facts, 50)


# ============================================================
# AI
# ============================================================

def call_ai(system_prompt, messages, temperature=0.8, max_tokens=600):
    if not client:
        return "AI_ERROR: API key is not configured."

    try:
        response = client.chat.completions.create(
            model=MODEL,
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
            return "AI_ERROR: The AI returned no response."

        result = response.choices[0].message.content

        return clean_text(result)

    except Exception as e:
        return f"AI_ERROR: {str(e)}"


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
    return jsonify({
        "world_id": data["world_id"],
        "world_number": data["world_number"],
        "location": data["player_location"],
        "characters": data["characters"],
        "locations": data["locations"],
        "world_memory": data["world_memory"][-20:],
        "background_events": data["background_events"][-20:],
        "story": data["story"],
        "improvement": data["improvement"]
    })


# ============================================================
# NORMAL AI CHARACTER CHAT
# ============================================================

@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}

    character_id = body.get("character_id")
    message = clean_text(body.get("message"))

    if not character_id or not message:
        return jsonify({
            "error": "Character and message are required."
        }), 400

    character = find_character(character_id)

    if not character:
        return jsonify({
            "error": "Character not found."
        }), 404

    remember(character, f"Player said: {message}")

    recent = character.get("conversation", [])[-18:]

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
            "personality": c["personality"]
        }
        for c in data["characters"]
        if c["id"] != character["id"]
    ]

    system_prompt = f"""
You are {character["name"]}, a person inside a living school simulation.

ROLE:
{character["role"]}

PERSONALITY:
{character["personality"]}

DESCRIPTION:
{character["description"]}

TRAITS:
{", ".join(character.get("traits", []))}

CURRENT PLAYER LOCATION:
{data["player_location"]}

WORLD:
World #{data["world_number"]}

YOUR MEMORY:
{json.dumps(character.get("memory", [])[-20:], ensure_ascii=False)}

WORLD MEMORY:
{json.dumps(data.get("world_memory", [])[-20:], ensure_ascii=False)}

OTHER CHARACTERS:
{json.dumps(other_characters, ensure_ascii=False)}

IMPORTANT:

- Stay in character.
- Have your own opinions.
- Do not blindly agree.
- Remember previous conversations.
- Use the character's personality.
- Give medium-length responses.
- Usually respond in 2-5 paragraphs.
- Don't make every response enormous.
- React naturally.
- The player is a separate person.
- Never control the player's actions.
- If the player says they are traveling somewhere, acknowledge it naturally.
- Do not pretend to physically travel with the player unless appropriate.
- You live in the school world.
- You can know other students.
- You can mention things that happened earlier.
- Do not constantly mention AI or chatbots.
"""

    answer = call_ai(
        system_prompt,
        messages,
        temperature=0.82,
        max_tokens=650
    )

    if answer.startswith("AI_ERROR:"):
        return jsonify({
            "error": answer
        }), 500

    character.setdefault("conversation", [])

    character["conversation"].append({
        "role": "user",
        "content": message,
        "time": datetime.utcnow().isoformat()
    })

    character["conversation"].append({
        "role": "assistant",
        "content": answer,
        "time": datetime.utcnow().isoformat()
    })

    character["conversation"] = trim(
        character["conversation"],
        80
    )

    if len(message) >= 25:
        add_improvement(
            f"{character['name']} conversation detail: {message[:160]}"
        )

    save_data()

    return jsonify({
        "reply": answer,
        "character": character,
        "location": data["player_location"]
    })


# ============================================================
# CONVERSATION RESET
# ============================================================

@app.route("/conversation/reset", methods=["POST"])
def reset_conversation():
    body = request.get_json(silent=True) or {}

    character = find_character(body.get("character_id"))

    if not character:
        return jsonify({
            "error": "Character not found."
        }), 404

    character["conversation"] = []

    save_data()

    return jsonify({
        "success": True,
        "message": f"Conversation with {character['name']} reset."
    })


@app.route("/conversation/new", methods=["POST"])
def new_conversation():
    return jsonify({
        "success": True
    })


# ============================================================
# CHARACTER CREATION
# ============================================================

@app.route("/characters/create", methods=["POST"])
def create_character():
    body = request.get_json(silent=True) or {}

    name = clean_text(body.get("name"))
    role = clean_text(body.get("role")) or "Student"
    personality = clean_text(body.get("personality"))
    description = clean_text(body.get("description"))

    traits = body.get("traits", [])

    if not name:
        return jsonify({
            "error": "Name is required."
        }), 400

    if not personality:
        return jsonify({
            "error": "Personality is required."
        }), 400

    if not isinstance(traits, list):
        traits = []

    safe_name = re.sub(
        r"[^a-z0-9]+",
        "-",
        name.lower()
    ).strip("-")

    character_id = (
        safe_name +
        "-" +
        str(random.randint(1000, 9999))
    )

    character = {
        "id": character_id,
        "name": name,
        "role": role,
        "personality": personality,
        "description": description or f"{name} is a {role.lower()} at the school.",
        "traits": [
            clean_text(t)
            for t in traits
            if clean_text(t)
        ],
        "memory": [],
        "conversation": []
    }

    data["characters"].append(character)

    save_data()

    return jsonify({
        "success": True,
        "character": character
    })


# ============================================================
# TRAVEL
# ============================================================

@app.route("/world/travel", methods=["POST"])
def travel():
    body = request.get_json(silent=True) or {}

    location = clean_text(body.get("location"))

    if location not in data["locations"]:
        return jsonify({
            "error": "Unknown location."
        }), 400

    old = data["player_location"]

    if old != location:
        data["player_location"] = location

        add_world_memory(
            f"The player traveled from {old} to {location}."
        )

    save_data()

    return jsonify({
        "success": True,
        "location": location
    })


# ============================================================
# BACKGROUND CHARACTER INTERACTIONS
# ============================================================

@app.route("/world/advance", methods=["POST"])
def world_advance():
    if len(data["characters"]) < 2:
        return jsonify({
            "event": "Not enough characters."
        })

    first, second = random.sample(
        data["characters"],
        2
    )

    location = random.choice(data["locations"])

    # Local fallback interaction.
    interaction_templates = [
        (
            f"{first['name']} and {second['name']} ran into each other "
            f"in the {location}. They talked for a while, with "
            f"{first['name']} being {first['traits'][0].lower() if first.get('traits') else 'casual'} "
            f"while {second['name']} responded in their own way."
        ),
        (
            f"In the {location}, {first['name']} and {second['name']} "
            f"ended up talking about school. The conversation was "
            f"surprisingly interesting, and neither of them seemed "
            f"ready to leave immediately."
        ),
        (
            f"{first['name']} noticed {second['name']} in the {location} "
            f"and started a conversation. They joked around for a bit "
            f"before eventually going their separate ways."
        ),
        (
            f"{first['name']} and {second['name']} disagreed about "
            f"something in the {location}. Neither completely changed "
            f"their mind, but the conversation gave both of them "
            f"something to think about."
        )
    ]

    event_text = random.choice(interaction_templates)

    event = {
        "characters": [
            first["name"],
            second["name"]
        ],
        "location": location,
        "event": event_text,
        "time": datetime.utcnow().isoformat()
    }

    data["background_events"].append(event)

    data["background_events"] = trim(
        data["background_events"],
        50
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
        f"{first['name']} and {second['name']} interacted at {location}."
    )

    save_data()

    return jsonify({
        "success": True,
        "event": event
    })


# ============================================================
# WORLD RESET
# ============================================================

@app.route("/world/reset", methods=["POST"])
def reset_world():
    global data

    old_number = data["world_number"]

    new_data = default_data()

    new_data["world_number"] = old_number + 1
    new_data["world_id"] = random.randint(100000, 999999)

    # Completely new story seed.
    new_data["story"]["story_id"] = random.randint(
        100000,
        999999
    )

    data = new_data

    save_data()

    return jsonify({
        "success": True,
        "world_number": data["world_number"],
        "world_id": data["world_id"],
        "message": "New universe created."
    })


# ============================================================
# ============================================================
# LOCAL STORY ENGINE
# ============================================================
# This section DOES NOT call OpenRouter.
# Therefore Story Mode costs ZERO API credits.
# ============================================================
# ============================================================

STORY_SCENARIOS = [
    {
        "title": "The Door Beneath the School",
        "theme": "A strange door appears beneath the school.",
        "intro": "During an ordinary school day, you notice a hallway that seems different from yesterday. At the end is a door nobody remembers seeing.",
        "mystery": "The door appears to react to decisions made by students.",
        "special": "The doorway may connect this school to another version of reality."
    },
    {
        "title": "The Missing Afternoon",
        "theme": "An entire afternoon seems to have disappeared from everyone's memory.",
        "intro": "The school day starts normally, but several students insist that something happened during a period nobody can remember.",
        "mystery": "A few students remember different versions of the same afternoon.",
        "special": "The missing time may belong to another universe."
    },
    {
        "title": "The Other School",
        "theme": "A second version of the school appears.",
        "intro": "You glance through a classroom window and see the same school across the courtyard—but the people inside are different.",
        "mystery": "The other school appears to exist in a parallel world.",
        "special": "Something from that world is slowly crossing over."
    },
    {
        "title": "The Signal",
        "theme": "A mysterious signal begins affecting the school.",
        "intro": "Every computer in the school suddenly displays the same strange symbol.",
        "mystery": "The signal seems to predict events before they happen.",
        "special": "The signal may be coming from another version of Earth."
    }
]


def make_choice(a, b, c, d, next_a, next_b, next_c, next_d):
    return [
        {"id": "A", "text": a, "next": next_a},
        {"id": "B", "text": b, "next": next_b},
        {"id": "C", "text": c, "next": next_c},
        {"id": "D", "text": d, "next": next_d}
    ]


def build_local_story():
    """
    Builds a different story tree every time.

    The structure is intentionally generated with random variations,
    while still guaranteeing six possible endings.
    """

    scenario = random.choice(STORY_SCENARIOS)

    names = [
        c["name"]
        for c in data["characters"]
    ]

    random.shuffle(names)

    while len(names) < 4:
        names.append("another student")

    a, b, c, d = names[:4]

    # Random story details make each new world different.
    object_names = [
        "a cracked phone",
        "an old school key",
        "a glowing notebook",
        "a strange USB drive",
        "a locked metal box",
        "a photograph from tomorrow"
    ]

    locations = data["locations"]

    special_object = random.choice(object_names)

    loc1 = random.choice(locations)
    loc2 = random.choice(locations)
    loc3 = random.choice(locations)

    # --------------------------------------------------------
    # ENDINGS
    # --------------------------------------------------------

    endings = [
        {
            "id": "ending_1",
            "title": "The Quiet Escape",
            "text": f"You stop the mystery from spreading. {a} helps you keep the discovery secret, and the school returns to normal. Nobody ever learns how close the world came to changing."
        },
        {
            "id": "ending_2",
            "title": "The Worlds Collide",
            "text": f"The boundary between realities breaks. Students from another version of the school appear, and the two worlds become connected. The school will never be the same."
        },
        {
            "id": "ending_3",
            "title": "The Truth Revealed",
            "text": f"You expose the mystery to everyone. {b} helps piece together the evidence, and the entire school learns that reality is far stranger than anyone imagined."
        },
        {
            "id": "ending_4",
            "title": "The Sacrifice",
            "text": f"You choose to close the phenomenon permanently. The school survives, but the evidence—and one important memory—vanishes forever."
        },
        {
            "id": "ending_5",
            "title": "The New Timeline",
            "text": f"Your decisions create a completely different timeline. When the school day ends, you realize that several small details about your world have changed."
        },
        {
            "id": "ending_6",
            "title": "Beyond the Door",
            "text": f"You step through the phenomenon instead of closing it. On the other side is another school, another world, and another version of yourself waiting."
        }
    ]

    nodes = {}

    # --------------------------------------------------------
    # START
    # --------------------------------------------------------

    nodes["start"] = {
        "title": scenario["title"],
        "text": (
            f"{scenario['intro']} "
            f"{scenario['mystery']} "
            f"You are near {loc1}. {a} is nearby when you notice {special_object}."
        ),
        "choices": make_choice(
            "Investigate the strange object.",
            "Ask Alex what they saw.",
            "Leave and investigate the hallway.",
            "Tell Maya about the discovery.",
            "investigate",
            "alex",
            "hallway",
            "maya"
        )
    }

    # --------------------------------------------------------
    # FIRST BRANCH
    # --------------------------------------------------------

    nodes["investigate"] = {
        "title": "The Discovery",
        "text": (
            f"You examine {special_object}. Something about it feels "
            f"wrong. The object briefly displays a message that should "
            f"not be possible."
        ),
        "choices": make_choice(
            "Take the object.",
            "Leave it where it is.",
            "Show it to Sam.",
            "Destroy it.",
            "take_object",
            "leave_object",
            "sam",
            "destroy_object"
        )
    }

    nodes["alex"] = {
        "title": "Alex Saw Something",
        "text": (
            f"{a} looks nervous. They tell you they saw someone "
            f"walking through the hallway who looked exactly like "
            f"{a}, but they disappeared before anyone else noticed."
        ),
        "choices": make_choice(
            "Believe them.",
            "Ask for proof.",
            "Search for the person.",
            "Tell them to forget it.",
            "believe",
            "proof",
            "search_person",
            "forget"
        )
    }

    nodes["hallway"] = {
        "title": "The Empty Hallway",
        "text": (
            f"You enter the hallway. The lights flicker, and for a "
            f"moment the hallway looks completely different. A sound "
            f"comes from {loc2}."
        ),
        "choices": make_choice(
            "Follow the sound.",
            "Return to class.",
            "Call Jordan.",
            "Enter {0}.".format(loc2),
            "sound",
            "return_class",
            "jordan",
            "location_two"
        )
    }

    nodes["maya"] = {
        "title": "Maya's Theory",
        "text": (
            f"{b} listens carefully. Instead of laughing, {b} says "
            f"the evidence looks like a repeating pattern. "
            f"They think the school might be experiencing "
            f"something that happened before."
        ),
        "choices": make_choice(
            "Trust Maya.",
            "Ask for more evidence.",
            "Investigate alone.",
            "Tell another student.",
            "trust_maya",
            "maya_evidence",
            "alone",
            "tell_student"
        )
    }

    # --------------------------------------------------------
    # SECOND LEVEL
    # --------------------------------------------------------

    nodes["take_object"] = {
        "title": "The Object Reacts",
        "text": (
            f"The moment you pick up {special_object}, every clock "
            f"nearby changes by several minutes. You hear a voice "
            f"coming from somewhere that sounds like the school—but "
            f"not your school."
        ),
        "choices": make_choice(
            "Answer the voice.",
            "Run to the library.",
            "Give the object to Maya.",
            "Turn it off.",
            "voice",
            "library",
            "object_maya",
            "turn_off"
        )
    }

    nodes["leave_object"] = {
        "title": "Walking Away",
        "text": (
            "You leave the object behind. Unfortunately, someone else "
            "finds it. A few minutes later, the school begins behaving "
            "strangely."
        ),
        "choices": make_choice(
            "Find who took it.",
            "Warn the teachers.",
            "Stay out of it.",
            "Search the cameras.",
            "find_taker",
            "teachers",
            "stay_out",
            "cameras"
        )
    }

    nodes["sam"] = {
        "title": "Sam's Drawing",
        "text": (
            f"Sam studies the object and quietly shows you a drawing "
            f"they made yesterday. It shows the exact same thing."
        ),
        "choices": make_choice(
            "Ask Sam how they knew.",
            "Follow Sam.",
            "Keep the drawing.",
            "Destroy the drawing.",
            "sam_truth",
            "follow_sam",
            "keep_drawing",
            "destroy_drawing"
        )
    }

    nodes["destroy_object"] = {
        "title": "Breaking the Pattern",
        "text": (
            "You destroy the object. For a moment everything seems "
            "normal. Then every screen in the school displays the "
            "same message: YOU CHANGED THE STORY."
        ),
        "choices": make_choice(
            "Investigate the message.",
            "Ignore it.",
            "Tell everyone.",
            "Find the source.",
            "message",
            "ignore_message",
            "public_truth",
            "source"
        )
    }

    nodes["believe"] = {
        "title": "The Double",
        "text": (
            f"{a} takes you toward {loc2}. Someone is standing at the "
            f"far end of the hallway. They look exactly like {a}."
        ),
        "choices": make_choice(
            "Approach them.",
            "Hide.",
            "Call Maya.",
            "Leave the school.",
            "approach_double",
            "hide_double",
            "call_maya",
            "leave_school"
        )
    }

    nodes["proof"] = {
        "title": "Proof",
        "text": (
            f"{a} shows you a photograph. In the background is "
            f"a version of the school that doesn't exist."
        ),
        "choices": make_choice(
            "Study the photograph.",
            "Delete it.",
            "Show Maya.",
            "Show Jordan.",
            "photo",
            "delete_photo",
            "photo_maya",
            "photo_jordan"
        )
    }

    nodes["search_person"] = {
        "title": "Searching",
        "text": (
            f"You search {loc2}. Nobody is there. Then you hear your "
            f"own voice coming from an empty classroom."
        ),
        "choices": make_choice(
            "Enter the classroom.",
            "Run.",
            "Call Sam.",
            "Answer your own voice.",
            "voice_room",
            "run",
            "call_sam",
            "answer_self"
        )
    }

    nodes["forget"] = {
        "title": "Ignoring the Warning",
        "text": (
            "You decide to forget what happened. The rest of the day "
            "seems normal until you notice that one of your classmates "
            "has completely disappeared from everyone's memories."
        ),
        "choices": make_choice(
            "Find the missing memory.",
            "Ask Maya.",
            "Ask a teacher.",
            "Accept it.",
            "memory",
            "memory_maya",
            "memory_teacher",
            "accept"
        )
    }

    # --------------------------------------------------------
    # MORE BRANCHES
    # --------------------------------------------------------

    extra_nodes = {
        "voice": ("The Voice", "A voice from another reality answers your question."),
        "library": ("The Library", "The library contains a book describing today's events."),
        "object_maya": ("Maya Gets the Object", "Maya realizes the object reacts to decisions."),
        "turn_off": ("Silence", "You turn the object off, but something else turns on."),
        "find_taker": ("The Search", "You discover the object was taken toward the gym."),
        "teachers": ("The Teachers", "The adults don't believe you until the lights change."),
        "stay_out": ("Staying Out", "You avoid the mystery, but it follows you anyway."),
        "cameras": ("The Cameras", "The security footage shows two different versions of the same hallway."),
        "sam_truth": ("Sam's Secret", "Sam admits the drawing came from a dream that keeps repeating."),
        "follow_sam": ("Following Sam", "Sam leads you toward a place beneath the school."),
        "keep_drawing": ("The Drawing", "The drawing changes while you watch."),
        "destroy_drawing": ("Erasing Evidence", "Destroying the drawing causes the memory to disappear."),
        "message": ("The Message", "The message predicts your next decision."),
        "ignore_message": ("Ignoring It", "Ignoring the message causes another reality to notice you."),
        "public_truth": ("Everyone Knows", "The entire school sees evidence of the multiverse."),
        "source": ("The Source", "You find where the signal originates."),
        "approach_double": ("The Other Student", "The double claims they came from another world."),
        "hide_double": ("Hiding", "You stay hidden while the double searches for you."),
        "call_maya": ("Maya Arrives", "Maya immediately realizes what the double is."),
        "leave_school": ("Leaving", "You leave the school, but the strange world follows."),
        "photo": ("The Photograph", "The photograph changes when you make a decision."),
        "delete_photo": ("Deleting the Evidence", "The photograph disappears from reality."),
        "photo_maya": ("Maya Sees It", "Maya recognizes a building from another timeline."),
        "photo_jordan": ("Jordan's Reaction", "Jordan believes you and wants to investigate."),
        "voice_room": ("The Classroom", "You find another version of yourself."),
        "run": ("Running", "You run, but the hallway keeps repeating."),
        "call_sam": ("Sam's Help", "Sam says they have seen this before."),
        "answer_self": ("The Other You", "The voice tells you that your choices are changing worlds."),
        "memory": ("The Missing Memory", "You discover someone has been removed from reality."),
        "memory_maya": ("Maya Remembers", "Maya remembers something nobody else can."),
        "memory_teacher": ("The Teacher", "A teacher admits this has happened before."),
        "accept": ("Acceptance", "You accept the strange world and watch reality settle.")
    }

    # Connect every extra node to endings.
    ending_ids = [e["id"] for e in endings]

    for index, (node_id, info) in enumerate(extra_nodes.items()):
        title, text = info

        choices = make_choice(
            "Keep investigating.",
            "Trust the person beside you.",
            "Take a dangerous shortcut.",
            "Walk away.",
            ending_ids[index % 6],
            ending_ids[(index + 1) % 6],
            ending_ids[(index + 2) % 6],
            ending_ids[(index + 3) % 6]
        )

        nodes[node_id] = {
            "title": title,
            "text": text,
            "choices": choices
        }

    # Add a few special longer paths.
    nodes["trust_maya"] = {
        "title": "Trust",
        "text": f"Maya leads you toward {loc3}. She believes the answer is hidden there.",
        "choices": make_choice(
            "Follow her.",
            "Ask Jordan to come.",
            "Go alone.",
            "Turn back.",
            "follow_maya",
            "jordan_help",
            "alone_deep",
            "ending_1"
        )
    }

    nodes["maya_evidence"] = {
        "title": "More Evidence",
        "text": "Maya shows you several details that seem impossible to explain.",
        "choices": make_choice(
            "Believe her.",
            "Challenge the theory.",
            "Look for another explanation.",
            "Show everyone.",
            "follow_maya",
            "ending_3",
            "ending_5",
            "public_truth"
        )
    }

    nodes["alone"] = {
        "title": "Alone",
        "text": "You investigate without telling anyone. The mystery becomes more dangerous.",
        "choices": make_choice(
            "Continue.",
            "Stop.",
            "Search the library.",
            "Go underground.",
            "alone_deep",
            "ending_1",
            "library",
            "follow_sam"
        )
    }

    nodes["tell_student"] = {
        "title": "The Warning Spreads",
        "text": "You tell another student. Within minutes, the rumor spreads across the school.",
        "choices": make_choice(
            "Tell everyone.",
            "Stop the rumor.",
            "Use the rumor as a distraction.",
            "Find the source.",
            "public_truth",
            "ending_1",
            "ending_5",
            "source"
        )
    }

    nodes["jordan"] = {
        "title": "Jordan Joins",
        "text": "Jordan arrives and immediately treats the mystery like a challenge.",
        "choices": make_choice(
            "Let Jordan lead.",
            "Work together.",
            "Challenge Jordan.",
            "Leave Jordan behind.",
            "jordan_help",
            "ending_3",
            "ending_5",
            "ending_1"
        )
    }

    nodes["return_class"] = {
        "title": "Back to Class",
        "text": "You return to class. Everything seems normal until your teacher calls you by a name you don't recognize.",
        "choices": make_choice(
            "Correct them.",
            "Say nothing.",
            "Ask about the name.",
            "Leave the classroom.",
            "ending_5",
            "ending_1",
            "memory_teacher",
            "hallway"
        )
    }

    nodes["location_two"] = {
        "title": loc2,
        "text": f"You enter {loc2} and find a strange symbol carved into the wall.",
        "choices": make_choice(
            "Touch the symbol.",
            "Photograph it.",
            "Call Maya.",
            "Walk away.",
            "ending_6",
            "photo",
            "call_maya",
            "ending_1"
        )
    }

    nodes["follow_maya"] = {
        "title": "The Hidden Room",
        "text": f"Maya leads you beneath {loc3}. A hidden room contains evidence of several different school timelines.",
        "choices": make_choice(
            "Open the portal.",
            "Close the portal.",
            "Study the timelines.",
            "Destroy the machine.",
            "ending_6",
            "ending_4",
            "ending_3",
            "ending_5"
        )
    }

    nodes["jordan_help"] = {
        "title": "The Team",
        "text": "Jordan gathers a small group of students. For the first time, everyone works together.",
        "choices": make_choice(
            "Enter the anomaly.",
            "Protect the school.",
            "Expose everything.",
            "Let the anomaly decide.",
            "ending_6",
            "ending_1",
            "ending_3",
            "ending_2"
        )
    }

    nodes["alone_deep"] = {
        "title": "Beneath the School",
        "text": "You find a machine that appears to be watching every choice you have made.",
        "choices": make_choice(
            "Shut it down.",
            "Use it.",
            "Destroy it.",
            "Step inside it.",
            "ending_4",
            "ending_5",
            "ending_1",
            "ending_6"
        )
    }

    # --------------------------------------------------------
    # ENDINGS ARE INCLUDED IN TREE FOR DISPLAY
    # --------------------------------------------------------

    for ending in endings:
        nodes[ending["id"]] = {
            "title": ending["title"],
            "text": ending["text"],
            "ending": True,
            "choices": []
        }

    return {
        "title": scenario["title"],
        "theme": scenario["theme"],
        "start": "start",
        "nodes": nodes,
        "endings": endings
    }


# ============================================================
# STORY START
# ============================================================

@app.route("/story/start", methods=["POST"])
def story_start():
    # LOCAL GENERATION ONLY
    story = build_local_story()

    data["story"] = {
        "active": True,
        "story_id": random.randint(100000, 999999),
        "title": story["title"],
        "theme": story["theme"],
        "current_node": story["start"],
        "history": [],
        "seen_nodes": ["start"],
        "ending": None,
        "tree": story
    }

    add_world_memory(
        f"Started story: {story['title']}"
    )

    save_data()

    return jsonify({
        "success": True,
        "story": data["story"]
    })


# ============================================================
# STORY CHOICE
# ============================================================

@app.route("/story/choose", methods=["POST"])
def story_choose():
    body = request.get_json(silent=True) or {}

    choice_id = clean_text(body.get("choice"))

    if not data["story"]["active"]:
        return jsonify({
            "error": "There is no active story."
        }), 400

    story = data["story"]["tree"]

    current_id = data["story"]["current_node"]

    node = story.get("nodes", {}).get(current_id)

    if not node:
        return jsonify({
            "error": "Current story node not found."
        }), 404

    choice = None

    for option in node.get("choices", []):
        if option.get("id") == choice_id:
            choice = option
            break

    if not choice:
        return jsonify({
            "error": "Invalid choice."
        }), 400

    next_id = choice["next"]

    data["story"]["history"].append({
        "node": current_id,
        "choice": choice_id,
        "choice_text": choice.get("text", ""),
        "next": next_id
    })

    data["story"]["current_node"] = next_id

    if next_id not in data["story"]["seen_nodes"]:
        data["story"]["seen_nodes"].append(next_id)

    next_node = story.get("nodes", {}).get(next_id)

    if next_node and next_node.get("ending"):
        data["story"]["ending"] = {
            "id": next_id,
            "title": next_node["title"],
            "text": next_node["text"]
        }

        data["story"]["active"] = False

        add_world_memory(
            f"Story ending reached: {next_node['title']}"
        )

    save_data()

    return jsonify({
        "success": True,
        "story": data["story"],
        "node": next_node
    })


# ============================================================
# STORY TREE
# ============================================================

@app.route("/story/tree", methods=["GET"])
def story_tree():
    story = data["story"]

    return jsonify({
        "title": story["title"],
        "theme": story["theme"],
        "tree": story["tree"],
        "seen_nodes": story["seen_nodes"],
        "history": story["history"],
        "ending": story["ending"],
        "active": story["active"]
    })


# ============================================================
# REPLAY CURRENT WORLD
# ============================================================

@app.route("/story/replay", methods=["POST"])
def replay_story():
    if not data["story"].get("tree"):
        return jsonify({
            "error": "There is no story to replay."
        }), 400

    story = data["story"]["tree"]

    data["story"] = {
        "active": True,
        "story_id": random.randint(100000, 999999),
        "title": story.get("title", "Story"),
        "theme": story.get("theme", ""),
        "current_node": story.get("start", "start"),
        "history": [],
        "seen_nodes": [story.get("start", "start")],
        "ending": None,
        "tree": story
    }

    save_data()

    return jsonify({
        "success": True,
        "story": data["story"]
    })


# ============================================================
# SELF IMPROVEMENT
# ============================================================

@app.route("/improvement", methods=["GET"])
def get_improvement():
    return jsonify(data["improvement"])


@app.route("/improvement/learn", methods=["POST"])
def improvement_learn():
    body = request.get_json(silent=True) or {}

    lesson = clean_text(body.get("lesson"))

    if not lesson:
        return jsonify({
            "error": "Lesson is required."
        }), 400

    add_improvement(lesson)

    save_data()

    return jsonify({
        "success": True,
        "improvement": data["improvement"]
    })


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "ai_configured": bool(API_KEY),
        "model": MODEL,
        "story_mode": "local",
        "world": data["world_number"]
    })


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
