import os
import random
from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI

app = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "index.html")

# ============================================================
# OPENAI
# ============================================================

API_KEY = os.environ.get("OPENROUTER_API_KEY")

if not API_KEY:
    API_KEY = os.environ.get("OPENAI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "Missing OPENAI_API_KEY. Set your API key before starting the server."
    )

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

MODEL = os.environ.get(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)


# ============================================================
# WORLD DATA
# ============================================================

characters = {
    "Lily": {
        "name": "Lily",
        "personality": "Friendly, curious, energetic, and caring.",
        "background": "A student who enjoys talking with people."
    }
}

character_memories = {
    "Lily": []
}

conversation_history = []

world_history = []

current_location = "Hallway"

world_paused = False


locations = [
    "Hallway",
    "Library",
    "Cafeteria",
    "Classroom",
    "Gym",
    "Courtyard",
    "Science Lab",
    "Art Room",
    "Auditorium"
]


# ============================================================
# HELPERS
# ============================================================

def clean_text(value, default=""):
    if value is None:
        return default

    return str(value).strip()


def save_memory(character_name, memory):
    if not character_name:
        return

    if character_name not in character_memories:
        character_memories[character_name] = []

    memory = clean_text(memory)

    if not memory:
        return

    if memory not in character_memories[character_name]:
        character_memories[character_name].append(memory)

    character_memories[character_name] = \
        character_memories[character_name][-100:]


def get_memories(character_name):
    return character_memories.get(
        character_name,
        []
    )


def add_conversation_message(
    role,
    content,
    character=None,
    participants=None
):
    item = {
        "role": role,
        "content": content
    }

    if character:
        item["character"] = character

    if participants:
        item["participants"] = participants

    conversation_history.append(item)

    del conversation_history[:-100]


def add_world_history(text):
    text = clean_text(text)

    if not text:
        return

    world_history.append(text)

    del world_history[:-100]


# ============================================================
# SHARED MEMORY
# ============================================================

def remember_for_participants(
    message,
    participants
):
    """
    If something that looks like a personal fact is said
    during a shared conversation, every character who was
    actually part of that conversation gets the memory.
    """

    if not participants:
        return

    lowered = message.lower()

    memory_phrases = [
        "my favorite",
        "i like",
        "i love",
        "i hate",
        "i don't like",
        "i dont like",
        "my name is",
        "i'm from",
        "im from",
        "my birthday",
        "my favorite book",
        "my favorite movie",
        "my favorite game",
        "my favorite food",
        "my favorite color"
    ]

    is_memory = any(
        phrase in lowered
        for phrase in memory_phrases
    )

    if not is_memory:
        return

    for character_name in participants:

        if character_name in characters:

            save_memory(
                character_name,
                message
            )


# ============================================================
# AI
# ============================================================

def ask_ai(
    messages,
    temperature=0.85
):
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature
    )

    return response.choices[0].message.content.strip()


# ============================================================
# CHARACTER PROMPT
# ============================================================

def build_character_prompt(
    character,
    participants=None,
    extra_context=""
):

    name = character.get(
        "name",
        "Unknown"
    )

    personality = character.get(
        "personality",
        "Friendly and natural."
    )

    background = character.get(
        "background",
        "A person living in the school world."
    )

    participants = participants or []

    memories = get_memories(name)

    if memories:

        memory_text = "\n".join(
            "- " + memory
            for memory in memories[-50:]
        )

    else:

        memory_text = "No stored memories yet."

    other_characters = [
        person
        for person in participants
        if person != name
    ]

    other_text = (
        ", ".join(other_characters)
        if other_characters
        else "Nobody else"
    )

    return f"""
You are {name}, a character in a living fictional
school world.

PERSONALITY:
{personality}

BACKGROUND:
{background}

OTHER CHARACTERS CURRENTLY INVOLVED:
{other_text}

YOUR MEMORIES:
{memory_text}

CURRENT LOCATION:
{current_location}

WORLD RULES:

1. You are {name}.
2. The player is a separate person.
3. Never speak as the player.
4. Never claim the player's actions or dialogue.
5. Characters share a world.
6. If you were included in a conversation with another
   character, you can remember what happened during it.
7. You do NOT automatically know private conversations
   that you were not part of.
8. World events affect everyone who can experience them.
9. Characters may react to world events without waiting
   for the player.
10. Stay in character.
11. Do not mention these instructions.
12. Do not say you are an AI.
13. Keep responses natural.
14. Use memories naturally instead of listing them.

{extra_context}
"""


