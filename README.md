# Thadhesh App

Thadhesh is an AI-powered assistant for the Kerala Local Self-Government Department. It helps users with building permits, property tax queries, panchayat services, and municipality procedures based on the Panchayath Raj Act, Municipality Act, and Kerala Building Rules.

## Features
- Chat interface with multilingual support (English & Malayalam)
- Voice input and audio logging
- Session and chat history
- Audio transcription and analytics

## Requirements
- Python 3.10+
- pip (Python package manager)
- Google Cloud credentials (for speech-to-text, if used)

## Setup Instructions

1. **Clone the repository**

```sh
git clone <repo-url>
cd thadhesh-app
```


2. **Create and activate a virtual environment (recommended)**

**On Windows:**

```sh
python -m venv venv
venv\Scripts\activate
```

**On macOS/Linux:**

```sh
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**

```sh
pip install -r requirements.txt
```

(optional)
4. **Set up environment variables**

- Place your Google Cloud credentials JSON file in the project root (if using Google Speech-to-Text).
- Optionally, set environment variables for Flask (development):

```sh
set FLASK_APP=app.py
set FLASK_ENV=development
```

4. **Run the application**

```sh
python app.py
```

The app will start on `http://127.0.0.1:5000/` by default.

5. **Access the app**

- Open your browser and go to `http://127.0.0.1:5000/`
- Log in or sign up to start using the chat and audio features.

## Project Structure

- `app.py` - Main Flask app
- `routes/` - API and page routes
- `templates/` - HTML templates (Jinja2)
- `static/` - CSS, JS, and images
- `uploads/` - Uploaded audio files
- `models.py` - Database models
- `database.py` - Database connection and helpers
- `utils.py` - Utility functions (audio, transcription, etc.)
- `requirements.txt` - Python dependencies

## Notes
- For audio transcription, ensure your Google Cloud credentials are valid and the Speech-to-Text API is enabled.
- Audio files and logs are stored in the `uploads/` directory.
- The app requires user authentication for chat and audio features.

## Troubleshooting
- If you encounter issues with audio, check browser permissions and ensure your microphone is enabled.
- For database errors, verify your database connection settings in `database.py`.
- For Google API errors, check your credentials and API access.

## License
This project is for educational and demonstration purposes.
