# main.py - הקוד המלא המעודכן
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import json
import os

app = Flask(__name__)
CORS(app)  # אפשר גישה מ-Forminator ו-Google Sheets

# הגדר logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# מאגר נתונים פשוט בזיכרון (בפועל תשתמש ב-Database כמו Firestore)
submissions_db = []
processed_ids = set()

@app.route('/', methods=['GET'])
def home():
    """דף הבית - בדיקת חיבור"""
    return jsonify({
        'service': 'Forminator to Google Sheets Webhook',
        'status': 'running',
        'endpoints': {
            'webhook': '/webhook (POST)',
            'sync': '/get-unprocessed (GET)',
            'health': '/health (GET)'
        },
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/webhook', methods=['POST', 'OPTIONS'])
def forminator_webhook():
    """קבלת webhook מ-Forminator"""
    
    # טיפול ב-CORS preflight
    if request.method == 'OPTIONS':
        return '', 200, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    
    logger.info("=== FORMINTOR WEBHOOK RECEIVED ===")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Content-Type: {request.content_type}")
    
    try:
        # נסה לקבל את הנתונים בכל הפורמטים האפשריים
        data = {}
        
        if request.is_json:
            data = request.get_json()
            logger.info("Parsed as JSON data")
        elif request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()
            logger.info("Parsed as Form data")
        else:
            # נסה לפרק אוטומטית
            raw_data = request.get_data(as_text=True)
            logger.info(f"Raw data (first 500 chars): {raw_data[:500]}")
            
            # נסה JSON
            try:
                data = json.loads(raw_data)
                logger.info("Parsed raw data as JSON")
            except:
                # נסה form data
                try:
                    from urllib.parse import parse_qs
                    data = {k: v[0] for k, v in parse_qs(raw_data).items()}
                    logger.info("Parsed raw data as Form URL encoded")
                except:
                    data = {'raw_data': raw_data}
        
        # הוסף metadata
        submission_id = f"sub_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        submission = {
            'id': submission_id,
            'data': data,
            'received_at': datetime.now().isoformat(),
            'processed': False,
            'form_id': data.get('form_id', data.get('form-id', 'unknown')),
            'entry_id': data.get('entry_id', data.get('entry-id', submission_id)),
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'unknown')
        }
        
        # עיבוד קבצים אם יש
        if request.files:
            files_info = []
            for key, file in request.files.items():
                file_info = {
                    'field_name': key,
                    'filename': file.filename,
                    'content_type': file.content_type,
                    'size': len(file.read())
                }
                files_info.append(file_info)
                # החזר את הקובץ להתחלה
                file.seek(0)
            
            submission['files'] = files_info
            logger.info(f"Received {len(files_info)} files")
        
        # שמור במאגר
        submissions_db.append(submission)
        
        logger.info(f"✅ Submission saved: {submission_id}")
        logger.info(f"Data keys: {list(data.keys())}")
        
        # תשובה ל-Forminator
        response = {
            'success': True,
            'message': 'Webhook received successfully',
            'submission_id': submission_id,
            'timestamp': submission['received_at'],
            'queue_size': len([s for s in submissions_db if not s['processed']])
        }
        
        return jsonify(response), 200, {
            'Access-Control-Allow-Origin': '*'
        }
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 400, {
            'Access-Control-Allow-Origin': '*'
        }

