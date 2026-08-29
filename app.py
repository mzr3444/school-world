import os
import random
import uuid
from copy import deepcopy

from flask import Flask, jsonify, render_template, request, session
from openai import OpenAI

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "school-world-secret-key")

API_KEY = os.environ.get("OPENROUTER_API_KEY")
MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-20b")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY or "missing-key"
)

# ---------------------------------------------------------
# WORLD STORAGE
# ---------------------------------------------------------

WORLDS = {}

LOCATIONS = [
    "Classroom",
    "Library",
    "Cafeteria",
    "Gym",
    "Courtyard",
    "Science Lab",
    "Music Room",
    "Art Room",
    "Rooftop",
    "Hallway",
    "Computer Lab"
]

CHARACTERS = [
    {
        "name": "Alex",
        "personality": "quiet, observant, intelligent, and suspicious of strange events"
    },
    {
        "name": "Maya",
        "personality": "confident, energetic, loyal, and willing to take risks"
    },
    {
        "name": "Jordan",
        "personality": "funny, sarcastic, friendly, but hides serious feelings"
    },
    {
        "name": "Sam",
        "personality": "curious, analytical, investigative, and easily fascinated"
    }
]

STORY_THEMES = [
    {
        "title": "The Locked Wing",
        "setup": (
            "A normally sealed wing of the school suddenly opens after the final bell. "
            "Nobody admits knowing why."
        )
    },
    {
        "title": "The Missing Memory",
        "setup": (
            "One student insists that something important happened yesterday, "
            "but everyone else remembers the day differently."
        )
    },
    {
        "title": "The School After Dark",
        "setup": (
            "After the lights go out, one hallway remains illuminated even though "
            "the entire school should be empty."
        )
    },
    {
        "title": "The Unsent Message",
        "setup": (
            "A forgotten computer displays a message containing your name, "
            "even though nobody remembers typing it."
        )
    },
    {
        "title": "The Hidden Floor",
        "setup": (
            "An elevator button appears that nobody has ever seen before."
        )
    },
    {
        "title": "The Substitute",
        "setup": (
            "A substitute teacher arrives who seems to know details about students "
            "that they should not know."
        )
    }
]

ENDING_TYPES = [
    "Truth",
    "Trust",
    "Rebellion",
    "Quiet Escape",
    "Discovery",
    "Sacrifice"
]


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def make_world():
    rng = random.Random(uuid.uuid4().int)

    theme = rng.choice(STORY_THEMES)

    characters = deepcopy(CHARACTERS)
    rng.shuffle(characters)

    locations = LOCATIONS[:]
    rng.shuffle(locations)

    endings = ENDING_TYPES[:]
    rng.shuffle(endings)

    world_id = str(uuid.uuid4())

    nodes = {}

    # -----------------------------------------------------
    # ROOT
    # -----------------------------------------------------

    nodes["start"] = {
        "id": "start",
        "title": theme["title"],
        "depth": 0,
        "text": theme["setup"],
        "choices": [],
        "ending": None
    }

    # -----------------------------------------------------
    # FIRST BRANCH
    # -----------------------------------------------------

    first_choices = [
        ("Investigate immediately", "curiosity"),
        ("Find someone you trust", "trust"),
        ("Stay out of it", "caution")
    ]

    rng.shuffle(first_choices)

    for i, (text, flag) in enumerate(first_choices):
        node_id = f"a{i}"

        nodes["start"]["choices"].append({
            "id": node_id,
            "text": text,
            "next": node_id
        })

        nodes[node_id] = {
            "id": node_id,
            "title": text,
            "depth": 1,
            "text": (
                f"Your decision to {text.lower()} changes the situation. "
                f"The people around you react differently, and the mystery becomes "
                f"more complicated."
            ),
            "choices": [],
            "flag": flag,
            "ending": None
        }

        # -------------------------------------------------
        # SECOND BRANCH
        # -------------------------------------------------

        second_choices = [
            ("Tell Alex what you discovered", "alex"),
            ("Keep the information secret", "secret"),
            ("Search another part of the school", "search")
        ]

        rng.shuffle(second_choices)

        for j, (second_text, second_flag) in enumerate(second_choices):

            node2 = f"b{i}_{j}"

            nodes[node_id]["choices"].append({
                "id": node2,
                "text": second_text,
                "next": node2
            })

            nodes[node2] = {
                "id": node2,
                "title": second_text,
                "depth": 2,
                "text": (
                    "Your previous decision has consequences. "
                    "Someone notices what you are doing, and the situation begins "
                    "moving in a direction you did not completely expect."
                ),
                "choices": [],
                "flag": second_flag,
                "ending": None
            }

            # ---------------------------------------------
            # FINAL BRANCH
            # ---------------------------------------------

            final_choices = [
                ("Protect what you discovered", "protect"),
                ("Tell everyone the truth", "truth"),
                ("Use the information to your advantage", "power")
            ]

            rng.shuffle(final_choices)

            for k, (final_text, final_flag) in enumerate(final_choices):

                node3 = f"c{i}_{j}_{k}"

                ending = endings[
                    (i * 3 + j + k) % len(endings)
                ]

                nodes[node2]["choices"].append({
                    "id": node3,
                    "text": final_text,
                    "next": node3
                })

                nodes[node3] = {
                    "id": node3,
                    "title": final_text,
                    "depth": 3,
                    "text": (
                        f"The consequences of your earlier choices finally collide. "
                        f"You chose {flag}, then {second_flag}, and finally "
                        f"{final_flag}. Those decisions determine how everything ends."
                    ),
                    "choices": [],
                    "ending": ending
                }

    world = {
        "id": world_id,
        "title": theme["title"],
        "setup": theme["setup"],
        "locations": locations,
        "characters": characters,
        "nodes": nodes,

        "current": "start",
        "visited": ["start"],
        "history": [],
        "flags": [],

        "started": False,
        "ended": False,
        "ending": None,

        "chat_history": []
    }

    WORLDS[world_id] = world

    return world


