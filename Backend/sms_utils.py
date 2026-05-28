import os
import re
import requests
import logging
from config import SMS_PROVIDER, FAST2SMS_API_KEY


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def normalize_and_validate_phone(phone):
    """
    Normalizes phone number to 10-digit format for Indian numbers, or leaves it as-is if it's already 10-digits.
    Returns (cleaned_phone, error_message). If error_message is not None, the phone is invalid.
    """
    if not phone:
        return None, "Phone number is required."
    
    # Strip whitespace, dashes, parentheses, plus
    cleaned = re.sub(r'[\s\-()+]+', '', phone)
    
    # If it starts with +91 or 91, handle it
    # We stripped '+' so check for starting with '91' and having 12 digits
    if cleaned.startswith('91') and len(cleaned) == 12:
        cleaned = cleaned[2:]
    elif cleaned.startswith('0') and len(cleaned) == 11:
        cleaned = cleaned[1:]
        
    # Check if the remaining part is exactly 10 digits
    if not re.match(r'^[6-9]\d{9}$', cleaned):
        return None, "Invalid phone number. Must be a 10-digit Indian mobile number."
        
    return cleaned, None

def send_otp_sms(phone, otp):
    """
    Sends OTP via configured SMS provider.
    """
    message = f"Your CRMS verification code is: {otp}. Valid for 2 minutes."
    
    cleaned_phone, err = normalize_and_validate_phone(phone)
    if err:
        return False, err
        
    if SMS_PROVIDER == "fast2sms":
        if not FAST2SMS_API_KEY:
            logger.warning("SMS_PROVIDER set to fast2sms but FAST2SMS_API_KEY is missing. Falling back to mock mode.")
            return send_otp_mock(cleaned_phone, otp, message)
        
        success, response_msg = send_sms_via_fast2sms(FAST2SMS_API_KEY, cleaned_phone, message)
        if not success:
            logger.error(f"Fast2SMS API failed: {response_msg}. Falling back to mock mode.")
            return send_otp_mock(cleaned_phone, otp, message)
        return True, response_msg
    else:
        # Mock mode
        return send_otp_mock(cleaned_phone, otp, message)

def send_otp_mock(phone, otp, message):
    logger.info("=" * 60)
    logger.info(f"MOCK SMS SENT TO {phone}")
    logger.info(f"Message: {message}")
    logger.info(f"OTP: {otp}")
    logger.info("=" * 60)
    return True, f"Mock SMS sent. OTP code is: {otp}"

def send_sms_via_fast2sms(api_key, phone, message):
    url = "https://www.fast2sms.com/dev/bulkV2"
    headers = {
        "authorization": api_key,
        "Content-Type": "application/json",
        "cache-control": "no-cache"
    }
    payload = {
        "route": "q",
        "message": message,
        "numbers": phone
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        result = response.json()
        if response.status_code == 200 and result.get("return") is True:
            return True, "SMS sent successfully via Fast2SMS"
        else:
            return False, f"Fast2SMS error: {result.get('message', 'Unknown error')}"
    except Exception as e:
        logger.error(f"Failed to send SMS via POST: {e}")
        try:
            params = {
                "authorization": api_key,
                "route": "q",
                "message": message,
                "numbers": phone
            }
            response = requests.get(url, params=params, timeout=10)
            result = response.json()
            if response.status_code == 200 and result.get("return") is True:
                return True, "SMS sent successfully via Fast2SMS GET"
            else:
                return False, f"Fast2SMS GET error: {result.get('message', 'Unknown error')}"
        except Exception as ex:
            return False, f"Fast2SMS API Exception: {ex}"
