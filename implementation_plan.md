# Implementation Plan: Complaint Filing Safety & Verification System

## Goal

Before a citizen can submit a public complaint, we will:
1. Show a **legal disclaimer alert** — they must confirm their intent.
2. **Validate email** without sending an OTP — using DNS MX-record lookup (checks the domain actually has a mail server).
3. **Verify phone number** via a timed **SMS OTP** — 6-digit code, 2-minute countdown, resend button.

Only after all verifications pass does the final `POST /public/complaint` fire.

---

## System Design

```
User fills form
      │
      ▼
[Submit] button → Legal Disclaimer modal appears
      │
      ├─ "No, Wait" → modal closes, form stays
      │
      └─ "Yes, Proceed" →
              │
              ▼
          Email validation (if email provided)
          Backend: POST /public/verify-email
          ↳ DNS MX lookup on email domain
          ↳ Returns { valid: true/false, reason }
              │
              ▼
          Phone OTP send
          Backend: POST /public/otp/send
          ↳ Generates 6-digit OTP, stores in-memory with TTL=120s
          ↳ Sends via SMS (Twilio / Fast2SMS / mock fallback)
              │
              ▼
          OTP entry screen (countdown timer, resend after 30s)
          Backend: POST /public/otp/verify
          ↳ Checks OTP + expiry
              │
              ▼
          POST /public/complaint (existing endpoint, unchanged)
```

---

## Open Questions

> [!IMPORTANT]
> **SMS Provider**: No SMS library is currently installed. We have three options:
> - **Option A** — `Fast2SMS` (Indian, free tier, easiest setup — just an API key in `.env`)
> - **Option B** — `Twilio` (industry-standard, needs Account SID + Auth Token + phone number)
> - **Option C** — **Mock/Log mode** (OTP printed to Flask logs only — works immediately, no signup needed, great for dev/testing)
>
> We will implement **Option C (mock fallback) by default**, with `Fast2SMS` as the primary option via env config. This means it works right now with zero external accounts, and you can enable real SMS later by just adding env keys.

> [!NOTE]
> **Email MX validation** does not send any email. It queries the DNS server for the domain's mail exchange records. If `gmail.com` is the domain, it finds Google's MX servers and returns valid. If the domain is `fakedomain123.xyz`, DNS returns nothing and we return invalid. This is how most services do "email format + domain" checking without SMTP.

---

## Proposed Changes

### Backend — New Dependencies
Install `dnspython` for MX lookup:
```
pip install dnspython
```
Add to `requirements.txt`.

---

### Backend — `Backend/otp_store.py` [NEW]

A lightweight in-process OTP store (thread-safe dict) with TTL. No Redis needed.

```python
# otp_store.py
# Thread-safe in-memory OTP store with expiry.
```

Fields per entry: `{ otp, expires_at, attempts }`  
Max 3 verification attempts per OTP before invalidation.

---

### Backend — `Backend/sms_utils.py` [NEW]

SMS dispatch with graceful mock fallback:
- Reads `SMS_PROVIDER`, `FAST2SMS_API_KEY` from `.env`
- If no keys configured → logs OTP to console (mock mode)
- If `fast2sms` configured → calls `https://www.fast2sms.com/dev/bulkV2` API

---

### Backend — `Backend/config.py` [MODIFY]

Add optional SMS config vars:
```python
SMS_PROVIDER     = _get_optional_env("SMS_PROVIDER", "mock")  # "fast2sms" | "mock"
FAST2SMS_API_KEY = _get_optional_env("FAST2SMS_API_KEY", "")
```

---

### Backend — `Backend/app.py` [MODIFY]

Add 3 new endpoints (additive, does not touch existing `/public/complaint`):

#### `POST /public/verify-email`
```json
Body: { "email": "user@domain.com" }
Returns: { "success": true, "valid": true|false, "reason": "..." }
```
- Regex check first (format)
- DNS MX lookup on domain
- Returns result immediately (non-blocking, ~100ms)
- No rate limit bypass risk since it doesn't send any email

