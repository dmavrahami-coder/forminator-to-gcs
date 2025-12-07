from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'service': 'Forminator Webhook',
        'status': 'running'
    }), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/webhook', methods=['POST', 'OPTIONS'])
def webhook():
    if request.method == 'OPTIONS':
        return '', 200
    
    print("=" * 50)
    print("📨 Forminator webhook received")
    print(f"Content-Type: {request.content_type}")
    
    if request.form:
        print(f"Form fields: {list(request.form.keys())}")
        for key, value in request.form.items():
            print(f"  {key}: {value[:50]}")
    
    if request.files:
        print(f"Files: {list(request.files.keys())}")
        for key, file in request.files.items():
            if file and file.filename:
                print(f"  {key}: {file.filename}")
    
    print("=" * 50)
    
    return jsonify({
        'success': True,
        'message': 'Received'
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
