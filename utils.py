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
from sarvamai import SarvamAI


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

def _chunk_text(text: str, max_length: int = 1000) -> list[str]:
    """
    Splits a given text into chunks of a specified maximum length,
    attempting to break at word boundaries if possible.

    Args:
        text: The input string to be chunked.
        max_length: The maximum length of each chunk.

    Returns:
        A list of text chunks.
    """
    chunks = []
    current_text = text
    while len(current_text) > max_length:
        # Find the last space within the max_length to avoid breaking words
        split_index = current_text.rfind(' ', 0, max_length)
        if split_index == -1: # No space found, force split at max_length
            split_index = max_length
        
        chunk = current_text[:split_index].strip()
        if chunk: # Add chunk if not empty after stripping
            chunks.append(chunk)
        current_text = current_text[split_index:].lstrip() # Remove leading spaces from next chunk

    if current_text.strip(): # Add any remaining text as the last chunk
        chunks.append(current_text.strip())
    
    return chunks

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
            


def translate_malayalam_to_english(malayalam_text: str) -> str | None:
    """
    Translates Malayalam text to English using the Sarvam AI Text Translation API.

    The Sarvam AI API key is loaded from a .env file (SARVAM_API_KEY).

    Args:
        malayalam_text: The input text in Malayalam to be translated.

    Returns:
        The translated text in English as a string, or None if an error occurs.
    """
    # Load environment variables from .env file
    load_dotenv()

    # Get the Sarvam AI API key from environment variables
    sarvam_api_key = os.getenv("SARVAM_API_KEY")

    if not sarvam_api_key:
        print("Error: SARVAM_API_KEY not found in .env file or environment variables.")
        return None

    if not malayalam_text.strip():
        print("Warning: Input Malayalam text is empty. Returning empty string.")
        return ""

    try:
        # Initialize the SarvamAI client with your API key
        client = SarvamAI(api_subscription_key=sarvam_api_key)

        # Call the text translation API
        # source_language_code="ml-IN" for Malayalam (India)
        # target_language_code="en-IN" for English (India)
        # You can specify a 'model' here if you have a preference, e.g., model="sarvam-translate:v1"
        response = client.text.translate(
            input=malayalam_text,
            source_language_code="ml-IN",
            target_language_code="en-IN",
            # model="sarvam-translate:v1" # Uncomment if you want to specify a model
        )
        # The translated text is typically in a 'translatedText' attribute of the response object.
        # Refer to Sarvam AI's documentation for the exact response structure if this doesn't work.
        if hasattr(response, 'translated_text'):
            return response.translated_text
        else:
            print(f"Error: Unexpected response structure from Sarvam AI API. Response: {response}")
            return None

    except Exception as e:
        print(f"An error occurred during translation: {e}")
        return None

def translate_english_to_malayalam(english_text: str) -> str | None:
    """
    Translates English text to Malayalam using the Sarvam AI Text Translation API.

    The Sarvam AI API key is loaded from a .env file (SARVAM_API_KEY).
    This function handles input texts longer than the API's character limit
    by chunking them and reassembling the translation.

    Args:
        english_text: The input text in English to be translated.

    Returns:
        The translated text in Malayalam as a string, or None if an error occurs.
    """
    # Load environment variables from .env file
    load_dotenv()

    # Get the Sarvam AI API key from environment variables
    sarvam_api_key = os.getenv("SARVAM_API_KEY")

    if not sarvam_api_key:
        print("Error: SARVAM_API_KEY not found in .env file or environment variables.")
        return None

    if not english_text.strip():
        print("Warning: Input English text is empty. Returning empty string.")
        return ""

    try:
        # Initialize the SarvamAI client with your API key
        client = SarvamAI(api_subscription_key=sarvam_api_key)

        # The Sarvam AI 'mayura:v1' model has a 1000 character limit.
        # 'sarvam-translate:v1' supports up to 2000 characters.
        # We'll use 1000 as a safe default for chunking.
        MAX_CHAR_LIMIT = 1000
        text_chunks = _chunk_text(english_text, MAX_CHAR_LIMIT)
        
        translated_chunks = []
        for i, chunk in enumerate(text_chunks):
            print(f"Translating English chunk {i+1}/{len(text_chunks)} (length: {len(chunk)})...")
            response = client.text.translate(
                input=chunk,
                source_language_code="en-IN",
                target_language_code="ml-IN",
                # model="mayura:v1" # This model has a 1000 char limit.
                # model="sarvam-translate:v1" # This model supports up to 2000 chars and all 22 Indic languages.
                # If no model is specified, a default might be used, which could be mayura:v1.
                # Consider explicitly setting 'model' if you have specific requirements or encounter issues.
            )

            if hasattr(response, 'translated_text'):
                translated_chunks.append(response.translated_text)
            else:
                print(f"Error: Unexpected response structure from Sarvam AI API for chunk {i+1}. Response: {response}")
                return None
        
        return " ".join(translated_chunks) # Join translated chunks with a space

    except Exception as e:
        print(f"An error occurred during translation: {e}")
        return None
