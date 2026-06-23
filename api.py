from flask import Flask, request, jsonify, send_file
import edge_tts
import os
import tempfile
import uuid
import logging
import time
import asyncio
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Production configuration
app.config['ENV'] = 'production'
app.config['DEBUG'] = False
app.config['PROPAGATE_EXCEPTIONS'] = True

# Get configuration from environment
API_KEY = os.environ.get('TTS_API_KEY')
PORT = int(os.environ.get('PORT', 5001))

# Validate API key at startup
if not API_KEY:
    logger.error("❌ TTS_API_KEY environment variable not set!")
    raise ValueError("TTS_API_KEY environment variable is required")

ALLOWED_VOICES = [
    # English voices
    "en-US-JennyNeural", "en-US-GuyNeural",
    "en-GB-SoniaNeural", "en-AU-WilliamNeural",
    # Spanish
    "es-ES-ElviraNeural", "es-MX-DaliaNeural",
    # French
    "fr-FR-DeniseNeural", "fr-FR-HenriNeural",
    # German
    "de-DE-KatjaNeural", "de-DE-ConradNeural",
    # Italian
    "it-IT-ElsaNeural", "it-IT-IsabellaNeural",
    # Portuguese
    "pt-BR-FranciscaNeural", "pt-PT-FernandaNeural",
    # Russian
    "ru-RU-DariyaNeural", "ru-RU-SvetlanaNeural",
    # Japanese
    "ja-JP-NanamiNeural", "ja-JP-KeitaNeural",
    # Korean
    "ko-KR-SunHiNeural", "ko-KR-InJoonNeural",
    # Chinese
    "zh-CN-XiaoxiaoNeural", "zh-CN-YunyangNeural",
    # Arabic
    "ar-SA-ZariyahNeural", "ar-EG-ShakirNeural",
    # Hindi
    "hi-IN-SwaraNeural", "hi-IN-MadhurNeural"
]

# Voice mapping for OpenAI compatibility
VOICE_MAPPING = {
    "alloy": "en-US-JennyNeural",
    "echo": "en-GB-SoniaNeural",
    "fable": "en-GB-RyanNeural",
    "onyx": "en-US-GuyNeural",
    "nova": "en-US-AriaNeural",
    "shimmer": "en-AU-WilliamNeural"
}

def verify_auth():
    """Verify the API key from Authorization header"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return False
    
    token = auth_header.replace('Bearer ', '')
    return token == API_KEY

@app.before_request
def authenticate():
    """Global authentication for all routes except health check"""
    if request.path == '/health':
        return None
    
    if not verify_auth():
        return jsonify({
            "error": {
                "message": "Invalid authentication credentials",
                "type": "authentication_error"
            }
        }), 401

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "service": "OpenSpeech-TTS",
        "version": "1.0.0",
        "timestamp": time.time()
    })

@app.route('/v1/audio/speech', methods=['POST'])
def text_to_speech():
    """
    OpenAI-compatible text-to-speech endpoint
    """
    temp_file = None
    
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        text = data.get('input', '')
        if not text:
            return jsonify({"error": "Missing 'input' field"}), 400
        
        # Limit text length to prevent abuse
        if len(text) > 5000:
            return jsonify({"error": "Text exceeds maximum length of 5000 characters"}), 400
        
        # Get voice (default to alloy)
        voice = data.get('voice', 'alloy')
        
        # Map voice or use direct Edge TTS voice
        edge_voice = VOICE_MAPPING.get(voice, voice)
        
        # Validate voice is allowed
        if edge_voice not in ALLOWED_VOICES:
            return jsonify({"error": f"Voice '{voice}' is not supported"}), 400
        
        # Get speed (optional)
        speed = data.get('speed', 1.0)
        if speed < 0.5 or speed > 2.0:
            return jsonify({"error": "Speed must be between 0.5 and 2.0"}), 400
        
        logger.info(f"Generating speech: {len(text)} chars, voice: {edge_voice}, speed: {speed}")
        
        # Create temporary file for audio
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, f"speech_{uuid.uuid4()}.mp3")
        
        # Generate speech using edge-tts
        async def generate():
            rate = f"{int((speed - 1) * 100):+d}%" if speed != 1.0 else "+0%"
            communicate = edge_tts.Communicate(text, edge_voice, rate=rate)
            await communicate.save(temp_file)
        
        # Run async function with timeout
        try:
            asyncio.run(asyncio.wait_for(generate(), timeout=60))
        except asyncio.TimeoutError:
            raise Exception("Speech generation timed out after 60 seconds")
        
        # Check if file was created
        if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
            raise Exception("Failed to generate audio")
        
        file_size = os.path.getsize(temp_file)
        logger.info(f"Audio generated successfully: {file_size} bytes")
        
        # Send the file
        response = send_file(
            temp_file,
            mimetype='audio/mpeg',
            as_attachment=False,
            download_name='speech.mp3'
        )
        
        # Clean up after sending
        @response.call_on_close
        def cleanup():
            try:
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.debug(f"Cleaned up temp file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file: {e}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        
        # Cleanup on error
        try:
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass
        
        return jsonify({
            "error": {
                "message": str(e),
                "type": "internal_error"
            }
        }), 500

@app.route('/v1/models', methods=['GET'])
def list_models():
    """List available TTS models"""
    return jsonify({
        "data": [
            {
                "id": "tts-1",
                "object": "model",
                "created": 1677610602,
                "owned_by": "openai"
            }
        ]
    })

@app.route('/v1/voices', methods=['GET'])
def list_voices():
    """List available voices"""
    return jsonify({
        "voices": ALLOWED_VOICES
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

# This is only used when running directly (development)
# In production, Gunicorn will use the 'app' variable
if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("⚠️  RUNNING IN DEVELOPMENT MODE")
    print("=" * 50)
    print(f"🔑 API Key: {API_KEY[:4]}...{API_KEY[-4:]}")
    print(f"🚀 Server starting on port {PORT}")
    print("📝 Endpoint: /v1/audio/speech")
    print("💚 Health: /health")
    print("\n⚠️  Use Gunicorn for production!")
    print("=" * 50 + "\n")
    
    app.run(host='0.0.0.0', port=PORT, debug=False)
