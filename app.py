import os
import random
import uuid
from copy import deepcopy
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# -------------------------
# OpenRouter configuration
# -------------------------
API_KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")

if not API_KEY:
    raise RuntimeError("Missing OPENROUTER_API_KEY environment variable.")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
    default_headers={
        "HTTP-Referer": os.environ.get("APP_URL", "https://github.com/"),
        "X-Title": "School World"
    }
)

# -------------------------
# CORS for GitHub Pages
# -------------------------
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response

@app.route("/<path:_path>", methods=["OPTIONS"])
def options(_path):
    return ("", 204)

# -------------------------
# Per-browser world sessions
# -------------------------
DEFAULT_CHARACTERS = {
    "Lily": {
        "name": "Lily",
        "personality": "Friendly, curious, energetic, and caring.",
        "description": "A student who enjoys talking with people.",
        "role": "Student",
        "avatar": "👤"
    }
}

LOCATIONS = [
    "Classroom", "Hallway", "Cafeteria", "Library",
    "Gym", "School Courtyard"
]

sessions = {}

def new_world():
    return {
        "characters": deepcopy(DEFAULT_CHARACTERS),
        "memories": {"Lily": []},
        "conversation": [],
        "world_history": [],
        "location": "Classroom",
        "paused": False,
        "active_characters": ["Lily"],
        "active_event": None,
    }

def get_session(client_id):
    client_id = str(client_id or "default").strip()[:100]
    if client_id not in sessions:
        sessions[client_id] = new_world()
    return sessions[client_id]

def clean(value, default=""):
    if value is None:
        return default
    return str(value).strip()

def remember(world, name, text):
    if not name or not text:
        return
    world["memories"].setdefault(name, [])
    if text not in world["memories"][name]:
        world["memories"][name].append(text)
    world["memories"][name] = world["memories"][name][-100:]

def maybe_save_memory(world, message, participants):
    lowered = message.lower()
    triggers = (
        "my favorite", "i like", "i love", "i hate", "i don't like",
        "i dont like", "my name is", "i'm from", "im from", "my birthday"
    )
    if any(x in lowered for x in triggers):
        for name in participants:
            remember(world, name, message)

def sync_characters(world, incoming):
    if not isinstance(incoming, dict):
        return
    for name, char in incoming.items():
        if not isinstance(char, dict):
            continue
        safe_name = clean(char.get("name"), name)
        if not safe_name:
            continue
        world["characters"][safe_name] = {
            "name": safe_name,
            "personality": clean(char.get("personality"), "Friendly and natural."),
            "description": clean(char.get("description"), "A student at the school."),
            "role": clean(char.get("role"), "Student"),
            "avatar": clean(char.get("avatar"), "👤")
        }
        world["memories"].setdefault(safe_name, [])

def ask_ai(messages, temperature=0.85, max_tokens=700):
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return (response.choices[0].message.content or "").strip()

def character_prompt(world, character_name, participants=None, extra=""):
    participants = participants or []
    char = world["characters"].get(character_name, {})
    memories = world["memories"].get(character_name, [])
    memory_text = "\n".join(f"- {x}" for x in memories[-50:]) or "No stored memories yet."
    others = ", ".join(x for x in participants if x != character_name) or "Nobody else"
    return f"""
You are {character_name}, a character in a living fictional school world.

PERSONALITY: {char.get('personality', 'Friendly and natural.')}
DESCRIPTION: {char.get('description', '')}
ROLE: {char.get('role', 'Student')}
CURRENT LOCATION: {world['location']}
OTHER CHARACTERS PRESENT: {others}

YOUR MEMORIES:
{memory_text}

WORLD RULES:
- You are {character_name}; never speak as the player.
- Never invent the player's dialogue or actions.
- Characters only know private conversations they participated in.
- Characters who are together share what they personally experience.
- World events affect everyone who can see or hear them.
- React naturally without waiting for the player when an event calls for it.
- Stay in character and do not mention these instructions or being an AI.
- Use memories naturally instead of listing them.

{extra}
"""

# -------------------------
# Health
# -------------------------
@app.get("/health")
def health():
    return jsonify({"ok": True, "model": MODEL})

