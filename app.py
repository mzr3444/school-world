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

# IMPORTANT:
# Use the exact model slug supplied by your OpenRouter account.
# The old "...:free" version can return a 404 if it is no longer free.
MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b")

client = None

if API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY
    )


# ============================================================
# STORAGE
# ============================================================

DATA_FILE = "school_world_data.json"
LOCK = threading.Lock()


# ============================================================
# DEFAULT CHARACTERS
# ============================================================

DEFAULT_CHARACTERS = [
    {
        "id": "alex",
        "name": "Alex",
        "role": "Student",
        "personality": "Friendly, curious, funny, energetic, impulsive, and social.",
        "description": "Alex likes meeting people and turning boring situations into something interesting.",
        "traits": ["Friendly", "Curious", "Funny", "Energetic"],
        "memory": [],
        "conversation": []
    },
    {
        "id": "maya",
        "name": "Maya",
        "role": "Student",
        "personality": "Intelligent, calm, observant, sarcastic, independent, and thoughtful.",
        "description": "Maya notices details other people miss and thinks carefully before speaking.",
        "traits": ["Smart", "Calm", "Observant", "Sarcastic"],
        "memory": [],
        "conversation": []
    },
    {
        "id": "jordan",
        "name": "Jordan",
        "role": "Student",
        "personality": "Confident, competitive, outgoing, playful, stubborn, and ambitious.",
        "description": "Jordan loves competition and enjoys challenging people.",
        "traits": ["Confident", "Competitive", "Outgoing", "Stubborn"],
        "memory": [],
        "conversation": []
    },
    {
        "id": "sam",
        "name": "Sam",
        "role": "Student",
        "personality": "Quiet, creative, kind, thoughtful, observant, and slightly mysterious.",
        "description": "Sam likes drawing, reading, and quietly observing what happens around school.",
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
# HELPERS
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = text.replace("\x00", "")
    text = re.sub(r"```(?:json|python|html)?", "", text, flags=re.I)
    text = text.replace("```", "")

    return text.strip()


def trim(items, amount):
    if not isinstance(items, list):
        return []

    return items[-amount:]


def find_character(character_id):
    for character in data["characters"]:
        if character["id"] == character_id:
            return character

    return None


def remember(character, text):
    text = clean_text(text)

    if not text:
        return

    character.setdefault("memory", [])
    character["memory"].append(text)
    character["memory"] = trim(character["memory"], 50)


def world_memory(text):
    text = clean_text(text)

    if not text:
        return

    data.setdefault("world_memory", [])
    data["world_memory"].append(text)
    data["world_memory"] = trim(data["world_memory"], 100)


def improvement(text):
    text = clean_text(text)

    if not text:
        return

    facts = data["improvement"].setdefault("facts", [])

    if text not in facts:
        facts.append(text)

    data["improvement"]["facts"] = trim(facts, 100)


def save_data(obj):
    with LOCK:
        temporary = DATA_FILE + ".tmp"

        with open(temporary, "w", encoding="utf-8") as f:
            json.dump(
                obj,
                f,
                indent=2,
                ensure_ascii=False
            )

        os.replace(temporary, DATA_FILE)


# ============================================================
# WORLD CREATION
# ============================================================

def make_universe():
    return {
        "id": random.randint(100000, 999999),
        "timeline": random.randint(1000, 9999),
        "created": datetime.utcnow().isoformat(),
        "anomaly_level": random.randint(0, 8),
        "crossovers": [],
        "alternate_characters": [],
        "events": []
    }


def default_story():
    return {
        "active": False,
        "story_id": random.randint(100000, 999999),
        "title": "",
        "theme": "",
        "current_node": "start",
        "history": [],
        "seen_nodes": [],
        "ending": None,
        "nodes": {},
        "endings": []
    }


def default_data():
    universe = make_universe()

    return {
        "world_number": 1,
        "world_id": random.randint(100000, 999999),

        "player_location": "Classroom",

        "characters": json.loads(
            json.dumps(DEFAULT_CHARACTERS)
        ),

        "locations": list(DEFAULT_LOCATIONS),

        "world_memory": [],

        "background_events": [],

        "universe": universe,

        "saved_universes": [],

        "story": default_story(),

        "improvement": {
            "facts": [],
            "preferences": [],
            "successful_patterns": [],
            "relationship_notes": []
        }
    }


def load_data():
    if not os.path.exists(DATA_FILE):
        result = default_data()
        save_data(result)
        return result

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            result = json.load(f)

        base = default_data()

        for key, value in base.items():
            if key not in result:
                result[key] = value

        return result

    except Exception:
        result = default_data()
        save_data(result)
        return result


data = load_data()


# ============================================================
# AI
# ============================================================

def call_ai(system_prompt, messages=None, temperature=0.8, max_tokens=600):
    if messages is None:
        messages = []

    if not client:
        return "AI_ERROR: No API key configured."

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
            return "AI_ERROR: The model returned no choices."

        content = response.choices[0].message.content

        if not content:
            return "AI_ERROR: The model returned an empty response."

        return clean_text(content)

    except Exception as exc:
        return "AI_ERROR: " + str(exc)


def ai_json(system_prompt, max_tokens=1800):
    result = call_ai(
        system_prompt,
        [],
        temperature=0.9,
        max_tokens=max_tokens
    )

    if result.startswith("AI_ERROR:"):
        return None, result

    result = clean_text(result)

    # Try normal JSON.
    try:
        return json.loads(result), None
    except Exception:
        pass

    # Find JSON object.
    start = result.find("{")
    end = result.rfind("}")

    if start >= 0 and end > start:
        try:
            return json.loads(result[start:end + 1]), None
        except Exception:
            pass

    # Find JSON array.
    start = result.find("[")
    end = result.rfind("]")

    if start >= 0 and end > start:
        try:
            return json.loads(result[start:end + 1]), None
        except Exception:
            pass

    return None, "AI_ERROR: The AI returned invalid JSON."


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
        "world_number": data["world_number"],
        "world_id": data["world_id"],
        "location": data["player_location"],
        "characters": data["characters"],
        "locations": data["locations"],
        "universe": data["universe"],
        "saved_universes": data["saved_universes"],
        "story": data["story"],
        "improvement": data["improvement"],
        "background_events": data["background_events"][-10:]
    })


