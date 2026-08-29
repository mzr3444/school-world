python
import os
import json
import random
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, render_template
from openai import OpenAI


# ============================================================
# CONFIG
# ============================================================

app = Flask(__name__)

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY
) if API_KEY else None

SAVE_FILE = Path("worlds.json")


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value, fallback=""):
    if value is None:
        return fallback

    text = str(value).strip()

    return text if text else fallback


def now():
    return datetime.utcnow().isoformat()


def load_worlds():
    if not SAVE_FILE.exists():
        return {}

    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return {}


def save_worlds(worlds):
    temporary = SAVE_FILE.with_suffix(".tmp")

    with open(temporary, "w", encoding="utf-8") as f:
        json.dump(worlds, f, indent=2, ensure_ascii=False)

    temporary.replace(SAVE_FILE)


def get_world(world_id):
    worlds = load_worlds()
    return worlds.get(world_id)


def store_world(world):
    worlds = load_worlds()
    worlds[world["id"]] = world
    save_worlds(worlds)


# ============================================================
# STORY TREE
# ============================================================

LOCATIONS = [
    "Classroom",
    "Library",
    "Science Hall",
    "Courtyard",
    "Gym",
    "Computer Lab",
    "Administration Office",
    "Back Hallway",
    "Rooftop",
    "Auditorium",
    "Basement",
    "Front Entrance"
]


CHARACTER_FIRST_NAMES = [
    "Alex",
    "Jordan",
    "Maya",
    "Ethan",
    "Riley",
    "Sam",
    "Taylor",
    "Casey",
    "Morgan",
    "Avery"
]


CHARACTER_TRAITS = [
    "quiet but observant",
    "confident and sarcastic",
    "friendly but nervous",
    "extremely curious",
    "protective of their friends",
    "skeptical of authority",
    "calm under pressure",
    "impulsive and fearless",
    "secretive and intelligent",
    "loyal but easily hurt"
]


def generate_characters(rng):
    names = rng.sample(CHARACTER_FIRST_NAMES, 5)

    characters = {}

    for i, name in enumerate(names):
        characters[name] = {
            "name": name,
            "trait": rng.choice(CHARACTER_TRAITS),
            "relationship": 0,
            "trust": 0,
            "alive": True
        }

    return characters