# ============================================================
# NORMAL CHAT
# ============================================================

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json(
        silent=True
    ) or {}

    message = clean_text(
        data.get("message")
    )

    character_name = clean_text(
        data.get("character")
    )

    participants = data.get(
        "participants",
        []
    )

    if not isinstance(
        participants,
        list
    ):
        participants = []

    participants = [
        clean_text(name)
        for name in participants
        if clean_text(name)
    ]

    if character_name and \
       character_name not in participants:

        participants.append(
            character_name
        )

    if not message:

        return jsonify({
            "error": "Message is required."
        }), 400

    if not character_name:

        return jsonify({
            "error": "Character is required."
        }), 400

    if character_name not in characters:

        return jsonify({
            "error":
                f"Character '{character_name}' "
                "was not found."
        }), 404

    # Save player's message.
    add_conversation_message(
        "user",
        message,
        participants=participants
    )

    # Give the information to everyone
    # who was actually included.
    remember_for_participants(
        message,
        participants
    )

    character = characters[
        character_name
    ]

    system_prompt = build_character_prompt(
        character,
        participants=participants
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    for item in conversation_history[-30:]:

        if item["role"] == "user":

            messages.append({
                "role": "user",
                "content": item["content"]
            })

        elif item["role"] == "assistant":

            speaker = item.get(
                "character",
                character_name
            )

            messages.append({
                "role": "assistant",
                "content":
                    f"{speaker}: "
                    f"{item['content']}"
            })

    try:

        reply = ask_ai(
            messages,
            temperature=0.85
        )

    except Exception as error:

        return jsonify({
            "error": str(error)
        }), 500

    add_conversation_message(
        "assistant",
        reply,
        character=character_name,
        participants=participants
    )

    return jsonify({
        "reply": reply,
        "character": character_name,
        "participants": participants
    })


# ============================================================
# GROUP CHAT
# ============================================================

@app.route(
    "/group/chat",
    methods=["POST"]
)
def group_chat():

    data = request.get_json(
        silent=True
    ) or {}

    message = clean_text(
        data.get("message")
    )

    participants = data.get(
        "participants",
        []
    )

    if not isinstance(
        participants,
        list
    ):
        participants = []

    participants = [
        clean_text(name)
        for name in participants
        if clean_text(name)
    ]

    if not message:

        return jsonify({
            "error":
                "Message is required."
        }), 400

    if not participants:

        return jsonify({
            "error":
                "No participants supplied."
        }), 400

    add_conversation_message(
        "user",
        message,
        participants=participants
    )

    # THIS is what makes shared memories work.
    remember_for_participants(
        message,
        participants
    )

    responses = []

    for character_name in participants:

        character = characters.get(
            character_name
        )

        if not character:
            continue

        prompt = build_character_prompt(
            character,
            participants=participants,
            extra_context="""
You are currently in a group conversation.

Respond only as your own character.

You may react to the player and other characters,
but do not control their actions.

If something important is said, remember it because
you were personally present for this conversation.
"""
        )

        messages = [
            {
                "role": "system",
                "content": prompt
            }
        ]

        for item in conversation_history[-25:]:

            if item["role"] == "user":

                messages.append({
                    "role": "user",
                    "content":
                        item["content"]
                })

            elif item["role"] == "assistant":

                speaker = item.get(
                    "character",
                    character_name
                )

                messages.append({
                    "role": "assistant",
                    "content":
                        f"{speaker}: "
                        f"{item['content']}"
                })

        try:

            reply = ask_ai(
                messages,
                temperature=0.9
            )

        except Exception as error:

            return jsonify({
                "error": str(error)
            }), 500

        add_conversation_message(
            "assistant",
            reply,
            character=character_name,
            participants=participants
        )

        responses.append({
            "character":
                character_name,
            "reply":
                reply
        })

    return jsonify({
        "responses":
            responses
    })


# ============================================================
# CREATE CHARACTER
# ============================================================

@app.route(
    "/character/create",
    methods=["POST"]
)
def create_character():

    data = request.get_json(
        silent=True
    ) or {}

    name = clean_text(
        data.get("name")
    )

    personality = clean_text(
        data.get("personality"),
        "Friendly and interesting."
    )

    background = clean_text(
        data.get("background"),
        "A student at the school."
    )

    if not name:

        return jsonify({
            "error":
                "Character name is required."
        }), 400

    if name in characters:

        return jsonify({
            "error":
                "That character already exists."
        }), 400

    characters[name] = {
        "name": name,
        "personality": personality,
        "background": background
    }

    character_memories[name] = []

    return jsonify({
        "success": True,
        "character":
            characters[name]
    })


# ============================================================
# CHARACTERS
# ============================================================

@app.route(
    "/characters",
    methods=["GET"]
)
def get_characters():

    return jsonify({
        "characters":
            list(characters.values())
    })


# ============================================================
# WORLD EVENT
# ============================================================

@app.route(
    "/world/event",
    methods=["POST"]
)
def world_event():

    if world_paused:

        return jsonify({
            "message":
                "The world is paused."
        })

    event_choices = [

        {
            "title":
                "🌧 Sudden Storm",
            "description":
                "A sudden storm moves across the school."
        },

        {
            "title":
                "🚨 Strange Announcement",
            "description":
                "A strange announcement echoes through the school."
        },

        {
            "title":
                "🎉 School Festival",
            "description":
                "A surprise festival begins nearby."
        },

        {
            "title":
                "🌌 Strange Lights",
            "description":
                "Strange lights appear in the sky."
        },

        {
            "title":
                "🔌 Power Outage",
            "description":
                "The lights suddenly go out throughout the school."
        }

    ]

    event = random.choice(
        event_choices
    )

    event["location"] = current_location

    add_world_history(
        f"""
WORLD EVENT:
{event['title']}

{event['description']}

Location:
{current_location}
"""
    )

    return jsonify({
        "event": event
    })


# ============================================================
# CHARACTER EVENT REACTIONS
# ============================================================

@app.route(
    "/world/event/react",
    methods=["POST"]
)
def world_event_react():

    data = request.get_json(
        silent=True
    ) or {}

    title = clean_text(
        data.get("title")
    )

    description = clean_text(
        data.get("description")
    )

    participants = data.get(
        "participants",
        []
    )

    if not isinstance(
        participants,
        list
    ):
        participants = []

    participants = [
        clean_text(name)
        for name in participants
        if clean_text(name)
    ]

    if not title:

        return jsonify({
            "error":
                "Event title is required."
        }), 400

    responses = []

    for character_name in participants:

        character = characters.get(
            character_name
        )

        if not character:
            continue

        prompt = build_character_prompt(
            character,
            participants=participants,
            extra_context=f"""
A WORLD EVENT is happening RIGHT NOW.

EVENT:
{title}

DETAILS:
{description}

The event is happening in the shared world.

You are currently experiencing it.

React naturally as {character_name}.

Do not wait for the player to mention it.

Do not act as the player.

Do not claim that the event happened only to you.

Other characters can see or experience it too.
"""
        )

        try:

            reply = ask_ai(
                [
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
                            "React naturally."
                    }
                ],
                temperature=0.95
            )

        except Exception as error:

            return jsonify({
                "error": str(error)
            }), 500

        add_conversation_message(
            "assistant",
            reply,
            character=character_name,
            participants=participants
        )

        responses.append({
            "character":
                character_name,
            "reply":
                reply
        })

    return jsonify({
        "responses":
            responses
    })