@app.route('/get-unprocessed', methods=['GET'])
def get_unprocessed():
    """Endpoint לסנכרון עם Google Apps Script"""
    
    try:
        # קבלת פרמטרים
        limit = int(request.args.get('limit', 50))
        form_id = request.args.get('form_id')
        since = request.args.get('since')
        
        logger.info(f"📥 Sync request - Limit: {limit}, Form: {form_id}")
        
        # סינון רשומות שלא עובדו
        unprocessed = [
            s for s in submissions_db 
            if not s['processed'] and s['id'] not in processed_ids
        ]
        
        # סינון נוסף לפי form_id אם צוין
        if form_id:
            unprocessed = [s for s in unprocessed if s['form_id'] == form_id]
        
        # סינון לפי תאריך אם צוין
        if since:
            unprocessed = [
                s for s in unprocessed 
                if s['received_at'] > since
            ]
        
        # הגבלת מספר הרשומות
        results = unprocessed[:limit]
        
        logger.info(f"📤 Returning {len(results)} unprocessed submissions")
        
        # הכן את הנתונים לתגובה
        formatted_results = []
        for sub in results:
            formatted = {
                'id': sub['id'],
                'form_id': sub['form_id'],
                'entry_id': sub['entry_id'],
                'received_at': sub['received_at'],
                'data': sub['data'],
                'has_files': 'files' in sub and len(sub['files']) > 0
            }
            
            # הוסף קבצים אם יש
            if 'files' in sub:
                formatted['files'] = sub['files']
            
            formatted_results.append(formatted)
        
        # סימון כבעיבוד (אבל לא מוחקים)
        # בפועל היית משנה את הסטטוס ב-Database
        
        return jsonify({
            'success': True,
            'count': len(formatted_results),
            'records': formatted_results,
            'total_unprocessed': len(unprocessed),
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error in get-unprocessed: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/mark-processed', methods=['POST'])
def mark_processed():
    """סמן רשומות שטופלו"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        submission_ids = data.get('ids', [])
        mark_all = data.get('mark_all', False)
        
        marked_count = 0
        
        if mark_all:
            # סמן הכל כ-processed
            for sub in submissions_db:
                if not sub['processed']:
                    sub['processed'] = True
                    processed_ids.add(sub['id'])
                    marked_count += 1
        else:
            # סמן רק את ה-IDs הספציפיים
            for sub_id in submission_ids:
                processed_ids.add(sub_id)
                # עדכן גם במאגר הראשי
                for sub in submissions_db:
                    if sub['id'] == sub_id:
                        sub['processed'] = True
                marked_count += 1
        
        logger.info(f"✅ Marked {marked_count} submissions as processed")
        
        return jsonify({
            'success': True,
            'marked': marked_count,
            'total_processed': len(processed_ids)
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error marking as processed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/stats', methods=['GET'])
def get_stats():
    """סטטיסטיקות על הנתונים"""
    total = len(submissions_db)
    processed = len(processed_ids)
    unprocessed = total - processed
    
    # חישוב לפי form_id
    form_stats = {}
    for sub in submissions_db:
        form_id = sub['form_id']
        if form_id not in form_stats:
            form_stats[form_id] = {'total': 0, 'processed': 0}
        
        form_stats[form_id]['total'] += 1
        if sub['processed']:
            form_stats[form_id]['processed'] += 1
    
    return jsonify({
        'total_submissions': total,
        'processed': processed,
        'unprocessed': unprocessed,
        'forms': form_stats,
        'oldest': submissions_db[0]['received_at'] if submissions_db else None,
        'newest': submissions_db[-1]['received_at'] if submissions_db else None
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Forminator Webhook Processor',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat(),
        'queue_size': len([s for s in submissions_db if not s['processed']]),
        'total_submissions': len(submissions_db),
        'processed_count': len(processed_ids)
    }), 200

@app.route('/debug/reset', methods=['POST'])
def debug_reset():
    """Endpoint לדיבוג - איפוס הנתונים (רק בסביבת פיתוח!)"""
    if os.environ.get('FLASK_ENV') != 'development':
        return jsonify({'error': 'Not allowed in production'}), 403
    
    global submissions_db, processed_ids
    old_count = len(submissions_db)
    
    submissions_db = []
    processed_ids = set()
    
    logger.warning(f"⚠️ Debug reset - cleared {old_count} submissions")
    
    return jsonify({
        'success': True,
        'cleared': old_count,
        'message': 'Database reset (development only)'
    }), 200

if __name__ == '__main__':
    # הפעל את השרת
    port = int(os.environ.get('PORT', 8080))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"🚀 Starting Forminator Webhook Service on port {port}")
    logger.info(f"Debug mode: {debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
