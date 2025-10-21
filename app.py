# emailfake-monitor/app.py
from flask import Flask, jsonify
import socketio
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import os
import time
import logging

app = Flask(__name__)
sio = socketio.Client()

# Email ayarları - RENDER'da environment variables olacak
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
EMAIL_USER = os.getenv('EMAIL_USER', 'your_email@gmail.com')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'your_app_password')
TO_EMAIL = os.getenv('TO_EMAIL', 'notification@yourdomain.com')

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_email_notification(mail_data):
    """Render'dan direkt email gönder"""
    try:
        subject = f"📧 Yeni Mail: {mail_data.get('subject', 'Konu Yok')}"
        
        body = f"""
🎉 YENİ MAIL ALGILANDI!

📨 Takip Edilen Email: fedotiko@newdailys.com
👤 Gönderen: {mail_data.get('from', 'Bilinmiyor')}
📌 Konu: {mail_data.get('subject', 'Konu Yok')}
📅 Tarih: {mail_data.get('date', 'Tarih Yok')}

⏰ Algılama Zamanı: {time.strftime('%Y-%m-%d %H:%M:%S')}
🔍 Kaynak: EmailFake + Render API

---
🤖 Otomatik Bildirim Sistemi
        """.strip()

        # Email oluştur
        msg = MimeMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = TO_EMAIL
        msg['Subject'] = subject
        msg.attach(MimeText(body, 'plain'))
        
        # SMTP ile gönder
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"✅ Email gönderildi: {subject}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Email gönderme hatası: {e}")
        return False

@sio.event
def connect():
    logger.info("✅ Emailfake WebSocket'e bağlandı!")
    sio.emit("watch_for_my_email", "fedotiko@newdailys.com")

@sio.event
def disconnect():
    logger.warning("❌ Bağlantı kesildi, 10 saniye sonra yeniden bağlanıyor...")
    time.sleep(10)
    try:
        sio.connect("wss://tr.emailfake.com")
    except:
        pass

@sio.event
def new_email(data):
    logger.info(f"🎉 YENİ MAIL ALGILANDI: {data}")
    success = send_email_notification(data)
    if success:
        logger.info("✅ Bildirim başarıyla gönderildi")
    else:
        logger.error("❌ Bildirim gönderilemedi")

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "service": "EmailFake Monitor + Notification",
        "monitored_email": "fedotiko@newdailys.com",
        "websocket_connected": sio.connected,
        "notification_email": TO_EMAIL
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy", 
        "websocket_connected": sio.connected,
        "timestamp": time.time()
    })

@app.route('/test-email')
def test_email():
    """Test emaili gönder"""
    test_data = {
        "from": "test@sender.com",
        "subject": "Test Mail - Render API",
        "date": time.strftime('%Y-%m-%d %H:%M:%S')
    }
    success = send_email_notification(test_data)
    return jsonify({
        "status": "success" if success else "error",
        "message": "Test emaili gönderildi" if success else "Email gönderilemedi"
    })

def start_websocket():
    """WebSocket bağlantısını başlat"""
    max_retries = 5
    retry_delay = 10
    
    for attempt in range(max_retries):
        try:
            sio.connect("wss://tr.emailfake.com")
            logger.info("🚀 WebSocket bağlantısı başlatıldı!")
            break
        except Exception as e:
            logger.error(f"❌ Bağlantı hatası (deneme {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2

if __name__ == '__main__':
    start_websocket()
    app.run(host='0.0.0.0', port=10000, debug=False)
