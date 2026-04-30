# Claude Slack Bot

A Slack bot powered by Claude API that can engage in conversations, maintain context, and respond to mentions and direct messages.

## Features

- Responds to @mentions in channels
- Handles direct messages
- Maintains conversation history per thread
- Shows typing indicator while processing
- Supports `/claude-reset` command to clear conversation history
- Built with TypeScript and Slack Bolt framework

## Prerequisites

- Node.js 18+ and npm
- A Slack workspace where you can install apps
- An Anthropic API key

## Setup Instructions

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Name your app (e.g., "Claude Bot") and select your workspace
4. Click **Create App**

### 2. Configure Bot Permissions

1. In your app settings, go to **OAuth & Permissions**
2. Under **Scopes** → **Bot Token Scopes**, add:
   - `app_mentions:read` - Read messages that mention the bot
   - `chat:write` - Send messages
   - `channels:history` - Read channel messages
   - `groups:history` - Read private channel messages
   - `im:history` - Read direct messages
   - `im:write` - Send direct messages
   - `reactions:write` - Add reactions (for typing indicator)
   - `commands` - Register slash commands

### 3. Enable Socket Mode

1. Go to **Socket Mode** in your app settings
2. Toggle **Enable Socket Mode** to ON
3. Give your token a name (e.g., "claude-bot-token")
4. Copy the **App Token** (starts with `xapp-`) - you'll need this later

### 4. Subscribe to Events

1. Go to **Event Subscriptions**
2. Toggle **Enable Events** to ON
3. Under **Subscribe to bot events**, add:
   - `app_mention` - When someone mentions your bot
   - `message.im` - Direct messages to the bot
4. Click **Save Changes**

### 5. Add Slash Command

1. Go to **Slash Commands**
2. Click **Create New Command**
3. Enter:
   - Command: `/claude-reset`
   - Short Description: "Clear conversation history with Claude"
4. Click **Save**

### 6. Install App to Workspace

1. Go to **Install App**
2. Click **Install to Workspace**
3. Review permissions and click **Allow**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 7. Get Your Signing Secret

1. Go to **Basic Information**
2. Under **App Credentials**, find **Signing Secret**
3. Click **Show** and copy it

### 8. Configure Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Fill in your credentials:
   ```env
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_APP_TOKEN=xapp-your-app-token
   SLACK_SIGNING_SECRET=your-signing-secret
   ANTHROPIC_API_KEY=your-anthropic-api-key
   CLAUDE_MODEL=claude-opus-4-6
   ```

### 9. Install Dependencies and Run

```bash
# Install dependencies
npm install

# Run in development mode
npm run dev

# Or build and run in production
npm run build
npm start
```

## Usage

### In Channels

Mention the bot to start a conversation:
```
@Claude Bot What is the capital of France?
```

The bot will respond in a thread, maintaining conversation context within that thread.

### Direct Messages

Simply send a message to the bot in a DM. The bot will respond and maintain conversation history for that DM session.

### Clear History

Use the slash command to clear conversation history:
```
/claude-reset
```

## Project Structure

```
claude-slack-bot/
├── src/
│   └── index.ts          # Main application code
├── dist/                 # Compiled JavaScript (generated)
├── .env                  # Environment variables (create from .env.example)
├── .env.example          # Example environment variables
├── package.json          # Dependencies and scripts
├── tsconfig.json         # TypeScript configuration
└── README.md            # This file
```

## Configuration

### Model Selection

By default, the bot uses `claude-opus-4-6`. You can change this in `.env`:

- `claude-opus-4-6` - Most capable model
- `claude-sonnet-4-6` - Balanced speed and intelligence
- `claude-haiku-4-5` - Fastest and most cost-effective

### Conversation History

The bot stores conversation history in memory per thread/DM. If you restart the bot, history is cleared. For production, consider:

- Using Redis or a database for persistent storage
- Implementing automatic cleanup of old conversations
- Adding conversation history limits to manage memory

## Advanced Features

### Add Streaming Responses

For faster perceived response times, you can enable streaming:

```typescript
const stream = claude.messages.stream({
  model: CLAUDE_MODEL,
  max_tokens: 16000,
  messages: messages,
});

let fullResponse = "";
for await (const event of stream) {
  if (event.type === "content_block_delta" && event.delta.type === "text_delta") {
    fullResponse += event.delta.text;
  }
}
```

### Add Tool Use

Enable Claude to use tools (search, calculations, etc.) by adding tools to the API call:

```typescript
const response = await claude.messages.create({
  model: CLAUDE_MODEL,
  max_tokens: 16000,
  tools: [
    {
      name: "get_weather",
      description: "Get current weather for a location",
      input_schema: {
        type: "object",
        properties: {
          location: { type: "string" }
        },
        required: ["location"]
      }
    }
  ],
  messages: messages,
});
```

### Add System Prompts

Customize Claude's behavior with a system prompt:

```typescript
const response = await claude.messages.create({
  model: CLAUDE_MODEL,
  max_tokens: 16000,
  system: "You are a helpful assistant in a Slack workspace. Be concise and professional.",
  messages: messages,
});
```

## Troubleshooting

### Bot doesn't respond to mentions
- Check that Event Subscriptions are enabled
- Verify `app_mentions:read` scope is added
- Make sure the bot is invited to the channel

### Bot doesn't respond to DMs
- Check `message.im` event subscription
- Verify `im:history` and `im:write` scopes

### "Invalid token" errors
- Double-check your tokens in `.env`
- Bot token should start with `xoxb-`
- App token should start with `xapp-`

### Rate limiting
- Implement exponential backoff for API calls
- Consider adding a queue for high-volume usage
- Monitor usage in the Anthropic Console

## Production Deployment

For production use, consider:

1. **Deploy to a server**: Use services like Heroku, AWS, or Railway
2. **Add error handling**: Implement comprehensive error logging
3. **Monitor costs**: Track API usage in Anthropic Console
4. **Implement rate limiting**: Prevent abuse and control costs
5. **Add user permissions**: Restrict bot access to specific users/channels
6. **Persistent storage**: Use Redis or a database for conversation history

## Resources

- [Slack Bolt Framework](https://slack.dev/bolt-js/)
- [Anthropic API Documentation](https://docs.anthropic.com/)
- [Claude API TypeScript SDK](https://github.com/anthropics/anthropic-sdk-typescript)

## License

MIT
