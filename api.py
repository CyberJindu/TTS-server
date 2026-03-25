from flask import Flask, request, jsonify, send_file
import edge_tts
import os
import tempfile
import uuid
import logging
import time

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - you'll set these when running
API_KEY = None
#ALLOWED_VOICES = [
    #"alloy", "echo", "fable", "onyx", "nova", "shimmer",  # OpenAI compatible
    #"en-US-JennyNeural", "en-US-GuyNeural",  # Edge TTS specific
    #"en-GB-SoniaNeural", "en-AU-WilliamNeural"
#]

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
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "OpenSpeech-TTS",
        "timestamp": time.time()
    })


@app.route('/v1/audio/speech', methods=['POST'])
def text_to_speech():
    """
    OpenAI-compatible text-to-speech endpoint
    """
    try:
        data = request.get_json()

        # Validate required fields
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        text = data.get('input', '')
        if not text:
            return jsonify({"error": "Missing 'input' field"}), 400

        # Get voice (default to alloy)
        voice = data.get('voice', 'alloy')

        # Map OpenAI voice names to Edge TTS voices
        voice_mapping = {
            "alloy": "en-US-JennyNeural",
            "echo": "en-GB-SoniaNeural",
            "fable": "en-GB-RyanNeural",
            "onyx": "en-US-GuyNeural",
            "nova": "en-US-AriaNeural",
            "shimmer": "en-AU-WilliamNeural"
        }

        # Use mapped voice or fallback to direct Edge TTS voice
        edge_voice = voice_mapping.get(voice, voice)

        # Get speed (optional)
        speed = data.get('speed', 1.0)

        logger.info(f"Generating speech: {len(text)} chars, voice: {edge_voice}, speed: {speed}")

        # Create temporary file for audio
        temp_dir = tempfile.gettempdir()
        output_file = os.path.join(temp_dir, f"speech_{uuid.uuid4()}.mp3")

        # Generate speech using edge-tts
        async def generate():
            communicate = edge_tts.Communicate(text, edge_voice, rate=f"{int((speed - 1) * 100):+d}%")
            await communicate.save(output_file)

        # Run async function
        import asyncio
        asyncio.run(generate())

        # Check if file was created
        if not os.path.exists(output_file):
            raise Exception("Failed to generate audio")

        logger.info(f"Audio generated successfully: {os.path.getsize(output_file)} bytes")

        # Send the file
        return send_file(
            output_file,
            mimetype='audio/mpeg',
            as_attachment=False,
            download_name='speech.mp3'
        )

    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        return jsonify({
            "error": {
                "message": str(e),
                "type": "internal_error"
            }
        }), 500
    finally:
        # Clean up temp file after sending
        try:
            if 'output_file' in locals() and os.path.exists(output_file):
                os.remove(output_file)
        except:
            pass


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


if __name__ == '__main__':
    import sys
    from art import tprint

    # Get configuration from environment or input
    API_KEY = os.environ.get('TTS_API_KEY')
    port = os.environ.get('PORT', '5001')

    if not API_KEY:
        print("\n" + "=" * 50)
        print("OPENSPEECH-TTS SERVER SETUP")
        print("=" * 50)
        API_KEY = input("Enter your API key: ").strip()
        port = input(f"Enter port [5001]: ").strip() or "5001"

    try:
        port = int(port)
    except:
        port = 5001

    tprint("OpenSpeech-TTS")
    print(f"\n🚀 Server starting on port {port}")
    print(f"🔑 API Key: {API_KEY}")
    print(f"📝 Endpoint: http://localhost:{port}/v1/audio/speech")
    print(f"💚 Health: http://localhost:{port}/health")
    print("\nPress Ctrl+C to stop\n")

    app.run(host='0.0.0.0', port=port, debug=False)
