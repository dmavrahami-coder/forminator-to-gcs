from flask import Flask, request, jsonify
import os
import requests
from google.cloud import storage
from datetime import datetime
import logging
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['POST', 'OPTIONS'])
def upload_to_gcs():
    """Upload files from Forminator to Google Cloud Storage"""
    
    if request.method == 'OPTIONS':
        return '', 204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        file_url = data.get('file_url')
        submission_id = data.get('submission_id', 'unknown')
        client_name = data.get('client_name', 'Unknown')
        
        if not file_url:
            return jsonify({'error': 'No file URL provided'}), 400
        
        logger.info(f"Processing: {submission_id} for {client_name}")
        
        # Download file
        response = requests.get(file_url, timeout=30)
        response.raise_for_status()
        
        # Create project ID
        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
        project_id = f"PRJ_{timestamp}"
        
        # Get filename
        if 'uploads/' in file_url:
            filename = file_url.split('uploads/')[-1]
        else:
            filename = file_url.split('/')[-1]
        
        # Create GCS path
        now = datetime.now()
        gcs_filename = f"{now.strftime('%H%M%S')}_{submission_id}_{filename}"
        gcs_path = f"projects/{project_id}/01_architecture/{gcs_filename}"
        
        # Upload to GCS
        client = storage.Client()
        bucket_name = os.environ.get('GCS_BUCKET', 'aiquantifier-uploads')
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_path)
        
        blob.upload_from_string(
            response.content,
            content_type=response.headers.get('content-type', 'application/pdf')
        )
        
        logger.info(f"✅ Uploaded: {gcs_path} ({len(response.content)} bytes)")
        
        return jsonify({
            'success': True,
            'project_id': project_id,
            'gcs_path': gcs_path,
            'file_name': filename,
            'file_size': len(response.content),
            'message': 'File uploaded successfully'
        })
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
