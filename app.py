from flask import Flask, jsonify, request
import requests
import time

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "active", 
        "service": "EmailFake API - PythonAnywhere",
        "usage": "POST /get-emails with {'email': 'address@domain.com'}"
    })

@app.route('/get-emails', methods=['POST'])
def get_emails():
    try:
        data = request.get_json()
        email = data.get('email', '')
        
        if not email:
            return jsonify({"error": "Email required"}), 400
        
        username, domain = email.split('@')
        url = f"https://tr.emailfake.com/mail{domain}/{username}"
        
        response = requests.get(url, timeout=10, verify=False)
        
        return jsonify({
            "status": "success",
            "email": email,
            "url": url,
            "status_code": response.status_code,
            "content_length": len(response.text)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/test')
def test():
    return jsonify({"status": "working", "timestamp": time.time()})

if __name__ == '__main__':
    app.run(debug=True)