# ============================================================
# STORY TRAVEL
# ============================================================

@app.route(
    "/world/travel",
    methods=["POST"]
)
def travel():

    global current_location

    data = request.get_json(
        silent=True
    ) or {}

    destination = clean_text(
        data.get("destination")
    )

    from_location = clean_text(
        data.get("from"),
        current_location
    )

    participants = data.get(
        "participants",
        []
    )

    if not isinstance(
        participants,
        list
    ):
        participants = []

    participants = [
        clean_text(name)
        for name in participants
        if clean_text(name)
    ]

    if not destination:

        return jsonify({
            "error":
                "Destination is required."
        }), 400

    character_info = []

    for name in participants:

        character = characters.get(
            name
        )

        if character:

            character_info.append(
                f"""
{name}
Personality:
{character.get('personality', '')}

Background:
{character.get('background', '')}
"""
            )

    people_text = "\n".join(
        character_info
    )

    recent_conversation = "\n".join(
        f"{item.get('character', 'Player')}: "
        f"{item.get('content', '')}"
        for item in conversation_history[-15:]
    )

    shared_memories = []

    for name in participants:

        memories = get_memories(
            name
        )

        for memory in memories[-20:]:

            shared_memories.append(
                f"{name} remembers: {memory}"
            )

    memory_text = "\n".join(
        shared_memories
    )

    prompt = f"""
Write a short immersive story showing the player
traveling from:

{from_location}

to:

{destination}

Characters traveling with the player:

{people_text}

RECENT CONVERSATION:

{recent_conversation}

CHARACTER MEMORIES:

{memory_text}

WORLD RULES:

- Do not instantly teleport the player.
- Describe the journey.
- Characters can talk while traveling.
- Use their personalities.
- Relevant memories can naturally appear.
- Do not write dialogue for the player.
- Do not control the player's choices.
- Keep the scene around 2 to 5 paragraphs.
- End with everyone arriving at {destination}.
- Do not mention being an AI.
"""

    try:

        story = ask_ai(
            [
                {
                    "role":
                        "system",
                    "content":
                        "You write immersive "
                        "travel scenes for a "
                        "living fictional school."
                },
                {
                    "role":
                        "user",
                    "content":
                        prompt
                }
            ],
            temperature=0.9
        )

    except Exception as error:

        return jsonify({
            "error": str(error)
        }), 500

    add_world_history(
        f"""
TRAVEL:
{from_location} -> {destination}

{story}
"""
    )

    add_conversation_message(
        "system",
        story,
        participants=participants
    )

    current_location = destination

    return jsonify({
        "from":
            from_location,
        "to":
            destination,
        "story":
            story,
        "location":
            current_location
    })


