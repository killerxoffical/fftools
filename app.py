import os
import sys
import json
import time
import urllib.parse
import base64
import hashlib
import re
import imaplib
import email
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Safe Crypto Import
HAS_CRYPTO = False
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    HAS_CRYPTO = True
    AeSkEy = b'Yg&tc%DEuh6%Zc^8'
    AeSiV  = b'6oyZDr22E3ychjM%'
except Exception as e:
    print(f"Crypto Notice: {e}")

# Safe Protobuf Import
HAS_PROTOBUF = False
try:
    import MajoRLogin_pb2 as mLpB
    import MajorLoginRes_pb2 as mLrPb
    HAS_PROTOBUF = True
except Exception as e:
    print(f"Protobuf Notice: {e}")

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json"
}

PLATFORM_MAP = {
    1: "Garena", 3: "Facebook", 4: "Guest", 5: "VK", 
    6: "Huawei", 7: "Apple", 8: "Google", 10: "GameCenter / Line", 
    11: "X (Twitter)", 13: "Apple ID", 28: "Line", 35: "TikTok"
}

def convert_seconds(s):
    try:
        d, h = divmod(s, 86400)
        h, m = divmod(h, 3600)
        m, s = divmod(m, 60)
        return f"{d} Day {h} Hour {m} Min {s} Sec"
    except:
        return ""

def extract_otp_from_mailbox(user_email, app_password, max_wait_sec=35):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(user_email, app_password)
        mail.select("inbox")

        start_time = time.time()
        while time.time() - start_time < max_wait_sec:
            status, messages = mail.search(None, '(UNSEEN)')
            if status == "OK" and messages[0]:
                msg_ids = messages[0].split()
                latest_id = msg_ids[-1]
                res, msg_data = mail.fetch(latest_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = msg.get("Subject", "")
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body += part.get_payload(decode=True).decode(errors='ignore')
                        else:
                            body = msg.get_payload(decode=True).decode(errors='ignore')

                        full_text = f"{subject} {body}"
                        otp_match = re.search(r'\b\d{6}\b', full_text)
                        if otp_match:
                            otp_code = otp_match.group(0)
                            try: mail.close(); mail.logout()
                            except: pass
                            return otp_code
            time.sleep(2.0)

        try: mail.close(); mail.logout()
        except: pass
    except Exception as e:
        print(f"IMAP Error: {e}")
    return None


@app.route('/')
def home():
    return jsonify({
        "status": "Online",
        "service": "Booyah Day Official Direct Garena API",
        "crypto_enabled": HAS_CRYPTO,
        "protobuf_enabled": HAS_PROTOBUF
    })


# 🚀 DIRECT OFFICIAL GARENA EAT TO ACCESS TOKEN CONVERTER
@app.route('/api/eat-to-token', methods=['POST'])
def eat_to_token():
    data = request.get_json(silent=True) or {}
    raw_input = data.get('eat', '').strip() or data.get('access_token', '').strip() or data.get('url', '').strip()

    if not raw_input:
        return jsonify({"success": False, "message": "EAT token or URL is required"}), 400

    # 1. Parse URL if full redirected URL is pasted
    eat_token = None
    if "http" in raw_input or "?" in raw_input:
        parsed_url = urllib.parse.urlparse(raw_input)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        if 'eat' in query_params:
            eat_token = query_params['eat'][0]
        elif 'access_token' in query_params:
            return jsonify({
                "success": True,
                "access_token": query_params['access_token'][0],
                "method": "direct_url_param"
            })
    else:
        eat_token = raw_input.strip()

    if not eat_token:
        return jsonify({"success": False, "message": "Could not extract EAT token from input"}), 400

    # 2. Official Garena Callback Redirect Resolution
    try:
        api_url = f"https://api-otrss.garena.com/support/callback/?access_token={eat_token}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36"
        }
        
        response = requests.get(api_url, headers=headers, allow_redirects=True, timeout=15, verify=False)
        parsed_final = urllib.parse.urlparse(response.url)
        final_params = urllib.parse.parse_qs(parsed_final.query)

        if 'access_token' in final_params:
            access_token = final_params['access_token'][0]
            account_id = final_params.get('account_id', ['Unknown'])[0]
            nickname = urllib.parse.unquote(final_params.get('nickname', ['Unknown'])[0])
            region = final_params.get('region', ['Unknown'])[0]

            return jsonify({
                "success": True,
                "access_token": access_token,
                "uid": account_id,
                "nickname": nickname,
                "region": region,
                "method": "garena_official_redirect"
            })
        else:
            return jsonify({"success": False, "message": "Access token not found in response. Token might be expired or invalid."}), 401

    except Exception as e:
        return jsonify({"success": False, "message": f"Failed to generate access token: {str(e)}"}), 500


