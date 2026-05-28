import time
import uuid
import threading

class OTPStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.otps = {}  # phone -> { "otp": otp, "expires_at": ts, "attempts": int }
        self.tokens = {}  # token_uuid -> { "phone": phone, "expires_at": ts }
        self.send_history = {}  # phone -> list of timestamps

    def can_send_otp(self, phone):
        with self.lock:
            now = time.time()
            # Clean up old timestamps (> 10 mins ago)
            cutoff = now - 600
            timestamps = [ts for ts in self.send_history.get(phone, []) if ts > cutoff]
            self.send_history[phone] = timestamps
            if len(timestamps) >= 3:
                return False
            return True

    def record_send(self, phone):
        with self.lock:
            now = time.time()
            if phone not in self.send_history:
                self.send_history[phone] = []
            self.send_history[phone].append(now)

    def save_otp(self, phone, otp, ttl=120):
        with self.lock:
            now = time.time()
            self.otps[phone] = {
                "otp": otp,
                "expires_at": now + ttl,
                "attempts": 0
            }

    def verify_otp(self, phone, otp):
        with self.lock:
            now = time.time()
            entry = self.otps.get(phone)
            if not entry:
                return False, "OTP not found. Please request a new one."
            
            if now > entry["expires_at"]:
                del self.otps[phone]
                return False, "OTP has expired."
            
            if entry["attempts"] >= 3:
                del self.otps[phone]
                return False, "Too many failed attempts. OTP invalidated."
            
            # Increment attempts
            entry["attempts"] += 1
            
            if entry["otp"] != otp:
                if entry["attempts"] >= 3:
                    del self.otps[phone]
                    return False, "Incorrect OTP. Too many failed attempts. OTP invalidated."
                return False, f"Incorrect OTP. {3 - entry['attempts']} attempts remaining."
            
            # Success - invalidate OTP
            del self.otps[phone]
            
            # Issue verification token
            token = str(uuid.uuid4())
            self.tokens[token] = {
                "phone": phone,
                "expires_at": now + 600  # 10 minutes TTL
            }
            return True, token

    def verify_token(self, phone, token):
        with self.lock:
            now = time.time()
            entry = self.tokens.get(token)
            if not entry:
                return False
            if now > entry["expires_at"]:
                del self.tokens[token]
                return False
            if entry["phone"] != phone:
                return False
            # Consume the token on use
            del self.tokens[token]
            return True

# Global instance
otp_store = OTPStore()
