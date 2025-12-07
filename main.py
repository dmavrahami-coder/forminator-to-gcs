from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from google.cloud import storage
from uuid import uuid4

# ... (שאר ייבוא והגדרות קודמות) ...

# הגדרת שם הדלי לשמירת הקבצים
GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'client_upload')

# אתחול לקוח GCS גלובלי
try:
    storage_client = storage.Client()
    GCS_BUCKET = storage_client.bucket(GCS_BUCKET_NAME)
    # ... (הדפסת הצלחה) ...
except Exception as e:
    # ... (טיפול בשגיאה) ...


@app.route('/webhook', methods=['POST', 'OPTIONS'])
def webhook():
    if request.method == 'OPTIONS':
        return '', 200
    
    if not GCS_BUCKET:
        print("🛑 ERROR: GCS Bucket not initialized.")
        return jsonify({'success': False, 'message': 'GCS service unavailable'}), 500

    print("=" * 50)
    print("📨 Forminator webhook received")
    
    submission_id = str(uuid4())
    uploaded_files_urls = []
    
    print(f"Generated Submission ID: {submission_id}")

    # הדפסת נתוני הטופס (לצורך אימות שדות)
    print(f"Form fields received: {list(request.form.keys())}")
    for key, value in request.form.items():
         print(f"  FORM DATA - {key}: {value[:50]}{'...' if len(value) > 50 else ''}")

    # 1. עיבוד והעלאת קבצים
    if request.files:
        print(f"✅ FILES FOUND! Keys: {list(request.files.keys())}")
        
        # אנחנו מצפים לשמות שדות כמו upload-1, upload-2, וכו'
        for key, file in request.files.items():
            if file and file.filename:
                # לוודא ששם הקובץ אינו ריק (שדות קובץ ריקים נשלחים גם כן)
                
                # הנתיב בתוך הדלי: submission_id/שם_קובץ_מקורי
                destination_blob_name = f"{submission_id}/{file.filename}" 
                
                print(f"Attempting upload of {file.filename} (Field: {key}) to gs://{GCS_BUCKET_NAME}/{destination_blob_name}")

                try:
                    blob = GCS_BUCKET.blob(destination_blob_name)
                    
                    # מעביר את הקורא לתחילת הקובץ למקרה ש-Flask קרא אותו
                    file.seek(0) 
                    blob.upload_from_file(file)
                    
                    file_url = f"gs://{GCS_BUCKET_NAME}/{destination_blob_name}"
                    uploaded_files_urls.append(file_url)
                    print(f"✅ SUCCESSFULLY UPLOADED. URL: {file_url}")
                    
                except Exception as e:
                    # אם יש שגיאת GCS, נדפיס אותה עכשיו
                    print(f"❌ CRITICAL GCS ERROR during upload of {file.filename}: {e}")
            else:
                print(f"⚠️ Warning: File key '{key}' was found but filename was empty.")

    else:
        print("❌ NO FILES FOUND in request.files. Forminator is not sending file contents.")
    
    # ... (המשך קוד: שמירת מטא-דאטה והחזרת תשובה) ...
    
    # 2. עיבוד נתוני הטופס
    form_data = request.form.to_dict()
    form_data['submission_id'] = submission_id
    form_data['uploaded_files'] = uploaded_files_urls
    
    # ... (המשך שמירה לתור/DB) ...
    
    print("=" * 50)
    
    return jsonify({
        'success': True,
        'message': 'Files processed.',
        'submission_id': submission_id,
        'uploaded_count': len(uploaded_files_urls)
    }), 200

# ... (שאר הקוד) ...
