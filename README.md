# AI PRO Revolution - YouTube Live Bot v1.0

Assistant bot for YouTube live streams that answers questions in chat using the OpenAI Assistants API.

![AI PRO Revolution Bot](https://img.shields.io/badge/AI%20PRO-Revolution%20Bot-red)
![Python](https://img.shields.io/badge/Python-3.7+-blue)
![OpenAI](https://img.shields.io/badge/OpenAI-Assistants%20API-lightgrey)
![YouTube](https://img.shields.io/badge/YouTube-Live%20API-red)

## Overview

The YouTube Live Bot is a tool developed to enhance interaction with viewers during YouTube live streams. The bot monitors the chat for mentions of its name or specific commands, and generates automatic responses using the OpenAI Assistants API.

## Features

- 🔄 Connects to YouTube live chat using the YouTube Data API
- 🤖 Uses OpenAI Assistants API to generate contextual responses
- 📊 API quota monitoring to avoid exceeding limits
- 🔋 Economy mode to preserve quota when nearing the limit
- 👤 Intelligent extraction of usernames for cleaner mentions
- 🔁 Response loop prevention system
- 📈 Usage statistics at the end of session

## Requirements

- Python 3.7+
- A Google account with YouTube Data v3 API enabled
- An OpenAI account with access to the Assistants API
- A configured assistant in OpenAI

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/thiagocaliman/youtube-live-chat-openai.git
   cd youtube-live-chat-openai
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a configuration file:
   ```
   cp config.example.json config.json
   ```

4. Edit the `config.json` file with your information.

## Setup

### 1. Configure Google credentials

- Go to the [Google Cloud Console](https://console.cloud.google.com/)
- Create a project and enable the YouTube Data v3 API
- Create OAuth 2.0 credentials for desktop application
- Download the JSON file and rename it to `client_secret.json`

### 2. Configure OpenAI API

- Get an OpenAI API key
- Set it as an environment variable:
  - Windows: `set OPENAI_API_KEY=your-api-key`
  - Linux/Mac: `export OPENAI_API_KEY=your-api-key`

### 3. Create an assistant in OpenAI

- Go to [platform.openai.com](https://platform.openai.com/)
- Navigate to the "Assistants" section
- Create a new assistant and copy the ID (`asst_...`)

### 4. Configure `config.json` file

```json
{
    "nome_bot": "Janete",
    "id_transmissao": "YOUR-LIVESTREAM-ID",
    "id_assistente": "YOUR-ASSISTANT-ID",
    "nome_canal_bot": "YOUR-CHANNEL-NAME",
    "intervalo_verificacao": 10,
    "modo_economia": false,
    "intervalo_economia": 20,
    "cota_diaria": 10000
}
```

## Usage

### Basic execution

```
python youtube_bot.py
```

### Command line options

```
python youtube_bot.py -t LIVESTREAM_ID -i 10 -e
```

- `-t`, `--transmissao`: YouTube livestream ID
- `-i`, `--intervalo`: Interval in seconds between chat checks (default: 10)
- `-e`, `--economia`: Activate economy mode to save quota

### During the livestream

The bot will respond to:
- Messages that mention the bot's name (e.g., "Janete, what's the event topic?")
- Messages that start with "!" (e.g., "!help")

## Quota Management

The YouTube API has a daily limit of 10,000 units. The bot consumes:
- ~5 units per chat check
- ~50 units per message sent

The bot includes:
- Automatic quota usage tracking
- Economy mode that increases the interval between checks
- Quota reserve to ensure functionality until the end of the stream

## Troubleshooting

- **"Quota exceeded" error**: You've reached the daily limit of 10,000 units. Request a quota increase in the Google Cloud Console or wait until the next day.
- **Authentication error**: Check if your `client_secret.json` file is correct and that you've authorized the application.
- **Bot can't find the livestream**: Make sure the livestream ID is correct and the stream is active.
- **OpenAI API error**: Verify that your API key is correct and has available credits.

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/NewFeature`)
3. Commit your changes (`git commit -m 'Add new feature'`)
4. Push to the branch (`git push origin feature/NewFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [OpenAI](https://openai.com/) for the Assistants API
- [Google](https://developers.google.com/youtube/v3) for the YouTube Data API

---

Developed by Thiago Caliman | AI PRO Revolution | [\[YouTube\]](https://www.youtube.com/@thiagocalimanIA)

