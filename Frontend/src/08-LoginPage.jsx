        // ─── LOGIN PAGE ───────────────────────────────────────────────────────
        const LoginPage = ({ onLogin, onBack }) => {
            const [badgeId, setBadgeId]         = useState("");
            const [password, setPassword]       = useState("");
            const [error, setError]             = useState("");
            const [loading, setLoading]         = useState(false);
            const [showForceLogin, setShowForceLogin] = useState(false);

            const handleLogin = async (e, force = false) => {
                if (e && e.preventDefault) e.preventDefault();
                setError("");
                setLoading(true);
                try {
                    // Get CAPTCHA token
                    const captchaToken = await executeRecaptcha("login");
                    if (!captchaToken) {
                        setError("CAPTCHA verification is required to log in");
                        return;
                    }
                    const res = await apiFetch("/auth/login", {
                        method: "POST",
                        body: JSON.stringify({ badge_id: badgeId, password, captcha_token: captchaToken, force }),
                    });
                    setShowForceLogin(false);
                    onLogin(res.officer || res.data);
                } catch (err) {
                    const msg = err.message || "Invalid credentials";
                    setError(msg);
                    // If the server says "already logged in on another device", offer force login
                    if (msg.toLowerCase().includes("already logged in")) {
                        setShowForceLogin(true);
                    } else {
                        setShowForceLogin(false);
                    }
                } finally {
                    setLoading(false);
                }
            };

            const handleForceLogin = async () => {
                await handleLogin(null, true);
            };

            return (
                <CrmsPageShell
                    title="Staff Login"
                    subtitle="Bengaluru Police Department · Themis's Domain"
                    onBack={onBack}
                    scrim="bg-white/45"
                    className="flex flex-col"
                >
                    <div className="flex flex-1 items-center justify-center px-5 py-12">
                        <motion.div
                            className={`w-full max-w-md ${ThemisNomos_CARD}`}
                            initial={{ opacity: 0, y: 24 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                        >
                            <div className="mb-10 text-center">
                                <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full border-2 border-ink bg-paper-card">
                                    <Icon name="Shield" size={24} className="text-accent" />
                                </div>
                                <p className="kicker mb-2">Authorised Personnel Only</p>
                                <h1 className="headline mb-2 text-3xl sm:text-4xl">Staff Login</h1>
                                <div className="rule-hair mx-auto mt-3 w-16" />
                                <p className="mt-3 font-editorial text-sm italic text-ink-muted">Secure officer access</p>
                            </div>

                            <form onSubmit={handleLogin} className="space-y-5">
                                <div>
                                    <label className={ThemisNomos_LABEL}>Officer Badge ID</label>
                                    <input autoFocus type="text" required value={badgeId}
                                        onChange={e => { setBadgeId(e.target.value); setShowForceLogin(false); }}
                                        className={`${ThemisNomos_INPUT} font-mono`}
                                        placeholder="e.g., BPD-7821" />
                                </div>
                                <div>
                                    <label className={ThemisNomos_LABEL}>Password</label>
                                    <input type="password" required value={password}
                                        onChange={e => { setPassword(e.target.value); setShowForceLogin(false); }}
                                        className={ThemisNomos_INPUT}
                                        placeholder="••••••••" />
                                </div>
                                {error && (
                                    <div className="flex items-center gap-2 border-l-4 border-red-warn bg-red-warn/5 px-4 py-3 text-xs font-semibold text-red-warn font-sans">
                                        <Icon name="AlertTriangle" size={14} /> {error}
                                    </div>
                                )}
                                <button type="submit" disabled={loading}
                                    className={`flex w-full items-center justify-center gap-2 border-2 border-ink bg-ink-black py-3.5 text-xs font-bold uppercase tracking-[0.18em] text-paper transition-colors hover:bg-accent hover:border-accent font-sans ${loading ? "cursor-not-allowed opacity-60" : ""}`}>
                                    <Icon name={loading ? "Clock" : "Lock"} size={16} />
                                    {loading ? "Authenticating..." : "Sign In"}
                                </button>
                            </form>

                            {showForceLogin && (
                                <motion.div
                                    initial={{ opacity: 0, y: 8 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.3 }}
                                    className="mt-5 rounded-xl border-2 border-amber-400 bg-amber-50 p-4"
                                >
                                    <div className="mb-3 flex items-start gap-3">
                                        <Icon name="AlertTriangle" size={16} className="mt-0.5 shrink-0 text-amber-700" />
                                        <div>
                                            <p className="text-xs font-bold uppercase tracking-[0.1em] text-amber-900">Already signed in elsewhere</p>
                                            <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-amber-800/80">
                                                This badge is currently active on another device or browser tab. You can force sign out those sessions and sign in here instead.
                                            </p>
                                        </div>
                                    </div>
                                    <button
                                        type="button"
                                        disabled={loading}
                                        onClick={handleForceLogin}
                                        className={`flex w-full items-center justify-center gap-2 rounded-full border-2 border-amber-600 bg-amber-600 py-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-white transition-opacity hover:opacity-80 ${loading ? "cursor-not-allowed opacity-60" : ""}`}
                                    >
                                        <Icon name={loading ? "Clock" : "LogIn"} size={14} />
                                        {loading ? "Signing in..." : "Log Out Other Devices & Sign In Here"}
                                    </button>
                                </motion.div>
                            )}

                            <div className="mt-8 rounded-xl border-2 border-black/15 bg-white/60 p-4">
                                <p className="mb-2 text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-black/50">Development credentials</p>
                                <p className="text-center text-xs font-medium text-black/80">Badge: <span className="font-mono font-semibold">BPD-7821</span> · Password: <span className="font-mono font-semibold">crms1234</span></p>
                                <p className="mt-1 text-center text-[10px] font-semibold uppercase tracking-[0.1em] text-black/50">(Inspector = read+write · Sub-Inspector = read only)</p>
                            </div>
                        </motion.div>
                    </div>
                </CrmsPageShell>
            );
        };

