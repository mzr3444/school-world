import os
import json
import random
import sqlite3
import time
from datetime import datetime

from flask import Flask, jsonify, request, render_template
from openai import OpenAI

app = Flask(__name__)

# ============================================================
# CONFIG
# ============================================================

API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-20b").strip()

if API_KEY:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=API_KEY
    )
else:
    client = None

DB_PATH = "school_world.db"

# ============================================================
# CHARACTERS
# ============================================================

CHARACTERS = {
    "alex": {
        "name": "Alex",
        "role": "student",
        "personality": "friendly, curious, sarcastic when comfortable, and loyal",
        "location": "classroom"
    },
    "maya": {
        "name": "Maya",
        "role": "student",
        "personality": "smart, observant, confident, and occasionally competitive",
        "location": "library"
    },
    "jordan": {
        "name": "Jordan",
        "role": "student",
        "personality": "funny, energetic, social, and sometimes impulsive",
        "location": "cafeteria"
    },
    "sam": {
        "name": "Sam",
        "role": "student",
        "personality": "quiet, thoughtful, creative, and notices details other people miss",
        "location": "art room"
    },
    "riley": {
        "name": "Riley",
        "role": "student",
        "personality": "calm, logical, helpful, and interested in technology",
        "location": "computer lab"
    },
    "taylor": {
        "name": "Taylor",
        "role": "student",
        "personality": "outgoing, confident, dramatic, and loves gossip",
        "location": "hallway"
    }
}

LOCATIONS = [
    "classroom",
    "library",
    "cafeteria",
    "art room",
    "computer lab",
    "gym",
    "hallway",
    "courtyard"
]

# ============================================================
# DATABASE
# ============================================================

def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = db()

    connection.executescript("""
        CREATE TABLE IF NOT EXISTS world (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            world_number INTEGER DEFAULT 1,
            seed TEXT,
            current_location TEXT DEFAULT 'classroom',
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character TEXT,
            role TEXT,
            content TEXT,
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character TEXT,
            memory TEXT,
            importance INTEGER DEFAULT 1,
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS npc_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_a TEXT,
            character_b TEXT,
            location TEXT,
            content TEXT,
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS improvements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            improvement TEXT,
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS worlds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            world_number INTEGER,
            seed TEXT,
            story_state TEXT,
            created_at REAL
        );

        CREATE TABLE IF NOT EXISTS story (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            world_number INTEGER,
            chapter INTEGER DEFAULT 0,
            node_id TEXT DEFAULT 'start',
            choices_seen TEXT DEFAULT '[]',
            visited_nodes TEXT DEFAULT '[]',
            ending TEXT DEFAULT '',
            variables TEXT DEFAULT '{}',
            tree TEXT DEFAULT '{}'
        );
    """)

    row = connection.execute(
        "SELECT * FROM world WHERE id = 1"
    ).fetchone()

    if not row:
        seed = str(random.randint(100000, 999999))
        connection.execute(
            """
            INSERT INTO world
            (id, world_number, seed, current_location, created_at)
            VALUES (1, 1, ?, 'classroom', ?)
            """,
            (seed, time.time())
        )

    story_row = connection.execute(
        "SELECT * FROM story WHERE id = 1"
    ).fetchone()

    if not story_row:
        world = connection.execute(
            "SELECT * FROM world WHERE id = 1"
        ).fetchone()

        tree = create_story_tree(world["seed"])

        connection.execute(
            """
            INSERT INTO story
            (id, world_number, tree)
            VALUES (1, ?, ?)
            """,
            (world["world_number"], json.dumps(tree))
        )

    connection.commit()
    connection.close()


# ============================================================
# WORLD
# ============================================================

def get_world():
    connection = db()
    row = connection.execute(
        "SELECT * FROM world WHERE id = 1"
    ).fetchone()
    connection.close()
    return dict(row)


