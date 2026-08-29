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

# IMPORTANT:
# Do NOT depend on the old OPENROUTER_MODEL variable.
#
# We try these models in order.
# openrouter/free is especially useful because OpenRouter
# automatically selects an available free model.
FREE_MODELS = [
    "openrouter/free",
    "openai/gpt-oss-20b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-super:free",
    "nvidia/nemotron-nano-9b-v2:free",
]

# If the environment variable contains a model, put it first,
# but NEVER let an old paid/invalid model prevent fallback.
ENV_MODEL = os.getenv("OPENROUTER_MODEL", "").strip()

if ENV_MODEL and ENV_MODEL not in FREE_MODELS:
    # Only use an explicitly supplied model if it appears to be
    # a free variant or the OpenRouter free router.
    if ENV_MODEL == "openrouter/free" or ENV_MODEL.endswith(":free"):
        FREE_MODELS.insert(0, ENV_MODEL)

client = None

if API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY
    )


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

        "characters": json.loads(
            json.dumps(DEFAULT_CHARACTERS)
        ),

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
        new_data = default_data()
        save_data(new_data)
        return new_data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        base = default_data()

        for key, value in base.items():
            if key not in loaded:
                loaded[key] = value

        return loaded

    except Exception:
        new_data = default_data()
        save_data(new_data)
        return new_data


def save_data(current_data):
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


data = load_data()


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(text):
    if text is None:
        return ""

    text = str(text)

    text = text.replace("\x00", "")

    text = re.sub(
        r"```(?:json|python|html|text)?",
        "",
        text,
        flags=re.I
    )

    text = text.replace("```", "")

    return text.strip()


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
            return json.loads(text[start:end + 1])
        except Exception:
            pass

    return None


def trim_memory(items, limit=30):
    if not items:
        return []

    if len(items) <= limit:
        return items

    return items[-limit:]


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

    character["memory"] = trim_memory(
        character["memory"],
        40
    )


def add_world_memory(text):
    text = clean_text(text)

    if not text:
        return

    data.setdefault("world_memory", [])

    data["world_memory"].append(text)

    data["world_memory"] = trim_memory(
        data["world_memory"],
        50
    )


def add_improvement(text):
    text = clean_text(text)

    if not text:
        return

    improvements = data["improvement"]["facts"]

    if text not in improvements:
        improvements.append(text)

    data["improvement"]["facts"] = trim_memory(
        improvements,
        50
    )


# ============================================================
# AI SYSTEM WITH AUTOMATIC FALLBACK
# ============================================================

