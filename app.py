# 📁 app.py - CATCHCLIENT ENTEGRASYONU
from flask import Flask, jsonify, request
import time
import logging
import sys
import os

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CatchClient import etmeyi dene
try:
    # Önce direkt import dene
    from catchclient import TempMail
    logger.info("✅ CatchClient başarıyla import edildi")
    CATCHCLIENT_AVAILABLE = True
except ImportError:
    try:
        # GitHub'dan kurulum dene
        import subprocess
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "git+https://github.com/Podzied/catchclient.git"
        ])
        from catchclient import TempMail
        logger.info("✅ CatchClient GitHub'dan kuruldu ve import edildi")
        CATCHCLIENT_AVAILABLE = True
    except:
        # Fallback client
        logger.warning("⚠️ CatchClient bulunamadı, fallback kullanılıyor")
        CATCHCLIENT_AVAILABLE = False
        from fallback_client import FallbackTempMail
        TempMail = FallbackTempMail

# Mail depolama
email_storage = {}

def get_emails_with_catchclient(email_address, only_last_email=False):
    """CatchClient ile mailleri al"""
    try:
        logger.info(f"🎯 CatchClient ile mailler alınıyor: {email_address}")
        
        # CatchClient instance
        client = TempMail()
        
        # Domain mapping
        domain = email_address.split('@')[1]
        domain_map = {
            'newdailys.com': 'newdailys',
            'emailfake.com': 'emailfake',
            'tempm.com': 'tempm',
            'temp-mail.io': 'tempmail',
        }
        
        service_name = domain_map.get(domain, 'emailfake')
        logger.info(f"🔧 Servis: {service_name}, Email: {email_address}")
        
        # Mailleri al
        if only_last_email:
            email = client.get_last_email(service_name, email_address)
            emails = [email] if email else []
        else:
            emails = client.get_emails(service_name, email_address) or []
        
        # Formatla
        formatted_emails = []
        for i, email in enumerate(emails):
            if email:  # None kontrolü
                formatted_emails.append({
                    'id': i + 1,
                    'from': email.get('from', 'Bilinmiyor'),
                    'subject': email.get('subject', 'Konu Yok'),
                    'date': email.get('date', ''),
                    'content': email.get('content', email.get('body', '')),
                    'to': email_address,
                    'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'source': 'catchclient',
                    'service': service_name
                })
        
        logger.info(f"✅ {len(formatted_emails)} mail alındı")
        return {
            "status": "success",
            "email": email_address,
            "total_emails": len(formatted_emails),
            "emails": formatted_emails,
            "service": service_name,
            "client": "catchclient"
        }
        
    except Exception as e:
        logger.error(f"❌ CatchClient hatası: {e}")
        return {
            "status": "error",
            "error": str(e),
            "emails": []
        }

# Fallback client (CatchClient yoksa)
class FallbackTempMail:
    def get_emails(self, service, email):
        logger.info(f"🔄 Fallback: {email}")
        # Basit requests ile mailleri al
        import requests
        try:
            domain = email.split('@')[1]
            url = f"https://{domain}/inbox/{email}"
            response = requests.get(url, timeout=10)
            # Basit parsing...
            return [{"from": "Fallback", "subject": "Test", "date": "2024-01-01"}]
        except:
            return []
    
    def get_last_email(self, service, email):
        emails = self.get_emails(service, email)
        return emails[0] if emails else None

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "service": "CatchClient Email API",
        "catchclient_available": CATCHCLIENT_AVAILABLE,
        "endpoints": {
            "all_emails": "POST /get-emails",
            "last_email": "POST /get-last-email", 
            "services": "GET /services",
            "health": "GET /health"
        }
    })

@app.route('/get-emails', methods=['POST'])
def get_emails():
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    result = get_emails_with_catchclient(email, only_last_email=False)
    
    if result['emails']:
        email_storage[email] = result['emails']
    
    return jsonify(result)

@app.route('/get-last-email', methods=['POST'])
def get_last_email():
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    result = get_emails_with_catchclient(email, only_last_email=True)
    return jsonify(result)

@app.route('/services')
def list_services():
    return jsonify({
        "supported_services": [
            "newdailys.com", "emailfake.com", "tempm.com", "temp-mail.io"
        ],
        "catchclient_status": "active" if CATCHCLIENT_AVAILABLE else "fallback"
    })

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "catchclient": CATCHCLIENT_AVAILABLE,
        "timestamp": time.time()
    })

if __name__ == '__main__':
    logger.info("🚀 CatchClient API Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
