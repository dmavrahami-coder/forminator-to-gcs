from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from google.cloud import storage
from uuid import uuid4

app = Flask(__name__)
CORS(app)

# הגדרת שם הדלי לשמירת הקבצים
GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'client_upload')

# שדות קבצים שאנו מצפים לראות בנתוני הטופס (FORM DATA)
# שמות השדות נלקחים מהדוגמאות ששלחת בעבר: upload-1, upload-2 וכו'.
FILE_FIELD_KEYS = [
    'upload-1', 'upload-2', 'upload-3', 'upload-4', 
    'upload-5', 'upload-6', 'upload-7'
]

# אתחול לקוח GCS גלובלי
try:
    storage_client = storage.Client()
    GCS_BUCKET = storage_client.bucket(GCS_BUCKET_NAME)
    print(f"🚀 GCS Client initialized for bucket: {GCS_BUCKET_NAME}")
except Exception as e:
    print(f"⚠️ Warning: Could not initialize GCS client: {e}")
    GCS_BUCKET = None


@app.route('/', methods=['GET'])
def home():
    """בדיקת בריאות בסיסית של השירות."""
    return jsonify({
        'service': 'Forminator Webhook (AI QUANTIFIER) - PULL MODE',
        'status': 'running',
        'target_bucket': GCS_BUCKET_NAME
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """בדיקת בריאות מפורטת."""
    return jsonify({'status': 'healthy'}), 200


@app.route('/webhook', methods=['POST', 'OPTIONS'])
def webhook():
    """קליטת נתוני הטופס, משיכת קבצים מ-WP והעלאתם לדלי GCS."""
    if request.method == 'OPTIONS':
        return '', 200
    
    if not GCS_BUCKET:
        print("🛑 ERROR: GCS Bucket not initialized.")
        return jsonify({'success': False, 'message': 'GCS service unavailable'}), 500

    print("=" * 50)
    print("📨 Forminator webhook received - Starting PULL mode")
    print(f"Content-Type: {request.content_type}")
    
    submission_id = str(uuid4())
    uploaded_files_urls = []
    
    print(f"Generated Submission ID: {submission_id}")

    # הדפסת נתוני הטופס (FORM DATA) וחיפוש URLים
    form_data = request.form.to_dict()
    print(f"Form fields received: {list(form_data.keys())}")
    
    # 1. משיכת קבצים מ-WordPress והעלאה ל-GCS
    
    # עובר על שדות הקבצים המצופים
    for field_key in FILE_FIELD_KEYS:
        # Forminator יכול לשלוח מספר URLים מופרדים בפסיקים אם מדובר בשדה מרובה קבצים
        url_string = form_data.get(field_key)
        
        if url_string:
            # מנקה ומפצל URLים
            urls = [url.strip() for url in url_string.split(',') if url.strip()]
            
            for wp_url in urls:
                
                # מפיק את שם הקובץ מה-URL
                filename = os.path.basename(wp_url)
                
                if not filename:
                    print(f"⚠️ Warning: Could not extract filename from URL: {wp_url}")
                    continue
                
                destination_blob_name = f"{submission_id}/{filename}"
                print(f"Attempting to pull {filename} from WP URL and upload to GCS.")

                try:
                    # משיכת הקובץ משרת ה-WordPress
                    pull_response = requests.get(wp_url, stream=True, timeout=30)
                    pull_response.raise_for_status() # מעורר שגיאה אם ה-HTTP נכשל
                    
                    # העלאה ל-GCS
                    blob = GCS_BUCKET.blob(destination_blob_name)
                    blob.upload_from_file(pull_response.raw)
                    
                    file_url = f"gs://{GCS_BUCKET_NAME}/{destination_blob_name}"
                    uploaded_files_urls.append(file_url)
                    print(f"✅ SUCCESSFULLY UPLOADED. URL: {file_url}")
                    
                except requests.exceptions.HTTPError as e:
                    print(f"❌ HTTP Error pulling file {filename} from WP: {e}")
                except Exception as e:
                    print(f"❌ CRITICAL ERROR during pull/upload of {filename}: {e}")
    
    
    # 2. הוספת מטא-דאטה לתשובה (לסנכרון Apps Script)
    form_data['submission_id'] = submission_id
    form_data['uploaded_files'] = uploaded_files_urls
    
    # ... כאן נדרשת לוגיקה לשמירת ה-form_data למסד נתונים פנימי (כדי שה-Apps Script יוכל למשוך אותם) ...

    print("-" * 50)
    print(f"Final summary: {len(uploaded_files_urls)} files uploaded.")
    print("=" * 50)
    
    return jsonify({
        'success': True,
        'message': 'Files processed and uploaded to GCS.',
        'submission_id': submission_id,
        'uploaded_count': len(uploaded_files_urls)
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
