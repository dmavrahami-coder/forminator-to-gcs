from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import storage
import logging
from datetime import datetime
import json
import os
import uuid
from werkzeug.utils import secure_filename
import mimetypes

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ============ הגדרות ============
GCS_BUCKET_NAME = 'aiquantifier-uploads'
ALLOWED_EXTENSIONS = {
    # תמונות
    'png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'webp', 'heic',
    # מסמכים
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods',
    # טקסט
    'txt', 'csv', 'json', 'xml', 'html',
    # ארכיונים
    'zip', 'rar', '7z', 'tar', 'gz',
    # מדיה
    'mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv',
    'mp3', 'wav', 'm4a', 'ogg', 'flac'
}

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_TOTAL_SIZE = 500 * 1024 * 1024  # 500MB לכל פרויקט

# ============ אתחול ============
storage_client = storage.Client()
bucket = storage_client.bucket(GCS_BUCKET_NAME)

# מאגר זמני (בפרודקשן תשתמש ב-Firestore/DB)
submissions_db = []
processed_ids = set()

# ============ פונקציות עזר ============
def allowed_file(filename):
    """בודק אם סוג הקובץ מותר"""
    if not filename:
        return False
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def generate_project_id():
    """
    מייצר מזהה פרויקט בתבנית: YYYYMMDD_HHMMSS
    דוגמה: 20251207_143025
    """
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def get_file_size(file):
    """מחזיר גודל קובץ"""
    current_pos = file.tell()
    file.seek(0, 2)  # סוף הקובץ
    size = file.tell()
    file.seek(current_pos)  # חזרה למיקום המקורי
    return size

def upload_to_gcs(file_stream, filename, project_id, field_name):
    """מעלה קובץ ל-GCS ומחזיר URL"""
    try:
        # בדיקת גודל
        file_size = get_file_size(file_stream)
        if file_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE})")
        
        # שמור שם מקורי
        original_filename = secure_filename(filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
        
        # צור שם קובץ ייחודי עם timestamp
        timestamp = datetime.now().strftime('%H%M%S')
        file_uuid = uuid.uuid4().hex[:6]
        safe_filename = f"{timestamp}_{file_uuid}_{original_filename}"
        
        # נתיב מלא ב-GCS: projects/20251207_143025/143025_abc123_filename.jpg
        gcs_path = f"projects/{project_id}/{safe_filename}"
        
        # אתחול blob
        blob = bucket.blob(gcs_path)
        
        # ניחוש content type
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = 'application/octet-stream'
        
        # העלאה ל-GCS
        file_stream.seek(0)
        blob.upload_from_file(
            file_stream,
            content_type=content_type,
            timeout=600  # 10 דקות timeout
        )
        
        # צור signed URL (תקף ל-7 ימים)
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(days=7),
            method="GET"
        )
        
        # מידע על הקובץ
        file_info = {
            'field_name': field_name,
            'original_filename': original_filename,
            'gcs_filename': safe_filename,
            'gcs_path': gcs_path,
            'url': url,
            'size': file_size,
            'content_type': content_type,
            'upload_time': datetime.now().isoformat(),
            'bucket': GCS_BUCKET_NAME,
            'project_id': project_id
        }
        
        logging.info(f"✅ File uploaded: {original_filename} → gs://{GCS_BUCKET_NAME}/{gcs_path}")
        return file_info
        
    except Exception as e:
        logging.error(f"❌ Error uploading {filename}: {str(e)}")
        raise