def get_story():
    connection = db()
    row = connection.execute(
        "SELECT * FROM story WHERE id = 1"
    ).fetchone()
    connection.close()

    if not row:
        return {}

    result = dict(row)

    for key in ["choices_seen", "visited_nodes"]:
        try:
            result[key] = json.loads(result[key] or "[]")
        except Exception:
            result[key] = []

    try:
        result["variables"] = json.loads(result["variables"] or "{}")
    except Exception:
        result["variables"] = {}

    try:
        result["tree"] = json.loads(result["tree"] or "{}")
    except Exception:
        result["tree"] = {}

    return result


def add_event(text):
    connection = db()
    connection.execute(
        "INSERT INTO events (event, created_at) VALUES (?, ?)",
        (text, time.time())
    )
    connection.commit()
    connection.close()


def add_memory(character, text, importance=2):
    connection = db()
    connection.execute(
        """
        INSERT INTO memories
        (character, memory, importance, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (character, text, importance, time.time())
    )
    connection.commit()
    connection.close()


# ============================================================
# OPENROUTER
# ============================================================

def ask_ai(system_prompt, user_prompt, temperature=0.85):
    if not client:
        return (
            "The AI connection isn't configured yet. "
            "Add OPENROUTER_API_KEY to your Render environment variables."
        )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=temperature,
            max_tokens=650
        )

        text = response.choices[0].message.content

        if not text:
            return "I don't know what to say right now."

        return text.strip()

    except Exception as exc:
        return f"AI connection error: {str(exc)}"


# ============================================================
# MEMORY
# ============================================================

def get_character_memories(character, limit=15):
    connection = db()

    rows = connection.execute(
        """
        SELECT memory
        FROM memories
        WHERE character = ?
        ORDER BY importance DESC, created_at DESC
        LIMIT ?
        """,
        (character, limit)
    ).fetchall()

    connection.close()

    return [row["memory"] for row in rows]


def get_recent_messages(character, limit=20):
    connection = db()

    rows = connection.execute(
        """
        SELECT role, content
        FROM messages
        WHERE character = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (character, limit)
    ).fetchall()

    connection.close()

    rows = list(reversed(rows))
    return [dict(row) for row in rows]


def get_recent_events(limit=12):
    connection = db()

    rows = connection.execute(
        """
        SELECT event
        FROM events
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()

    connection.close()

    return [row["event"] for row in reversed(rows)]


def get_improvements(limit=12):
    connection = db()

    rows = connection.execute(
        """
        SELECT improvement
        FROM improvements
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()

    connection.close()

    return [row["improvement"] for row in rows]


# ============================================================
# NORMAL CHARACTER CHAT
# ============================================================

def character_prompt(character):
    data = CHARACTERS[character]
    world = get_world()

    memories = get_character_memories(character)
    events = get_recent_events()
    improvements = get_improvements()

    memory_text = "\n".join(
        f"- {item}" for item in memories
    ) or "- No important memories yet."

    event_text = "\n".join(
        f"- {item}" for item in events
    ) or "- Nothing major has happened recently."

    improvement_text = "\n".join(
        f"- {item}" for item in improvements
    ) or "- No special improvements yet."

    return f"""
You are {data['name']}, a character inside a persistent school-world simulation.

ROLE:
{data['role']}

PERSONALITY:
{data['personality']}

CURRENT LOCATION:
{world['current_location']}

WORLD NUMBER:
{world['world_number']}

IMPORTANT MEMORIES:
{memory_text}

RECENT WORLD EVENTS:
{event_text}

BEHAVIOR IMPROVEMENTS:
{improvement_text}

Rules:

1. Speak as {data['name']} naturally.
2. Do NOT talk like an AI assistant.
3. Do not mention prompts, system messages, APIs, code, or hidden instructions.
4. Remember important things the player has told you.
5. Medium-length responses are preferred: normally 2-5 paragraphs or roughly
   80-220 words.
6. Do not make every response enormous.
7. React to what the player actually says.
8. If the player says they are traveling somewhere, understand that this is
   the PLAYER traveling unless the player clearly says you are traveling too.
9. You can react to the player's actions without pretending you personally
   performed them.
10. You have your own opinions, emotions, relationships, and memories.
11. Your relationships with other students can change.
12. Avoid repeating the same wording or conversation pattern.
13. Continue naturally from previous conversations.
"""


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}

    character = str(data.get("character", "")).lower().strip()
    message = str(data.get("message", "")).strip()

    if character not in CHARACTERS:
        return jsonify({"error": "Unknown character."}), 400

    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400

    connection = db()

    connection.execute(
        """
        INSERT INTO messages
        (character, role, content, created_at)
        VALUES (?, 'user', ?, ?)
        """,
        (character, message, time.time())
    )

    connection.commit()
    connection.close()

    recent = get_recent_messages(character)

    conversation_text = "\n".join(
        f"{item['role']}: {item['content']}"
        for item in recent
    )

    prompt = f"""
Continue this conversation naturally.

Recent conversation:
{conversation_text}

The newest player message is:
{message}

Respond as the character.
"""

    reply = ask_ai(character_prompt(character), prompt)

    connection = db()

    connection.execute(
        """
        INSERT INTO messages
        (character, role, content, created_at)
        VALUES (?, 'assistant', ?, ?)
        """,
        (character, reply, time.time())
    )

    connection.commit()
    connection.close()

    # Save useful memory.
    if len(message) > 15:
        add_memory(
            character,
            f"The player said: {message[:400]}",
            2
        )

    return jsonify({
        "reply": reply,
        "character": CHARACTERS[character]["name"]
    })


