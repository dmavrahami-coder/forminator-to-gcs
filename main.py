from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from google.cloud import storage
from uuid import uuid4

app = Flask(__name__)
CORS(app)

# הגדרת שם הדלי לשמירת הקבצים
# ניתן לקרוא ממשתנה סביבה או להגדיר ישירות
GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'client_upload')

# אתחול לקוח GCS גלובלי (עדיף לאתחל מחוץ לפונקציה הראשית ב-Cloud Run)
try:
    storage_client = storage.Client()
    GCS_BUCKET = storage_client.bucket(GCS_BUCKET_NAME)
    print(f"🚀 Google Cloud Storage Client initialized for bucket: {GCS_BUCKET_NAME}")
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
    
    # יצירת מזהה הזמנה ייחודי עבור הפנייה (חיוני לשמירת נתונים מופרדת)
    submission_id = str(uuid4())
    uploaded_files_urls = []
    
    print(f"Generated Submission ID: {submission_id}")

    # 1. עיבוד והעלאת קבצים
    if request.files:
        print(f"Files received: {list(request.files.keys())}")
        for key, file in request.files.items():
            if file and file.filename:
                # הנתיב בתוך הדלי: submission_id/שם_קובץ_מקורי
                # לדוגמה: 1a2b3c4d-5e6f/.../plan.pdf
                destination_blob_name = f"{submission_id}/{file.filename}" 
                
                print(f"Attempting upload of {file.filename} to gs://{GCS_BUCKET_NAME}/{destination_blob_name}")

                try:
                    blob = GCS_BUCKET.blob(destination_blob_name)
                    
                    # העלאה מהזיכרון. rewind=True חשוב
                    file.seek(0) # ודא שקורא הקובץ ממוקם בתחילתו
                    blob.upload_from_file(file)
                    
                    # בניית ה-URL הציבורי (או gs:// נגיש)
                    file_url = f"gs://{GCS_BUCKET_NAME}/{destination_blob_name}"
                    uploaded_files_urls.append(file_url)
                    print(f"✅ Successfully uploaded. URL: {file_url}")
                    
                except Exception as e:
                    print(f"❌ Error uploading file {file.filename}: {e}")
                    # ניתן להחליט אם להפיל את כל הטרנזקציה או להמשיך
                    pass 
    
    # 2. עיבוד נתוני הטופס
    form_data = request.form.to_dict()
    form_data['submission_id'] = submission_id
    form_data['uploaded_files'] = uploaded_files_urls # הוספת ה-URLs לנתוני הטופס
    
    # הדפסת נתונים קריטיים (לצורך ניפוי באגים/לוגים)
    print("-" * 50)
    print(f"Form Data Summary:")
    print(f"Email: {form_data.get('email', 'N/A')}")
    print(f"Files Uploaded: {len(uploaded_files_urls)}")
    
    # 3. כאן נדרשת לוגיקה נוספת:
    #    - שליחת נתוני ה-form_data (כולל ה-URLs) למנגנון עיבוד נוסף
    #       (למשל, Pub/Sub, או כתיבה ל-Google Sheets/Database)
    #       **שלב זה קריטי להפעלת שירות `tilingquantitiescalculator`**
    
    print("=" * 50)
    
    return jsonify({
        'success': True,
        'message': 'Files uploaded to GCS. Ready for processing.',
        'submission_id': submission_id,
        'uploaded_urls': uploaded_files_urls
    }), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 Starting server on port {port}")
    # שימוש בפורט 8080 המוגדר בדרך כלל עבור Cloud Run
    app.run(host='0.0.0.0', port=port, debug=False)