def make_story_tree(rng):
    """
    Every world gets the same overall branching structure,
    but different titles, locations, themes and characters.

    There are 12 major nodes and 5 major endings.
    """

    locations = rng.sample(LOCATIONS, 12)

    themes = [
        "a hidden experiment",
        "a missing student's secret",
        "a strange message appearing around the school",
        "a locked room nobody remembers",
        "a conspiracy involving the administration",
        "a mysterious device discovered after school",
        "a series of unexplained events",
        "a secret meeting beneath the school"
    ]

    theme = rng.choice(themes)

    tree = {
        "start": {
            "id": "start",
            "title": "The Beginning",
            "chapter": 1,
            "location": locations[0],
            "type": "normal",
            "seen": True,
            "description": "",
            "choices": [
                {"text": "Investigate", "next": "investigate"},
                {"text": "Ignore it", "next": "ignore"},
                {"text": "Tell someone", "next": "tell"}
            ]
        },

        "investigate": {
            "id": "investigate",
            "title": "Something Is Wrong",
            "chapter": 2,
            "location": locations[1],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Search for evidence", "next": "evidence"},
                {"text": "Question someone", "next": "question"},
                {"text": "Keep the discovery secret", "next": "secret"}
            ]
        },

        "ignore": {
            "id": "ignore",
            "title": "Pretending Nothing Happened",
            "chapter": 2,
            "location": locations[2],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Follow the strange event", "next": "evidence"},
                {"text": "Stay with your friends", "next": "friend"},
                {"text": "Leave the area", "next": "question"}
            ]
        },

        "tell": {
            "id": "tell",
            "title": "Who Can Be Trusted?",
            "chapter": 2,
            "location": locations[3],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Trust your friend", "next": "friend"},
                {"text": "Tell an adult", "next": "authority"},
                {"text": "Tell everyone", "next": "chaos"}
            ]
        },

        "evidence": {
            "id": "evidence",
            "title": "The First Clue",
            "chapter": 3,
            "location": locations[4],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Take the evidence", "next": "discovery"},
                {"text": "Leave it behind", "next": "friend"},
                {"text": "Destroy it", "next": "rebellion"}
            ]
        },

        "question": {
            "id": "question",
            "title": "Questions Without Answers",
            "chapter": 3,
            "location": locations[5],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Push for the truth", "next": "discovery"},
                {"text": "Back off", "next": "friend"},
                {"text": "Threaten to expose them", "next": "rebellion"}
            ]
        },

        "secret": {
            "id": "secret",
            "title": "A Secret Between Friends",
            "chapter": 3,
            "location": locations[6],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Tell your closest ally", "next": "friend"},
                {"text": "Investigate alone", "next": "discovery"},
                {"text": "Use the secret against someone", "next": "betrayal"}
            ]
        },

        "friend": {
            "id": "friend",
            "title": "An Unexpected Alliance",
            "chapter": 4,
            "location": locations[7],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Work together", "next": "alliance"},
                {"text": "Keep your distance", "next": "discovery"},
                {"text": "Test their loyalty", "next": "betrayal"}
            ]
        },

        "authority": {
            "id": "authority",
            "title": "The Official Story",
            "chapter": 4,
            "location": locations[8],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Believe them", "next": "alliance"},
                {"text": "Investigate their story", "next": "discovery"},
                {"text": "Challenge them", "next": "rebellion"}
            ]
        },

        "chaos": {
            "id": "chaos",
            "title": "Everything Changes",
            "chapter": 4,
            "location": locations[9],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Protect your friends", "next": "alliance"},
                {"text": "Find out who caused this", "next": "rebellion"},
                {"text": "Run", "next": "isolation"}
            ]
        },

        "discovery": {
            "id": "discovery",
            "title": "The Truth Beneath Everything",
            "chapter": 5,
            "location": locations[10],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Reveal the truth", "next": "truth"},
                {"text": "Hide the truth", "next": "sacrifice"},
                {"text": "Use the truth as leverage", "next": "betrayal"}
            ]
        },

        "alliance": {
            "id": "alliance",
            "title": "Choose Who Stands With You",
            "chapter": 5,
            "location": locations[11],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Protect everyone", "next": "truth"},
                {"text": "Choose one person", "next": "sacrifice"},
                {"text": "Take control", "next": "rebellion"}
            ]
        },

        "rebellion": {
            "id": "rebellion",
            "title": "No Going Back",
            "chapter": 6,
            "location": locations[0],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Lead the resistance", "next": "ending_revolution"},
                {"text": "Protect the innocent", "next": "ending_hope"},
                {"text": "Destroy everything connected to it", "next": "ending_collapse"}
            ]
        },

        "betrayal": {
            "id": "betrayal",
            "title": "The Price of Trust",
            "chapter": 6,
            "location": locations[1],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Admit what you did", "next": "ending_sacrifice"},
                {"text": "Blame someone else", "next": "ending_betrayal"},
                {"text": "Run before they find out", "next": "ending_isolation"}
            ]
        },

        "isolation": {
            "id": "isolation",
            "title": "Alone",
            "chapter": 6,
            "location": locations[2],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Return to your friends", "next": "ending_hope"},
                {"text": "Leave everything behind", "next": "ending_isolation"}
            ]
        },

        "truth": {
            "id": "truth",
            "title": "The Final Choice",
            "chapter": 6,
            "location": locations[3],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Tell everyone", "next": "ending_hope"},
                {"text": "Take responsibility", "next": "ending_sacrifice"},
                {"text": "Expose the people responsible", "next": "ending_revolution"}
            ]
        },

        "sacrifice": {
            "id": "sacrifice",
            "title": "What Are You Willing To Lose?",
            "chapter": 6,
            "location": locations[4],
            "type": "normal",
            "seen": False,
            "description": "",
            "choices": [
                {"text": "Save everyone else", "next": "ending_sacrifice"},
                {"text": "Save yourself", "next": "ending_betrayal"}
            ]
        },

        "ending_hope": {
            "id": "ending_hope",
            "title": "ENDING: A New Beginning",
            "chapter": 7,
            "location": locations[5],
            "type": "ending",
            "ending_name": "A New Beginning",
            "seen": False,
            "description": "",
            "choices": []
        },

        "ending_revolution": {
            "id": "ending_revolution",
            "title": "ENDING: The Revolution",
            "chapter": 7,
            "location": locations[6],
            "type": "ending",
            "ending_name": "The Revolution",
            "seen": False,
            "description": "",
            "choices": []
        },

        "ending_sacrifice": {
            "id": "ending_sacrifice",
            "title": "ENDING: The Sacrifice",
            "chapter": 7,
            "location": locations[7],
            "type": "ending",
            "ending_name": "The Sacrifice",
            "seen": False,
            "description": "",
            "choices": []
        },

        "ending_betrayal": {
            "id": "ending_betrayal",
            "title": "ENDING: Broken Trust",
            "chapter": 7,
            "location": locations[8],
            "type": "ending",
            "ending_name": "Broken Trust",
            "seen": False,
            "description": "",
            "choices": []
        },

        "ending_isolation": {
            "id": "ending_isolation",
            "title": "ENDING: Alone",
            "chapter": 7,
            "location": locations[9],
            "type": "ending",
            "ending_name": "Alone",
            "seen": False,
            "description": "",
            "choices": []
        },

        "ending_collapse": {
            "id": "ending_collapse",
            "title": "ENDING: Collapse",
            "chapter": 7,
            "location": locations[10],
            "type": "ending",
            "ending_name": "Collapse",
            "seen": False,
            "description": "",
            "choices": []
        }
    }

    # Give the world a unique theme.
    for node in tree.values():
        node["theme"] = theme

    return tree