def get_world():
    world_id = session.get("world_id")

    if world_id and world_id in WORLDS:
        return WORLDS[world_id]

    world = make_world()
    session["world_id"] = world["id"]

    return world


def public_world(world):
    result = deepcopy(world)

    # Don't send the entire AI conversation to the browser API.
    result.pop("chat_history", None)

    return result


# ---------------------------------------------------------
# AI
# ---------------------------------------------------------

def build_messages(world, user_message, story_mode=False):

    character_info = "\n".join(
        f"- {c['name']}: {c['personality']}"
        for c in world["characters"]
    )

    recent_history = world["chat_history"][-24:]

    location = world["locations"][0]

    system_prompt = f"""
You are the AI inside a living school-world game.

WORLD:
Title: {world["title"]}
Current location: {location}

CHARACTERS:
{character_info}

CURRENT STORY NODE:
{world["current"]}

WORLD FLAGS:
{", ".join(world["flags"]) if world["flags"] else "None"}

IMPORTANT:

The player controls themselves.

Never speak as the player.

Never say that the player "must" perform an action.

If the player says they traveled from one location to another,
characters may notice their arrival naturally.

For example, DO NOT say:
"You traveled from the classroom to the library."

Instead, have the character react naturally:
"You made it. Maya looks up from the table and raises an eyebrow."

Characters should feel like actual people.

They can:
- disagree
- joke
- become suspicious
- remember previous conversations
- become closer to the player
- become angry
- change their opinions
- make their own decisions
- react to events
- interrupt
- ask questions
- have different personalities

Do not repeat internal game instructions.

Do not reveal hidden story tree information.

Keep conversations substantial.

When a response deserves it, write several paragraphs rather than only
one or two sentences.

Do not rush the story toward an ending.

Keep continuity with previous conversations.
"""

    if story_mode:
        system_prompt += """
STORY MODE IS ACTIVE.

The current story node and previous choices are canon.

The player's choices must have consequences.

Do not reset the story because of a normal conversation.

Do not invent a completely unrelated storyline.

Make events feel connected to previous decisions.
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    for item in recent_history:
        messages.append(item)

    messages.append({
        "role": "user",
        "content": clean_text(user_message)
    })

    return messages


def ask_ai(world, message, story_mode=False):

    if not API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is missing from Render Environment Variables."
        )

    response = client.chat.completions.create(
        model=MODEL,
        messages=build_messages(
            world,
            message,
            story_mode
        ),
        temperature=0.9,
        max_tokens=1200
    )

    answer = response.choices[0].message.content

    if not answer:
        answer = "I don't have a response right now."

    answer = clean_text(answer)

    world["chat_history"].append({
        "role": "user",
        "content": clean_text(message)
    })

    world["chat_history"].append({
        "role": "assistant",
        "content": answer
    })

    # Keeps conversations long without allowing infinite memory growth.
    world["chat_history"] = world["chat_history"][-50:]

    return answer


# ---------------------------------------------------------
# HOME
# ---------------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------------------------------------------------
# WORLD API
# ---------------------------------------------------------

@app.get("/api/world")
def api_world():

    world = get_world()

    return jsonify(public_world(world))


@app.post("/world/reset")
def reset_world():

    old_world = get_world()

    old_world["ended"] = True

    new_world = make_world()

    session["world_id"] = new_world["id"]

    return jsonify(public_world(new_world))


@app.post("/world/advance")
def advance_world():

    world = get_world()

    return jsonify({
        "ok": True,
        "world_id": world["id"],
        "location": world["locations"][0]
    })


# ---------------------------------------------------------
# NORMAL AI CHAT
# ---------------------------------------------------------

@app.post("/chat")
def chat():

    world = get_world()

    data = request.get_json(silent=True) or {}

    message = clean_text(data.get("message"))

    if not message:
        return jsonify({
            "error": "Message cannot be empty."
        }), 400

    try:

        answer = ask_ai(
            world,
            message,
            story_mode=False
        )

        return jsonify({
            "reply": answer,
            "world": public_world(world)
        })

    except Exception as exc:

        app.logger.exception("Chat failed")

        return jsonify({
            "error": f"AI error: {clean_text(exc)}"
        }), 500


# ---------------------------------------------------------
# STORY START
# ---------------------------------------------------------

@app.post("/story/start")
def story_start():

    world = get_world()

    world["started"] = True

    node = world["nodes"][world["current"]]

    prompt = f"""