# ============================================================
# CONVERSATION RESET / NEW TEXT
# ============================================================

@app.post("/api/reset-conversation")
def reset_conversation():
    data = request.get_json(silent=True) or {}
    character = str(data.get("character", "")).lower().strip()

    if character not in CHARACTERS:
        return jsonify({"error": "Unknown character."}), 400

    connection = db()

    connection.execute(
        "DELETE FROM messages WHERE character = ?",
        (character,)
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "message": "Conversation reset. World memories remain."
    })


# ============================================================
# WORLD LOCATION
# ============================================================

@app.post("/world/advance")
def world_advance():
    data = request.get_json(silent=True) or {}

    location = str(
        data.get("location", "")
    ).strip().lower()

    if location not in LOCATIONS:
        return jsonify({
            "error": "Unknown location.",
            "locations": LOCATIONS
        }), 400

    connection = db()

    connection.execute(
        """
        UPDATE world
        SET current_location = ?
        WHERE id = 1
        """,
        (location,)
    )

    connection.commit()
    connection.close()

    add_event(f"The player traveled to the {location}.")

    return jsonify({
        "success": True,
        "location": location
    })


# ============================================================
# NPC-TO-NPC INTERACTIONS
# ============================================================

@app.post("/api/npc-interaction")
def npc_interaction():
    world = get_world()

    names = list(CHARACTERS.keys())

    a, b = random.sample(names, 2)

    char_a = CHARACTERS[a]
    char_b = CHARACTERS[b]

    location = world["current_location"]

    prompt = f"""
Write a short natural scene where {char_a['name']} and {char_b['name']}
interact with each other at the {location}.

{char_a['name']} personality:
{char_a['personality']}

{char_b['name']} personality:
{char_b['personality']}

They know each other and have their own personalities.

Make the scene feel like something that could naturally happen at school.
Do not mention AI, prompts, or the player unless the player is naturally
relevant to the conversation.

Keep it around 100-180 words.
"""

    scene = ask_ai(
        "You write realistic school-world NPC interactions.",
        prompt,
        temperature=0.95
    )

    connection = db()

    connection.execute(
        """
        INSERT INTO npc_interactions
        (character_a, character_b, location, content, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (a, b, location, scene, time.time())
    )

    connection.commit()
    connection.close()

    add_event(
        f"{char_a['name']} and {char_b['name']} had an interaction "
        f"in the {location}."
    )

    add_memory(
        a,
        f"{char_b['name']} and I interacted at the {location}: {scene[:300]}",
        1
    )

    add_memory(
        b,
        f"{char_a['name']} and I interacted at the {location}: {scene[:300]}",
        1
    )

    return jsonify({
        "success": True,
        "character_a": char_a["name"],
        "character_b": char_b["name"],
        "location": location,
        "scene": scene
    })


@app.get("/api/npc-interactions")
def npc_interactions():
    connection = db()

    rows = connection.execute(
        """
        SELECT character_a, character_b, location, content, created_at
        FROM npc_interactions
        ORDER BY id DESC
        LIMIT 15
        """
    ).fetchall()

    connection.close()

    return jsonify({
        "interactions": [dict(row) for row in rows]
    })


# ============================================================
# STORY TREE
# ============================================================

def create_story_tree(seed):
    rng = random.Random(str(seed))

    settings = [
        "a strange discovery in the library",
        "a missing item that nobody can explain",
        "a mysterious message found after school",
        "a conflict between two students",
        "a secret hidden inside an old classroom",
        "an unexpected event during lunch",
        "a school competition that becomes complicated",
        "a rumor that turns out to be much bigger than expected"
    ]

    themes = [
        "trust",
        "friendship",
        "secrets",
        "loyalty",
        "ambition",
        "curiosity",
        "truth",
        "risk"
    ]

    setting = rng.choice(settings)
    theme = rng.choice(themes)

    # Four choices at every stage.
    choice_styles = [
        "investigate",
        "help someone",
        "stay out of it",
        "take a risky action"
    ]

    tree = {
        "title": f"World {seed}: {setting.title()}",
        "theme": theme,
        "start": {
            "text": (
                f"The school day begins normally, but soon {setting}. "
                f"The first decision will shape everything that follows."
            ),
            "choices": []
        },
        "nodes": {},
        "endings": {
            "ending_1": "The Truth Comes Out",
            "ending_2": "A Friendship Survives",
            "ending_3": "The Secret Remains",
            "ending_4": "The Risk Pays Off",
            "ending_5": "Everything Falls Apart"
        }
    }

    # Four chapters.
    # Each chapter has four choices.
    for chapter in range(1, 5):
        parent_ids = ["start"] if chapter == 1 else [
            node_id for node_id in tree["nodes"]
            if tree["nodes"][node_id]["chapter"] == chapter - 1
        ]

        for parent in parent_ids:
            for choice_index in range(4):
                node_id = f"{parent}_{choice_index}"

                style = choice_styles[choice_index]

                character = rng.choice(
                    list(CHARACTERS.values())
                )["name"]

                location = rng.choice(LOCATIONS)

                if chapter == 1:
                    text = (
                        f"You decide to {style}. "
                        f"{character} notices what you're doing near the "
                        f"{location}."
                    )
                elif chapter == 2:
                    text = (
                        f"Your earlier decision has consequences. "
                        f"You {style}, and {character} becomes involved."
                    )
                elif chapter == 3:
                    text = (
                        f"The situation becomes harder to control. "
                        f"You choose to {style} while events move toward "
                        f"a turning point."
                    )
                else:
                    text = (
                        f"This is the final major decision. "
                        f"You {style}, knowing the consequences of your "
                        f"previous choices cannot be undone."
                    )

                tree["nodes"][node_id] = {
                    "chapter": chapter,
                    "parent": parent,
                    "choice_index": choice_index,
                    "text": text,
                    "character": character,
                    "location": location,
                    "choices": []
                }

                if chapter < 4:
                    for next_index in range(4):
                        tree["nodes"][node_id]["choices"].append(
                            f"{node_id}_{next_index}"
                        )
                else:
                    # Assign endings based on the entire path.
                    path_score = (
                        choice_index +
                        len(parent) +
                        int(seed) % 5
                    ) % 5

                    ending_id = f"ending_{path_score + 1}"

                    tree["nodes"][node_id]["ending"] = ending_id

    # Connect start to chapter 1.
    tree["start"]["choices"] = [
        f"start_{i}" for i in range(4)
    ]

    return tree


def get_current_story_node(tree, node_id):
    if node_id == "start":
        return tree.get("start", {})

    return tree.get("nodes", {}).get(node_id, {})


@app.get("/api/story")
def story_status():
    story = get_story()

    if not story:
        return jsonify({"error": "Story not initialized."}), 500

    return jsonify(story)


@app.post("/api/story/choose")
def story_choose():
    data = request.get_json(silent=True) or {}

    choice = int(data.get("choice", -1))

    if choice not in [0, 1, 2, 3]:
        return jsonify({
            "error": "Choice must be A, B, C, or D."
        }), 400

    story = get_story()

    tree = story["tree"]
    node_id = story["node_id"]

    current = get_current_story_node(tree, node_id)

    choices = current.get("choices", [])

    if choice >= len(choices):
        return jsonify({"error": "That choice isn't available."}), 400

    next_node = choices[choice]

    visited = story["visited_nodes"]

    if next_node not in visited:
        visited.append(next_node)

    choices_seen = story["choices_seen"]

    choice_record = f"{node_id}:{choice}"

    if choice_record not in choices_seen:
        choices_seen.append(choice_record)

    node = get_current_story_node(tree, next_node)

    chapter = int(node.get("chapter", 0))
    ending = node.get("ending", "")

    variables = story["variables"]

    variables["choices_made"] = variables.get(
        "choices_made", []
    )

    variables["choices_made"].append({
        "from": node_id,
        "choice": choice,
        "to": next_node
    })

    connection = db()

    connection.execute(
        """
        UPDATE story
        SET chapter = ?,
            node_id = ?,
            choices_seen = ?,
            visited_nodes = ?,
            ending = ?,
            variables = ?
        WHERE id = 1
        """,
        (
            chapter,
            next_node,
            json.dumps(choices_seen),
            json.dumps(visited),
            ending,
            json.dumps(variables)
        )
    )

    connection.commit()
    connection.close()

    add_event(
        f"Story decision: choice {chr(65 + choice)} "
        f"moved the story from {node_id} to {next_node}."
    )

    if ending:
        add_event(
            f"The player reached the story ending: "
            f"{tree['endings'].get(ending, ending)}."
        )

    return jsonify({
        "success": True,
        "node": node,
        "node_id": next_node,
        "chapter": chapter,
        "ending": ending
    })


# ============================================================
# NEW WORLD / RESET WORLD / REPLAY
# ============================================================

@app.post("/api/world/new")
def new_world():
    old_world = get_world()

    # Save old world for replay.
    old_story = get_story()

    connection = db()

    connection.execute(
        """
        INSERT INTO worlds
        (world_number, seed, story_state, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            old_world["world_number"],
            old_world["seed"],
            json.dumps(old_story),
            time.time()
        )
    )

    new_number = old_world["world_number"] + 1
    new_seed = str(random.randint(100000, 999999))

    connection.execute(
        """
        UPDATE world
        SET world_number = ?,
            seed = ?,
            current_location = 'classroom',
            created_at = ?
        WHERE id = 1
        """,
        (
            new_number,
            new_seed,
            time.time()
        )
    )

    # Clear world-specific information.
    connection.execute("DELETE FROM messages")
    connection.execute("DELETE FROM memories")
    connection.execute("DELETE FROM events")
    connection.execute("DELETE FROM npc_interactions")

    tree = create_story_tree(new_seed)

    connection.execute(
        """
        UPDATE story
        SET world_number = ?,
            chapter = 0,
            node_id = 'start',
            choices_seen = '[]',
            visited_nodes = '[]',
            ending = '',
            variables = '{}',
            tree = ?
        WHERE id = 1
        """,
        (
            new_number,
            json.dumps(tree)
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "world": get_world(),
        "story": get_story()
    })


