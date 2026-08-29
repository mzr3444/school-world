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
MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b")

if API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY
    )
else:
    client = None


# ============================================================
# DATA
# ============================================================

DATA_FILE = "school_world_data.json"

data_lock = threading.Lock()

DEFAULT_CHARACTERS = [
    {
        "id": "alex",
        "name": "Alex",
        "role": "Student",
        "personality": "Friendly, curious, funny, energetic, and sometimes impulsive.",
        "description": "Alex likes meeting people and usually tries to turn boring situations into something interesting.",
        "traits": ["Friendly", "Curious", "Funny", "Impulsive"],
        "memory": [],
        "conversation": []
    },
    {
        "id": "maya",
        "name": "Maya",
        "role": "Student",
        "personality": "Intelligent, calm, observant, sarcastic, and independent.",
        "description": "Maya notices details other people miss and tends to think before she speaks.",
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
        "description": "Sam spends a lot of time drawing, reading, and observing what happens around the school.",
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


def default_data():
    return {
        "world_id": random.randint(100000, 999999),
        "world_number": 1,
        "player_location": "Classroom",
        "characters": DEFAULT_CHARACTERS,
        "locations": DEFAULT_LOCATIONS,
        "world_memory": [],
        "background_events": [],
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


def load_data():
    if not os.path.exists(DATA_FILE):
        data = default_data()
        save_data(data)
        return data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Safety defaults for older versions.
        base = default_data()

        for key, value in base.items():
            if key not in data:
                data[key] = value

        return data

    except Exception:
        data = default_data()
        save_data(data)
        return data


def save_data(data):
    with data_lock:
        temp_file = DATA_FILE + ".tmp"

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        os.replace(temp_file, DATA_FILE)


data = load_data()


# ============================================================
# HELPERS
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)

    # Remove accidental model formatting.
    text = text.replace("\x00", "")
    text = re.sub(r"```(?:json|python|html)?", "", text, flags=re.I)
    text = text.replace("```", "")

    return text.strip()


def find_character(character_id):
    for character in data["characters"]:
        if character["id"] == character_id:
            return character

    return None


def trim_memory(items, limit=30):
    if len(items) <= limit:
        return items

    return items[-limit:]


def remember(character, text):
    text = clean_text(text)

    if not text:
        return

    character.setdefault("memory", [])
    character["memory"].append(text)
    character["memory"] = trim_memory(character["memory"], 40)


def add_world_memory(text):
    text = clean_text(text)

    if not text:
        return

    data.setdefault("world_memory", [])
    data["world_memory"].append(text)
    data["world_memory"] = trim_memory(data["world_memory"], 50)


def add_improvement(text):
    text = clean_text(text)

    if not text:
        return

    improvements = data["improvement"]["facts"]

    if text not in improvements:
        improvements.append(text)

    data["improvement"]["facts"] = trim_memory(improvements, 50)


def call_ai(system_prompt, messages, temperature=0.8, max_tokens=700):
    if not client:
        return "The AI connection is not configured yet. Add your OPENROUTER_API_KEY in Render."

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

        result = response.choices[0].message.content

        return clean_text(result)

    except Exception as e:
        return f"AI_ERROR: {str(e)}"


def safe_json_from_ai(text):
    text = clean_text(text)

    # Remove markdown fences.
    text = re.sub(r"```json", "", text, flags=re.I)
    text = text.replace("```", "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    # Try extracting the largest JSON object.
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass

    return None


# ============================================================
# HOME
# ============================================================

@app.route("/", methods=["GET", "HEAD"])
def home():
    return render_template("index.html")


# ============================================================
# WORLD INFORMATION
# ============================================================

@app.route("/world", methods=["GET"])
def get_world():
    return jsonify({
        "world_id": data["world_id"],
        "world_number": data["world_number"],
        "location": data["player_location"],
        "characters": data["characters"],
        "locations": data["locations"],
        "story": data["story"],
        "improvement": data["improvement"]
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
            "error": "character_id and message are required"
        }), 400

    character = find_character(character_id)

    if not character:
        return jsonify({
            "error": "Character not found"
        }), 404

    # Remember what the player said.
    remember(
        character,
        f"Player said: {message}"
    )

    recent_conversation = character.get("conversation", [])[-16:]

    messages = []

    for item in recent_conversation:
        messages.append({
            "role": item["role"],
            "content": item["content"]
        })

    messages.append({
        "role": "user",
        "content": message
    })

    location = data["player_location"]

    system_prompt = f"""
You are {character["name"]}, a character inside a living school simulation.

ROLE:
{character["role"]}

PERSONALITY:
{character["personality"]}

DESCRIPTION:
{character["description"]}

TRAITS:
{", ".join(character.get("traits", []))}

CURRENT LOCATION:
{location}

WORLD NUMBER:
{data["world_number"]}

IMPORTANT CHARACTER MEMORY:
{json.dumps(character.get("memory", [])[-20:], ensure_ascii=False)}

WORLD MEMORY:
{json.dumps(data.get("world_memory", [])[-20:], ensure_ascii=False)}

OTHER CHARACTERS:
{json.dumps([
    {
        "name": c["name"],
        "role": c["role"],
        "personality": c["personality"]
    }
    for c in data["characters"]
    if c["id"] != character["id"]
], ensure_ascii=False)}

RULES:

1. Stay in character.
2. Remember previous conversations when relevant.
3. Give medium-length natural responses.
4. Usually respond with 2-5 paragraphs or a few natural sentences.
5. Do not constantly mention being an AI.
6. Do not describe yourself as a chatbot.
7. React naturally to what the player says.
8. You know where you are in the school.
9. You can mention other characters when it makes sense.
10. You can have opinions, preferences, disagreements, jokes, and emotions appropriate to your personality.
11. Do not blindly agree with the player.
12. If the player says they are traveling somewhere, react naturally to the information but do not pretend you are physically traveling with them unless the conversation makes that logical.
13. The player is a separate person from you.
14. Never control the player's actions.
15. You can remember important events from conversations.
16. Do not make every response extremely long.
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

    character["conversation"] = trim_memory(
        character["conversation"],
        60
    )

    # Controlled learning/memory.
    if len(message) > 20:
        add_improvement(
            f"Conversation pattern with {character['name']}: {message[:180]}"
        )

    save_data(data)

    return jsonify({
        "reply": answer,
        "character": character,
        "location": location
    })


# ============================================================
# RESET ONE CONVERSATION
# ============================================================

@app.route("/conversation/reset", methods=["POST"])
def reset_conversation():
    body = request.get_json(silent=True) or {}

    character_id = body.get("character_id")

    character = find_character(character_id)

    if not character:
        return jsonify({
            "error": "Character not found"
        }), 404

    character["conversation"] = []

    save_data(data)

    return jsonify({
        "success": True,
        "message": f"Conversation with {character['name']} was reset."
    })


# ============================================================
# NEW TEXT
# ============================================================

@app.route("/conversation/new", methods=["POST"])
def new_text():
    return jsonify({
        "success": True,
        "message": "New conversation started."
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
            "error": "Character name is required."
        }), 400

    if not personality:
        return jsonify({
            "error": "Character personality is required."
        }), 400

    if not isinstance(traits, list):
        traits = []

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
        "traits": [clean_text(x) for x in traits if clean_text(x)],
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
# CHARACTER TO CHARACTER BACKGROUND LIFE
# ============================================================

@app.route("/world/advance", methods=["POST"])
def world_advance():
    if len(data["characters"]) < 2:
        return jsonify({
            "event": "There are not enough characters for a background interaction."
        })

    first, second = random.sample(data["characters"], 2)

    locations = data["locations"]

    location = random.choice(locations)

    system_prompt = f"""
You are generating a short background event for a living school simulation.

Character A:
Name: {first["name"]}
Personality: {first["personality"]}

Character B:
Name: {second["name"]}
Personality: {second["personality"]}

Location:
{location}

Generate a natural interaction between them.

Do not make it overly dramatic every time.
Sometimes they should joke, disagree, study, gossip, help each other,
talk about school, misunderstand something, or simply have an ordinary interaction.

Keep it around 3-7 sentences.

Do not control the player.
"""

    event = call_ai(
        system_prompt,
        [],
        temperature=0.9,
        max_tokens=350
    )

    if event.startswith("AI_ERROR:"):
        return jsonify({
            "error": event
        }), 500

    background = {
        "characters": [first["name"], second["name"]],
        "location": location,
        "event": event,
        "time": datetime.utcnow().isoformat()
    }

    data["background_events"].append(background)
    data["background_events"] = trim_memory(
        data["background_events"],
        40
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

    save_data(data)

    return jsonify({
        "success": True,
        "event": background
    })


# ============================================================
# PLAYER TRAVEL
# ============================================================

@app.route("/world/travel", methods=["POST"])
def travel():
    body = request.get_json(silent=True) or {}

    location = clean_text(body.get("location"))

    if location not in data["locations"]:
        return jsonify({
            "error": "Unknown location."
        }), 400

    old_location = data["player_location"]

    data["player_location"] = location

    add_world_memory(
        f"Player traveled from {old_location} to {location}."
    )

    save_data(data)

    return jsonify({
        "success": True,
        "location": location
    })


# ============================================================
# RESET WORLD
# ============================================================

@app.route("/world/reset", methods=["POST"])
def reset_world():
    global data

    old_world = data["world_number"]

    new_data = default_data()

    new_data["world_number"] = old_world + 1
    new_data["world_id"] = random.randint(100000, 999999)

    # Create a completely new story seed.
    new_data["story"]["story_id"] = random.randint(
        100000,
        999999
    )

    data = new_data

    save_data(data)

    return jsonify({
        "success": True,
        "world_number": data["world_number"],
        "world_id": data["world_id"],
        "message": "World reset. Memories and story progression were cleared."
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
    "A student disappears from class and several people know something.",
    "A strange object is discovered inside the school.",
    "A school event goes completely wrong.",
    "A rumor spreads through the school and changes everyone's behavior."
]


def generate_story():
    theme = random.choice(STORY_THEMES)

    story_system = f"""
Create a branching interactive school story.

THEME:
{theme}

The story should feel like a choice-driven narrative game.

Requirements:

- 5 major endings minimum.
- 12-20 total meaningful story nodes.
- Choices must actually change future events.
- Choices should affect relationships, locations, information, trust,
  opportunities, and future decisions.
- Do not make every branch reconnect immediately.
- Some branches should be unavailable because of earlier choices.
- The player gets exactly four choices: A, B, C, D.
- Each node should have consequences.
- Characters should behave according to their personalities.
- The story should be different for every new world.
- The story should feel coherent from beginning to end.
- Include some ordinary school moments between major events.
- The player should never know which choice is the "correct" ending.
- Avoid copying famous copyrighted game stories.

Return ONLY valid JSON.

Schema:

{{
  "title": "story title",
  "theme": "short theme",
  "start": "start",
  "nodes": {{
    "start": {{
      "title": "Scene title",
      "text": "Scene description",
      "choices": [
        {{
          "id": "A",
          "text": "Choice text",
          "next": "node_id"
        }},
        {{
          "id": "B",
          "text": "Choice text",
          "next": "node_id"
        }},
        {{
          "id": "C",
          "text": "Choice text",
          "next": "node_id"
        }},
        {{
          "id": "D",
          "text": "Choice text",
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

Every choice next value must refer to another node or an ending ID.

Make sure the story is complete.
"""

    response = call_ai(
        story_system,
        [],
        temperature=1.0,
        max_tokens=7000
    )

    parsed = safe_json_from_ai(response)

    if not parsed:
        return None

    if "nodes" not in parsed:
        return None

    if "endings" not in parsed:
        parsed["endings"] = []

    return parsed


@app.route("/story/start", methods=["POST"])
def story_start():
    # Generate a completely new story for this world.
    story = generate_story()

    if not story:
        return jsonify({
            "error": "The story generator failed. Check your AI model/API key."
        }), 500

    data["story"] = {
        "active": True,
        "story_id": random.randint(100000, 999999),
        "title": story.get("title", "Untitled Story"),
        "theme": story.get("theme", ""),
        "current_node": story.get("start", "start"),
        "history": [],
        "seen_nodes": [story.get("start", "start")],
        "ending": None,
        "tree": story
    }

    add_world_memory(
        f"Story started: {data['story']['title']}"
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

    if not data["story"]["active"]:
        return jsonify({
            "error": "No active story."
        }), 400

    story = data["story"]["tree"]
    current_id = data["story"]["current_node"]

    node = story.get("nodes", {}).get(current_id)

    if not node:
        return jsonify({
            "error": "Story node not found."
        }), 404

    choice = None

    for item in node.get("choices", []):
        if item.get("id") == choice_id:
            choice = item
            break

    if not choice:
        return jsonify({
            "error": "Invalid choice."
        }), 400

    next_id = choice.get("next")

    data["story"]["history"].append({
        "node": current_id,
        "choice": choice_id,
        "choice_text": choice.get("text", ""),
        "next": next_id
    })

    data["story"]["current_node"] = next_id

    if next_id not in data["story"]["seen_nodes"]:
        data["story"]["seen_nodes"].append(next_id)

    # Is it an ending?
    ending = None

    for item in story.get("endings", []):
        if item.get("id") == next_id:
            ending = item
            break

    if ending:
        data["story"]["ending"] = ending
        data["story"]["active"] = False

        add_world_memory(
            f"Story ended: {ending.get('title', 'Unknown ending')}"
        )

    save_data(data)

    return jsonify({
        "success": True,
        "current_node": next_id,
        "ending": ending,
        "story": data["story"]
    })


@app.route("/story/tree", methods=["GET"])
def story_tree():
    story = data["story"]["tree"]

    return jsonify({
        "title": data["story"]["title"],
        "tree": story,
        "seen_nodes": data["story"]["seen_nodes"],
        "history": data["story"]["history"],
        "ending": data["story"]["ending"],
        "active": data["story"]["active"]
    })


# ============================================================
# SELF-IMPROVEMENT / LEARNING SYSTEM
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

    save_data(data)

    return jsonify({
        "success": True,
        "improvement": data["improvement"]
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "ai_configured": bool(API_KEY),
        "model": MODEL,
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
