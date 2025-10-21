# 📁 app.py - TEMİZLENMİŞ EMAIL DATA
from flask import Flask, jsonify, request
import requests
import time
import logging
import re
from bs4 import BeautifulSoup

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mail depolama
email_storage = {}

def clean_email_data(emails):
    """Email datalarını temizle ve normalize et"""
    cleaned_emails = []
    seen_subjects = set()
    
    for email in emails:
        # Boş veya anlamsız dataları filtrele
        from_text = email.get('from', '').strip()
        subject_text = email.get('subject', '').strip()
        date_text = email.get('date', '').strip()
        
        # Filtreleme kuralları
        if not from_text and not subject_text:
            continue  # Tamamen boş
            
        if len(subject_text) < 5 and len(from_text) < 5:
            continue  # Çok kısa
            
        if any(keyword in subject_text.lower() for keyword in ['incele', 'görüntüle', 'numara', 'tl', 'teslimat']):
            continue  # Spam/HTML fragment'leri
            
        if subject_text in seen_subjects:
            continue  # Duplicate subject
            
        # Email formatını kontrol et
        if '@' not in from_text and not any(domain in from_text.lower() for domain in ['.com', '.net', '.org']):
            # From kısmı email adresi değilse, muhtemelen spam
            if len(from_text) > 50:
                continue
        
        # Temizlenmiş email
        cleaned_email = {
            'from': from_text[:100],  # Max 100 karakter
            'subject': subject_text[:150],  # Max 150 karakter  
            'date': date_text[:50] if date_text else time.strftime('%Y-%m-%d %H:%M:%S'),
            'to': email.get('to', ''),
            'received_at': email.get('received_at', ''),
            'source': 'cleaned'
        }
        
        cleaned_emails.append(cleaned_email)
        seen_subjects.add(subject_text)
    
    return cleaned_emails

def get_emails_clean(email_address):
    """Temizlenmiş email datalarını getir"""
    try:
        username, domain = email_address.split('@')
        
        # Doğru URL
        base_url = "https://tr.emailfake.com"
        inbox_url = f"{base_url}/mail{domain}/{username}"
        
        logger.info(f"🌐 Sayfa açılıyor: {inbox_url}")
        
        # Session
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = session.get(inbox_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return {
                "status": "error",
                "error": f"HTTP {response.status_code}",
                "emails": []
            }
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ham email'leri topla
        raw_emails = []
        
        # Tablo parsing
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')[1:]  # Header'ı atla
            for row in rows:
                cells = row.find_all(['td', 'div'])
                if len(cells) >= 2:
                    raw_emails.append({
                        'from': cells[0].get_text(strip=True),
                        'subject': cells[1].get_text(strip=True),
                        'date': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                        'to': email_address,
                        'received_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'source': 'table'
                    })
        
        # Temizle
        cleaned_emails = clean_email_data(raw_emails)
        
        logger.info(f"✅ {len(raw_emails)} ham -> {len(cleaned_emails)} temiz mail")
        
        return {
            "status": "success",
            "email": email_address,
            "total_raw_emails": len(raw_emails),
            "total_cleaned_emails": len(cleaned_emails),
            "emails": cleaned_emails,
            "url_used": inbox_url
        }
        
    except Exception as e:
        logger.error(f"❌ Hata: {e}")
        return {
            "status": "error",
            "error": str(e),
            "emails": []
        }

@app.route('/')
def home():
    return jsonify({
        "status": "active",
        "service": "Clean EmailFake Scraper",
        "usage": "POST /get-emails with {'email': 'address@domain.com'}"
    })

@app.route('/get-emails', methods=['POST'])
def get_emails():
    """Temizlenmiş mailleri getir"""
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({"error": "Email adresi gerekli"}), 400
    
    logger.info(f"📨 İstek: {email}")
    
    result = get_emails_clean(email)
    
    if result['emails']:
        email_storage[email] = result['emails']
    
    return jsonify(result)

@app.route('/emails/<email_address>')
def list_emails(email_address):
    """Depolanan mailleri göster"""
    if email_address in email_storage:
        return jsonify({
            "email": email_address,
            "total_emails": len(email_storage[email_address]),
            "emails": email_storage[email_address]
        })
    else:
        return jsonify({
            "email": email_address,
            "total_emails": 0,
            "emails": []
        })

@app.route('/debug-raw', methods=['POST'])
def debug_raw():
    """Ham datayı göster (debug için)"""
    data = request.get_json()
    email = data.get('email', '')
    
    try:
        username, domain = email.split('@')
        url = f"https://tr.emailfake.com/{domain}/{username}"
        
        session = requests.Session()
        response = session.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Tüm tabloları bul
        tables = []
        for i, table in enumerate(soup.find_all('table')):
            table_data = []
            rows = table.find_all('tr')
            for row in rows:
                cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'div'])]
                table_data.append(cells)
            tables.append({
                'table_index': i,
                'row_count': len(rows),
                'data': table_data
            })
        
        return jsonify({
            "email": email,
            "url": url,
            "tables_found": len(tables),
            "tables": tables[:3]  # İlk 3 tablo
        })
        
    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == '__main__':
    logger.info("🚀 Temiz Email Scraper Başlatılıyor...")
    app.run(host='0.0.0.0', port=10000, debug=False)
