from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import json
import os

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

submissions_db = []
processed_ids = set()

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'service': 'Forminator to Google Sheets Webhook',
        'status': 'running',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/webhook', methods=['POST', 'OPTIONS'])
def forminator_webhook():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = {}
        
        if request.is_json:
            data = request.get_json()
        elif request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()
        else:
            raw_data = request.get_data(as_text=True)
            try:
                data = json.loads(raw_data)
            except:
                from urllib.parse import parse_qs
                data = {k: v[0] for k, v in parse_qs(raw_data).items()}
        
        submission_id = f"sub_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        submission = {
            'id': submission_id,
            'data': data,
            'received_at': datetime.now().isoformat(),
            'processed': False,
            'form_id': data.get('form_id', 'unknown'),
            'entry_id': data.get('entry_id', submission_id)
        }
        
        submissions_db.append(submission)
        
        logger.info(f"Submission received: {submission_id}")
        
        return jsonify({
            'success': True,
            'message': 'Webhook received',
            'submission_id': submission_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/get-unprocessed', methods=['GET'])
def get_unprocessed():
    try:
        limit = int(request.args.get('limit', 50))
        
        unprocessed = [
            s for s in submissions_db 
            if not s['processed'] and s['id'] not in processed_ids
        ]
        
        results = unprocessed[:limit]
        
        return jsonify({
            'success': True,
            'count': len(results),
            'records': results
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'queue_size': len([s for s in submissions_db if not s['processed']])
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
