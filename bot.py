import os
import requests
import logging
import time
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Slack app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Gateway configuration - using Bedrock endpoint
GATEWAY_URL = os.environ.get("ANTHROPIC_BEDROCK_BASE_URL", "https://eng-ai-model-gateway.sfproxy.devx-preprod.aws-esvc1-useast2.aws.sfdc.cl/bedrock")
AUTH_TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "anthropic.claude-sonnet-4-20250514-v1:0")
SKIP_SSL_VERIFY = os.environ.get("SKIP_SSL_VERIFY", "1") == "1"

# Log startup configuration
logger.info(f"Bot starting up...")
logger.info(f"Gateway URL: {GATEWAY_URL}")
logger.info(f"Model: {CLAUDE_MODEL}")
logger.info(f"Auth token present: {bool(AUTH_TOKEN)}")
logger.info(f"Auth token length: {len(AUTH_TOKEN) if AUTH_TOKEN else 0}")
logger.info(f"Skip SSL verify: {SKIP_SSL_VERIFY}")

# Store conversation history per thread
conversation_history = {}


def get_conversation_key(event):
    """Get a unique key for conversation history based on thread or channel."""
    if event.get("thread_ts"):
        return event["thread_ts"]
    return event.get("channel", event.get("ts"))


def call_claude_api(messages):
    """Call the enterprise AI gateway with the messages."""
    start_time = time.time()

    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": CLAUDE_MODEL,
        "messages": messages,
        "max_tokens": 4000  # Reduced from 16000 for faster responses
    }

    logger.info(f"=== API Call Starting ===")
    logger.info(f"Gateway URL: {GATEWAY_URL}")
    logger.info(f"Model: {CLAUDE_MODEL}")
    logger.info(f"Message count: {len(messages)}")
    logger.info(f"Auth token present: {bool(AUTH_TOKEN)}")
    logger.info(f"SSL verify: {not SKIP_SSL_VERIFY}")

    try:
        logger.info("Sending POST request to gateway...")
        response = requests.post(
            GATEWAY_URL,
            headers=headers,
            json=payload,
            timeout=30,  # Increased timeout for Claude processing
            verify=not SKIP_SSL_VERIFY
        )

        elapsed = time.time() - start_time
        logger.info(f"Response received in {elapsed:.2f}s")
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")

        response.raise_for_status()

        data = response.json()
        logger.info(f"Response data keys: {list(data.keys())}")

        # Extract message content from response
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["message"]["content"]
            logger.info(f"Extracted content (OpenAI format), length: {len(content)}")
            return content
        elif "content" in data and isinstance(data["content"], list):
            # Handle Anthropic-style response
            content = "".join([block.get("text", "") for block in data["content"] if block.get("type") == "text"])
            logger.info(f"Extracted content (Anthropic format), length: {len(content)}")
            return content
        else:
            logger.error(f"Unexpected response format: {data}")
            raise Exception(f"Unexpected response format: {data}")
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        logger.error(f"Timeout after {elapsed:.2f}s")
        raise Exception("Gateway connection timed out after 30s.")
    except requests.exceptions.ConnectionError as e:
        elapsed = time.time() - start_time
        logger.error(f"Connection error after {elapsed:.2f}s: {str(e)}")
        raise Exception(f"Cannot connect to gateway: {str(e)}")
    except requests.exceptions.HTTPError as e:
        elapsed = time.time() - start_time
        logger.error(f"HTTP error after {elapsed:.2f}s: {str(e)}")
        logger.error(f"Response body: {response.text}")
        raise Exception(f"Gateway returned error: {response.status_code} - {response.text}")
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Unexpected error after {elapsed:.2f}s: {str(e)}")
        raise


@app.event("app_mention")
def handle_mention(event, say, client):
    """Handle @mentions of the bot in channels."""
    request_start = time.time()
    logger.info(f"=== Received app_mention event ===")
    logger.info(f"Channel: {event.get('channel')}, User: {event.get('user')}")

    try:
        # Remove bot mention from the message
        text = event["text"]
        # Remove all user mentions (e.g., <@U12345>)
        import re
        user_message = re.sub(r'<@[^>]+>', '', text).strip()
        logger.info(f"User message: {user_message[:100]}...")

        # Get thread ID (use main message ts if not in a thread)
        thread_ts = event.get("thread_ts", event["ts"])

        # Get or initialize conversation history for this thread
        if thread_ts not in conversation_history:
            conversation_history[thread_ts] = []
            logger.info(f"New conversation thread: {thread_ts}")
        else:
            logger.info(f"Existing thread with {len(conversation_history[thread_ts])} messages")

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
            logger.info("Added thinking_face reaction")
        except Exception as e:
            logger.warning(f"Could not add reaction: {e}")

        # Call Claude API
        logger.info("Calling Claude API...")
        assistant_message = call_claude_api(messages)
        logger.info(f"Received response, length: {len(assistant_message)}")

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
            logger.info("Removed thinking_face reaction")
        except Exception as e:
            logger.warning(f"Could not remove reaction: {e}")

        # Send response in thread
        say(text=assistant_message, thread_ts=thread_ts)

        total_time = time.time() - request_start
        logger.info(f"=== Request completed in {total_time:.2f}s ===")

    except Exception as e:
        total_time = time.time() - request_start
        logger.error(f"Error handling mention after {total_time:.2f}s: {e}", exc_info=True)
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

    request_start = time.time()
    logger.info(f"=== Received DM message ===")
    logger.info(f"Channel: {event.get('channel')}, User: {event.get('user')}")

    try:
        user_message = event["text"]
        conversation_id = event["channel"]
        logger.info(f"User message: {user_message[:100]}...")

        # Get or initialize conversation history
        if conversation_id not in conversation_history:
            conversation_history[conversation_id] = []
            logger.info(f"New DM conversation: {conversation_id}")
        else:
            logger.info(f"Existing DM with {len(conversation_history[conversation_id])} messages")

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
            logger.info("Added thinking_face reaction")
        except Exception as e:
            logger.warning(f"Could not add reaction: {e}")

        # Call Claude API
        logger.info("Calling Claude API...")
        assistant_message = call_claude_api(messages)
        logger.info(f"Received response, length: {len(assistant_message)}")

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
            logger.info("Removed thinking_face reaction")
        except Exception as e:
            logger.warning(f"Could not remove reaction: {e}")

        # Send response
        say(assistant_message)

        total_time = time.time() - request_start
        logger.info(f"=== DM request completed in {total_time:.2f}s ===")

    except Exception as e:
        total_time = time.time() - request_start
        logger.error(f"Error handling DM after {total_time:.2f}s: {e}", exc_info=True)
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