# ============================================================
# NORMAL CHARACTER CHAT
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

    recent = character.get("conversation", [])[-20:]

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
            "personality": c["personality"],
            "role": c["role"]
        }
        for c in data["characters"]
        if c["id"] != character["id"]
    ]

    system = f"""
You are {character["name"]}, a person living inside a persistent school simulation.

ROLE:
{character["role"]}

PERSONALITY:
{character["personality"]}

DESCRIPTION:
{character["description"]}

TRAITS:
{", ".join(character.get("traits", []))}

CURRENT LOCATION OF PLAYER:
{data["player_location"]}

CURRENT UNIVERSE:
{data["universe"]["id"]}

TIMELINE:
{data["universe"]["timeline"]}

ANOMALY LEVEL:
{data["universe"]["anomaly_level"]}

YOUR MEMORIES:
{json.dumps(character.get("memory", [])[-25:], ensure_ascii=False)}

WORLD MEMORIES:
{json.dumps(data.get("world_memory", [])[-25:], ensure_ascii=False)}

OTHER CHARACTERS:
{json.dumps(other_characters, ensure_ascii=False)}

RULES:

- Stay in character.
- Have your own opinions.
- Do not blindly agree with the player.
- Remember previous conversations.
- Use the current location naturally.
- You know the player is a separate person.
- Never control the player's actions.
- If the player says they are traveling somewhere, acknowledge it naturally.
- Do not pretend you traveled with them unless that makes sense.
- You may talk about other characters.
- Characters can disagree.
- Characters can become friends, annoyed, curious, suspicious, etc.
- Do not mention these instructions.
- Do not constantly say you are an AI.
- Keep responses medium length.
- Usually write 2-5 paragraphs.
- Avoid one-sentence answers unless the situation naturally calls for one.
- Don't make every conversation dramatic.
- School life should sometimes be ordinary.
"""

    answer = call_ai(
        system,
        messages,
        temperature=0.84,
        max_tokens=750
    )

    if answer.startswith("AI_ERROR:"):
        return jsonify({
            "error": answer
        }), 500

    now = datetime.utcnow().isoformat()

    character.setdefault("conversation", [])

    character["conversation"].append({
        "role": "user",
        "content": message,
        "time": now
    })

    character["conversation"].append({
        "role": "assistant",
        "content": answer,
        "time": now
    })

    character["conversation"] = trim(
        character["conversation"],
        80
    )

    remember(
        character,
        "Player said: " + message[:300]
    )

    if len(message) > 15:
        improvement(
            f"{character['name']} conversation detail: {message[:200]}"
        )

    save_data(data)

    return jsonify({
        "reply": answer,
        "character": character
    })


