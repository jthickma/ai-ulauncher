# Ulauncher AI Extension
[*Download ULauncher*](https://ulauncher.io/)


To get an API key for access to all this goodness, you just need to sign up on [openrouter.ai](https://openrouter.ai/). Registration is also free.

Forked from [other repository](https://github.com/seofernando25/ulauncher-gpt) and extended with new features.

## New Features
- **Automatic Logging**: Each conversation is automatically saved in a structured Markdown format, including history, model details, and timestamps. Logs are saved to the selected directory or home folder by default.
- **Conversation History**: The extension supports continuous chats (history is preserved until restart or the `clear history` command).
- **Commands**: 
  - `clear history`: Reset history.
  - `view history`: View the last 5 exchanges.
  - `export full log`: Export the full history to a new file and copy the path.
  - `generate image [prompt]`: Generate an image using DALL-E mini (requires a configured API key).
- **Theming**: Choose "dark" or "light" theme for response styles (affects text wrapping and icons).
- **Multi-language Support**: Supports English (Russian and French removed to enforce English-only codebase).
- **API Usage Tracking**: Quota warnings (simulated if the number of calls exceeds 50 per session).
- **Automatic Log Cleanup**: Logs older than 7 days are deleted when the extension starts.
- **Other Improvements**: Enhanced error handling, request retries, logging level configuration, and more.

![Screenshot](images/screenshot.png)

## Installation
- Open **Ulauncher**.
- Click the **gear icon** to open settings.
- Go to the **EXTENSIONS** tab.
- Click **Add extension**.
- Paste the URL of this repository.

## Configuration
After installation, configure the extension in Ulauncher settings:
- **Keyword**: Keyword to activate (default `ais`).
- **Openrouter API Key**: Your API key.
- **DALL-E API Key**: Key for image generation (optional).
- **Model**: Choose a model from the list.
- **System Prompt**: System prompt for context.
- **Temperature**: Temperature (0-1).
- **Line Wrap Length**: Maximum line length (or 0 to disable).
- **Enable Wrapping**: Enable text wrapping.
- **Log Directory**: Directory for saving logs (leave empty for home folder).
- **Logging Level**: Logging level (DEBUG, INFO, WARNING, ERROR).
- **Theme**: Theme for responses (dark/light).
- **Language**: Interface language (en only).
- **Log Cleanup Days**: Days to keep logs before automatic deletion (0 to disable).

Logs are saved automatically after each request.