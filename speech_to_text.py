import os
import subprocess
import io
from google.cloud import speech
from dotenv import load_dotenv


load_dotenv()

# Set GCP credentials from .env
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

print("GCP Credentials:", os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))



def transcribe_with_gcp(file_path):
    try:
        # Convert to FLAC format for Google API
        flac_path = file_path.rsplit('.', 1)[0] + '.flac'
        subprocess.run(['ffmpeg', '-y', '-i', file_path, flac_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        client = speech.SpeechClient()

        with io.open(flac_path, "rb") as audio_file:
            content = audio_file.read()

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.FLAC,
            language_code='ml-IN',  # Malayalam input
            alternative_language_codes=['en-IN', 'en-US']  # Help detect English if user switches
            # sample_rate_hertz is omitted for FLAC to avoid GCP error
        )

        response = client.recognize(config=config, audio=audio)

        transcript = ''
        for result in response.results:
            transcript += result.alternatives[0].transcript + ' '

        return transcript.strip()
    except Exception as e:
        print(f"[GCP TRANSCRIBE ERROR]: {e}")
        return ""