@app.route('/api/check-bind', methods=['POST'])
def check_bind():
    data = request.get_json(silent=True) or {}
    access_token = data.get('access_token', '').strip()
    if not access_token:
        return jsonify({"success": False, "message": "Access token or URL is required"}), 400

    # Auto convert if EAT URL is sent directly
    if 'http' in access_token or 'eat=' in access_token or len(access_token) != 32:
        try:
            conv_res = eat_to_token()
            conv_json = conv_res.get_json()
            if conv_json and conv_json.get('success'):
                access_token = conv_json.get('access_token')
        except Exception as e:
            print(f"Auto EAT Conversion error: {e}")

    try:
        player_url = f"https://api-otrss.garena.com/support/callback/?access_token={access_token}"
        p_res = requests.get(player_url, headers=HEADERS, timeout=15, allow_redirects=True, verify=False)
        parsed = urllib.parse.urlparse(p_res.url)
        params = urllib.parse.parse_qs(parsed.query)

        uid = params.get("account_id", ["Unknown"])[0]
        nickname = urllib.parse.unquote(params.get("nickname", ["Unknown"])[0])
        region = params.get("region", ["Unknown"])[0]

        if uid == "Unknown":
            return jsonify({"success": False, "message": "Invalid or expired access token"}), 401

        info_url = "https://100067.connect.garena.com/game/account_security/bind:get_bind_info"
        info_res = requests.get(info_url, params={'app_id': "100067", 'access_token': access_token}, headers=HEADERS, timeout=15, verify=False)
        info_data = info_res.json() if info_res.status_code == 200 else {}

        current_email = info_data.get("email", "")
        email_to_be = info_data.get("email_to_be", "")
        countdown = info_data.get("request_exec_countdown", 0)

        return jsonify({
            "success": True,
            "uid": uid,
            "nickname": nickname,
            "region": region,
            "access_token": access_token,
            "current_email": current_email if current_email else "None",
            "email_to_be": email_to_be if email_to_be else "None",
            "countdown_seconds": countdown,
            "countdown_human": convert_seconds(countdown) if countdown > 0 else ""
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/auto-bind-imap', methods=['POST'])
def auto_bind_imap():
    data = request.get_json(silent=True) or {}
    access_token = data.get('access_token', '').strip()
    email_addr = data.get('email', '').strip()
    app_password = data.get('app_password', '').strip().replace(" ", "")
    sec_code = data.get('security_code', '').strip()

    if not access_token or not email_addr or not app_password or not sec_code:
        return jsonify({"success": False, "message": "All fields are required"}), 400

    try:
        send_url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
        send_payload = {
            "email": email_addr,
            "locale": "en_PK",
            "region": "PK",
            "app_id": "100067",
            "access_token": access_token
        }
        send_res = requests.post(send_url, headers=HEADERS, data=send_payload, timeout=15, verify=False)
        if send_res.json().get("result") != 0:
            return jsonify({"success": False, "message": "Failed to send OTP"}), 400

        otp = extract_otp_from_mailbox(email_addr, app_password, max_wait_sec=35)
        if not otp:
            return jsonify({"success": False, "message": "OTP not found in inbox. Verify App Password."}), 400

        verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_otp"
        v_payload = {
            "app_id": "100067",
            "access_token": access_token,
            "email": email_addr,
            "code": otp,
            "otp": otp,
            "type": "1"
        }
        v_res = requests.post(verify_url, headers=HEADERS, data=v_payload, timeout=15, verify=False)
        verifier_token = v_res.json().get("verifier_token", "")

        if not verifier_token:
            return jsonify({"success": False, "message": "OTP verification failed"}), 400

        bind_url = "https://100067.connect.garena.com/game/account_security/bind:create_bind_request"
        b_payload = {
            "email": email_addr,
            "app_id": "100067",
            "access_token": access_token,
            "verifier_token": verifier_token,
            "secondary_password": sec_code
        }
        b_res = requests.post(bind_url, headers=HEADERS, data=b_payload, timeout=15, verify=False)
        b_json = b_res.json()

        if b_json.get("result") == 0:
            return jsonify({"success": True, "message": "Account Bound Successfully!", "otp_used": otp})
        else:
            return jsonify({"success": False, "message": b_json.get("error", "Bind request failed")}), 400

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json(silent=True) or {}
    access_token = data.get('access_token', '').strip()
    email_addr = data.get('email', '').strip()

    if not access_token or not email_addr:
        return jsonify({"success": False, "message": "Token & Email required"}), 400

    try:
        url = "https://100067.connect.garena.com/game/account_security/bind:send_otp"
        payload = {
            "email": email_addr,
            "locale": "en_PK",
            "region": "PK",
            "app_id": "100067",
            "access_token": access_token
        }
        res = requests.post(url, headers=HEADERS, data=payload, timeout=15, verify=False)
        res_json = res.json()
        if res_json.get("result") == 0:
            return jsonify({"success": True, "message": "OTP sent successfully"})
        else:
            return jsonify({"success": False, "message": res_json.get("error", "Failed to send OTP")}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/complete-bind', methods=['POST'])
def complete_bind():
    data = request.get_json(silent=True) or {}
    access_token = data.get('access_token', '').strip()
    email_addr = data.get('email', '').strip()
    otp = data.get('otp', '').strip()
    security_code = data.get('security_code', '').strip()

    try:
        verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_otp"
        v_payload = {
            "app_id": "100067",
            "access_token": access_token,
            "email": email_addr,
            "code": otp,
            "otp": otp,
            "type": "1"
        }
        v_res = requests.post(verify_url, headers=HEADERS, data=v_payload, timeout=15, verify=False)
        verifier_token = v_res.json().get("verifier_token", "")

        if not verifier_token:
            return jsonify({"success": False, "message": "Invalid OTP code"}), 400

        bind_url = "https://100067.connect.garena.com/game/account_security/bind:create_bind_request"
        b_payload = {
            "email": email_addr,
            "app_id": "100067",
            "access_token": access_token,
            "verifier_token": verifier_token,
            "secondary_password": security_code
        }
        b_res = requests.post(bind_url, headers=HEADERS, data=b_payload, timeout=15, verify=False)
        b_json = b_res.json()

        if b_json.get("result") == 0:
            return jsonify({"success": True, "message": "Bind successful"})
        else:
            return jsonify({"success": False, "message": b_json.get("error", "Bind request failed")}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)