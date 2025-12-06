from flask import Flask, request, jsonify
import os
import requests
from google.cloud import storage
from datetime import datetime
import logging
from flask_cors import CORS
# >>> ייבוא חדש לטיפול ב-URL-ים
import urllib.parse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# פונקציה מסייעת לעיבוד קובץ יחיד
def _process_single_file(file_url_encoded, project_id, submission_id):
    """Handles download, GCS path creation, and upload for a single, encoded file URL."""
    
    # 1. פענוח (Unquote) של ה-URL לטיפול בתווים עבריים
    file_url = urllib.parse.unquote(file_url_encoded.strip())
    
    # 2. הורדת קובץ
    logger.info(f"-> Attempting to download: {file_url}")
    response = requests.get(file_url, timeout=30)
    response.raise_for_status() # יזרוק שגיאת 404/אחרת אם הכשל ממשי
    
    # 3. יצירת נתיב GCS (שם הקובץ בתוך תיקיית הפרויקט)
    # לוקח את שם הקובץ משורת ה-URL
    if 'uploads/' in file_url:
        filename = file_url.split('uploads/')[-1]
    else:
        # טיפול ב-URL שונה
        filename = file_url.split('/')[-1]
    
    # הנתיב ב-GCS כולל את project_id ואת תיקיית הסיווג
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
    
    # ... (CORS logic remains here) ...
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
            
        file_url_string = data.get('file_url')
        submission_id = data.get('submission_id', 'unknown')
        client_name = data.get('client_name', 'Unknown')
        
        if not file_url_string:
            return jsonify({'error': 'No file URL provided'}), 400
            
        # יצירת Project ID קבוע עבור ה-Submission הנוכחי
        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
        project_id = f"PRJ_{timestamp}"
        
        logger.info(f"Processing Submission {submission_id} for {client_name}. Project ID: {project_id}")
        
        # >>> התיקון הקריטי: פיצול המחרוזת ל-URLs נפרדים <<<
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
                
        if errors and not results:
             # אם כל הקבצים נכשלו
             raise Exception(f"All files failed to upload. Errors: {errors}")

        return jsonify({
            'success': True,
            'project_id': project_id,
            'uploaded_files_count': len(results),
            'files_uploaded': results,
            'files_failed': len(errors),
            'message': 'File processing completed, see details for errors.'
        }), 200
        
    except Exception as e:
        logger.error(f"❌ FATAL Error in request: {str(e)}")
        # ה-Apps Script מצפה ל-500 כדי לרשום ERROR
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
