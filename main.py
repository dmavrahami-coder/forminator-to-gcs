from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# הגדר logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
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
    
    # CORS preflight
    if request.method == 'OPTIONS':
        return '', 200
    
    logger.info("=" * 50)
    logger.info("📨 FORMINTOR WEBHOOK RECEIVED")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Content-Type: {request.content_type}")
    
    try:
        # קבלת form data
        form_data = {}
        if request.form:
            form_data = request.form.to_dict()
            logger.info(f"📝 FORM DATA ({len(form_data)} fields):")
            for key, value in form_data.items():
                logger.info(f"  {key}: {value}")
        
        # קבלת files
        files_data = {}
        if request.files:
            files_data = request.files.to_dict()
            logger.info(f"📁 FILES ({len(files_data)} files):")
            for key, file in files_data.items():
                if file and file.filename:
                    # קרא את הקובץ
                    file.seek(0, 2)  # סוף הקובץ
                    size = file.tell()
                    file.seek(0)  # חזרה להתחלה
                    logger.info(f"  {key}: {file.filename} ({size} bytes)")
        
        logger.info("=" * 50)
        
        # תשובה ל-Forminator
        response = {
            'success': True,
            'message': 'Webhook received successfully',
            'timestamp': datetime.now().isoformat(),
            'received': {
                'form_fields': list(form_data.keys()),
                'file_fields': list(files_data.keys()),
                'form_count': len(form_data),
                'file_count': len(files_data)
            }
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"❌ ERROR: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 400

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Starting Forminator Webhook Service on port {port}")
    logger.info(f"📡 Ready to receive webhooks at /webhook")
    app.run(host='0.0.0.0', port=port, debug=False)
