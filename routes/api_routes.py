from flask import Blueprint, request, jsonify, session, current_app
from utils import (require_login, allowed_file, generate_secure_filename, 
                   save_uploaded_file, get_response_message, format_timestamp,
                   validate_audio_data, process_base64_audio, transcribe_audio,
                   translate_malayalam_to_english,translate_english_to_malayalam)
from RAG_engine import ask_kerala_panchayat
from models import SessionModel, ChatModel, AudioModel
from database import check_db_connection

api_bp = Blueprint('api', __name__)

@api_bp.route('/chat', methods=['POST'])
@require_login
def chat_api():
    """API endpoint for chat messages"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    user_message = data.get('message', '')
    language = data.get('language', 'english')

    if not user_message.strip():
        return jsonify({'error': 'Message cannot be empty'}), 400

    print(f"[CHAT API] User message: {user_message}, Language: {language}")

    # Always work in English for the RAG engine
    if language == 'malayalam':
        text = translate_malayalam_to_english(user_message)
        if text is None:
            return jsonify({'error': 'Translation failed. Please try again.'}), 500
        user_message_en = text
    else:
        user_message_en = user_message

    session_id = session.get('session_id')
    user_id = session.get('user_id')

    # Update session activity
    SessionModel.update_session_activity(session_id)

    # Generate response from RAG engine using English message
    get_response_message = ask_kerala_panchayat(user_message_en)
    if get_response_message is None:
        return jsonify({'error': 'Failed to get response from RAG engine'}), 500

    print(f"\n\n[CHAT API] Response from RAG engine: {get_response_message['answer']}\n\n")

    if language == 'malayalam':
        response_message = translate_english_to_malayalam(get_response_message['answer'])
        if response_message is None:
            return jsonify({'error': 'Translation failed. Please try again.'}), 500
    else:
        response_message = get_response_message['answer']

    print(f"\n\n[CHAT API] Response message: {response_message}\n\n")

    response = {
        'message': response_message,
        'timestamp': format_timestamp(),
        'source_reference': get_response_message['sources']
    }

    # Save chat messages to database
    ChatModel.save_message(session_id, user_id, user_message, 'user', language=language)
    ChatModel.save_message(session_id, user_id, response_message, 'assistant', language=language)

    return jsonify(response)

@api_bp.route('/upload_audio', methods=['POST'])
@require_login
def upload_audio():
    """API endpoint for uploading audio (base64 or file) and transcription"""
    session_id = session.get('session_id')
    user_id = session.get('user_id')
    
    
    # Update session activity
    SessionModel.update_session_activity(session_id)
    
    # Check for base64 audio data
    if request.is_json and 'audio_data' in request.json:
        audio_data = request.json.get('audio_data')
        language = request.json.get('language', 'english')
        transcript = request.json.get('transcript', '')
        print(f"[UPLOAD AUDIO] Session ID: {session_id}, User ID: {user_id}, Language: {language}")
        print(f"transcript: {transcript}")
        
        try:
            # Validate and process base64 audio
            audio_bytes, ext = process_base64_audio(audio_data)
            filename = generate_secure_filename(session_id, ext)
            file_path = save_uploaded_file(audio_bytes, filename)
            # Do not transcribe audio, just log the provided transcript (from client)
            audio_log_id = AudioModel.log_interaction(
                session_id=session_id,
                user_id=user_id,
                audio_file_path=file_path,
                transcript=transcript,
                language=language
            )
            return jsonify({
                'success': True,
                'message': 'Audio uploaded successfully',
                'audio_log_id': audio_log_id,
                'file_path': file_path,
                'transcription': transcript
            })
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error processing audio: {str(e)}'}), 500
    # Check for file upload
    elif 'audio_file' in request.files:
        file = request.files['audio_file']
        language = request.form.get('language', 'english')
        transcript = request.form.get('transcript', '')
        if file and file.filename and allowed_file(file.filename):
            filename = generate_secure_filename(session_id, file.filename.split('.')[-1])
            file_path = save_uploaded_file(file.read(), filename)
            # Do not transcribe audio, just log the provided transcript (from client)
            audio_log_id = AudioModel.log_interaction(
                session_id=session_id,
                user_id=user_id,
                audio_file_path=file_path,
                transcript=transcript,
                language=language
            )
            return jsonify({
                'success': True,
                'message': 'Audio file uploaded successfully',
                'audio_log_id': audio_log_id,
                'file_path': file_path,
                'transcription': transcript
            })
        else:
            return jsonify({'success': False, 'message': 'Invalid file type. Please upload a valid audio file.'}), 400
    return jsonify({'success': False, 'message': 'No audio data provided'}), 400

@api_bp.route('/session_info', methods=['GET'])
@require_login
def session_info():
    """API endpoint to get session information"""
    return jsonify({
        'session_id': session.get('session_id'),
        'user_id': session.get('user_id')
    })