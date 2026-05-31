        // ─── APP ──────────────────────────────────────────────────────────────
        const App = () => {
            const storedOfficer = getStoredOfficer();
            const storedPublicComplaintDraft = getPublicComplaintDraft();
            // A draft is "live" if:
            //   (a) it has an active OTP step that hasn't expired yet, OR
            //   (b) it was saved within the last 2 hours (user was actively filling the form)
            const isDraftLive = (() => {
                if (!storedPublicComplaintDraft) return false;
                const { verifyStep, otpExpiresAt, savedAt } = storedPublicComplaintDraft;
                if (verifyStep === "otp" && otpExpiresAt && otpExpiresAt > Date.now()) return true;
                const TWO_HOURS = 2 * 60 * 60 * 1000;
                if (savedAt && (Date.now() - savedAt) < TWO_HOURS) return true;
                // Stale draft — clean it up silently
                clearPublicComplaintDraft();
                return false;
            })();
            const [currentView, setCurrentView] = useState(() => {
                const persistedView = localStorage.getItem("CRMS_CURRENT_VIEW");
                if (persistedView) {
                    if (storedOfficer) {
                        if (persistedView === "admin" || persistedView === "staff") return persistedView;
                        return (storedOfficer.role || "").toLowerCase() === "admin" ? "admin" : "staff";
                    } else {
                        if (persistedView === "public" || persistedView === "login" || persistedView === "landing") return persistedView;
                        if (isDraftLive) return "public";
                        return "landing";
                    }
                }
                if (storedOfficer) {
                    return (storedOfficer.role || "").toLowerCase() === "admin" ? "admin" : "staff";
                }
                if (isDraftLive) return "public";
                return "landing";
            });
            useEffect(() => {
                localStorage.setItem("CRMS_CURRENT_VIEW", currentView);
            }, [currentView]);
            const [officer, setOfficer]         = useState(() => storedOfficer);

            // Map DB role to legacy P1/P2 gate the dashboard already uses
            const userRole = officer?.role === "inspector" ? "P1" : "P2";

            const handleLogin = (officerData) => {
                storeOfficerSession(officerData);
                setOfficer(officerData);
                // Route to admin dashboard if role is admin, otherwise to staff dashboard
                const targetView = (officerData.role || "").toLowerCase() === "admin" ? "admin" : "staff";
                setCurrentView(targetView);
            };

            const handleLogout = async () => {
                const activeOfficer = officer || getStoredOfficer();
                if (activeOfficer?.officer_id && activeOfficer?.session_token) {
                    try {
                        await apiFetch("/auth/logout", {
                            method: "POST",
                            body: JSON.stringify({
                                officer_id: activeOfficer.officer_id,
                                session_token: activeOfficer.session_token
                            })
                        });
                    } catch (err) {
                        console.warn("Logout request failed:", err.message);
                    }
                }
                clearOfficerSession();
                setOfficer(null);
                setCurrentView("landing");
            };

            return (
                <div className="min-h-screen">
                    <AnimatePresence mode="wait">
                        {currentView === "landing" && (
                            <motion.div key="landing" className="min-h-[100dvh]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.5 }}>
                                <LandingPage onNavigate={setCurrentView} officer={officer} />
                            </motion.div>
                        )}
                        {currentView === "public" && (
                            <motion.div key="public" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}>
                                <PublicPortal onNavigate={setCurrentView} />
                            </motion.div>
                        )}
                        {currentView === "login" && (
                            <motion.div key="login" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} transition={{ duration: 0.4 }}>
                                <LoginPage onLogin={handleLogin} onBack={() => setCurrentView("landing")} />
                            </motion.div>
                        )}
                        {currentView === "admin" && officer && (
                            <motion.div key="admin" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.4 }}>
                                <AdminDashboard officer={officer} onLogout={handleLogout} onNavigate={setCurrentView} />
                            </motion.div>
                        )}
                        {currentView === "staff" && officer && (
                            <motion.div key="staff" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} transition={{ duration: 0.4 }}>
                                <StaffDashboard onNavigate={setCurrentView} userRole={userRole} officer={officer} onLogout={handleLogout} />
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            );
        };

        const root = ReactDOM.createRoot(document.getElementById("root"));
        root.render(<App />);
