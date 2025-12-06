from flask import Flask, request, jsonify
import os
import requests
from google.cloud import storage
from datetime import datetime
import logging
from flask_cors import CORS
import urllib.parse
import json

logging.basicConfig(level=logging.DEBUG)  # שיניתי ל-DEBUG
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

def _process_single_file(file_url_encoded, project_id, submission_id):
    """Handles download, GCS path creation, and upload for a single, encoded file URL."""
    
    # 1. פענוח (Unquote) של ה-URL לטיפול בתווים עבריים
    file_url = urllib.parse.unquote(file_url_encoded.strip())
    
    # 2. הורדת קובץ
    logger.info(f"-> Attempting to download: {file_url}")
    response = requests.get(file_url, timeout=30)
    response.raise_for_status()
    
    # 3. יצירת נתיב GCS
    if 'uploads/' in file_url:
        filename = file_url.split('uploads/')[-1]
    else:
        filename = file_url.split('/')[-1]
    
    gcs_filename = f"{submission_id}_{filename}"
    gcs_path = f"projects/{project_id}/01_architecture/{gcs_filename}"
    
    # 4. העלאה ל-GCS
    client = storage.Client()
    bucket_name = os.environ.get('GCS_BUCKET', 'aiquantifier-uploads')
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_path)
    
    blob.upload_from_string(
        response.content,
        content_type=response.headers.get('content-type', 'application/pdf')
    )
    
    return {
        'success': True,
        'gcs_path': gcs_path,
        'file_name': filename,
        'file_size': len(response.content)
    }

@app.route('/', methods=['POST', 'OPTIONS'])
def upload_to_gcs():
    """Upload multiple files from Forminator to Google Cloud Storage"""
    
    # CORS headers
    if request.method == 'OPTIONS':
        return '', 204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Max-Age': '3600'
        }
    
    logger.info(f"=== NEW WEBHOOK REQUEST ===")
    logger.info(f"Method: {request.method}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Content-Type: {request.content_type}")
    
    try:
        # בדוק את סוג התוכן שהתקבל
        if request.is_json:
            logger.info("Request is JSON")
            data = request.get_json()
        elif 'application/x-www-form-urlencoded' in request.content_type:
            logger.info("Request is FORM URLENCODED")
            data = request.form.to_dict()
            # נסה להמיר שדות JSON אם קיימים
            for key in data:
                try:
                    data[key] = json.loads(data[key])
                except:
                    pass
        elif 'multipart/form-data' in request.content_type:
            logger.info("Request is MULTIPART FORM")
            data = request.form.to_dict()
            # טיפול בקבצים אם יש
            files = request.files.to_dict()
            logger.info(f"Files received: {list(files.keys())}")
        else:
            # נסה לקרוא כטקסט
            raw_data = request.get_data(as_text=True)
            logger.info(f"Raw data: {raw_data}")
            try:
                data = json.loads(raw_data)
            except:
                data = {'raw_data': raw_data}
        
        logger.info(f"Parsed data: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # 🔧 **חלק קריטי: מיפוי שדות מ-Forminator**
        # Forminator שולח נתונים בשדות שונים. צריך למצוא את השדה הנכון
        
        # נסה שמות שדות שונים ש-Forminator עשוי לשלוח
        file_url_string = None
        
        # אפשרויות שונות לשדה של קבצים
        possible_file_fields = [
            'file_url',           # השדה שלך
            'url',                # Forminator default
            'uploaded_files',     # Forminator field
            'form_fields',        # אם כל השדות באובייקט אחד
            'data',               # שדה כללי
            'field-values',       # Forminator field
            'field_values_1'      # שדה מספרי
        ]
        
        for field in possible_file_fields:
            if field in data:
                file_url_string = data[field]
                logger.info(f"Found file URL in field '{field}': {file_url_string}")
                break
        
        # אם לא מצאנו, נבדוק אם כל הנתונים הם בעצם קישור
        if not file_url_string and isinstance(data, str):
            file_url_string = data
        elif not file_url_string:
            # נבדוק בכל המפתחות
            for key, value in data.items():
                logger.info(f"Checking key '{key}': {value}")
                if isinstance(value, str) and ('http://' in value or 'https://' in value or 'uploads/' in value):
                    file_url_string = value
                    logger.info(f"Found URL in key '{key}'")
                    break
        
        if not file_url_string:
            logger.error(f"No file URL found in data. Available keys: {list(data.keys())}")
            return jsonify({
                'error': 'No file URL found in request',
                'received_data': data,
                'success': False
            }), 400
        
        # קבלת submission_id ו-client_name
        submission_id = data.get('submission_id', 
                                data.get('entry_id', 
                                        data.get('id', 'unknown')))
        
        client_name = data.get('client_name', 
                              data.get('name',
                                      data.get('form_name', 'Unknown')))
        
        # יצירת Project ID
        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
        project_id = f"PRJ_{timestamp}"
        
        logger.info(f"Processing Submission {submission_id} for {client_name}. Project ID: {project_id}")
        
        # פיצול המחרוזת ל-URLs נפרדים
        file_urls = [url.strip() for url in file_url_string.split(',')]
        
        results = []
        errors = []
        
        for file_url_encoded in file_urls:
            if not file_url_encoded:
                continue
                
            try:
                result = _process_single_file(file_url_encoded, project_id, submission_id)
                results.append(result)
                logger.info(f"✅ Successful upload for Project {project_id}.")
                
            except Exception as e:
                error_msg = f"Failed to upload file from URL: {file_url_encoded}. Error: {str(e)}"
                logger.error(f"❌ {error_msg}")
                errors.append(error_msg)
                
        response_data = {
            'success': True,
            'project_id': project_id,
            'uploaded_files_count': len(results),
            'files_uploaded': results,
            'message': 'File processing completed'
        }
        
        if errors:
            response_data['files_failed'] = errors
            response_data['warning'] = f'{len(errors)} files failed'
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"❌ FATAL Error in request: {str(e)}")
        return jsonify({
            'error': str(e),
            'success': False,
            'content_type': request.content_type,
            'headers': dict(request.headers)
        }), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'service': 'Forminator to GCS Webhook',
        'status': 'running',
        'endpoints': {
            'POST /': 'Process Forminator webhook',
            'GET /health': 'Health check'
        }
    }), 200

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