# ============================================================
# WORLD CREATION
# ============================================================

def create_world():
    seed = random.randint(100000000, 999999999)
    rng = random.Random(seed)

    characters = generate_characters(rng)
    tree = make_story_tree(rng)

    world_id = str(uuid.uuid4())

    world = {
        "id": world_id,
        "seed": seed,
        "title": f"School World #{str(seed)[-4:]}",
        "created_at": now(),
        "last_played": now(),

        "theme": tree["start"]["theme"],

        "characters": characters,
        "tree": tree,

        "current_node": "start",

        "story_state": {
            "trust": 0,
            "courage": 0,
            "rebellion": 0,
            "reputation": 0,
            "secrets": [],
            "major_choices": [],
            "visited_locations": [],
            "relationship_changes": []
        },

        "history": [
            {
                "node": "start",
                "choice": None,
                "timestamp": now()
            }
        ],

        "completed": False,
        "ending": None
    }

    store_world(world)

    return world


# ============================================================
# STORY TREE DATA FOR FRONTEND
# ============================================================

def tree_for_client(world):
    result = []

    for node_id, node in world["tree"].items():

        choices = []

        for choice in node.get("choices", []):
            target = world["tree"].get(choice["next"])

            choices.append({
                "text": choice["text"],
                "next": choice["next"],
                "next_seen": bool(target and target.get("seen", False))
            })

        result.append({
            "id": node_id,
            "title": node["title"],
            "chapter": node["chapter"],
            "location": node["location"],
            "type": node["type"],
            "seen": bool(node.get("seen", False)),
            "choices": choices,
            "ending_name": node.get("ending_name")
        })

    result.sort(key=lambda x: (x["chapter"], x["id"]))

    return result


def public_world(world):
    current = world["tree"][world["current_node"]]

    return {
        "id": world["id"],
        "title": world["title"],
        "seed": world["seed"],
        "theme": world["theme"],
        "current_node": world["current_node"],
        "current_scene": {
            "id": current["id"],
            "title": current["title"],
            "chapter": current["chapter"],
            "location": current["location"],
            "type": current["type"],
            "description": current.get("description", ""),
            "choices": current.get("choices", []),
            "ending_name": current.get("ending_name")
        },
        "characters": world["characters"],
        "story_state": world["story_state"],
        "history": world["history"],
        "completed": world["completed"],
        "ending": world["ending"],
        "tree": tree_for_client(world)
    }


# ============================================================
# AI STORY GENERATION
# ============================================================

