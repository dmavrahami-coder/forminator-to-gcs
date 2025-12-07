from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'service': 'Forminator to GCS',
        'status': 'running',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/webhook', methods=['POST', 'OPTIONS'])
def webhook():
    """קבלת webhook מ-Forminator"""
    
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        logger.info("📨 Forminator webhook received")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Has form data: {bool(request.form)}")
        logger.info(f"Has files: {bool(request.files)}")
        
        # הדפס את כל השדות שהתקבלו
        if request.form:
            logger.info("Form data fields:")
            for key in request.form.keys():
                logger.info(f"  - {key}")
        
        if request.files:
            logger.info("File fields:")
            for key in request.files.keys():
                file = request.files[key]
                if file and file.filename:
                    logger.info(f"  - {key}: {file.filename} ({len(file.read())} bytes)")
                    file.seek(0)
        
        # תשובה ל-Forminator
        response = {
            'success': True,
            'message': 'Webhook received successfully',
            'timestamp': datetime.now().isoformat(),
            'received_fields': {
                'form': list(request.form.keys()) if request.form else [],
                'files': list(request.files.keys()) if request.files else []
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
