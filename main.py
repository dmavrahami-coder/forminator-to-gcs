from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import storage
import logging
from datetime import datetime
import os
import uuid

app = Flask(__name__)
CORS(app)

# הגדרות
GCS_BUCKET = 'aiquantifier-uploads'

# אתחול logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# אתחול GCS client
storage_client = None
bucket = None

try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET)
    logger.info(f"✅ Connected to GCS bucket: {GCS_BUCKET}")
except Exception as e:
    logger.error(f"❌ GCS connection error: {str(e)}")

def generate_project_id():
    """יצירת project_id בתבנית YYYYMMDD_HHMMSS"""
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def upload_file_to_gcs(file, project_id, field_name):
    """העלאת קובץ ל-GCS"""
    if not storage_client or not bucket:
        raise Exception("GCS client not initialized")
    
    try:
        # שם קובץ ייחודי
        timestamp = datetime.now().strftime('%H%M%S')
        unique_id = uuid.uuid4().hex[:6]
        original_name = file.filename
        safe_name = f"{timestamp}_{unique_id}_{original_name}"
        
        # נתיב ב-GCS
        gcs_path = f"projects/{project_id}/{safe_name}"
        
        # העלאה
        blob = bucket.blob(gcs_path)
        file.seek(0)
        blob.upload_from_file(file)
        
        logger.info(f"✅ Uploaded: {original_name} → {gcs_path}")
        
        return {
            'field_name': field_name,
            'original_name': original_name,
            'gcs_path': gcs_path,
            'size': blob.size,
            'url': f"gs://{GCS_BUCKET}/{gcs_path}"
        }
        
    except Exception as e:
        logger.error(f"❌ Upload failed: {str(e)}")
        raise

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'service': 'Forminator to GCS Uploader',
        'status': 'running',
        'gcs_bucket': GCS_BUCKET,
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/webhook', methods=['POST', 'OPTIONS'])
def webhook():
    if request.method == 'OPTIONS':
        return '', 200
    
    project_id = None
    uploaded_files = []
    
    try:
        logger.info("📨 Forminator webhook received")
        
        # יצירת project_id
        project_id = generate_project_id()
        logger.info(f"📂 Project ID: {project_id}")
        
        # קבלת נתונים
        form_data = request.form.to_dict() if request.form else {}
        files_data = request.files.to_dict() if request.files else {}
        
        logger.info(f"📝 Form fields: {list(form_data.keys())}")
        logger.info(f"📁 File fields: {list(files_data.keys())}")
        
        # העלאת קבצים ל-GCS
        for field_name, file in files_data.items():
            if file and file.filename:
                logger.info(f"  Uploading: {field_name} = {file.filename}")
                file_info = upload_file_to_gcs(file, project_id, field_name)
                uploaded_files.append(file_info)
        
        # תשובה
        response = {
            'success': True,
            'message': 'Files uploaded successfully',
            'project_id': project_id,
            'files_uploaded': len(uploaded_files),
            'gcs_bucket': GCS_BUCKET,
            'gcs_folder': f"projects/{project_id}/",
            'upload_timestamp': datetime.now().isoformat(),
            'file_list': uploaded_files
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'project_id': project_id
        }), 400

@app.route('/health', methods=['GET'])
def health():
    gcs_status = 'connected' if storage_client and bucket else 'not connected'
    return jsonify({
        'status': 'healthy',
        'gcs_bucket': GCS_BUCKET,
        'gcs_status': gcs_status,
        'timestamp': datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
