import os
import io
import subprocess
import base64
import magic
from flask import jsonify
from datetime import datetime
from functools import wraps
from flask import session, redirect, url_for, current_app
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from google.cloud import speech

# --- Setup GCP Credentials and Environment ---
# Load environment variables from .env file
load_dotenv()

# Set Google Cloud credentials from the environment variable
gcp_credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if gcp_credentials_path and os.path.exists(gcp_credentials_path):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = gcp_credentials_path
    print(f"INFO: GCP Credentials loaded from: {gcp_credentials_path}")
else:
    print("WARNING: GOOGLE_APPLICATION_CREDENTIALS path not found or not set in .env file.")
# ---------------------------------------------


# --- Placeholder functions from original context ---
# (These are required for the API blueprint to work)

def require_login(f):
    """Decorator to ensure a user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # For an API, returning a 401 is standard
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'ogg', 'flac', 'webm'}

def allowed_file(filename):
    """Checks if a file has an allowed audio extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_secure_filename(session_id, extension):
    """Generates a secure, unique filename for an uploaded file."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_extension = secure_filename(extension)
    return f"{session_id}_{timestamp}.{safe_extension}"

def save_uploaded_file(file_data, filename):
    """Saves file data to the configured upload folder."""
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    file_path = os.path.join(upload_folder, filename)
    with open(file_path, 'wb') as f:
        f.write(file_data)
    return file_path

def translate_to_english(text, source_language='ml'):
    """
    Translate text to English using Google Translate API.
    """
    try:
        from google.cloud import translate_v2 as translate
        translate_client = translate.Client()
        result = translate_client.translate(text, target_language='en', source_language=source_language)
        print(f"[TRANSLATE] {source_language} to English: {result['translatedText']}")
        return result['translatedText']
    except Exception as e:
        print(f"[TRANSLATE ERROR]: {e}")
        return text

def get_response_message(user_message, language):
    """Generate a chat response. If user_message is Malayalam, translate to English first."""
    # Detect Malayalam (simple check: Unicode range)
    def is_malayalam(text):
        return any('\u0d00' <= c <= '\u0d7f' for c in text)

    if language == 'malayalam' or is_malayalam(user_message):
        user_message_en = translate_to_english(user_message, source_language='ml')
        print(f"[USER TEXT] Malayalam detected. Translated to English: {user_message_en}")
        user_message = user_message_en
        language = 'english'
    return f"This is a placeholder response in {language} to: '{user_message}'"

def format_timestamp():
    """Returns the current time as an ISO-formatted string."""
    return datetime.now().isoformat()

def process_base64_audio(base64_string):
    """Decodes a base64 audio string and determines its file extension."""
    if ',' in base64_string:
        header, encoded = base64_string.split(',', 1)
    else:
        encoded = base64_string

    audio_bytes = base64.b64decode(encoded)
    
    # Use python-magic to detect the MIME type and get an extension
    mime_type = magic.from_buffer(audio_bytes, mime=True)
    ext = 'bin' # default extension
    if mime_type == 'audio/mpeg': ext = 'mp3'
    elif mime_type in ['audio/wav', 'audio/x-wav']: ext = 'wav'
    elif mime_type == 'audio/ogg': ext = 'ogg'
    elif mime_type == 'audio/mp4': ext = 'm4a'
    elif mime_type == 'audio/webm': ext = 'webm'
    
    return audio_bytes, ext

def validate_audio_data(audio_data):
    """(Unused in API) Validates if a string is valid base64."""
    try:
        if ',' in audio_data:
            audio_data = audio_data.split(',')[1]
        base64.b64decode(audio_data)
        return True
    except (TypeError, ValueError):
        return False

# --- NEW GCP TRANSCRIPTION FUNCTION ---

def transcribe_audio(file_path, language='ml-IN'):
    """
    Transcribes the given audio file using Google Cloud Speech-to-Text.
    It converts the audio to FLAC format before sending it to the API.
    Language is set based on user selection (Malayalam or English).
    If Malayalam is detected, translate to English.
    """
    try:
        # Convert audio to FLAC format, which is recommended for GCP Speech-to-Text
        flac_path = file_path.rsplit('.', 1)[0] + '.flac'
        command = ['ffmpeg', '-y', '-i', file_path, flac_path]
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("[FFMPEG ERROR]: 'ffmpeg' command not found. Please install ffmpeg and add it to your PATH.")
        return ""
    except subprocess.CalledProcessError as e:
        print(f"[FFMPEG CONVERSION ERROR]: Failed to convert {file_path} to FLAC. Error: {e}")
        return ""

    try:
        client = speech.SpeechClient()

        with io.open(flac_path, "rb") as audio_file:
            content = audio_file.read()

        # Set language code based on input
        if language == 'ml-IN':
            alt_langs = ['en-IN', 'en-US']
        else:
            alt_langs = ['ml-IN']
        print(f"[TRANSCRIBE] Using language_code={language}, alternative_language_codes={alt_langs}")

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
            language_code=language,
            alternative_language_codes=alt_langs
            # sample_rate_hertz omitted for FLAC to let GCP auto-detect
        )

        print(f"INFO: Sending '{flac_path}' to GCP for transcription...")
        response = client.recognize(config=config, audio=audio)

        transcript = ' '.join([result.alternatives[0].transcript for result in response.results])
        print(f"INFO: Transcription successful. Transcript: {transcript}")

        # If Malayalam, translate to English
        if language == 'ml-IN' and transcript.strip():
            try:
                from google.cloud import translate_v2 as translate
                translate_client = translate.Client()
                translation = translate_client.translate(transcript, target_language='en')
                print(f"[TRANSLATE] Malayalam to English: {translation['translatedText']}")
                return translation['translatedText']
            except Exception as e:
                print(f"[TRANSLATE ERROR]: {e}")
                # Fallback to Malayalam transcript
                return transcript.strip()
        return transcript.strip()

    except Exception as e:
        print(f"[GCP TRANSCRIBE ERROR]: {e}")
        return ""
    finally:
        # Clean up the temporary FLAC file
        if os.path.exists(flac_path):
            os.remove(flac_path)