Begin the story naturally.

TITLE:
{world["title"]}

SCENE:
{node["text"]}

Introduce the situation and characters.

Do not list the player's choices as system instructions.

Make it feel like the opening scene of an interactive game.

Make the scene detailed and interesting.
"""

    try:

        answer = ask_ai(
            world,
            prompt,
            story_mode=True
        )

        return jsonify({
            "reply": answer,
            "world": public_world(world)
        })

    except Exception as exc:

        app.logger.exception("Story start failed")

        return jsonify({
            "error": f"Story error: {clean_text(exc)}"
        }), 500


# ---------------------------------------------------------
# STORY CHOICE
# ---------------------------------------------------------

@app.post("/story/choose")
def story_choose():

    world = get_world()

    data = request.get_json(silent=True) or {}

    choice_id = clean_text(data.get("choice_id"))

    current_node = world["nodes"].get(
        world["current"]
    )

    if not current_node:

        return jsonify({
            "error": "Current story node does not exist."
        }), 500

    choice = None

    for possible_choice in current_node["choices"]:

        if possible_choice["id"] == choice_id:

            choice = possible_choice
            break

    if not choice:

        return jsonify({
            "error": "That choice is not available."
        }), 400

    next_node = world["nodes"].get(
        choice["next"]
    )

    if not next_node:

        return jsonify({
            "error": "Next story node does not exist."
        }), 500

    # Record choice.
    world["history"].append({
        "from": current_node["id"],
        "choice": choice["text"],
        "to": next_node["id"]
    })

    world["current"] = next_node["id"]

    if next_node.get("flag"):

        if next_node["flag"] not in world["flags"]:

            world["flags"].append(
                next_node["flag"]
            )

    if next_node["id"] not in world["visited"]:

        world["visited"].append(
            next_node["id"]
        )

    if next_node.get("ending"):

        world["ended"] = True
        world["ending"] = next_node["ending"]

    prompt = f"""
The player just made this choice:

"{choice["text"]}"

The story has now moved to:

{next_node["title"]}

SCENE:

{next_node["text"]}

PREVIOUS CHOICES:

{world["history"][-8:]}

Write the next major scene.

Make the player's choice visibly matter.

Characters should react naturally.

Do not speak for the player.

If this is an ending, write a substantial ending scene that reflects
the player's previous decisions instead of simply saying "You won."
"""

    try:

        answer = ask_ai(
            world,
            prompt,
            story_mode=True
        )

        return jsonify({
            "reply": answer,
            "world": public_world(world)
        })

    except Exception as exc:

        app.logger.exception("Story choice failed")

        return jsonify({
            "error": f"Story error: {clean_text(exc)}"
        }), 500


# ---------------------------------------------------------
# STORY TREE
# ---------------------------------------------------------

@app.get("/story/tree")
def story_tree():

    world = get_world()

    nodes = []

    for node in world["nodes"].values():

        nodes.append({
            "id": node["id"],
            "title": node["title"],
            "depth": node["depth"],
            "text": node["text"],
            "choices": node["choices"],
            "ending": node.get("ending"),
            "seen": node["id"] in world["visited"],
            "current": node["id"] == world["current"]
        })

    nodes.sort(
        key=lambda x: (
            x["depth"],
            x["id"]
        )
    )

    return jsonify({
        "world_id": world["id"],
        "title": world["title"],
        "nodes": nodes
    })


# ---------------------------------------------------------
# REPLAY
# ---------------------------------------------------------

@app.post("/world/replay")
def replay_world():

    data = request.get_json(silent=True) or {}

    saved_world = data.get("world")

    if not isinstance(saved_world, dict):

        return jsonify({
            "error": "Invalid saved world."
        }), 400

    if not saved_world.get("id"):

        return jsonify({
            "error": "Saved world has no ID."
        }), 400

    if not saved_world.get("nodes"):

        return jsonify({
            "error": "Saved world has no story tree."
        }), 400

    world = deepcopy(saved_world)

    # The browser does not save private API conversation data.
    if "chat_history" not in world:
        world["chat_history"] = []

    WORLDS[world["id"]] = world

    session["world_id"] = world["id"]

    return jsonify(
        public_world(world)
    )


# ---------------------------------------------------------
# START SERVER
# ---------------------------------------------------------

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