def call_ai(
    system_prompt,
    messages,
    temperature=0.8,
    max_tokens=700
):
    """
    Attempts several OpenRouter free models.

    If one fails:
        404 -> next model
        402 -> next model
        429 -> next model
        timeout -> next model
        other API error -> next model

    Returns:
        AI response
        OR
        AI_ERROR: ...
    """

    if not client:
        return (
            "AI_ERROR: OPENROUTER_API_KEY is missing. "
            "Add it to Render Environment Variables."
        )

    errors = []

    # Remove duplicates while preserving order.
    models = []

    for model_name in FREE_MODELS:
        if model_name and model_name not in models:
            models.append(model_name)

    for model_name in models:

        try:
            print(
                f"[AI] Trying model: {model_name}",
                flush=True
            )

            response = client.chat.completions.create(
                model=model_name,
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
                errors.append(
                    f"{model_name}: no choices returned"
                )
                continue

            result = response.choices[0].message.content

            result = clean_text(result)

            if not result:
                errors.append(
                    f"{model_name}: empty response"
                )
                continue

            print(
                f"[AI] Success with model: {model_name}",
                flush=True
            )

            return result

        except Exception as e:

            error_text = str(e)

            print(
                f"[AI] Failed {model_name}: {error_text}",
                flush=True
            )

            errors.append(
                f"{model_name}: {error_text}"
            )

            continue

    return (
        "AI_ERROR: All free models failed.\n"
        + "\n".join(errors)
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

    remember(
        character,
        f"Player said: {message}"
    )

    recent_conversation = (
        character.get("conversation", [])
    )[-20:]

    messages = []

    for item in recent_conversation:

        role = item.get("role")

        if role not in ["user", "assistant"]:
            continue

        messages.append({
            "role": role,
            "content": item.get("content", "")
        })

    messages.append({
        "role": "user",
        "content": message
    })

    location = data["player_location"]

    other_characters = [
        {
            "name": c["name"],
            "role": c["role"],
            "personality": c["personality"]
        }
        for c in data["characters"]
        if c["id"] != character["id"]
    ]

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

CURRENT PLAYER LOCATION:
{location}

WORLD NUMBER:
{data["world_number"]}

YOUR MEMORY:
{json.dumps(character.get("memory", [])[-25:], ensure_ascii=False)}

WORLD MEMORY:
{json.dumps(data.get("world_memory", [])[-20:], ensure_ascii=False)}

OTHER CHARACTERS:
{json.dumps(other_characters, ensure_ascii=False)}

RULES:

1. Stay completely in character.

2. Remember previous conversations.

3. Give medium-length responses.

4. Normally respond with roughly 2-5 paragraphs,
   depending on what is happening.

5. Do not make every response extremely long.

6. Do not constantly agree with the player.

7. Have your own opinions.

8. You can joke, disagree, get excited, become confused,
   become suspicious, become interested, or become annoyed
   according to your personality.

9. You are a person in the school world, not a chatbot.

10. Never say that you are an AI unless the story logically
    requires it.

11. Never control the player's actions.

12. The player is a separate person.

13. If the player says they are traveling somewhere,
    acknowledge it naturally.

14. Do NOT automatically pretend you traveled with them.

15. You know the school locations.

16. You may know things that happened elsewhere if they
    are in your memory.

17. Characters can have relationships with one another.

18. Characters may remember things about the player.

19. Do not dump all memories into every response.

20. Use memories only when relevant.

21. Make the conversation feel like a real relationship
    developing over time.

22. If the player has talked to you many times before,
    your behavior should reflect that history.

23. Avoid repeating the same phrases.

24. Avoid generic assistant-style responses.

25. React naturally to what the player actually said.
"""

    answer = call_ai(
        system_prompt,
        messages,
        temperature=0.82,
        max_tokens=700
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
        80
    )

    if len(message) > 20:

        add_improvement(
            f"Conversation detail with "
            f"{character['name']}: "
            f"{message[:180]}"
        )

    save_data(data)

    return jsonify({
        "reply": answer,
        "character": character,
        "location": location
    })


# ============================================================
# RESET CHARACTER CONVERSATION
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
        "message":
            f"Conversation with {character['name']} reset."
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
        "description":
            description or
            f"{name} is a {role.lower()} at the school.",
        "traits": [
            clean_text(x)
            for x in traits
            if clean_text(x)
        ],
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
# BACKGROUND CHARACTER INTERACTIONS
# ============================================================

@app.route("/world/advance", methods=["POST"])
def world_advance():

    if len(data["characters"]) < 2:

        return jsonify({
            "event":
                "There are not enough characters "
                "for a background interaction."
        })

    first, second = random.sample(
        data["characters"],
        2
    )

    location = random.choice(
        data["locations"]
    )

    system_prompt = f"""
Generate a background event in a living school world.

Character A:
{first["name"]}

Personality:
{first["personality"]}

Character B:
{second["name"]}

Personality:
{second["personality"]}

Location:
{location}

Their interaction should feel natural.

Possible events include:

- joking
- studying
- arguing
- gossiping
- helping each other
- misunderstanding
- planning something
- discussing another student
- competition
- friendship
- awkward conversation
- ordinary school life

Do not make every event dramatic.

Keep it around 3-7 sentences.

Do not control the player.
"""

    event = call_ai(
        system_prompt,
        [],
        temperature=0.9,
        max_tokens=400
    )

    if event.startswith("AI_ERROR:"):

        return jsonify({
            "error": event
        }), 500

    background = {
        "characters": [
            first["name"],
            second["name"]
        ],
        "location": location,
        "event": event,
        "time": datetime.utcnow().isoformat()
    }

    data["background_events"].append(background)

    data["background_events"] = trim_memory(
        data["background_events"],
        50
    )

    remember(
        first,
        f"{second['name']} and I interacted "
        f"at {location}: {event[:220]}"
    )

    remember(
        second,
        f"I interacted with {first['name']} "
        f"at {location}: {event[:220]}"
    )

    add_world_memory(
        f"{first['name']} and {second['name']} "
        f"interacted at {location}."
    )

    save_data(data)

    return jsonify({
        "success": True,
        "event": background
    })


# ============================================================
# TRAVEL
# ============================================================

@app.route("/world/travel", methods=["POST"])
def travel():

    body = request.get_json(silent=True) or {}

    location = clean_text(
        body.get("location")
    )

    if location not in data["locations"]:

        return jsonify({
            "error": "Unknown location."
        }), 400

    old_location = data["player_location"]

    data["player_location"] = location

    add_world_memory(
        f"Player traveled from "
        f"{old_location} to {location}."
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

    new_data["world_id"] = random.randint(
        100000,
        999999
    )

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
        "message":
            "World reset. All character memories, "
            "world memories, conversations, and "
            "story progression were cleared."
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
    "A student disappears from class and several people know something.",
    "A strange object is discovered inside the school.",
    "A school event goes completely wrong.",
    "A rumor spreads through the school and changes everyone's behavior.",
    "A new student arrives and seems to know something about the school.",
    "Something strange keeps happening at the same time every day.",
    "Two students discover that their memories of an event do not match.",
    "A school project uncovers something nobody was supposed to find."
]


# ============================================================
# STORY GENERATOR
# ============================================================

def generate_story():

    theme = random.choice(
        STORY_THEMES
    )

    world_seed = random.randint(
        100000,
        999999999
    )

    character_info = [
        {
            "name": c["name"],
            "role": c["role"],
            "personality": c["personality"]
        }
        for c in data["characters"]
    ]

    story_system = f"""
Create a completely original branching interactive
school story.

WORLD SEED:
{world_seed}

THEME:
{theme}

AVAILABLE CHARACTERS:
{json.dumps(character_info, ensure_ascii=False)}

The story should feel like a choice-driven narrative game.

IMPORTANT:

The world seed means this story must be substantially
different from stories generated in other worlds.

Requirements:

- At least 5 major endings.
- Prefer 6-8 endings if possible.
- 16-25 meaningful story nodes.
- Multiple branches.
- Choices must affect future events.
- Choices must affect relationships.
- Choices can affect trust.
- Choices can affect information.
- Choices can affect locations.
- Choices can affect which characters help the player.
- Choices can cause characters to distrust the player.
- Choices can unlock or block later events.
- Some branches should stay separate.
- Do NOT reconnect every branch immediately.
- The player gets exactly four choices:
  A
  B
  C
  D
- Each choice must have consequences.
- Choices should not have obvious good/bad labels.
- The story should include normal school moments.
- Characters should act according to their personalities.
- The player should never know which choice leads
  to which ending.
- Some endings should be positive.
- Some endings should be negative.
- Some endings should be bittersweet.
- Some endings should reveal secrets.
- Some endings should depend on earlier choices.
- The story should feel like one evolving timeline.
- Do not copy any existing copyrighted game story.

Return ONLY valid JSON.

Use this exact general structure:

{{
  "title": "Story title",
  "theme": "Short theme",
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

Every choice's "next" MUST refer to:

1. another existing node ID

OR

2. an ending ID.

Do not create broken links.

Every non-ending node must contain exactly
four choices: A, B, C, D.

Make the story complete from beginning to end.
"""

    response = call_ai(
        story_system,
        [],
        temperature=1.0,
        max_tokens=7000
    )

    if response.startswith("AI_ERROR:"):
        return None, response

    parsed = safe_json_from_ai(response)

    if not parsed:

        return None, (
            "AI_ERROR: The model returned invalid story JSON."
        )

    if "nodes" not in parsed:

        return None, (
            "AI_ERROR: Story JSON did not contain nodes."
        )

    if "endings" not in parsed:

        parsed["endings"] = []

    return parsed, None


# ============================================================
# STORY START
# ============================================================

@app.route("/story/start", methods=["POST"])
def story_start():

    story, error = generate_story()

    if error:

        return jsonify({
            "error": error
        }), 500

    if not story:

        return jsonify({
            "error":
                "Story generator returned no story."
        }), 500

    start_node = story.get(
        "start",
        "start"
    )

    data["story"] = {
        "active": True,

        "story_id": random.randint(
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

        "current_node": start_node,

        "history": [],

        "seen_nodes": [
            start_node
        ],

        "ending": None,

        "tree": story
    }

    add_world_memory(
        f"Story started: "
        f"{data['story']['title']}"
    )

    save_data(data)

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

    choice_id = clean_text(
        body.get("choice")
    ).upper()

    if not data["story"]["active"]:

        return jsonify({
            "error": "No active story."
        }), 400

    story = data["story"]["tree"]

    current_id = data["story"]["current_node"]

    node = story.get(
        "nodes",
        {}
    ).get(current_id)

    if not node:

        return jsonify({
            "error":
                f"Story node '{current_id}' not found."
        }), 404

    choice = None

    for item in node.get("choices", []):

        if str(
            item.get("id", "")
        ).upper() == choice_id:

            choice = item
            break

    if not choice:

        return jsonify({
            "error":
                "Invalid choice. Choose A, B, C, or D."
        }), 400

    next_id = choice.get("next")

    if not next_id:

        return jsonify({
            "error":
                "This choice has no destination."
        }), 500

    data["story"]["history"].append({
        "node": current_id,
        "choice": choice_id,
        "choice_text":
            choice.get(
                "text",
                ""
            ),
        "next": next_id
    })

    data["story"]["current_node"] = next_id

    if next_id not in data["story"]["seen_nodes"]:

        data["story"]["seen_nodes"].append(
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

        data["story"]["ending"] = ending

        data["story"]["active"] = False

        add_world_memory(
            f"Story ended: "
            f"{ending.get('title', 'Unknown ending')}"
        )

    save_data(data)

    return jsonify({
        "success": True,
        "current_node": next_id,
        "ending": ending,
        "story": data["story"]
    })


# ============================================================
# STORY TREE
# ============================================================

@app.route("/story/tree", methods=["GET"])
def story_tree():

    story = data["story"]["tree"]

    return jsonify({
        "title":
            data["story"]["title"],

        "theme":
            data["story"]["theme"],

        "tree":
            story,

        "seen_nodes":
            data["story"]["seen_nodes"],

        "history":
            data["story"]["history"],

        "current_node":
            data["story"]["current_node"],

        "ending":
            data["story"]["ending"],

        "active":
            data["story"]["active"]
    })


# ============================================================
# IMPROVEMENT SYSTEM
# ============================================================

@app.route("/improvement", methods=["GET"])
def get_improvement():

    return jsonify(
        data["improvement"]
    )


@app.route("/improvement/learn", methods=["POST"])
def improvement_learn():

    body = request.get_json(silent=True) or {}

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

    save_data(data)

    return jsonify({
        "success": True,
        "improvement":
            data["improvement"]
    })


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
def health():

    return jsonify({
        "status": "ok",
        "ai_configured":
            bool(API_KEY),
        "models":
            FREE_MODELS,
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