#### `POST /public/otp/send`
```json
Body: { "phone": "+919999988888" }
Returns: { "success": true, "expires_in": 120 }
```
- Normalises Indian phone numbers (+91 prefix)
- Validates format (10 digit mobile)
- Generates 6-digit OTP, stores with 120s TTL
- Sends SMS (or logs to console in mock mode)
- Rate-limited: max 3 sends per phone per 10 minutes (in-memory counter)

#### `POST /public/otp/verify`
```json
Body: { "phone": "+919999988888", "otp": "123456" }
Returns: { "success": true, "verified": true, "token": "<uuid>" }
```
- Checks OTP + expiry
- On success: issues a short-lived **verification token** (UUID, 10-min TTL) tied to that phone number
- Existing `POST /public/complaint` endpoint will validate this token before accepting submission
- Max 3 wrong attempts → OTP invalidated

#### `POST /public/complaint` [MINOR MODIFY]
- Accept additional field `phone_verification_token`
- If provided, validate it against otp_store
- If no token provided: still works (for backward compatibility / dev mode)

---

### Frontend — `Frontend/crms_frontend.html` [MODIFY]

The `PublicPortal` complaint tab will get a multi-step verification flow replacing the single-step form submission:

#### New State Variables
```js
const [showDisclaimer, setShowDisclaimer] = useState(false);
const [emailValidating, setEmailValidating] = useState(false);
const [emailValid, setEmailValid] = useState(null); // null | true | false
const [otpSent, setOtpSent] = useState(false);
const [otpValue, setOtpValue] = useState("");
const [otpVerified, setOtpVerified] = useState(false);
const [verificationToken, setVerificationToken] = useState(null);
const [otpCountdown, setOtpCountdown] = useState(0);
const [otpResendAllowed, setOtpResendAllowed] = useState(false);
const [verifyStep, setVerifyStep] = useState("form"); // "form"|"disclaimer"|"email"|"otp"|"ready"
```

#### Legal Disclaimer Modal
A glassmorphism overlay modal that appears after the user clicks "Submit Complaint":
- **Warning icon** + bold header: *"Legal Notice — Bengaluru Police Department"*
- Body text: *"Filing a false or fabricated police complaint is a criminal offence punishable under Section 182 of the Indian Penal Code (IPC) and Section 211 IPC, which may result in imprisonment of up to 7 years and/or a fine. Please confirm that all information provided is accurate and truthful to the best of your knowledge."*
- Two buttons:
  - **"No, Wait"** → closes modal, returns to form
  - **"Yes, I Understand — Proceed"** → starts verification chain

#### Email Validation Step (if email provided)
- Inline indicator below email field: spinner → ✅ Domain verified / ❌ Invalid email domain
- Shown after disclaimer is accepted

#### OTP Step
- Phone OTP screen with:
  - Input field for 6-digit code
  - Live countdown timer `1:59 → 0:00`
  - "Verify" button
  - "Resend OTP" (disabled for first 30s, then enabled)
  - On success: green "Phone verified ✓" badge

---

## `.env` changes
```env
# SMS OTP Configuration (optional)
SMS_PROVIDER=mock          # "fast2sms" | "mock"
FAST2SMS_API_KEY=          # your Fast2SMS API key (leave blank for mock mode)
```

---

## Verification Plan

### Automated
- Start Flask server
- `POST /public/verify-email` with `test@gmail.com` → should return `valid: true`
- `POST /public/verify-email` with `test@notarealdomain99999.xyz` → should return `valid: false`
- `POST /public/otp/send` with a phone number → OTP printed in server log (mock mode)
- `POST /public/otp/verify` with correct OTP → returns `verified: true` + token
- `POST /public/otp/verify` with wrong OTP → returns `verified: false`
- After 3 wrong attempts → OTP invalidated

### Manual / Browser
- Open public portal → fill form → click Submit
- Legal disclaimer modal appears
- Click "Yes, Proceed" → email check runs
- OTP sent to phone (mock: visible in server log)
- Enter OTP → verification passes → complaint submits
- Reference number displayed