def generate_scene(world, node_id, player_choice=None):
    if not client:
        return (
            "The world is ready, but the AI connection is not configured. "
            "Check OPENROUTER_API_KEY in Render."
        )

    node = world["tree"][node_id]

    characters = []

    for character in world["characters"].values():
        if character["alive"]:
            characters.append(
                f"{character['name']} ({character['trait']}, "
                f"trust={character['trust']})"
            )

    previous_history = []

    for item in world["history"][-10:]:
        previous_history.append(
            f"Node: {item['node']} | Choice: {item.get('choice')}"
        )

    if not previous_history:
        previous_history_text = "This is the beginning."
    else:
        previous_history_text = "\n".join(previous_history)

    prompt = f"""
You are the narrative engine for a long-running interactive school-world game.

This is WORLD SEED {world['seed']}.
This seed represents one unique playthrough.

WORLD THEME:
{world['theme']}

CURRENT CHAPTER:
{node['chapter']}

CURRENT LOCATION:
{node['location']}

CURRENT SCENE:
{node['title']}

PLAYER'S PREVIOUS CHOICE:
{player_choice or "This is the opening scene."}

CHARACTERS:
{chr(10).join(characters)}

RECENT STORY HISTORY:
{previous_history_text}

STORY STATE:
{json.dumps(world['story_state'], indent=2)}

Write a substantial interactive scene.

IMPORTANT RULES:

1. Do NOT treat the player's actions such as "go to the library"
   as dialogue spoken by the player.

2. Treat player choices as EVENTS that happened in the world.

3. Characters should REACT to what the player did naturally.

4. Characters should have their own opinions, emotions,
   goals, fears and memories.

5. Characters may disagree with the player.

6. Characters may remember previous choices.

7. Never make every character automatically agree with the player.

8. The scene should feel like a continuation of the same story.

9. Mention the current location naturally.

10. Make consequences of previous choices matter.

11. Do not reveal future branches.

12. Do not tell the player which ending they are approaching.

13. Write around 700-1100 words.

14. Use dialogue heavily.

15. Do not write a list of choices at the end.
   The website will provide the choices.

16. Do not use markdown headings.

17. The player is the protagonist.
   Do not invent dialogue for the player unless necessary
   to describe what happened.

18. Make the characters react to the player's previous action
   without literally repeating the choice as if the player
   said it out loud.

Return only the story scene.
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an immersive branching-story writer. "
                        "Maintain continuity and character memory."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.9,
            max_tokens=1800
        )

        text = response.choices[0].message.content

        if not text:
            return "The scene could not be generated."

        return text.strip()

    except Exception as e:
        return f"AI story error: {str(e)}"


# ============================================================
# ROUTES
# ============================================================

@app.route("/", methods=["GET", "HEAD"])
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "ai_configured": bool(API_KEY),
        "model": MODEL
    })


@app.route("/world/new", methods=["POST"])
def new_world():
    world = create_world()

    # Generate opening scene immediately.
    scene = generate_scene(world, "start")
    world["tree"]["start"]["description"] = scene

    store_world(world)

    return jsonify(public_world(world))


@app.route("/worlds", methods=["GET"])
def worlds():
    all_worlds = load_worlds()

    result = []

    for world in all_worlds.values():
        result.append({
            "id": world["id"],
            "title": world["title"],
            "seed": world["seed"],
            "chapter": world["tree"][world["current_node"]]["chapter"],
            "current_node": world["current_node"],
            "completed": world["completed"],
            "ending": world["ending"],
            "last_played": world["last_played"]
        })

    result.sort(
        key=lambda x: x["last_played"],
        reverse=True
    )

    return jsonify({
        "worlds": result
    })


@app.route("/world/<world_id>", methods=["GET"])
def get_world_route(world_id):
    world = get_world(world_id)

    if not world:
        return jsonify({
            "error": "World not found."
        }), 404

    return jsonify(public_world(world))


@app.route("/world/<world_id>/restart", methods=["POST"])
def restart_world(world_id):
    world = get_world(world_id)

    if not world:
        return jsonify({
            "error": "World not found."
        }), 404

    # Reset every node's seen state.
    for node in world["tree"].values():
        node["seen"] = False
        node["description"] = ""

    world["tree"]["start"]["seen"] = True

    world["current_node"] = "start"

    world["story_state"] = {
        "trust": 0,
        "courage": 0,
        "rebellion": 0,
        "reputation": 0,
        "secrets": [],
        "major_choices": [],
        "visited_locations": [],
        "relationship_changes": []
    }

    for character in world["characters"].values():
        character["relationship"] = 0
        character["trust"] = 0
        character["alive"] = True

    world["history"] = [
        {
            "node": "start",
            "choice": None,
            "timestamp": now()
        }
    ]

    world["completed"] = False
    world["ending"] = None
    world["last_played"] = now()

    world["tree"]["start"]["description"] = generate_scene(
        world,
        "start"
    )

    store_world(world)

    return jsonify(public_world(world))


@app.route("/world/<world_id>", methods=["DELETE"])
def delete_world(world_id):
    worlds = load_worlds()

    if world_id not in worlds:
        return jsonify({
            "error": "World not found."
        }), 404

    del worlds[world_id]

    save_worlds(worlds)

    return jsonify({
        "success": True
    })


@app.route("/world/<world_id>/choose", methods=["POST"])
def choose(world_id):
    world = get_world(world_id)

    if not world:
        return jsonify({
            "error": "World not found."
        }), 404

    if world["completed"]:
        return jsonify({
            "error": "This world has already ended."
        }), 400

    data = request.get_json(silent=True) or {}

    choice_index = data.get("choice_index")

    if not isinstance(choice_index, int):
        return jsonify({
            "error": "choice_index must be a number."
        }), 400

    current_id = world["current_node"]
    current = world["tree"][current_id]

    choices = current.get("choices", [])

    if choice_index < 0 or choice_index >= len(choices):
        return jsonify({
            "error": "Invalid choice."
        }), 400

    selected = choices[choice_index]

    next_id = selected["next"]

    if next_id not in world["tree"]:
        return jsonify({
            "error": "Story branch does not exist."
        }), 500

    # --------------------------------------------------------
    # Apply consequences.
    # --------------------------------------------------------

    choice_text = selected["text"].lower()

    if any(word in choice_text for word in [
        "rebel",
        "destroy",
        "challenge",
        "expose",
        "resistance"
    ]):
        world["story_state"]["rebellion"] += 2

    if any(word in choice_text for word in [
        "protect",
        "trust",
        "together",
        "save",
        "help"
    ]):
        world["story_state"]["trust"] += 2

    if any(word in choice_text for word in [
        "secret",
        "hide",
        "alone",
        "run"
    ]):
        world["story_state"]["secrets"].append(
            f"{current_id}:{choice_text}"
        )

    if any(word in choice_text for word in [
        "betray",
        "blame",
        "threaten"
    ]):
        world["story_state"]["reputation"] -= 2

    world["story_state"]["major_choices"].append({
        "from": current_id,
        "choice": selected["text"],
        "to": next_id
    })

    # Character relationships evolve.
    for character in world["characters"].values():

        if any(word in choice_text for word in [
            "protect",
            "save",
            "help",
            "trust"
        ]):
            character["trust"] += 1
            character["relationship"] += 1

        if any(word in choice_text for word in [
            "betray",
            "blame",
            "threaten"
        ]):
            character["trust"] -= 1
            character["relationship"] -= 1

    world["story_state"]["visited_locations"].append(
        current["location"]
    )

    # Mark destination as seen.
    world["tree"][next_id]["seen"] = True

    world["history"].append({
        "node": next_id,
        "choice": selected["text"],
        "from": current_id,
        "timestamp": now()
    })

    world["current_node"] = next_id
    world["last_played"] = now()

    next_node = world["tree"][next_id]

    # --------------------------------------------------------
    # Ending
    # --------------------------------------------------------

    if next_node["type"] == "ending":

        scene = generate_scene(
            world,
            next_id,
            selected["text"]
        )

        next_node["description"] = scene

        world["completed"] = True
        world["ending"] = next_node.get(
            "ending_name",
            next_node["title"]
        )

    else:

        scene = generate_scene(
            world,
            next_id,
            selected["text"]
        )

        next_node["description"] = scene

    store_world(world)

    return jsonify(public_world(world))


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