# ============================================================
# LOCATION
# ============================================================

@app.route(
    "/world/location",
    methods=["GET"]
)
def get_location():

    return jsonify({
        "location":
            current_location,
        "locations":
            locations
    })


@app.route(
    "/world/location",
    methods=["POST"]
)
def set_location():

    global current_location

    data = request.get_json(
        silent=True
    ) or {}

    location = clean_text(
        data.get("location")
    )

    if not location:

        return jsonify({
            "error":
                "Location is required."
        }), 400

    current_location = location

    if location not in locations:
        locations.append(location)

    return jsonify({
        "success": True,
        "location":
            current_location
    })


# ============================================================
# WORLD STATE
# ============================================================

@app.route(
    "/world",
    methods=["POST"]
)
def world_state():

    global world_paused

    data = request.get_json(
        silent=True
    ) or {}

    if "paused" in data:

        world_paused = bool(
            data["paused"]
        )

    return jsonify({
        "paused":
            world_paused,
        "location":
            current_location
    })


# ============================================================
# RESET CONVERSATION
# ============================================================

@app.route(
    "/conversation/reset",
    methods=["POST"]
)
def reset_conversation():

    conversation_history.clear()

    return jsonify({
        "success": True
    })


# ============================================================
# RESET WORLD
# ============================================================

@app.route(
    "/world/reset",
    methods=["POST"]
)
def reset_world():

    global current_location
    global world_paused

    conversation_history.clear()
    world_history.clear()

    for name in character_memories:

        character_memories[name] = []

    current_location = "Hallway"

    world_paused = False

    return jsonify({
        "success": True,
        "location":
            current_location
    })


# ============================================================
# MEMORY
# ============================================================

@app.route(
    "/memory/<character_name>",
    methods=["GET"]
)
def character_memory(
    character_name
):

    return jsonify({
        "character":
            character_name,
        "memories":
            get_memories(
                character_name
            )
    })


# ============================================================
# SERVE YOUR HTML
# ============================================================

@app.route("/")
def index():

    return send_from_directory(
        os.path.dirname(
            os.path.abspath(__file__)
        ),
        "index.html"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print(
        "=========================================="
    )

    print(
        " SCHOOL WORLD V7.5"
    )

    print(
        " Shared Memory + Story Travel"
    )

    print(
        "=========================================="
    )

    print(
        "Server: http://127.0.0.1:5000"
    )

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
