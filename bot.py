import os
import requests
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Slack app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Gateway configuration
GATEWAY_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://eng-ai-model-gateway.sfproxy.devx-preprod.aws-esvc1-useast2.aws.sfdc.cl/chat/completions")
API_KEY = os.environ.get("ENG_AI_MODEL_GW_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-6")

# Store conversation history per thread
conversation_history = {}


def get_conversation_key(event):
    """Get a unique key for conversation history based on thread or channel."""
    if event.get("thread_ts"):
        return event["thread_ts"]
    return event.get("channel", event.get("ts"))


def call_claude_api(messages):
    """Call the enterprise AI gateway with the messages."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": CLAUDE_MODEL,
        "messages": messages,
        "max_tokens": 16000
    }

    response = requests.post(GATEWAY_URL, headers=headers, json=payload)
    response.raise_for_status()

    data = response.json()

    # Extract message content from response
    if "choices" in data and len(data["choices"]) > 0:
        return data["choices"][0]["message"]["content"]
    elif "content" in data and isinstance(data["content"], list):
        # Handle Anthropic-style response
        return "".join([block.get("text", "") for block in data["content"] if block.get("type") == "text"])
    else:
        raise Exception(f"Unexpected response format: {data}")


@app.event("app_mention")
def handle_mention(event, say, client):
    """Handle @mentions of the bot in channels."""
    try:
        # Remove bot mention from the message
        text = event["text"]
        # Remove all user mentions (e.g., <@U12345>)
        import re
        user_message = re.sub(r'<@[^>]+>', '', text).strip()

        # Get thread ID (use main message ts if not in a thread)
        thread_ts = event.get("thread_ts", event["ts"])

        # Get or initialize conversation history for this thread
        if thread_ts not in conversation_history:
            conversation_history[thread_ts] = []

        messages = conversation_history[thread_ts]

        # Add user message to history
        messages.append({
            "role": "user",
            "content": user_message
        })

        # Show typing indicator
        try:
            client.reactions_add(
                channel=event["channel"],
                timestamp=event["ts"],
                name="thinking_face"
            )
        except Exception as e:
            print(f"Could not add reaction: {e}")

        # Call Claude API
        assistant_message = call_claude_api(messages)

        # Add assistant response to history
        messages.append({
            "role": "assistant",
            "content": assistant_message
        })

        # Update conversation history
        conversation_history[thread_ts] = messages

        # Remove typing indicator
        try:
            client.reactions_remove(
                channel=event["channel"],
                timestamp=event["ts"],
                name="thinking_face"
            )
        except Exception as e:
            print(f"Could not remove reaction: {e}")

        # Send response in thread
        say(text=assistant_message, thread_ts=thread_ts)

    except Exception as e:
        print(f"Error handling mention: {e}")
        say(
            text="Sorry, I encountered an error processing your message.",
            thread_ts=event.get("thread_ts", event["ts"])
        )


@app.event("message")
def handle_message(event, say, client):
    """Handle direct messages to the bot."""
    # Ignore bot messages and threaded messages (handled by app_mention)
    if event.get("subtype") in ["bot_message", "message_changed"]:
        return

    if "thread_ts" in event:
        return

    # Only handle DMs (channel type is 'im')
    if event.get("channel_type") != "im":
        return

    try:
        user_message = event["text"]
        conversation_id = event["channel"]

        # Get or initialize conversation history
        if conversation_id not in conversation_history:
            conversation_history[conversation_id] = []

        messages = conversation_history[conversation_id]

        # Add user message to history
        messages.append({
            "role": "user",
            "content": user_message
        })

        # Show typing indicator
        try:
            client.reactions_add(
                channel=event["channel"],
                timestamp=event["ts"],
                name="thinking_face"
            )
        except Exception as e:
            print(f"Could not add reaction: {e}")

        # Call Claude API
        assistant_message = call_claude_api(messages)

        # Add assistant response to history
        messages.append({
            "role": "assistant",
            "content": assistant_message
        })

        # Update conversation history
        conversation_history[conversation_id] = messages

        # Remove typing indicator
        try:
            client.reactions_remove(
                channel=event["channel"],
                timestamp=event["ts"],
                name="thinking_face"
            )
        except Exception as e:
            print(f"Could not remove reaction: {e}")

        # Send response
        say(assistant_message)

    except Exception as e:
        print(f"Error handling DM: {e}")
        say("Sorry, I encountered an error processing your message.")


@app.command("/claude-reset")
def handle_reset_command(ack, respond, command):
    """Handle the /claude-reset command to clear conversation history."""
    ack()

    conversation_id = command["channel_id"]
    if conversation_id in conversation_history:
        del conversation_history[conversation_id]

    respond("Conversation history cleared!")


if __name__ == "__main__":
    # Start the app using Socket Mode
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    print("⚡️ Claude Slack Bot is running!")
    handler.start()
