        // ─── PUBLIC PORTAL ────────────────────────────────────────────────────
        const PublicPortal = ({ onNavigate }) => {
            const savedComplaintDraft = getPublicComplaintDraft();
            const [activeTab, setActiveTab] = useState(() => {
                return localStorage.getItem("CRMS_PUBLIC_ACTIVE_TAB") || "complaint";
            });
            useEffect(() => {
                localStorage.setItem("CRMS_PUBLIC_ACTIVE_TAB", activeTab);
            }, [activeTab]);
            const [error, setError] = useState("");
            const [formData, setFormData] = useState({
                name: savedComplaintDraft?.formData?.name || "",
                contact: savedComplaintDraft?.formData?.contact || "",
                email: savedComplaintDraft?.formData?.email || "",
                aadhaar: savedComplaintDraft?.formData?.aadhaar || "",
                incident_desc: savedComplaintDraft?.formData?.incident_desc || "",
                crime_type: savedComplaintDraft?.formData?.crime_type || "",
                location: savedComplaintDraft?.formData?.location || ""
            });
            const [aadhaarError, setAadhaarError] = useState("");
            const [submitted, setSubmitted] = useState(false);
            // Geolocation auto-fill for the Location field.
            // geoStatus: null | "loading" | "ok" | "denied" | "unsupported" | "error"
            const [geoStatus, setGeoStatus] = useState(null);
            const [geoMessage, setGeoMessage] = useState("");
            const [accessForm, setAccessForm] = useState({ case_id: "", requester_name: "", requester_email: "", requester_number: "", reason: "" });

            const [accessSubmitted, setAccessSubmitted] = useState(false);

            const [submitting, setSubmitting] = useState(false);
            const [caseRef, setCaseRef] = useState(null);

            // Browse Cases state
            const [browsingCases, setBrowsingCases] = useState([]);
            const [browseCaseFilters, setBrowseCaseFilters] = useState({ status: "Active", crime_type: "", location: "", search: "" });
            const [browseCaseLoading, setBrowseCaseLoading] = useState(false);
            const [browseCasePage, setBrowseCasePage] = useState(1);
            const [browseCaseTotalPages, setBrowseCaseTotalPages] = useState(1);
            const BROWSE_PAGE_SIZE = 20;

            // Safety and Verification states
            const [showDisclaimer, setShowDisclaimer] = useState(false);
            const [emailValidating, setEmailValidating] = useState(false);
            const [emailValid, setEmailValid] = useState(null); // null | true | false
            const [otpSent, setOtpSent] = useState(savedComplaintDraft?.verifyStep === "otp");
            const [otpValue, setOtpValue] = useState("");
            const [otpVerified, setOtpVerified] = useState(false);
            const [verificationToken, setVerificationToken] = useState(null);
            const [otpCountdown, setOtpCountdown] = useState(() => {
                if (savedComplaintDraft?.verifyStep !== "otp") return 0;
                return Math.max(0, Math.ceil(((savedComplaintDraft.otpExpiresAt || 0) - Date.now()) / 1000));
            });
            const [verifyStep, setVerifyStep] = useState(() => {
                if (savedComplaintDraft?.verifyStep === "otp") return "otp";
                return "form";
            }); // "form"|"disclaimer"|"email"|"otp"|"ready"
            const [otpExpiresAt, setOtpExpiresAt] = useState(savedComplaintDraft?.otpExpiresAt || null);

            useEffect(() => {
                const hasDraftData = Object.values(formData).some(value => String(value || "").trim());
                if (!hasDraftData && verifyStep === "form") {
                    clearPublicComplaintDraft();
                    return;
                }

                if (hasDraftData || verifyStep === "otp") {
                    localStorage.setItem(PUBLIC_COMPLAINT_DRAFT_KEY, JSON.stringify({
                        formData,
                        verifyStep: verifyStep === "otp" ? "otp" : "form",
                        otpExpiresAt: verifyStep === "otp" ? otpExpiresAt : null,
                        savedAt: Date.now()
                    }));
                }
            }, [formData, verifyStep, otpExpiresAt]);

            // OTP Countdown Timer Effect
            useEffect(() => {
                if (verifyStep !== "otp" || !otpExpiresAt) return;

                const syncCountdown = () => {
                    setOtpCountdown(Math.max(0, Math.ceil((otpExpiresAt - Date.now()) / 1000)));
                };

                syncCountdown();
                const timer = setInterval(syncCountdown, 1000);
                return () => clearInterval(timer);
            }, [verifyStep, otpExpiresAt]);

            const handleFormSubmitAttempt = (e) => {
                e.preventDefault();
                // Validate Aadhaar 12-digit number
                const a12 = formData.aadhaar.trim();
                if (!/^[0-9]{12}$/.test(a12)) {
                    setAadhaarError("Enter exactly 12 digits for Aadhaar number");
                    return;
                }
                setAadhaarError("");
                setError("");
                
                // Show Disclaimer Modal
                setShowDisclaimer(true);
                setVerifyStep("disclaimer");
            };

            const handleDisclaimerReject = () => {
                setShowDisclaimer(false);
                setVerifyStep("form");
            };

            const handleDisclaimerAccept = async () => {
                setShowDisclaimer(false);
                
                setVerifyStep("email");
                setEmailValidating(true);
                try {
                    const res = await apiFetch("/public/verify-email", {
                        method: "POST",
                        body: JSON.stringify({ email: formData.email.trim() })
                    });
                    if (res.success && res.valid) {
                        setEmailValid(true);
                        await startOtpFlow();
                    } else {
                        setEmailValid(false);
                        setError(res.reason || "Invalid email domain. Please check your email address.");
                        setVerifyStep("form");
                    }
                } catch (err) {
                    setEmailValid(false);
                    setError("Email verification failed: " + err.message);
                    setVerifyStep("form");
                } finally {
                    setEmailValidating(false);
                }
            };

            const startOtpFlow = async () => {
                setVerifyStep("otp");
                setOtpSent(false);
                setOtpValue("");
                setOtpVerified(false);
                setOtpCountdown(120);
                setOtpExpiresAt(Date.now() + 120000);
                setError("");
                
                try {
                    const res = await apiFetch("/public/otp/send", {
                        method: "POST",
                        body: JSON.stringify({ email: formData.email.trim() })
                    });
                    if (res.success) {
                        setOtpSent(true);
                    } else {
                        setError(res.message || "Failed to send OTP.");
                        setVerifyStep("form");
                    }
                } catch (err) {
                    setError("Failed to send OTP: " + err.message);
                    setVerifyStep("form");
                }
            };

            const handleResendOtp = async () => {
                if (otpCountdown > 90) return; // Wait 30 seconds
                setOtpCountdown(120);
                setOtpExpiresAt(Date.now() + 120000);
                setError("");
                try {
                    const res = await apiFetch("/public/otp/send", {
                        method: "POST",
                        body: JSON.stringify({ email: formData.email.trim() })
                    });
                    if (res.success) {
                        alert("OTP resent successfully.");
                    } else {
                        setError(res.message || "Failed to resend OTP.");
                    }
                } catch (err) {
                    setError("Failed to resend OTP: " + err.message);
                }
            };

            const handleVerifyOtp = async () => {
                if (!otpValue || otpValue.length !== 6) {
                    alert("Please enter a valid 6-digit OTP.");
                    return;
                }
                setError("");
                try {
                    const res = await apiFetch("/public/otp/verify", {
                        method: "POST",
                        body: JSON.stringify({ email: formData.email.trim(), otp: otpValue })
                    });
                    if (res.success && res.verified) {
                        setOtpVerified(true);
                        setVerificationToken(res.token);
                        setVerifyStep("ready");
                        await finalizeComplaintSubmission(res.token);
                    } else {
                        setError(res.message || "OTP verification failed.");
                    }
                } catch (err) {
                    setError("OTP verification failed: " + err.message);
                }
            };

            const finalizeComplaintSubmission = async (token) => {
                setSubmitting(true);
                setError("");
                try {
                    const captchaToken = await executeRecaptcha("complaint");
                    if (!captchaToken) {
                        setError("CAPTCHA verification is required");
                        setVerifyStep("form");
                        return;
                    }
                    const payload = {
                        ...formData,
                        aadhaar: formData.aadhaar.trim(),
                        complaint_mode: "Online",
                        captcha_token: captchaToken,
                        email_verification_token: token
                    };
                    const res = await apiFetch("/public/complaint", {
                        method: "POST",
                        body: JSON.stringify(payload),
                    });
                    setCaseRef(res.reference || null);
                    setSubmitted(true);
                    clearPublicComplaintDraft();
                    setFormData({
                        name: "", contact: "", email: "", aadhaar: "",
                        incident_desc: "", crime_type: "", location: ""
                    });
                    setGeoStatus(null);
                    setGeoMessage("");
                    setVerifyStep("form");
                } catch (err) {
                    setError("Submission failed: " + err.message);
                    setVerifyStep("form");
                } finally {
                    setSubmitting(false);
                }
                setTimeout(() => { setSubmitted(false); setCaseRef(null); }, 8000);
            };

            // ─── GEOLOCATION AUTO-FILL ──────────────────────────────────────
            // Triggers the browser's native permission prompt. On allow, reverse-
            // geocodes the coordinates to a human-readable address (OpenStreetMap
            // Nominatim — free, no API key) and fills the Location field. On deny
            // or any failure, we keep whatever the user typed manually.
            const handleUseMyLocation = () => {
                if (!("geolocation" in navigator)) {
                    setGeoStatus("unsupported");
                    setGeoMessage("Your browser does not support location access. Please type the address manually.");
                    return;
                }

                setGeoStatus("loading");
                setGeoMessage("Requesting your location…");

                navigator.geolocation.getCurrentPosition(
                    async (position) => {
                        const { latitude, longitude } = position.coords;
                        try {
                            // Reverse geocode via OpenStreetMap Nominatim.
                            const res = await fetch(
                                `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1`,
                                { headers: { "Accept": "application/json" } }
                            );
                            if (!res.ok) throw new Error("reverse geocode failed");
                            const data = await res.json();

                            // Build a concise, readable address from the parts we care about.
                            const a = data.address || {};
                            const parts = [
                                a.neighbourhood || a.suburb || a.residential,
                                a.city || a.town || a.village || a.county,
                                a.state,
                                a.postcode,
                            ].filter(Boolean);
                            const readable = parts.length ? parts.join(", ") : (data.display_name || "");

                            if (readable) {
                                setFormData(prev => ({ ...prev, location: readable }));
                                setGeoStatus("ok");
                                setGeoMessage("Location detected. You can edit it if needed.");
                            } else {
                                // Fall back to raw coordinates so the field is still useful.
                                setFormData(prev => ({ ...prev, location: `${latitude.toFixed(5)}, ${longitude.toFixed(5)}` }));
                                setGeoStatus("ok");
                                setGeoMessage("Couldn't resolve an address; filled with coordinates instead. You can edit it.");
                            }
                        } catch (err) {
                            // Geocoding failed but we still have coordinates.
                            setFormData(prev => ({ ...prev, location: `${latitude.toFixed(5)}, ${longitude.toFixed(5)}` }));
                            setGeoStatus("ok");
                            setGeoMessage("Location detected (as coordinates). You can edit it if needed.");
                        }
                    },
                    (err) => {
                        // PERMISSION_DENIED (1), POSITION_UNAVAILABLE (2), TIMEOUT (3)
                        if (err.code === 1) {
                            setGeoStatus("denied");
                            setGeoMessage("Location access denied. No problem — please type the address manually.");
                        } else {
                            setGeoStatus("error");
                            setGeoMessage("Couldn't determine your location. Please type the address manually.");
                        }
                    },
                    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
                );
            };


            const handleAccessSubmit = async (e) => {
                e.preventDefault();
                setError("");
                setSubmitting(true);
                try {
                    // Get CAPTCHA token
                    const captchaToken = await executeRecaptcha("access_request");
                    if (!captchaToken) {
                        setError("CAPTCHA verification is required for access requests");
                        setSubmitting(false);
                        return;
                    }
                    const payload = { ...accessForm, captcha_token: captchaToken };
                    await apiFetch("/public/access-request", {
                        method: "POST",
                        body: JSON.stringify(payload),
                    });
                    setAccessSubmitted(true);
                    setAccessForm({ case_id: "", requester_name: "", requester_email: "", requester_number: "", reason: "" });
                } catch (err) {
                    console.warn("[Themis's Domain] Access request POST failed:", err.message);
                    setError(err.message || "Failed to submit access request.");
                } finally {
                    setSubmitting(false);
                }
                setTimeout(() => setAccessSubmitted(false), 8000);
            };

            // Load cases when browse tab is selected
            useEffect(() => {
                if (activeTab === "browse") {
                    loadBrowsingCases();
                }
            }, [activeTab, browseCaseFilters, browseCasePage]);

            const loadBrowsingCases = async () => {
                setBrowseCaseLoading(true);
                try {
                    const params = new URLSearchParams();
                    if (browseCaseFilters.status) params.append("status", browseCaseFilters.status);
                    if (browseCaseFilters.crime_type) params.append("crime_type", browseCaseFilters.crime_type);
                    if (browseCaseFilters.location) params.append("location", browseCaseFilters.location);
                    if (browseCaseFilters.search) params.append("search", browseCaseFilters.search);
                    params.append("page", browseCasePage);
                    params.append("limit", BROWSE_PAGE_SIZE);

                    const res = await apiFetch(`/public/cases?${params.toString()}`, { method: "GET" });
                    setBrowsingCases(res.data || []);
                    if (res.pagination) {
                        setBrowseCaseTotalPages(res.pagination.total_pages || 1);
                    }
                } catch (err) {
                    console.warn("[Themis's Domain] Failed to load cases:", err.message);
                    setBrowsingCases([]);
                } finally {
                    setBrowseCaseLoading(false);
                }
            };

            const handleBrowseCaseFilterChange = (field, value) => {
                // Filter changes reset to page 1; the effect above re-fetches.
                setBrowseCasePage(1);
                setBrowseCaseFilters({ ...browseCaseFilters, [field]: value });
            };

            const handleSelectCaseForAccess = (caseId, caseDisplayId) => {
                setAccessForm({ ...accessForm, case_id: caseDisplayId });
                setActiveTab("access");
                setError("");
            };


            return (
                <CrmsPageShell
                    title="Themis's Domain Public Portal"
                    subtitle="Bengaluru Police Department"
                    onBack={() => onNavigate("landing")}
                    scrim="bg-white/40"
                >
                    <motion.div
                        className="mx-auto max-w-4xl px-5 py-10 sm:px-8 sm:py-12"
                        initial="hidden"
                        animate="visible"
                        variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.08 } } }}
                    >
                        <motion.div variants={fadeUp} custom={0} className="mb-10 border-b-2 border-ink/80 pb-6 text-center sm:mb-12">
                            <p className="kicker mb-3">Citizen Services Desk</p>
                            <h1 className="headline mb-3 text-4xl sm:text-5xl md:text-6xl">Public Services</h1>
                            <p className="font-editorial text-sm italic text-ink-muted sm:text-base">File complaints and request case information securely</p>
                        </motion.div>

                        {/* Editorial banner — institutional records registry */}
                        <motion.figure variants={fadeUp} custom={0} className="mb-10 overflow-hidden border border-ink/20">
                            <div className="relative">
                                <img
                                    src={EDITORIAL_IMG.registry}
                                    alt="The departmental records registry"
                                    loading="lazy"
                                    className="h-40 w-full object-cover grayscale-[40%] sepia-[10%] contrast-[1.05] sm:h-52"
                                />
                                <div className="absolute inset-0 bg-gradient-to-t from-ink-black/70 via-ink-black/10 to-transparent" />
                                <figcaption className="absolute bottom-0 left-0 right-0 px-4 py-3">
                                    <p className="font-display text-lg font-bold text-paper sm:text-xl">A public record, kept in trust.</p>
                                    <p className="mt-0.5 font-editorial text-[11px] italic text-paper/80">Every complaint and request is logged, tracked, and accountable.</p>
                                </figcaption>
                            </div>
                        </motion.figure>

                        {/* Tabs — editorial section markers */}
                        <motion.div variants={fadeUp} custom={1} className="mb-10 flex justify-center px-4">
                            <div className="flex w-full flex-col gap-0 border-y-2 border-ink sm:w-auto sm:flex-row sm:divide-x sm:divide-ink/20">
                                <button
                                    type="button"
                                    onClick={() => setActiveTab("complaint")}
                                    className={`w-full sm:w-auto px-6 py-3 text-[10px] font-bold uppercase tracking-[0.18em] transition-all sm:text-xs font-sans ${activeTab === "complaint" ? "bg-ink-black text-paper" : "text-ink/60 hover:text-accent"}`}
                                >
                                    <span className="flex items-center justify-center gap-2">
                                        <Icon name="FilePlus" size={14} />
                                        File Complaint
                                    </span>
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setActiveTab("browse")}
                                    className={`w-full sm:w-auto px-6 py-3 text-[10px] font-bold uppercase tracking-[0.18em] transition-all sm:text-xs font-sans ${activeTab === "browse" ? "bg-ink-black text-paper" : "text-ink/60 hover:text-accent"}`}
                                >
                                    <span className="flex items-center justify-center gap-2">
                                        <Icon name="Search" size={14} />
                                        Browse Cases
                                    </span>
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setActiveTab("access")}
                                    className={`w-full sm:w-auto px-6 py-3 text-[10px] font-bold uppercase tracking-[0.18em] transition-all sm:text-xs font-sans ${activeTab === "access" ? "bg-ink-black text-paper" : "text-ink/60 hover:text-accent"}`}
                                >
                                    <span className="flex items-center justify-center gap-2">
                                        <Icon name="Eye" size={14} />
                                        Request Case Access
                                    </span>
                                </button>
                            </div>
                        </motion.div>

                        {/* Complaint Form */}
                        {activeTab === "complaint" && (
                            <motion.div variants={fadeUp} custom={2} className={ThemisNomos_CARD}>
                                <div className="mb-8 flex items-center gap-3">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-black bg-white">
                                        <Icon name="FileText" size={18} className="text-black" />
                                    </div>
                                    <div>
                                        <h2 className="text-lg font-semibold uppercase tracking-[0.1em] text-black sm:text-xl">File a Complaint</h2>
                                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-black/65 sm:text-xs">Submit a new case to the Bengaluru Police</p>
                                    </div>
                                </div>

                                {submitted ? (
                                    <div className="py-12 text-center">
                                        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border-2 border-black bg-white">
                                            <Icon name="CheckCircle" size={28} className="text-accent" />
                                        </div>
                                        <h3 className="mb-2 text-lg font-semibold uppercase tracking-[0.1em] text-black">Complaint Submitted</h3>
                                        {caseRef && (
                                            <div className="mb-4 inline-flex items-center gap-2 rounded-full border-2 border-black bg-white/80 px-4 py-2">
                                                <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-black/60">Your Reference</span>
                                                <span className="font-mono text-lg font-bold text-accent">{caseRef}</span>
                                            </div>
                                        )}
                                        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-black/70">Complaint logged for officer review. Save your reference number — you will need it to track your case.</p>
                                    </div>
                                ) : verifyStep === "email" ? (
                                    <div className="py-12 text-center">
                                        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full border-2 border-black bg-white">
                                            <div className="h-8 w-8 animate-spin rounded-full border-4 border-black border-t-transparent" />
                                        </div>
                                        <h3 className="mb-2 text-lg font-semibold uppercase tracking-[0.1em] text-black">Verifying Email Domain</h3>
                                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-black/70">Performing DNS MX exchange lookup on {formData.email}...</p>
                                    </div>
                                ) : verifyStep === "otp" ? (
                                    <div className="py-8">
                                        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full border-2 border-black bg-white">
                                            <Icon name="Shield" size={24} className="text-black" />
                                        </div>
                                        <div className="text-center mb-6">
                                            <h3 className="text-lg font-semibold uppercase tracking-[0.1em] text-black">Verification Code</h3>
                                            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-black/65">
                                                We have sent a verification code to {formData.email}
                                            </p>
                                        </div>
                                        
                                        <div className="mx-auto max-w-sm space-y-4">
                                            <div>
                                                <label className={ThemisNomos_LABEL}>Enter 6-Digit OTP</label>
                                                <input
                                                    type="text"
                                                    maxLength={6}
                                                    value={otpValue}
                                                    onChange={e => setOtpValue(e.target.value.replace(/\D/g, ''))}
                                                    className={`${ThemisNomos_INPUT} text-center text-lg font-bold tracking-widest`}
                                                    placeholder="XXXXXX"
                                                />
                                            </div>
                                            
                                            <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-[0.1em]">
                                                <span className="text-black/60">
                                                    Code expires in: <span className="font-mono text-accent">{Math.floor(otpCountdown / 60)}:{(otpCountdown % 60).toString().padStart(2, '0')}</span>
                                                </span>
                                                <button
                                                    type="button"
                                                    disabled={otpCountdown > 90}
                                                    onClick={handleResendOtp}
                                                    className={`text-accent hover:underline ${otpCountdown > 90 ? "cursor-not-allowed opacity-40" : ""}`}
                                                >
                                                    Resend OTP
                                                </button>
                                            </div>

                                            {error && (
                                                <div className="rounded-xl border-2 border-red-600 bg-red-50 p-3 text-center text-xs font-semibold uppercase tracking-[0.1em] text-red-600">
                                                    {error}
                                                </div>
                                            )}

                                            <div className="flex gap-3">
                                                <button
                                                    type="button"
                                                    onClick={() => setVerifyStep("form")}
                                                    className="w-1/3 rounded-full border-2 border-black bg-white py-3 text-xs font-semibold uppercase tracking-[0.12em] text-black transition-opacity hover:opacity-80"
                                                >
                                                    Cancel
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={handleVerifyOtp}
                                                    className="w-2/3 rounded-full border-2 border-black bg-black py-3 text-xs font-semibold uppercase tracking-[0.12em] text-white transition-opacity hover:opacity-80"
                                                >
                                                    Verify & Submit
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                ) : (
                                    <form onSubmit={handleFormSubmitAttempt} className="space-y-5">
                                        {error && (
                                            <div className="rounded-xl border-2 border-red-600 bg-red-50 p-3 text-center text-xs font-semibold uppercase tracking-[0.1em] text-red-600">
                                                {error}
                                            </div>
                                        )}
                                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                            <div>
                                                <label className={ThemisNomos_LABEL}>Complainant Name *</label>
                                                <input type="text" required value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})}
                                                    className={ThemisNomos_INPUT} placeholder="Full name" />
                                            </div>
                                            <div>
                                                <label className={ThemisNomos_LABEL}>Contact Number *</label>
                                                <input type="tel" required value={formData.contact} onChange={e => setFormData({...formData, contact: e.target.value})}
                                                    className={ThemisNomos_INPUT} placeholder="+91-XXXXXXXXXX" />
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                            <div>
                                                <label className={ThemisNomos_LABEL}>Email Address *</label>
                                                <input type="email" required value={formData.email} onChange={e => setFormData({...formData, email: e.target.value})}
                                                    className={ThemisNomos_INPUT} placeholder="email@example.com" />
                                            </div>
                                            <div>
                                                <label className={ThemisNomos_LABEL}>
                                                    Aadhaar Number *
                                                    <span className="ml-1 font-normal normal-case tracking-normal text-black/50">(12 digits)</span>
                                                </label>
                                                <input type="text" required maxLength={12} inputMode="numeric" pattern="[0-9]{12}"
                                                    value={formData.aadhaar}
                                                    onChange={e => { setFormData({...formData, aadhaar: e.target.value.replace(/\D/g,"")}); setAadhaarError(""); }}
                                                    className={`${ThemisNomos_INPUT} font-mono tracking-widest ${aadhaarError ? "border-red-600" : ""}`}
                                                    placeholder="123412341234" />
                                                {aadhaarError && <p className="mt-1 text-xs font-semibold text-red-600">{aadhaarError}</p>}
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                            <div>
                                                <label className={ThemisNomos_LABEL}>Crime Type</label>
                                                <select value={formData.crime_type} onChange={e => setFormData({...formData, crime_type: e.target.value})}
                                                    className={`${ThemisNomos_INPUT} appearance-none`}>
                                                    <option value="">Select type</option>
                                                    <option value="Cyber Fraud">Cyber Fraud</option>
                                                    <option value="Theft">Theft</option>
                                                    <option value="Assault">Assault</option>
                                                    <option value="Fraud">Fraud</option>
                                                    <option value="Other">Other</option>
                                                </select>
                                            </div>
                                            <div>
                                                <label className={ThemisNomos_LABEL}>Location</label>
                                                <div className="flex gap-2">
                                                    <input type="text" value={formData.location} onChange={e => setFormData({...formData, location: e.target.value})}
                                                        className={`${ThemisNomos_INPUT} flex-1`} placeholder="Bengaluru area" />
                                                    <button
                                                        type="button"
                                                        onClick={handleUseMyLocation}
                                                        disabled={geoStatus === "loading"}
                                                        title="Detect my current location"
                                                        className="flex shrink-0 items-center gap-1.5 border-2 border-ink bg-paper-card px-3 text-[10px] font-bold uppercase tracking-[0.12em] text-ink transition-colors hover:bg-ink hover:text-paper disabled:cursor-not-allowed disabled:opacity-50 font-sans"
                                                    >
                                                        <Icon name={geoStatus === "loading" ? "Clock" : "MapPin"} size={14} />
                                                        {geoStatus === "loading" ? "Locating…" : "Use my location"}
                                                    </button>
                                                </div>
                                                {geoMessage && (
                                                    <p className={`mt-1.5 text-[11px] font-medium ${geoStatus === "ok" ? "text-green-tactical" : geoStatus === "denied" || geoStatus === "error" || geoStatus === "unsupported" ? "text-accent" : "text-ink-muted"}`}>
                                                        {geoMessage}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                        <input type="hidden" value="Online" name="complaint_mode" />
                                        <div>
                                            <label className={ThemisNomos_LABEL}>Incident Description</label>
                                            <textarea value={formData.incident_desc} onChange={e => setFormData({...formData, incident_desc: e.target.value})}
                                                rows={4}
                                                className={`${ThemisNomos_INPUT} resize-none`}
                                                placeholder="Describe the incident in detail..." />
                                        </div>
                                        <button type="submit" disabled={submitting} className={`flex w-full items-center justify-center gap-2 rounded-full border-2 border-black bg-black py-3.5 text-xs font-semibold uppercase tracking-[0.15em] text-white transition-opacity hover:opacity-80 ${submitting ? "cursor-not-allowed opacity-60" : ""}`}>
                                            <Icon name="FilePlus" size={16} />
                                            {submitting ? "Submitting..." : "Submit Complaint"}
                                        </button>
                                    </form>
                                )}
                            </motion.div>
                        )}


                        {/* Browse Cases */}
                        {activeTab === "browse" && (
                            <motion.div variants={fadeUp} custom={2} className={ThemisNomos_CARD}>
                                <div className="mb-8 flex items-center gap-3">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-black bg-white">
                                        <Icon name="Search" size={18} className="text-black" />
                                    </div>
                                    <div>
                                        <h2 className="text-lg font-semibold uppercase tracking-[0.1em] text-black sm:text-xl">Browse Cases</h2>
                                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-black/65 sm:text-xs">Find and select a case to request access</p>
                                    </div>
                                </div>

                                <div className="mb-6 space-y-4">
                                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                                        <div>
                                            <label className={ThemisNomos_LABEL}>Status Filter</label>
                                            <select value={browseCaseFilters.status} onChange={e => handleBrowseCaseFilterChange("status", e.target.value)}
                                                className={ThemisNomos_INPUT}>
                                                <option value="Active">Active Cases</option>
                                                <option value="Solved">Solved Cases</option>
                                                <option value="Closed">Closed Cases</option>
                                                <option value="">All Statuses</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className={ThemisNomos_LABEL}>Crime Type Filter</label>
                                            <select value={browseCaseFilters.crime_type} onChange={e => handleBrowseCaseFilterChange("crime_type", e.target.value)}
                                                className={ThemisNomos_INPUT}>
                                                <option value="">All Crime Types</option>
                                                <option value="Cyber Fraud">Cyber Fraud</option>
                                                <option value="Theft">Theft</option>
                                                <option value="Assault">Assault</option>
                                                <option value="Fraud">Fraud</option>
                                                <option value="Other">Other</option>
                                            </select>
                                        </div>
                                    </div>
                                    <div>
                                        <label className={ThemisNomos_LABEL}>Location Filter</label>
                                        <input type="text" value={browseCaseFilters.location} onChange={e => handleBrowseCaseFilterChange("location", e.target.value)}
                                            className={ThemisNomos_INPUT} placeholder="Search by location..." />
                                    </div>
                                    <div>
                                        <label className={ThemisNomos_LABEL}>Search by Case Title</label>
                                        <input type="text" value={browseCaseFilters.search} onChange={e => handleBrowseCaseFilterChange("search", e.target.value)}
                                            className={ThemisNomos_INPUT} placeholder="Search case details..." />
                                    </div>
                                </div>

                                {browseCaseLoading ? (
                                    <div className="flex items-center justify-center py-12">
                                        <div className="flex flex-col items-center gap-3">
                                            <div className="h-8 w-8 animate-spin rounded-full border-4 border-black/10 border-t-black"></div>
                                            <span className="text-xs font-semibold uppercase tracking-[0.1em] text-black/60">Loading cases...</span>
                                        </div>
                                    </div>
                                ) : browsingCases.length > 0 ? (
                                    <div className="space-y-3 max-h-96 overflow-y-auto">
                                        {browsingCases.map((c) => (
                                            <div
                                                key={c.case_id}
                                                onClick={() => handleSelectCaseForAccess(c.case_id, c.case_id_display)}
                                                className="cursor-pointer rounded-xl border-2 border-black/15 bg-white/60 p-4 transition-all hover:border-black/40 hover:bg-white/90"
                                            >
                                                <div className="mb-2 flex items-start justify-between">
                                                    <div className="flex-1">
                                                        <h3 className="font-mono text-sm font-bold text-accent">{c.case_id_display}</h3>
                                                        <h4 className="mt-1 text-sm font-semibold text-black">{c.title}</h4>
                                                    </div>
                                                    <span className={`ml-3 inline-block whitespace-nowrap rounded-full border-2 px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.1em] ${
                                                        c.status === "Active" ? "border-amber-400 bg-amber-100 text-amber-900" :
                                                        c.status === "Solved" ? "border-emerald-500 bg-emerald-100 text-emerald-900" :
                                                        c.status === "Pending Review" ? "border-blue-400 bg-blue-100 text-blue-900" :
                                                        c.status === "Recommended" ? "border-purple-400 bg-purple-100 text-purple-900" :
                                                        c.status === "Assigned" ? "border-indigo-400 bg-indigo-100 text-indigo-900" :
                                                        c.status === "Rejected" ? "border-red-400 bg-red-100 text-red-900" :
                                                        "border-black/20 bg-black/5 text-black/60"
                                                    }`}>
                                                        {c.status}
                                                    </span>
                                                </div>
                                                <div className="flex flex-wrap items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-black/60">
                                                    <span className="flex items-center gap-1">
                                                        <Icon name="Shield" size={12} /> {c.crime_type}
                                                    </span>
                                                    <span className="flex items-center gap-1">
                                                        <Icon name="MapPin" size={12} /> {c.location}
                                                    </span>
                                                    <span className="flex items-center gap-1">
                                                        <Icon name="Calendar" size={12} /> {c.date_reported ? new Date(c.date_reported).toLocaleDateString() : "N/A"}
                                                    </span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="flex items-center justify-center py-12">
                                        <div className="text-center">
                                            <Icon name="Search" size={32} className="mx-auto mb-3 text-black/30" />
                                            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-black/60">No cases found. Try adjusting your filters.</p>
                                        </div>
                                    </div>
                                )}
                                {browseCaseTotalPages > 1 && (
                                    <div className="mt-3 flex items-center justify-center gap-2">
                                        <button
                                            onClick={() => setBrowseCasePage(p => Math.max(1, p - 1))}
                                            disabled={browseCasePage === 1 || browseCaseLoading}
                                            className="rounded-full border-2 border-black/20 px-3 py-1 text-[10px] disabled:opacity-50"
                                        >
                                            ←
                                        </button>
                                        <span className="text-xs text-black/60">Page {browseCasePage} of {browseCaseTotalPages}</span>
                                        <button
                                            onClick={() => setBrowseCasePage(p => Math.min(browseCaseTotalPages, p + 1))}
                                            disabled={browseCasePage === browseCaseTotalPages || browseCaseLoading}
                                            className="rounded-full border-2 border-black/20 px-3 py-1 text-[10px] disabled:opacity-50"
                                        >
                                            →
                                        </button>
                                    </div>
                                )}
                            </motion.div>
                        )}

                        {/* Access Request Form */}
                        {activeTab === "access" && (
                            <motion.div variants={fadeUp} custom={2} className={ThemisNomos_CARD}>
                                <div className="mb-8 flex items-center gap-3">
                                    <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-black bg-white">
                                        <Icon name="Eye" size={18} className="text-accent" />
                                    </div>
                                    <div>
                                        <h2 className="text-lg font-semibold uppercase tracking-[0.1em] text-black sm:text-xl">Request Case Access</h2>
                                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-black/65 sm:text-xs">Request read access to case information</p>
                                    </div>
                                </div>

                                {accessSubmitted ? (
                                    <div className="py-12 text-center">
                                        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border-2 border-black bg-white">
                                            <Icon name="CheckCircle" size={28} className="text-accent" />
                                        </div>
                                        <h3 className="mb-2 text-lg font-semibold uppercase tracking-[0.1em] text-black">Request Submitted</h3>
                                        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-black/70">Your access request is under review. You will be notified via email.</p>
                                    </div>
                                ) : (
                                    <form onSubmit={handleAccessSubmit} className="space-y-5">
                                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                            <div>
                                                <label className={ThemisNomos_LABEL}>Case ID *</label>
                                                <input type="text" required value={accessForm.case_id} onChange={e => setAccessForm({...accessForm, case_id: e.target.value})}
                                                    className={`${ThemisNomos_INPUT} font-mono`} placeholder="e.g. BLR-001" />
                                            </div>
                                            <div>
                                                <label className={ThemisNomos_LABEL}>Contact Number *</label>
                                                <input type="tel" required value={accessForm.requester_number} onChange={e => setAccessForm({...accessForm, requester_number: e.target.value})}
                                                    className={ThemisNomos_INPUT} placeholder="+91-XXXXXXXXXX" />
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                                            <div>
                                                <label className={ThemisNomos_LABEL}>Your Name *</label>
                                                <input type="text" required value={accessForm.requester_name} onChange={e => setAccessForm({...accessForm, requester_name: e.target.value})}
                                                    className={ThemisNomos_INPUT} placeholder="Full name" />
                                            </div>
                                            <div>
                                                <label className={ThemisNomos_LABEL}>Email *</label>
                                                <input type="email" required value={accessForm.requester_email} onChange={e => setAccessForm({...accessForm, requester_email: e.target.value})}
                                                    className={ThemisNomos_INPUT} placeholder="email@example.com" />
                                            </div>
                                        </div>
                                        <div>
                                            <label className={ThemisNomos_LABEL}>Reason for Access *</label>
                                            <textarea required value={accessForm.reason} onChange={e => setAccessForm({...accessForm, reason: e.target.value})}
                                                rows={3}
                                                className={`${ThemisNomos_INPUT} resize-none`}
                                                placeholder="Explain why you need access to this case..." />
                                        </div>
                                        {error && (
                                            <div className="flex items-center gap-2 rounded-xl border-2 border-red-600/40 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                                                <Icon name="AlertTriangle" size={14} /> {error}
                                            </div>
                                        )}
                                        <button type="submit" disabled={submitting} className={`flex w-full items-center justify-center gap-2 rounded-full border-2 border-black bg-black py-3.5 text-xs font-semibold uppercase tracking-[0.15em] text-white transition-opacity hover:opacity-80 ${submitting ? "cursor-not-allowed opacity-60" : ""}`}>
                                            <Icon name={submitting ? "Clock" : "Eye"} size={16} />
                                            {submitting ? "Submitting Request..." : "Submit Access Request"}
                                        </button>
                                    </form>
                                )}
                            </motion.div>
                        )}
                    </motion.div>

                    {/* LEGAL DISCLAIMER MODAL */}
                    <AnimatePresence>
                        {showDisclaimer && (
                            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
                                <motion.div
                                    className={`max-w-md w-full ${ThemisNomos_CARD}`}
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.95 }}
                                    transition={{ duration: 0.2 }}
                                >
                                    <div className="mb-4 flex items-center gap-3 border-b-2 border-black/10 pb-4">
                                        <div className="flex h-10 w-10 items-center justify-center rounded-full border-2 border-red-600 bg-red-50 text-red-600">
                                            <Icon name="AlertTriangle" size={18} />
                                        </div>
                                        <div>
                                            <h3 className="text-sm font-bold uppercase tracking-[0.1em] text-red-600">Legal Notice</h3>
                                            <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-black/60">Bengaluru Police Department</p>
                                        </div>
                                    </div>
                                    <p className="mb-6 text-xs leading-relaxed text-black/80 font-medium">
                                        Filing a false or fabricated police complaint is a criminal offence punishable under Section 182 of the Indian Penal Code (IPC) and Section 211 IPC, which may result in imprisonment of up to 7 years and/or a fine. Please confirm that all information provided is accurate and truthful to the best of your knowledge.
                                    </p>
                                    <div className="flex justify-end gap-3">
                                        <button
                                            type="button"
                                            onClick={handleDisclaimerReject}
                                            className="rounded-full border-2 border-black bg-white px-5 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-black transition-opacity hover:opacity-80"
                                        >
                                            No, Wait
                                        </button>
                                        <button
                                            type="button"
                                            onClick={handleDisclaimerAccept}
                                            className="rounded-full border-2 border-black bg-red-600 px-5 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-white transition-opacity hover:opacity-80"
                                        >
                                            Yes, Proceed
                                        </button>
                                    </div>
                                </motion.div>
                            </div>
                        )}
                    </AnimatePresence>
                </CrmsPageShell>

            );
        };