# ============ Routes ============
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'service': 'Forminator to GCS Uploader',
        'version': '2.0',
        'gcs_bucket': GCS_BUCKET_NAME,
        'project_id_format': 'YYYYMMDD_HHMMSS',
        'endpoints': {
            'webhook': '/webhook (POST)',
            'get_files': '/files/<project_id> (GET)',
            'health': '/health (GET)',
            'projects': '/projects (GET)'
        },
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/webhook', methods=['POST', 'OPTIONS'])
def handle_forminator_webhook():
    """מקבל קבצים ונתונים מ-Forminator"""
    
    # CORS preflight
    if request.method == 'OPTIONS':
        return '', 200, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    
    start_time = datetime.now()
    project_id = None
    uploaded_files = []
    
    try:
        logging.info("=" * 60)
        logging.info("📨 FORMINTOR WEBHOOK - FILE UPLOAD")
        logging.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # יצירת project_id בתבנית YYYYMMDD_HHMMSS
        project_id = generate_project_id()
        logging.info(f"📂 PROJECT ID: {project_id}")
        logging.info(f"📁 GCS Path: projects/{project_id}/")
        
        # קבלת form data
        form_data = {}
        if request.form:
            form_data = request.form.to_dict()
            logging.info(f"📝 Form Data: {json.dumps(form_data, indent=2)}")
        
        # קבלת files
        files_data = {}
        if request.files:
            files_data = request.files.to_dict()
            logging.info(f"📦 Files received: {len(files_data)}")
        
        # העלאת קבצים ל-GCS
        if files_data:
            total_size = 0
            file_counter = 1
            
            for field_name, file in files_data.items():
                if file and file.filename and allowed_file(file.filename):
                    file_size = get_file_size(file)
                    total_size += file_size
                    
                    if total_size > MAX_TOTAL_SIZE:
                        raise ValueError(f"Total files size exceeds limit: {total_size} bytes")
                    
                    logging.info(f"  ┌── File #{file_counter}: {file.filename}")
                    logging.info(f"  ├── Size: {file_size:,} bytes")
                    logging.info(f"  ├── Field: {field_name}")
                    
                    # העלאה ל-GCS
                    file_info = upload_to_gcs(
                        file,
                        file.filename,
                        project_id,
                        field_name
                    )
                    
                    if file_info:
                        uploaded_files.append(file_info)
                        logging.info(f"  └── ✅ Uploaded to: {file_info['gcs_path']}")
                    
                    file_counter += 1
                else:
                    if file and file.filename:
                        logging.warning(f"  ✗ Skipping invalid file: {file.filename}")
                    else:
                        logging.warning("  ✗ Empty file field")
        
        # יצירת רשומת submission
        submission_id = f"sub_{project_id}"
        current_time = datetime.now()
        
        submission = {
            'id': submission_id,
            'project_id': project_id,
            'form_data': form_data,
            'files': uploaded_files,
            'files_count': len(uploaded_files),
            'total_size': sum(f['size'] for f in uploaded_files),
            'received_at': current_time.isoformat(),
            'formatted_time': current_time.strftime('%d/%m/%Y %H:%M:%S'),
            'processed': False,
            'form_id': form_data.get('form_id', 'unknown'),
            'entry_id': form_data.get('entry_id', submission_id),
            'gcs_bucket': GCS_BUCKET_NAME,
            'gcs_folder': f"gs://{GCS_BUCKET_NAME}/projects/{project_id}/",
            'gcs_console_url': f"https://console.cloud.google.com/storage/browser/{GCS_BUCKET_NAME}/projects/{project_id}"
        }
        
        # שמור במאגר זמני
        submissions_db.append(submission)
        
        # חישוב זמן עיבוד
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # סיכום
        logging.info("=" * 60)
        logging.info("🎯 SUBMISSION SUMMARY")
        logging.info(f"   Project ID: {project_id}")
        logging.info(f"   Files Uploaded: {len(uploaded_files)}")
        logging.info(f"   Total Size: {sum(f['size'] for f in uploaded_files):,} bytes")
        logging.info(f"   Processing Time: {processing_time:.2f} seconds")
        logging.info(f"   GCS Location: projects/{project_id}/")
        logging.info(f"   Upload Time: {submission['formatted_time']}")
        logging.info("=" * 60)
        
        # תשובה ל-Forminator
        response = {
            'success': True,
            'message': 'Files uploaded successfully to GCS',
            'submission_id': submission_id,
            'project_id': project_id,
            'files_uploaded': len(uploaded_files),
            'total_size': submission['total_size'],
            'gcs_bucket': GCS_BUCKET_NAME,
            'gcs_folder': submission['gcs_folder'],
            'upload_timestamp': submission['received_at'],
            'formatted_time': submission['formatted_time'],
            'project_id_format': 'YYYYMMDD_HHMMSS',
            'processing_time': processing_time,
            'file_list': [
                {
                    'original_name': f['original_filename'],
                    'gcs_path': f['gcs_path'],
                    'size': f['size'],
                    'url': f['url']
                } for f in uploaded_files
            ]
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        logging.error("❌" * 20)
        logging.error(f"ERROR PROCESSING WEBHOOK: {str(e)}")
        logging.error(f"Project ID: {project_id}")
        logging.error("❌" * 20)
        
        return jsonify({
            'success': False,
            'error': str(e),
            'project_id': project_id,
            'timestamp': datetime.now().isoformat()
        }), 400

@app.route('/get-unprocessed', methods=['GET'])
def get_unprocessed():
    """מחזיר רשומות שלא עובדו ל-Apps Script"""
    try:
        limit = int(request.args.get('limit', 100))
        
        unprocessed = [
            s for s in submissions_db 
            if not s['processed'] and s['id'] not in processed_ids
        ]
        
        results = unprocessed[:limit]
        
        return jsonify({
            'success': True,
            'count': len(results),
            'records': results,
            'gcs_bucket': GCS_BUCKET_NAME,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logging.error(f"Error in get-unprocessed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/mark-processed', methods=['POST'])
def mark_processed():
    """סימון רשומות כמעובדות"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        submission_ids = data.get('ids', [])
        marked_count = 0
        
        for sub_id in submission_ids:
            processed_ids.add(sub_id)
            for sub in submissions_db:
                if sub['id'] == sub_id:
                    sub['processed'] = True
            marked_count += 1
        
        logging.info(f"Marked {marked_count} submissions as processed")
        
        return jsonify({
            'success': True,
            'marked': marked_count,
            'total_processed': len(processed_ids)
        }), 200
        
    except Exception as e:
        logging.error(f"Error marking as processed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/files/<project_id>', methods=['GET'])
def list_project_files(project_id):
    """מחזיר רשימת קבצים של פרויקט ספציפי"""
    try:
        # חפש קבצים ב-GCS
        blobs = bucket.list_blobs(prefix=f"projects/{project_id}/")
        
        files = []
        for blob in blobs:
            files.append({
                'name': blob.name.split('/')[-1],
                'path': blob.name,
                'size': blob.size,
                'updated': blob.updated.isoformat(),
                'url': blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(days=1),
                    method="GET"
                )
            })
        
        # סדר לפי זמן (החדשים ראשון)
        files.sort(key=lambda x: x['updated'], reverse=True)
        
        return jsonify({
            'success': True,
            'project_id': project_id,
            'files_count': len(files),
            'total_size': sum(f['size'] for f in files),
            'files': files,
            'gcs_path': f"gs://{GCS_BUCKET_NAME}/projects/{project_id}/",
            'console_url': f"https://console.cloud.google.com/storage/browser/{GCS_BUCKET_NAME}/projects/{project_id}"
        }), 200
        
    except Exception as e:
        logging.error(f"Error listing files: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/projects', methods=['GET'])
def list_projects():
    """מחזיר רשימת כל הפרויקטים ב-GCS"""
    try:
        # חפש את כל התיקיות projects/
        blobs = bucket.list_blobs(prefix="projects/", delimiter='/')
        
        projects = []
        for prefix in blobs.prefixes:
            project_id = prefix.rstrip('/').split('/')[-1]
            
            # חשב כמה קבצים יש בפרויקט
            project_blobs = list(bucket.list_blobs(prefix=prefix))
            
            projects.append({
                'project_id': project_id,
                'files_count': len(project_blobs),
                'total_size': sum(b.size for b in project_blobs),
                'last_modified': max([b.updated for b in project_blobs]).isoformat() if project_blobs else None,
                'gcs_path': f"gs://{GCS_BUCKET_NAME}/{prefix}",
                'console_url': f"https://console.cloud.google.com/storage/browser/{GCS_BUCKET_NAME}/{prefix.rstrip('/')}"
            })
        
        # סדר לפי project_id (החדשים ראשון)
        projects.sort(key=lambda x: x['project_id'], reverse=True)
        
        return jsonify({
            'success': True,
            'projects_count': len(projects),
            'projects': projects,
            'gcs_bucket': GCS_BUCKET_NAME
        }), 200
        
    except Exception as e:
        logging.error(f"Error listing projects: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    # בדוק חיבור ל-GCS
    try:
        bucket.exists()
        gcs_status = 'connected'
    except Exception as e:
        gcs_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'healthy',
        'service': 'Forminator to GCS Uploader',
        'gcs_bucket': GCS_BUCKET_NAME,
        'gcs_status': gcs_status,
        'submissions_count': len(submissions_db),
        'processed_count': len(processed_ids),
        'project_id_format': 'YYYYMMDD_HHMMSS',
        'timestamp': datetime.now().isoformat(),
        'current_project_id_example': generate_project_id()
    }), 200

if __name__ == '__main__':
    # הגדר logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    port = int(os.environ.get('PORT', 8080))
    
    logging.info("=" * 60)
    logging.info(f"🚀 Starting Forminator to GCS Uploader")
    logging.info(f"📂 GCS Bucket: {GCS_BUCKET_NAME}")
    logging.info(f"🆔 Project ID Format: YYYYMMDD_HHMMSS")
    logging.info(f"🌐 Port: {port}")
    logging.info("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)