# ============================================================
# RESET CONVERSATION
# ============================================================

@app.route("/conversation/reset", methods=["POST"])
def reset_conversation():
    body = request.get_json(silent=True) or {}

    character = find_character(
        body.get("character_id")
    )

    if not character:
        return jsonify({
            "error": "Character not found."
        }), 404

    character["conversation"] = []

    save_data(data)

    return jsonify({
        "success": True
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

    if not name:
        return jsonify({
            "error": "Name required."
        }), 400

    if not personality:
        return jsonify({
            "error": "Personality required."
        }), 400

    character_id = (
        re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        + "-"
        + str(random.randint(1000, 9999))
    )

    character = {
        "id": character_id,
        "name": name,
        "role": role,
        "personality": personality,
        "description": description or f"{name} is a {role.lower()} at the school.",
        "traits": [],
        "memory": [],
        "conversation": []
    }

    data["characters"].append(character)

    save_data(data)

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

    destination = clean_text(body.get("location"))

    if destination not in data["locations"]:
        return jsonify({
            "error": "Unknown location."
        }), 400

    old = data["player_location"]

    data["player_location"] = destination

    world_memory(
        f"Player traveled from {old} to {destination}."
    )

    # Small anomaly increase from unusual events.
    if random.random() < 0.08:
        data["universe"]["anomaly_level"] += 1

    save_data(data)

    return jsonify({
        "success": True,
        "location": destination
    })


# ============================================================
# BACKGROUND CHARACTER LIFE
# ============================================================

@app.route("/world/advance", methods=["POST"])
def advance_world():
    if len(data["characters"]) < 2:
        return jsonify({
            "event": "Not enough characters."
        })

    a, b = random.sample(data["characters"], 2)

    location = random.choice(data["locations"])

    prompt = f"""
Generate a natural background school interaction.

CHARACTER A:
{a["name"]}
Personality: {a["personality"]}

CHARACTER B:
{b["name"]}
Personality: {b["personality"]}

LOCATION:
{location}

The player is NOT participating.

Sometimes they should:
- joke
- disagree
- study
- gossip
- help each other
- misunderstand something
- talk about school
- become closer
- become annoyed
- discover information
- simply have a normal conversation

Do not make every event dramatic.

Write 4-8 sentences.

Do not control the player.
"""

    event = call_ai(
        prompt,
        [],
        temperature=0.95,
        max_tokens=450
    )

    if event.startswith("AI_ERROR:"):
        return jsonify({
            "error": event
        }), 500

    record = {
        "characters": [a["name"], b["name"]],
        "location": location,
        "event": event,
        "time": datetime.utcnow().isoformat(),
        "universe": data["universe"]["id"]
    }

    data["background_events"].append(record)
    data["background_events"] = trim(
        data["background_events"],
        50
    )

    remember(
        a,
        f"Background interaction with {b['name']} at {location}: {event[:250]}"
    )

    remember(
        b,
        f"Background interaction with {a['name']} at {location}: {event[:250]}"
    )

    world_memory(
        f"{a['name']} and {b['name']} had an interaction at {location}."
    )

    save_data(data)

    return jsonify({
        "success": True,
        "event": record
    })


# ============================================================
# MULTIVERSE
# ============================================================

def create_alternate_character(original):
    return {
        "id": (
            original["id"]
            + "-alt-"
            + str(random.randint(1000, 9999))
        ),
        "name": original["name"],
        "original_character": original["id"],
        "universe": data["universe"]["id"],
        "personality": original["personality"],
        "variation": random.choice([
            "more serious",
            "more confident",
            "more quiet",
            "more rebellious",
            "more optimistic",
            "more suspicious",
            "more emotional",
            "more analytical"
        ]),
        "memory": []
    }


def generate_crossover():
    saved = data.get("saved_universes", [])

    if not saved:
        return None, "No alternate universes exist yet."

    other = random.choice(saved)

    current_chars = data["characters"]

    if not current_chars:
        return None, "No characters available."

    original = random.choice(current_chars)

    alternate = create_alternate_character(original)

    prompt = f"""
Create a multiverse crossover event in a school simulation.

CURRENT UNIVERSE:
{data["universe"]["id"]}

CURRENT TIMELINE:
{data["universe"]["timeline"]}

OTHER UNIVERSE:
{other.get("id")}

OTHER TIMELINE:
{other.get("timeline")}

CHARACTER FROM CURRENT UNIVERSE:
Name: {original["name"]}
Personality: {original["personality"]}

ALTERNATE VERSION:
Variation: {alternate["variation"]}

CURRENT LOCATION:
{data["player_location"]}

Write a cinematic but original crossover event.

The alternate character should feel like the same person from another life,
but clearly have differences.

The event should create questions rather than explain everything immediately.

Include:

1. What the player sees.
2. How the characters react.
3. Why the crossover might be happening.
4. A meaningful choice for the player.

Return JSON:

{{
    "title": "event title",
    "description": "event description",
    "alternate_character_dialogue": "dialogue",
    "choice_a": "choice",
    "choice_b": "choice",
    "choice_c": "choice",
    "choice_d": "choice",
    "anomaly_change": 10
}}
"""

    result, error = ai_json(
        prompt,
        max_tokens=1400
    )

    if error:
        return None, error

    alternate["dialogue"] = result.get(
        "alternate_character_dialogue",
        ""
    )

    data["universe"]["alternate_characters"].append(
        alternate
    )

    data["universe"]["crossovers"].append({
        "from_universe": other.get("id"),
        "to_universe": data["universe"]["id"],
        "character": original["name"],
        "time": datetime.utcnow().isoformat(),
        "event": result
    })

    amount = int(
        result.get("anomaly_change", 10)
    )

    data["universe"]["anomaly_level"] = min(
        100,
        data["universe"]["anomaly_level"] + amount
    )

    world_memory(
        f"Multiversal crossover involving {original['name']} occurred."
    )

    save_data(data)

    return result, None


@app.route("/multiverse/status", methods=["GET"])
def multiverse_status():
    return jsonify({
        "universe": data["universe"],
        "saved_universes": data["saved_universes"]
    })


@app.route("/multiverse/crossover", methods=["POST"])
def crossover():
    # Crossover probability increases as anomaly rises.
    anomaly = data["universe"]["anomaly_level"]

    result, error = generate_crossover()

    if error:
        return jsonify({
            "error": error
        }), 500

    return jsonify({
        "success": True,
        "event": result,
        "anomaly_level": data["universe"]["anomaly_level"],
        "universe": data["universe"]
    })


# ============================================================
# CREATE / RESET UNIVERSE
# ============================================================

@app.route("/world/reset", methods=["POST"])
def reset_world():
    global data

    # Save current universe before leaving it.
    saved = {
        "world_number": data["world_number"],
        "world_id": data["world_id"],
        "universe": data["universe"],
        "characters": data["characters"],
        "locations": data["locations"],
        "story": data["story"],
        "world_memory": data["world_memory"],
        "background_events": data["background_events"]
    }

    old_saved = data.get("saved_universes", [])

    # Avoid huge storage.
    old_saved.append(saved)
    old_saved = old_saved[-25:]

    new_data = default_data()

    new_data["world_number"] = data["world_number"] + 1
    new_data["world_id"] = random.randint(
        100000,
        999999
    )

    new_data["saved_universes"] = old_saved

    data = new_data

    save_data(data)

    return jsonify({
        "success": True,
        "message": "A new universe has been created.",
        "world_number": data["world_number"],
        "world_id": data["world_id"],
        "universe": data["universe"]
    })


@app.route("/multiverse/replay", methods=["POST"])
def replay_universe():
    global data

    body = request.get_json(silent=True) or {}

    world_id = body.get("world_id")

    if not world_id:
        return jsonify({
            "error": "world_id required."
        }), 400

    selected = None

    for universe in data.get("saved_universes", []):
        if str(universe.get("world_id")) == str(world_id):
            selected = universe
            break

    if not selected:
        return jsonify({
            "error": "Universe not found."
        }), 404

    # Save current universe before switching.
    current = {
        "world_number": data["world_number"],
        "world_id": data["world_id"],
        "universe": data["universe"],
        "characters": data["characters"],
        "locations": data["locations"],
        "story": data["story"],
        "world_memory": data["world_memory"],
        "background_events": data["background_events"]
    }

    remaining = [
        u for u in data.get("saved_universes", [])
        if str(u.get("world_id")) != str(world_id)
    ]

    remaining.append(current)

    data = {
        "world_number": selected["world_number"],
        "world_id": selected["world_id"],
        "player_location": "Classroom",
        "characters": selected["characters"],
        "locations": selected["locations"],
        "world_memory": selected["world_memory"],
        "background_events": selected["background_events"],
        "universe": selected["universe"],
        "saved_universes": remaining[-25:],
        "story": selected["story"],
        "improvement": {
            "facts": [],
            "preferences": [],
            "successful_patterns": [],
            "relationship_notes": []
        }
    }

    save_data(data)

    return jsonify({
        "success": True,
        "world": data
    })


# ============================================================
# STORY MODE
# ============================================================

STORY_THEMES = [
    "A mysterious event begins during an ordinary school day.",
    "A strange discovery inside the school changes everything.",
    "A rumor spreads and slowly reveals a hidden truth.",
    "A school competition becomes more serious than expected.",
    "A friendship begins to fall apart after a strange incident.",
    "A student discovers something that should not exist.",
    "A normal school event turns into an unexplained mystery.",
    "A secret room is discovered inside the school.",
    "A strange object appears in the library.",
    "Someone remembers an event that never happened."
]


def generate_story_start():
    theme = random.choice(STORY_THEMES)

    characters = [
        {
            "name": c["name"],
            "personality": c["personality"]
        }
        for c in data["characters"]
    ]

    prompt = f"""
Create the beginning of a branching interactive school story.

THEME:
{theme}

UNIVERSE:
{data["universe"]["id"]}

CHARACTERS:
{json.dumps(characters, ensure_ascii=False)}

Create the opening scene.

Return ONLY JSON:

{{
  "title": "story title",
  "theme": "story theme",
  "node": {{
    "id": "start",
    "title": "scene title",
    "text": "long scene description",
    "choices": [
      {{"id":"A","text":"choice"}},
      {{"id":"B","text":"choice"}},
      {{"id":"C","text":"choice"}},
      {{"id":"D","text":"choice"}}
    ]
  }}
}}

The scene should be detailed enough to feel like a real story.
Each choice must represent a genuinely different action.
"""

    return ai_json(prompt, max_tokens=1800)


def generate_story_next(previous_node, choice):
    characters = [
        {
            "name": c["name"],
            "personality": c["personality"]
        }
        for c in data["characters"]
    ]

    prompt = f"""
Continue a branching interactive school story.

STORY:
{data["story"]["title"]}

CURRENT SCENE:
{previous_node.get("text", "")}

PLAYER CHOSE:
{choice.get("text", "")}

CHARACTERS:
{json.dumps(characters, ensure_ascii=False)}

WORLD:
Universe {data["universe"]["id"]}
Location: {data["player_location"]}

This choice MUST matter.

Generate the next scene.

Sometimes a branch may move toward an ending.
Do not immediately reconnect every branch.

Return JSON:

{{
  "node": {{
    "id": "unique_node_id",
    "title": "scene title",
    "text": "detailed scene",
    "choices": [
      {{"id":"A","text":"choice"}},
      {{"id":"B","text":"choice"}},
      {{"id":"C","text":"choice"}},
      {{"id":"D","text":"choice"}}
    ],
    "ending": null
  }}
}}

OR if this branch ends:

{{
  "node": {{
    "id": "unique_node_id",
    "title": "ending title",
    "text": "detailed ending",
    "choices": [],
    "ending": {{
      "id": "ending_unique_id",
      "title": "ending title",
      "text": "detailed ending"
    }}
  }}
}}
"""

    return ai_json(prompt, max_tokens=2200)


@app.route("/story/start", methods=["POST"])
def story_start():
    result, error = generate_story_start()

    if error:
        return jsonify({
            "error": "Story generator failed: " + error
        }), 500

    node = result.get("node")

    if not node:
        return jsonify({
            "error": "Story generator returned no starting scene."
        }), 500

    data["story"] = {
        "active": True,
        "story_id": random.randint(100000, 999999),
        "title": result.get("title", "Untitled Story"),
        "theme": result.get("theme", ""),
        "current_node": "start",
        "history": [],
        "seen_nodes": ["start"],
        "ending": None,
        "nodes": {
            "start": node
        },
        "endings": []
    }

    world_memory(
        f"Started story: {data['story']['title']}"
    )

    save_data(data)

    return jsonify({
        "success": True,
        "story": data["story"]
    })


@app.route("/story/choose", methods=["POST"])
def story_choose():
    body = request.get_json(silent=True) or {}

    choice_id = clean_text(body.get("choice"))

    story = data["story"]

    if not story.get("active"):
        return jsonify({
            "error": "No active story."
        }), 400

    current_id = story["current_node"]

    node = story["nodes"].get(current_id)

    if not node:
        return jsonify({
            "error": "Current story node not found."
        }), 404

    selected = None

    for choice in node.get("choices", []):
        if choice.get("id") == choice_id:
            selected = choice
            break

    if not selected:
        return jsonify({
            "error": "Invalid choice."
        }), 400

    story["history"].append({
        "node": current_id,
        "choice": choice_id,
        "text": selected.get("text", "")
    })

    result, error = generate_story_next(
        node,
        selected
    )

    if error:
        return jsonify({
            "error": "Story continuation failed: " + error
        }), 500

    next_node = result.get("node")

    if not next_node:
        return jsonify({
            "error": "Story continuation returned no node."
        }), 500

    node_id = next_node.get(
        "id",
        "node-" + str(random.randint(100000, 999999))
    )

    next_node["id"] = node_id

    story["nodes"][node_id] = next_node
    story["current_node"] = node_id

    if node_id not in story["seen_nodes"]:
        story["seen_nodes"].append(node_id)

    ending = next_node.get("ending")

    if ending:
        story["ending"] = ending
        story["endings"].append(ending)
        story["active"] = False

    save_data(data)

    return jsonify({
        "success": True,
        "story": story,
        "node": next_node,
        "ending": ending
    })


@app.route("/story/tree", methods=["GET"])
def story_tree():
    return jsonify(data["story"])


# ============================================================
# IMPROVEMENT
# ============================================================

@app.route("/improvement", methods=["GET"])
def get_improvement():
    return jsonify(data["improvement"])


@app.route("/improvement/learn", methods=["POST"])
def learn():
    body = request.get_json(silent=True) or {}

    lesson = clean_text(body.get("lesson"))

    if not lesson:
        return jsonify({
            "error": "Lesson required."
        }), 400

    improvement(lesson)

    save_data(data)

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
        "world": data["world_number"],
        "universe": data["universe"]["id"],
        "anomaly": data["universe"]["anomaly_level"]
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