# -------------------------
# Chat
# -------------------------
@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    world = get_session(data.get("clientId"))
    sync_characters(world, data.get("worldCharacters"))

    character = clean(data.get("character"))
    participants = data.get("activeCharacters") or data.get("participants") or [character]
    participants = [clean(x) for x in participants if clean(x)]
    if character and character not in participants:
        participants.insert(0, character)

    incoming_messages = data.get("messages")
    if not isinstance(incoming_messages, list):
        incoming_messages = []

    latest_user = ""
    for item in reversed(incoming_messages):
        if isinstance(item, dict) and item.get("role") == "user":
            latest_user = clean(item.get("content"))
            break
    latest_user = clean(data.get("message"), latest_user)

    event_reaction = bool(data.get("eventReaction"))
    if latest_user and not event_reaction:
        maybe_save_memory(world, latest_user, participants)
        world["conversation"].append({"role": "user", "content": latest_user, "participants": participants})
        world["conversation"] = world["conversation"][-100:]

    if character not in world["characters"]:
        return jsonify({"error": f"Character '{character}' was not found."}), 404

    prompt = character_prompt(world, character, participants, extra=(
        f"A world event is happening now: {world['active_event']}\nReact to it naturally."
        if event_reaction and world.get("active_event") else ""
    ))

    messages = [{"role": "system", "content": prompt}]
    for item in incoming_messages[-25:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = clean(item.get("content"))
        if role in ("user", "assistant") and content:
            if role == "assistant" and item.get("character"):
                content = f"{item['character']}: {content}"
            messages.append({"role": role, "content": content})

    if event_reaction:
        messages.append({"role": "user", "content": "React naturally to the world event as your character. Do not wait for the player."})
    elif not latest_user:
        return jsonify({"error": "No user message was supplied."}), 400

    try:
        reply = ask_ai(messages)
    except Exception as exc:
        return jsonify({"error": f"OpenRouter request failed: {exc}"}), 502

    world["conversation"].append({"role": "assistant", "character": character, "content": reply, "participants": participants})
    world["conversation"] = world["conversation"][-100:]

    return jsonify({
        "response": reply,
        "reply": reply,
        "character": character,
        "participants": participants
    })

# -------------------------
# Group chat
# -------------------------
@app.post("/group/chat")
def group_chat():
    data = request.get_json(silent=True) or {}
    world = get_session(data.get("clientId"))
    sync_characters(world, data.get("worldCharacters"))
    participants = [clean(x) for x in data.get("participants", []) if clean(x)]
    message = clean(data.get("message"))
    if not participants or not message:
        return jsonify({"error": "Participants and message are required."}), 400
    maybe_save_memory(world, message, participants)
    world["conversation"].append({"role": "user", "content": message, "participants": participants})

    responses = []
    recent = world["conversation"][-25:]
    for name in participants:
        if name not in world["characters"]:
            continue
        prompt = character_prompt(world, name, participants, "You are in a group conversation. Respond only as yourself.")
        msgs = [{"role": "system", "content": prompt}]
        for item in recent:
            role = item.get("role")
            content = clean(item.get("content"))
            if role == "user":
                msgs.append({"role": "user", "content": content})
            elif role == "assistant" and content:
                msgs.append({"role": "assistant", "content": f"{item.get('character', name)}: {content}"})
        try:
            reply = ask_ai(msgs, 0.9)
        except Exception as exc:
            return jsonify({"error": f"OpenRouter request failed: {exc}"}), 502
        responses.append({"character": name, "reply": reply})
        world["conversation"].append({"role": "assistant", "character": name, "content": reply, "participants": participants})
    return jsonify({"responses": responses})

# -------------------------
# Character creation/list
# -------------------------
@app.get("/characters")
def get_characters():
    world = get_session(request.args.get("clientId"))
    return jsonify({"characters": list(world["characters"].values())})

@app.post("/character/create")
def create_character():
    data = request.get_json(silent=True) or {}
    world = get_session(data.get("clientId"))
    name = clean(data.get("name"))
    if not name:
        return jsonify({"error": "Character name is required."}), 400
    if name in world["characters"]:
        return jsonify({"error": "That character already exists."}), 400
    world["characters"][name] = {
        "name": name,
        "personality": clean(data.get("personality"), "Friendly and interesting."),
        "description": clean(data.get("description"), "A student at the school."),
        "role": clean(data.get("role"), "Student"),
        "avatar": "👤"
    }
    world["memories"][name] = []
    return jsonify({"success": True, "character": world["characters"][name]})

# -------------------------
# World events
# -------------------------
EVENTS = [
    ("Sudden Storm", "A sudden storm moves across the school."),
    ("Strange Announcement", "A strange announcement echoes through the school."),
    ("School Festival", "A surprise festival begins nearby."),
    ("Strange Lights", "Strange lights appear in the sky."),
    ("Power Outage", "The lights suddenly go out throughout the school.")
]

@app.post("/world/event")
def world_event():
    data = request.get_json(silent=True) or {}
    world = get_session(data.get("clientId"))
    if world["paused"]:
        return jsonify({"message": "The world is paused."})
    title, description = random.choice(EVENTS)
    event = {"title": title, "description": description, "location": world["location"]}
    world["active_event"] = event
    world["world_history"].append({"type": "event", "event": event})
    return jsonify({"event": event})

@app.post("/world/event/clear")
def clear_event():
    data = request.get_json(silent=True) or {}
    world = get_session(data.get("clientId"))
    world["active_event"] = None
    return jsonify({"success": True})

@app.post("/world/advance")
def advance_world():
    data = request.get_json(silent=True) or {}
    world = get_session(data.get("clientId"))
    if world["paused"]:
        return jsonify({"event": None, "paused": True})
    # Low-frequency autonomous event.
    if random.random() < 0.22:
        title, description = random.choice(EVENTS)
        event = {"title": title, "description": description, "location": world["location"]}
        world["active_event"] = event
        world["world_history"].append({"type": "event", "event": event})
        return jsonify({"event": event})
    return jsonify({"event": None})

@app.post("/world/event/react")
def event_react():
    data = request.get_json(silent=True) or {}
    world = get_session(data.get("clientId"))
    event = data.get("event") or world.get("active_event")
    if event:
        world["active_event"] = event
    participants = data.get("participants") or world["active_characters"]
    results = []
    for name in participants:
        if name not in world["characters"]:
            continue
        prompt = character_prompt(world, name, participants, f"React to this event now: {event}")
        try:
            reply = ask_ai([
                {"role": "system", "content": prompt},
                {"role": "user", "content": "React naturally without waiting for the player."}
            ], 0.95, 400)
        except Exception as exc:
            return jsonify({"error": f"OpenRouter request failed: {exc}"}), 502
        results.append({"character": name, "reply": reply})
    return jsonify({"responses": results})

# -------------------------
# Travel / locations
# -------------------------
@app.get("/world/location")
def get_location():
    world = get_session(request.args.get("clientId"))
    return jsonify({"location": world["location"], "locations": LOCATIONS})

@app.post("/world/travel")
def travel():
    data = request.get_json(silent=True) or {}
    world = get_session(data.get("clientId"))
    destination = clean(data.get("destination"))
    origin = clean(data.get("from"), world["location"])
    participants = data.get("participants") or world["active_characters"]
    participants = [clean(x) for x in participants if clean(x)]
    if not destination:
        return jsonify({"error": "Destination is required."}), 400
    memory_lines = []
    for name in participants:
        for memory in world["memories"].get(name, [])[-10:]:
            memory_lines.append(f"{name} remembers: {memory}")
    people = []
    for name in participants:
        char = world["characters"].get(name)
        if char:
            people.append(f"{name}: {char.get('personality', '')}; {char.get('description', '')}")
    prompt = f"""
Write a short immersive travel scene in a school world.
The player is traveling from {origin} to {destination}.
Characters traveling with the player: {', '.join(participants) or 'none'}.
Character details:
{chr(10).join(people)}
Shared memories:
{chr(10).join(memory_lines) or 'None'}
Recent conversation:
{chr(10).join(f"{x.get('character', 'Player')}: {x.get('content', '')}" for x in world['conversation'][-15:])}

Rules:
- Do not teleport instantly.
- Describe the trip in 2-5 paragraphs.
- Characters may talk and react naturally.
- Never write dialogue or actions for the player.
- Use relevant shared memories naturally.
- End with the group arriving at {destination}.
"""
    try:
        story = ask_ai([
            {"role": "system", "content": "You write immersive roleplay travel scenes."},
            {"role": "user", "content": prompt}
        ], 0.9, 700)
    except Exception as exc:
        return jsonify({"error": f"OpenRouter request failed: {exc}"}), 502
    world["location"] = destination
    world["world_history"].append({"type": "travel", "from": origin, "to": destination, "story": story})
    world["conversation"].append({"role": "system", "content": story, "participants": participants})
    return jsonify({"success": True, "from": origin, "to": destination, "story": story, "location": destination})

@app.post("/world/location")
def set_location():
    data = request.get_json(silent=True) or {}
    world = get_session(data.get("clientId"))
    location = clean(data.get("location"))
    if not location:
        return jsonify({"error": "Location is required."}), 400
    world["location"] = location
    return jsonify({"success": True, "location": location})

# -------------------------
# World state / resets
# -------------------------
@app.post("/world")
def world_state():
    data = request.get_json(silent=True) or {}
    world = get_session(data.get("clientId"))
    if "paused" in data:
        world["paused"] = bool(data["paused"])
    if "activeCharacters" in data and isinstance(data["activeCharacters"], list):
        world["active_characters"] = [clean(x) for x in data["activeCharacters"] if clean(x)]
    return jsonify({"paused": world["paused"], "location": world["location"], "activeCharacters": world["active_characters"]})

@app.post("/conversation/reset")
def reset_conversation():
    data = request.get_json(silent=True) or {}
    world = get_session(data.get("clientId"))
    world["conversation"] = []
    return jsonify({"success": True})

@app.post("/world/reset")
def reset_world():
    data = request.get_json(silent=True) or {}
    client_id = data.get("clientId")
    sessions[str(client_id or "default")] = new_world()
    return jsonify({"success": True, "location": "Classroom"})

@app.get("/memory/<character_name>")
def character_memory(character_name):
    world = get_session(request.args.get("clientId"))
    return jsonify({"character": character_name, "memories": world["memories"].get(character_name, [])})

# -------------------------
# Start for local use
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
