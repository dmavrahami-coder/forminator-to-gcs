from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from google.cloud import storage
from uuid import uuid4

app = Flask(__name__)
# הוספת CORS כדי למנוע בעיות דומיין
CORS(app)

# הגדרת שם הדלי לשמירת הקבצים
GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'client_upload')

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
        'service': 'Forminator Webhook (AI QUANTIFIER)',
        'status': 'running',
        'target_bucket': GCS_BUCKET_NAME
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """בדיקת בריאות מפורטת."""
    return jsonify({'status': 'healthy'}), 200


@app.route('/webhook', methods=['POST', 'OPTIONS'])
def webhook():
    """קליטת נתוני הטופס והקבצים והעלאתם לדלי GCS."""
    if request.method == 'OPTIONS':
        return '', 200
    
    if not GCS_BUCKET:
        print("🛑 ERROR: GCS Bucket not initialized.")
        return jsonify({'success': False, 'message': 'GCS service unavailable'}), 500

    print("=" * 50)
    print("📨 Forminator webhook received")
    
    # --- לוגיקת אימות קלט קריטית ---
    print(f"Content-Type: {request.content_type}")
    print(f"Headers Sample: {dict(request.headers)}")
    # ------------------------------------------

    submission_id = str(uuid4())
    uploaded_files_urls = []
    
    print(f"Generated Submission ID: {submission_id}")

    # הדפסת נתוני הטופס (FORM DATA)
    form_data = request.form.to_dict()
    print(f"Form fields received: {list(form_data.keys())}")
    
    # 1. עיבוד והעלאת קבצים
    if request.files:
        print(f"✅ FILES FOUND! Keys: {list(request.files.keys())}")
        
        # עובר על כל הקבצים שהתקבלו
        for key, file in request.files.items():
            
            # בודקים שם קובץ וגודל
            if file and file.filename and file.content_length > 0:
                
                # הנתיב בתוך הדלי: submission_id/שם_קובץ_מקורי
                destination_blob_name = f"{submission_id}/{file.filename}" 
                
                print(f"Attempting upload of {file.filename} (Field: {key}) to gs://{GCS_BUCKET_NAME}/{destination_blob_name}")

                try:
                    blob = GCS_BUCKET.blob(destination_blob_name)
                    
                    # מעביר את הקורא לתחילת הקובץ
                    file.seek(0) 
                    blob.upload_from_file(file)
                    
                    file_url = f"gs://{GCS_BUCKET_NAME}/{destination_blob_name}"
                    uploaded_files_urls.append(file_url)
                    print(f"✅ SUCCESSFULLY UPLOADED. URL: {file_url}")
                    
                except Exception as e:
                    # מדפיס שגיאה במקרה של כישלון GCS
                    print(f"❌ CRITICAL GCS ERROR during upload of {file.filename}: {e}")
            else:
                print(f"⚠️ Warning: File key '{key}' was sent, but file was empty or had no filename.")

    else:
        print("❌ NO FILES FOUND in request.files. Forminator is likely not sending file contents as 'multipart/form-data'.")
        # בודק אם לפחות נתוני טופס רגילים הגיעו
        if len(form_data) > 0:
            print(f"ℹ️ Received {len(form_data)} form fields, but no files.")
        else:
            print("🛑 No form data received either. Request seems empty.")
    
    # 2. הוספת מטא-דאטה לתשובה (נדרש לשלב הסנכרון Apps Script)
    form_data['submission_id'] = submission_id
    form_data['uploaded_files'] = uploaded_files_urls
    
    # ... כאן נדרשת לוגיקה לשמירת ה-form_data למסד נתונים פנימי (כדי שה-Apps Script יוכל למשוך אותם) ...

    print("-" * 50)
    print(f"Final summary: {len(uploaded_files_urls)} files uploaded.")
    print("=" * 50)
    
    return jsonify({
        'success': True,
        'message': 'Files processed and uploaded to GCS (if sent).',
        'submission_id': submission_id,
        'uploaded_count': len(uploaded_files_urls)
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
