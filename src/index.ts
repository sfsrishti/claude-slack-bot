import { App } from "@slack/bolt";
import Anthropic from "@anthropic-ai/sdk";
import * as dotenv from "dotenv";

dotenv.config();

// Initialize Slack app
const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  socketMode: true,
  appToken: process.env.SLACK_APP_TOKEN,
});

// Initialize Claude client
const claude = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const CLAUDE_MODEL = process.env.CLAUDE_MODEL || "claude-opus-4-6";

// Store conversation history per thread
const conversationHistory = new Map<string, Anthropic.MessageParam[]>();

// Listen for messages mentioning the bot or direct messages
app.event("app_mention", async ({ event, client, say }) => {
  try {
    // Remove bot mention from the message
    const userMessage = event.text.replace(/<@[^>]+>/g, "").trim();

    // Get thread ID (use main message ts if not in a thread)
    const threadTs = event.thread_ts || event.ts;

    // Get or initialize conversation history for this thread
    let messages = conversationHistory.get(threadTs) || [];

    // Add user message to history
    messages.push({
      role: "user",
      content: userMessage,
    });

    // Show typing indicator
    await client.reactions.add({
      channel: event.channel,
      timestamp: event.ts,
      name: "thinking_face",
    });

    // Call Claude API
    const response = await claude.messages.create({
      model: CLAUDE_MODEL,
      max_tokens: 16000,
      messages: messages,
    });

    // Extract text from response
    const assistantMessage = response.content
      .filter((block) => block.type === "text")
      .map((block) => (block as Anthropic.TextBlock).text)
      .join("\n");

    // Add assistant response to history
    messages.push({
      role: "assistant",
      content: assistantMessage,
    });

    // Store updated conversation history
    conversationHistory.set(threadTs, messages);

    // Remove typing indicator
    await client.reactions.remove({
      channel: event.channel,
      timestamp: event.ts,
      name: "thinking_face",
    });

    // Send response in thread
    await say({
      text: assistantMessage,
      thread_ts: threadTs,
    });
  } catch (error) {
    console.error("Error handling message:", error);

    await say({
      text: "Sorry, I encountered an error processing your message.",
      thread_ts: event.thread_ts || event.ts,
    });
  }
});

// Listen for direct messages
app.event("message", async ({ event, client, say }) => {
  // Ignore bot messages and threaded messages (handled by app_mention)
  if (
    event.subtype === "bot_message" ||
    event.subtype === "message_changed" ||
    "thread_ts" in event
  ) {
    return;
  }

  // Only handle DMs (channel type is 'im')
  if (event.channel_type !== "im") {
    return;
  }

  try {
    const userMessage = event.text;
    const conversationId = event.channel;

    // Get or initialize conversation history
    let messages = conversationHistory.get(conversationId) || [];

    // Add user message to history
    messages.push({
      role: "user",
      content: userMessage,
    });

    // Show typing indicator
    await client.reactions.add({
      channel: event.channel,
      timestamp: event.ts,
      name: "thinking_face",
    });

    // Call Claude API
    const response = await claude.messages.create({
      model: CLAUDE_MODEL,
      max_tokens: 16000,
      messages: messages,
    });

    // Extract text from response
    const assistantMessage = response.content
      .filter((block) => block.type === "text")
      .map((block) => (block as Anthropic.TextBlock).text)
      .join("\n");

    // Add assistant response to history
    messages.push({
      role: "assistant",
      content: assistantMessage,
    });

    // Store updated conversation history
    conversationHistory.set(conversationId, messages);

    // Remove typing indicator
    await client.reactions.remove({
      channel: event.channel,
      timestamp: event.ts,
      name: "thinking_face",
    });

    // Send response
    await say(assistantMessage);
  } catch (error) {
    console.error("Error handling DM:", error);

    await say("Sorry, I encountered an error processing your message.");
  }
});

// Add a slash command to clear conversation history
app.command("/claude-reset", async ({ command, ack, respond }) => {
  await ack();

  const conversationId = command.channel_id;
  conversationHistory.delete(conversationId);

  await respond("Conversation history cleared!");
});

// Start the app
(async () => {
  await app.start();
  console.log("⚡️ Claude Slack Bot is running!");
})();