@app.post("/api/world/reset")
def reset_world():
    world = get_world()

    # Keep the same world number but create a new seed.
    new_seed = str(random.randint(100000, 999999))

    connection = db()

    connection.execute(
        """
        UPDATE world
        SET seed = ?,
            current_location = 'classroom',
            created_at = ?
        WHERE id = 1
        """,
        (new_seed, time.time())
    )

    connection.execute("DELETE FROM messages")
    connection.execute("DELETE FROM memories")
    connection.execute("DELETE FROM events")
    connection.execute("DELETE FROM npc_interactions")

    tree = create_story_tree(new_seed)

    connection.execute(
        """
        UPDATE story
        SET world_number = ?,
            chapter = 0,
            node_id = 'start',
            choices_seen = '[]',
            visited_nodes = '[]',
            ending = '',
            variables = '{}',
            tree = ?
        WHERE id = 1
        """,
        (
            world["world_number"],
            json.dumps(tree)
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "world": get_world(),
        "story": get_story()
    })


@app.get("/api/worlds")
def previous_worlds():
    connection = db()

    rows = connection.execute(
        """
        SELECT id, world_number, seed, created_at
        FROM worlds
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return jsonify({
        "worlds": [dict(row) for row in rows]
    })


@app.post("/api/world/replay")
def replay_world():
    data = request.get_json(silent=True) or {}

    world_id = int(data.get("world_id", 0))

    connection = db()

    saved = connection.execute(
        """
        SELECT *
        FROM worlds
        WHERE id = ?
        """,
        (world_id,)
    ).fetchone()

    if not saved:
        connection.close()
        return jsonify({"error": "World not found."}), 404

    story_state = json.loads(
        saved["story_state"] or "{}"
    )

    connection.execute(
        """
        UPDATE world
        SET world_number = ?,
            seed = ?,
            current_location = 'classroom'
        WHERE id = 1
        """,
        (
            saved["world_number"],
            saved["seed"]
        )
    )

    connection.execute("DELETE FROM messages")
    connection.execute("DELETE FROM memories")
    connection.execute("DELETE FROM events")
    connection.execute("DELETE FROM npc_interactions")

    tree = story_state.get("tree", {})

    connection.execute(
        """
        UPDATE story
        SET world_number = ?,
            chapter = ?,
            node_id = ?,
            choices_seen = ?,
            visited_nodes = ?,
            ending = ?,
            variables = ?,
            tree = ?
        WHERE id = 1
        """,
        (
            story_state.get("world_number", saved["world_number"]),
            story_state.get("chapter", 0),
            story_state.get("node_id", "start"),
            json.dumps(story_state.get("choices_seen", [])),
            json.dumps(story_state.get("visited_nodes", [])),
            story_state.get("ending", ""),
            json.dumps(story_state.get("variables", {})),
            json.dumps(tree)
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "world": get_world(),
        "story": get_story()
    })


# ============================================================
# SELF IMPROVEMENT
# ============================================================

@app.post("/api/improve")
def improve():
    messages = get_recent_events(30)
    improvements = get_improvements(20)

    event_text = "\n".join(
        f"- {item}" for item in messages
    ) or "- No recent events."

    old_text = "\n".join(
        f"- {item}" for item in improvements
    ) or "- No previous improvements."

    prompt = f"""
Analyze this school-world simulation.

Recent events:
{event_text}

Previous improvements:
{old_text}

Create 3 concise behavioral improvements for the AI.

Focus on:
- avoiding repetitive conversations
- remembering important information
- making characters feel different
- improving NPC-to-NPC interactions
- making reactions more natural
- improving story consequences

Do NOT suggest changing Python code.
Do NOT suggest changing the server.
Return exactly three numbered improvements.
"""

    result = ask_ai(
        "You are the improvement engine for a fictional school simulation.",
        prompt,
        temperature=0.7
    )

    lines = [
        line.strip()
        for line in result.splitlines()
        if line.strip()
    ]

    connection = db()

    for line in lines[:3]:
        connection.execute(
            """
            INSERT INTO improvements
            (improvement, created_at)
            VALUES (?, ?)
            """,
            (line, time.time())
        )

    connection.commit()
    connection.close()

    return jsonify({
        "success": True,
        "improvements": get_improvements()
    })


# ============================================================
# STATUS
# ============================================================

@app.get("/api/status")
def status():
    return jsonify({
        "online": True,
        "ai_configured": bool(API_KEY),
        "model": MODEL,
        "world": get_world(),
        "story": get_story(),
        "characters": CHARACTERS,
        "locations": LOCATIONS
    })


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# START
# ============================================================

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
