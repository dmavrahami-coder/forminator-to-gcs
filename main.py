from flask import Flask, request, jsonify
import logging

app = Flask(__name__)

# הגדר logging מפורט
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.route('/', methods=['POST', 'GET', 'OPTIONS'])
def debug_webhook():
    """Endpoint פשוט רק כדי לראות מה Forminator שולח"""
    
    logger.info("=== NEW REQUEST RECEIVED ===")
    logger.info(f"Method: {request.method}")
    logger.info(f"Content-Type: {request.content_type}")
    logger.info(f"Headers: {dict(request.headers)}")
    
    # הדפס את כל הנתונים הגולמיים
    raw_data = request.get_data(as_text=True)
    logger.info(f"Raw body (length: {len(raw_data)}):")
    logger.info(raw_data[:500])  # רק 500 תווים ראשונים
    
    # נסה לקרוא כ-JSON
    json_data = request.get_json(silent=True)
    if json_data:
        logger.info("Parsed as JSON:")
        logger.info(json_data)
    
    # נסה לקרוא כ-form data
    form_data = request.form.to_dict()
    if form_data:
        logger.info("Parsed as Form Data:")
        logger.info(form_data)
    
    # בדוק קבצים
    files = request.files.to_dict()
    if files:
        logger.info(f"Files: {list(files.keys())}")
        for key, file in files.items():
            logger.info(f"  {key}: {file.filename}, {file.content_type}")
    
    # תמיד החזר 200 עם הודעה פשוטה
    return jsonify({
        'status': 'success',
        'message': 'Webhook received successfully',
        'debug_info': {
            'method': request.method,
            'content_type': request.content_type,
            'body_length': len(raw_data)
        }
    }), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
