        const { useState, useEffect, useRef, useMemo } = React;
        const { motion, AnimatePresence } = window.Motion || window.FramerMotion || window.framerMotion || window['framer-motion'] || {};

        // ─── API CONFIG ───────────────────────────────────────────────────────
        // For separate frontend/backend deploys, set window.CRMS_API_BASE or visit once with ?api_base=https://your-backend.onrender.com
        const queryApiBase = new URLSearchParams(window.location.search).get("api_base");
        if (queryApiBase) localStorage.setItem("CRMS_API_BASE", queryApiBase);
        const configuredApiBase = window.CRMS_API_BASE || localStorage.getItem("CRMS_API_BASE") || "";
        const API_BASE = (
            configuredApiBase ||
            (window.location.origin && window.location.origin !== "null" && !window.location.origin.startsWith("file:")
                ? window.location.origin
                : "http://localhost:5000")
        ).replace(/\/$/, "");
        const OFFICER_STORAGE_KEY = "CRMS_OFFICER_SESSION";

        const getStoredOfficer = () => {
            try {
                return JSON.parse(localStorage.getItem(OFFICER_STORAGE_KEY) || "null");
            } catch {
                return null;
            }
        };

        const getStoredSessionToken = () => getStoredOfficer()?.session_token || "";
        const storeOfficerSession = (officerData) => localStorage.setItem(OFFICER_STORAGE_KEY, JSON.stringify(officerData));
        const clearOfficerSession = () => localStorage.removeItem(OFFICER_STORAGE_KEY);
        const PUBLIC_COMPLAINT_DRAFT_KEY = "CRMS_PUBLIC_COMPLAINT_DRAFT";

        const getPublicComplaintDraft = () => {
            try {
                return JSON.parse(localStorage.getItem(PUBLIC_COMPLAINT_DRAFT_KEY) || "null");
            } catch {
                return null;
            }
        };

        const clearPublicComplaintDraft = () => localStorage.removeItem(PUBLIC_COMPLAINT_DRAFT_KEY);
        const authHeaders = (officer) => ({
            "X-Officer-Id": officer?.officer_id?.toString(),
            "X-Session-Token": officer?.session_token || getStoredSessionToken()
        });
        
        // reCAPTCHA v2 (Invisible) Configuration
        const RECAPTCHA_PUBLIC_KEY = window._recaptcha_site_key || "6LfLCfIsAAAAAK4ZwH_RMmvAPAi3vtkGKPLAYkuk";

        // Generic fetch helper — returns parsed JSON or throws with a readable message.
        const apiFetch = async (path, options = {}) => {
            const { headers, ...rest } = options;
            const sessionToken = getStoredSessionToken();
            const res = await fetch(`${API_BASE}${path}`, {
                headers: { 
                    "Content-Type": "application/json",
                    ...(sessionToken ? { "X-Session-Token": sessionToken } : {}),
                    ...(headers || {})
                },
                ...rest,
            });
            const json = await res.json();
            if (!res.ok && res.status === 401 && String(json.error || "").toLowerCase().includes("session")) {
                clearOfficerSession();
            }
            if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
            return json;
        };
        
        // Execute reCAPTCHA v2 and return token
        const executeRecaptcha = async (action = "submit") => {
            const siteKey = window._recaptcha_site_key || RECAPTCHA_PUBLIC_KEY;
            console.log("[reCAPTCHA] Executing reCAPTCHA v2 for action:", action);

            // Wait for grecaptcha to load
            const waitForGrecaptcha = () => new Promise(resolve => {
                if (window.grecaptcha?.render) {
                    return resolve();
                }
                let waited = 0;
                const iv = setInterval(() => {
                    if (window.grecaptcha?.render) {
                        clearInterval(iv);
                        resolve();
                    } else if (waited > 10000) {
                        console.error("[reCAPTCHA] Script failed to load");
                        clearInterval(iv);
                        resolve();
                    }
                    waited += 100;
                }, 100);
            });

            try {
                await waitForGrecaptcha();
                
                if (!window.grecaptcha?.render) {
                    console.error("[reCAPTCHA] grecaptcha.render unavailable");
                    return "";
                }

                return new Promise((resolve) => {
                    // Create modal for CAPTCHA challenge UI (rendered if verification is required)
                    const overlay = document.createElement('div');
                    overlay.style.cssText = `
                        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                        background: rgba(0,0,0,0.65); z-index: 9998;
                        display: flex; align-items: center; justify-content: center;
                        backdrop-filter: blur(3px);
                    `;
                    
                    const container = document.createElement('div');
                    container.style.cssText = `
                        background: #111827; padding: 30px; border-radius: 12px;
                        border: 1px solid #374151; text-align: center;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                    `;
                    
                    const title = document.createElement('p');
                    title.textContent = "Verifying Security Credentials";
                    title.style.cssText = 'margin-bottom: 20px; font-weight: 500; color: #f3f4f6; font-size: 15px; font-family: monospace;';
                    
                    const captchaDiv = document.createElement('div');
                    captchaDiv.id = `g-recaptcha-${Date.now()}`;
                    
                    container.appendChild(title);
                    container.appendChild(captchaDiv);
                    overlay.appendChild(container);
                    document.body.appendChild(overlay);
                    
                    // Track completion
                    let completed = false;
                    const timeoutId = setTimeout(() => {
                        if (!completed) {
                            console.warn("[reCAPTCHA] Timeout (2 min)");
                            overlay.remove();
                            resolve("");
                        }
                    }, 120000);
                    
                    // Callback
                    const callbackName = `onRecaptchaSuccess_${Date.now()}`;
                    window[callbackName] = (token) => {
                        if (completed) return;
                        completed = true;
                        clearTimeout(timeoutId);
                        console.log("[reCAPTCHA] Token received");
                        overlay.remove();
                        try { delete window[callbackName]; } catch(e) {}
                        resolve(token);
                    };
                    
                    try {
                        // 1. Render the reCAPTCHA instance configured explicitly as 'invisible'
                        const widgetId = grecaptcha.render(captchaDiv.id, {
                            sitekey: siteKey,
                            size: 'invisible',
                            callback: callbackName,
                            'error-callback': () => {
                                if (completed) return;
                                completed = true;
                                clearTimeout(timeoutId);
                                console.error("[reCAPTCHA] Execution error encountered");
                                overlay.remove();
                                resolve("");
                            },
                            'expired-callback': () => {
                                console.warn("[reCAPTCHA] Token expired");
                            }
                        });

                        // 2. Explicitly fire the execution challenge programmatically
                        grecaptcha.execute(widgetId);

                    } catch (err) {
                        clearTimeout(timeoutId);
                        console.error("[reCAPTCHA] Render error:", err);
                        overlay.remove();
                        resolve("");
                    }
                });
            } catch (err) {
                console.error("[reCAPTCHA] Error:", err);
                return "";
            }
        };

