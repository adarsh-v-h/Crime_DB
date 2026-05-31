        // ─── ADMIN DASHBOARD ──────────────────────────────────────────────────
        const AdminDashboard = ({ officer, onLogout, onNavigate }) => {
            const [dashboardStats, setDashboardStats] = useState(null);
            const [allCases, setAllCases] = useState([]);
            const [selectedCase, setSelectedCase] = useState(null);
            const [caseOfficers, setCaseOfficers] = useState([]);
            const [availableOfficers, setAvailableOfficers] = useState([]);
            const [loading, setLoading] = useState(false);
            const [error, setError] = useState(null);
            const [activeTab, setActiveTab] = useState("overview");
            const [statusFilter, setStatusFilter] = useState("All");
            const [currentPage, setCurrentPage] = useState(1);
            const [totalPages, setTotalPages] = useState(1);
            const [totalRecords, setTotalRecords] = useState(0);
            const [reassignLoading, setReassignLoading] = useState(false);
            const [reassignError, setReassignError] = useState(null);
            const [selectedOfficerToAdd, setSelectedOfficerToAdd] = useState(null);
            const [dossierLoading, setDossierLoading] = useState(false);
            const [dossierMessage, setDossierMessage] = useState(null);
            const [dossierError, setDossierError] = useState(null);
            const [modalTab, setModalTab] = useState("details");
            const [timelineUpdates, setTimelineUpdates] = useState([]);
            const [evidenceItems, setEvidenceItems] = useState([]);
            const [newUpdateText, setNewUpdateText] = useState("");
            const [evidenceFile, setEvidenceFile] = useState(null);
            const [evidenceDesc, setEvidenceDesc] = useState("");
            const isAdmin = () => (officer?.role || "").toLowerCase() === "admin";
            const itemsPerPage = 10;

            const loadDashboardStats = async () => {
                setLoading(true);
                try {
                    const res = await apiFetch("/admin/dashboard", {
                        headers: { "X-Officer-Id": officer?.officer_id?.toString() }
                    });
                    if (res.success) {
                        setDashboardStats(res.data);
                    } else {
                        setError(res.error || "Failed to load dashboard");
                    }
                } catch (err) {
                    setError(err.message);
                } finally {
                    setLoading(false);
                }
            };

            const loadAllCases = async () => {
                setLoading(true);
                try {
                    const params = new URLSearchParams({
                        page: currentPage,
                        limit: itemsPerPage,
                    });
                    if (statusFilter !== "All") params.append("status", statusFilter);
                    const url = `/admin/cases?${params.toString()}`;
                    const res = await apiFetch(url, {
                        headers: { "X-Officer-Id": officer?.officer_id?.toString() }
                    });
                    if (res.success) {
                        setAllCases(res.data || []);
                        if (res.pagination) {
                            setTotalPages(res.pagination.total_pages || 1);
                            setTotalRecords(res.pagination.total_records || 0);
                        }
                    } else {
                        setError(res.error || "Failed to load cases");
                    }
                } catch (err) {
                    setError(err.message);
                } finally {
                    setLoading(false);
                }
            };

            const loadCaseOfficers = async (caseId) => {
                try {
                    const res = await apiFetch(`/cases/${caseId}/officers`, {
                        headers: { "X-Officer-Id": officer?.officer_id?.toString() }
                    });
                    if (res.success) {
                        setCaseOfficers(res.data?.officers || []);
                    } else {
                        setReassignError("Failed to load assigned officers");
                    }
                } catch (err) {
                    setReassignError(err.message);
                }
            };

            const loadAvailableOfficers = async (caseId) => {
                try {
                    const res = await apiFetch(`/officers/available?case_id=${caseId}`, {
                        headers: { "X-Officer-Id": officer?.officer_id?.toString() }
                    });
                    if (res.success) {
                        setAvailableOfficers(res.data || []);
                    }
                } catch (err) {
                    console.error("Failed to load available officers:", err.message);
                }
            };

            const handleAddOfficer = async (caseId, newOfficerId) => {
                setReassignLoading(true);
                setReassignError(null);
                try {
                    const res = await apiFetch("/case-officer/add", {
                        method: "POST",
                        headers: { "X-Officer-Id": officer?.officer_id?.toString() },
                        body: JSON.stringify({ case_id: caseId, officer_id: newOfficerId })
                    });
                    if (res.success) {
                        await loadCaseOfficers(caseId);
                        await loadAvailableOfficers(caseId);
                        setSelectedOfficerToAdd(null);
                    } else {
                        setReassignError(res.message || "Failed to add officer");
                    }
                } catch (err) {
                    setReassignError(err.message);
                } finally {
                    setReassignLoading(false);
                }
            };

            const handleRemoveOfficer = async (caseId, officerId) => {
                if (!confirm("Remove this officer from the case? They will be notified by email.")) return;
                setReassignLoading(true);
                setReassignError(null);
                try {
                    const res = await apiFetch("/case-officer/remove", {
                        method: "POST",
                        headers: { "X-Officer-Id": officer?.officer_id?.toString() },
                        body: JSON.stringify({ case_id: caseId, officer_id: officerId })
                    });
                    if (res.success) {
                        await loadCaseOfficers(caseId);
                        await loadAvailableOfficers(caseId);
                    } else {
                        setReassignError(res.message || "Failed to remove officer");
                    }
                } catch (err) {
                    setReassignError(err.message);
                } finally {
                    setReassignLoading(false);
                }
            };

            const handleRequestDossier = async (caseId) => {
                setDossierLoading(true);
                setDossierMessage(null);
                setDossierError(null);
                try {
                    const response = await apiFetch(`/cases/${caseId}/request-dossier`, {
                        method: "POST",
                        headers: {
                            "X-Officer-Id": officer?.officer_id?.toString()
                        }
                    });
                    if (response.success) {
                        setDossierMessage(response.message || "Updated case dossier has been requested and will be emailed to you shortly.");
                        setTimeout(() => setDossierMessage(null), 5000);
                    } else {
                        setDossierError(response.error || "Failed to request updated dossier");
                        setTimeout(() => setDossierError(null), 5000);
                    }
                } catch (err) {
                    setDossierError(err.message || "Failed to request updated dossier");
                    setTimeout(() => setDossierError(null), 5000);
                } finally {
                    setDossierLoading(false);
                }
            };

            // Fetch case timeline updates
            const loadCaseTimeline = async (caseId) => {
                try {
                    const res = await apiFetch(`/cases/${caseId}/updates`, {
                        headers: { "X-Officer-Id": officer?.officer_id?.toString() }
                    });
                    if (res.success) {
                        setTimelineUpdates(res.data || []);
                    }
                } catch (err) {
                    console.error("Failed to load timeline updates:", err.message);
                }
            };

            // Fetch case evidence
            const loadCaseEvidence = async (caseId) => {
                try {
                    const res = await apiFetch(`/cases/${caseId}/evidence`, {
                        headers: { "X-Officer-Id": officer?.officer_id?.toString() }
                    });
                    if (res.success) {
                        setEvidenceItems(res.data || []);
                    }
                } catch (err) {
                    console.error("Failed to load evidence:", err.message);
                }
            };

            // Add timeline update
            const handleAddTimelineUpdate = async (caseId) => {
                if (!newUpdateText.trim()) return;
                setDossierLoading(true); // Reuse loading spinners safely
                setActionError(null);
                try {
                    const res = await apiFetch(`/cases/${caseId}/updates`, {
                        method: "POST",
                        headers: { 
                            "Content-Type": "application/json",
                            "X-Officer-Id": officer?.officer_id?.toString() 
                        },
                        body: JSON.stringify({ update_text: newUpdateText })
                    });
                    if (res.success) {
                        setNewUpdateText("");
                        await loadCaseTimeline(caseId);
                    } else {
                        setActionError(res.error || "Failed to add timeline update");
                    }
                } catch (err) {
                    setActionError(err.message);
                } finally {
                    setDossierLoading(false);
                }
            };

            // Upload evidence file
            const handleUploadEvidence = async (caseId) => {
                if (!evidenceFile) return;
                setDossierLoading(true);
                setActionError(null);
                try {
                    const formData = new FormData();
                    formData.append("file", evidenceFile);
                    if (evidenceDesc.trim()) {
                        formData.append("description", evidenceDesc);
                    }

                    const response = await fetch(`${API_BASE}/cases/${caseId}/evidence`, {
                        method: "POST",
                        headers: {
                            ...authHeaders(officer)
                        },
                        body: formData
                    });
                    const res = await response.json();
                    if (!response.ok && response.status === 401 && String(res.error || "").toLowerCase().includes("session")) {
                        clearOfficerSession();
                    }
                    if (response.ok && res.success) {
                        setEvidenceFile(null);
                        setEvidenceDesc("");
                        const fileInput = document.getElementById("evidence-file-input");
                        if (fileInput) fileInput.value = "";
                        await loadCaseEvidence(caseId);
                    } else {
                        setActionError(res.error || "Upload failed");
                    }
                } catch (err) {
                    setActionError(err.message);
                } finally {
                    setDossierLoading(false);
                }
            };

            // Delete evidence
            const handleDeleteEvidence = async (caseId, evidenceId) => {
                if (!confirm("Are you sure you want to permanently delete this evidence item? This will also remove the physical file from the server.")) return;
                setDossierLoading(true);
                setActionError(null);
                try {
                    const res = await apiFetch(`/cases/evidence/${evidenceId}`, {
                        method: "DELETE",
                        headers: {
                            "X-Officer-Id": officer?.officer_id?.toString()
                        }
                    });
                    if (res.success) {
                        await loadCaseEvidence(caseId);
                    } else {
                        setActionError(res.error || "Failed to delete evidence");
                    }
                } catch (err) {
                    setActionError(err.message);
                } finally {
                    setDossierLoading(false);
                }
            };

            // State variable for action errors
            const [actionError, setActionError] = useState(null);

            useEffect(() => {
                if (selectedCase) {
                    loadCaseOfficers(selectedCase.case_id);
                    loadAvailableOfficers(selectedCase.case_id);
                    setReassignError(null);
                    if (modalTab === "timeline") {
                        loadCaseTimeline(selectedCase.case_id);
                    } else if (modalTab === "evidence") {
                        loadCaseEvidence(selectedCase.case_id);
                    }
                } else {
                    setModalTab("details");
                }
            }, [selectedCase, modalTab]);

            useEffect(() => {
                loadDashboardStats();
                loadAllCases();
            }, [statusFilter, currentPage]);

            // Server-side pagination — `allCases` already holds only the current page,
            // and totalPages comes from the API response.
            const paginatedCases = allCases;

            return (
                <CrmsPageShell
                    title="Bengaluru Police · Administration"
                    subtitle="System Administrator Dashboard"
                    onBack={() => onNavigate("landing")}
                    scrim="bg-white/42"
                >
                    <div className="border-b-2 border-ink/80 bg-paper/85 backdrop-blur-sm">
                        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-5 py-3 sm:px-8">
                            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-muted font-sans sm:text-xs">
                                Administrator: <span className="text-ink-black">{officer?.name || "UNKNOWN"}</span>
                                <span className="text-accent"> (ADMIN)</span>
                            </div>
                            <button
                                type="button"
                                onClick={onLogout}
                                className="border-2 border-ink bg-ink-black px-4 py-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-paper transition-colors hover:bg-accent hover:border-accent sm:text-xs font-sans"
                            >
                                Sign Out
                            </button>
                        </div>
                    </div>

                    <motion.div
                        className="mx-auto max-w-[1600px] space-y-6 p-5 sm:p-6 lg:p-8"
                        initial="hidden"
                        animate="visible"
                        variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.06 } } }}
                    >
                        {/* SECTION TITLE */}
                        <motion.div variants={fadeUp} custom={0} className="border-b-2 border-ink/80 pb-4">
                            <p className="kicker mb-1">Administration · Command Room</p>
                            <h2 className="headline text-3xl sm:text-4xl md:text-5xl">The Bureau Ledger</h2>
                        </motion.div>

                        {/* TAB NAVIGATION */}
                        <motion.div variants={fadeUp} custom={0} className="mb-6 flex flex-wrap gap-6 border-b border-ink/20 sm:gap-8">
                            <button
                                type="button"
                                onClick={() => setActiveTab("overview")}
                                className={`pb-3 text-[10px] font-bold uppercase tracking-[0.16em] transition-all border-b-2 sm:text-xs font-sans ${
                                    activeTab === "overview"
                                        ? "border-accent text-ink-black"
                                        : "border-transparent text-ink/50 hover:text-accent"
                                }`}
                            >
                                Dashboard Overview
                            </button>
                            <button
                                type="button"
                                onClick={() => setActiveTab("cases")}
                                className={`pb-3 text-[10px] font-bold uppercase tracking-[0.16em] transition-all border-b-2 sm:text-xs font-sans ${
                                    activeTab === "cases"
                                        ? "border-accent text-ink-black"
                                        : "border-transparent text-ink/50 hover:text-accent"
                                }`}
                            >
                                All Cases
                            </button>
                        </motion.div>

                        {/* OVERVIEW TAB */}
                        {activeTab === "overview" && (
                            <>
                                {loading ? (
                                    <motion.div variants={fadeUp} className={`${ThemisNomos_CARD} p-8 text-center text-ink-muted font-editorial italic`}>
                                        Loading dashboard...
                                    </motion.div>
                                ) : error ? (
                                    <motion.div variants={fadeUp} className="flex items-center gap-2 border-l-4 border-red-warn bg-red-warn/5 px-4 py-3 text-xs font-semibold text-red-warn font-sans">
                                        <Icon name="AlertTriangle" size={14} />
                                        <span>{error}</span>
                                    </motion.div>
                                ) : dashboardStats ? (
                                    <>
                                        {/* STATISTICS — editorial fact blocks / pull quotes */}
                                        <div className="grid gap-px border border-ink/20 bg-ink/20 sm:grid-cols-2 lg:grid-cols-4">
                                            <motion.div variants={fadeUp} custom={1} className="bg-paper-card p-5">
                                                <div className="eyebrow">Total Cases</div>
                                                <div className="pull-quote mt-2 text-5xl text-ink-black">{dashboardStats.cases?.total || 0}</div>
                                            </motion.div>
                                            <motion.div variants={fadeUp} custom={2} className="bg-paper-card p-5">
                                                <div className="eyebrow">Active Cases</div>
                                                <div className="pull-quote mt-2 text-5xl text-accent">{dashboardStats.cases?.active || 0}</div>
                                            </motion.div>
                                            <motion.div variants={fadeUp} custom={3} className="bg-paper-card p-5">
                                                <div className="eyebrow">Solved Cases</div>
                                                <div className="pull-quote mt-2 text-5xl text-green-tactical">{dashboardStats.cases?.solved || 0}</div>
                                            </motion.div>
                                            <motion.div variants={fadeUp} custom={4} className="bg-paper-card p-5">
                                                <div className="eyebrow">Total Officers</div>
                                                <div className="pull-quote mt-2 text-5xl text-blue-electric">{dashboardStats.officers?.total || 0}</div>
                                            </motion.div>
                                        </div>

                                        {/* OFFICER WORKLOAD */}
                                        <motion.div variants={fadeUp} custom={5} className={`${ThemisNomos_CARD} p-6`}>
                                            <div className="mb-4 text-xs font-semibold uppercase tracking-[0.14em] text-black">Officer Workload</div>
                                            <div className="space-y-3">
                                                {(dashboardStats.officer_workload || []).slice(0, 5).map((off, idx) => (
                                                    <div key={off.officer_id} className="flex items-center justify-between border-b border-black/10 pb-2 last:border-0">
                                                        <div>
                                                            <div className="text-xs font-semibold text-black">{off.name}</div>
                                                            <div className="text-[10px] text-black/60">{off.rank} · {off.role}</div>
                                                        </div>
                                                        <div className="text-right">
                                                            <div className="text-sm font-bold text-accent">{off.case_count || 0}</div>
                                                            <div className="text-[10px] text-black/60">Cases</div>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </motion.div>
                                    </>
                                ) : null}
                            </>
                        )}

                        {/* CASES TAB */}
                        {activeTab === "cases" && (
                            <>
                                <motion.div variants={fadeUp} custom={1} className={`${ThemisNomos_CARD} flex flex-col gap-4 p-4 md:flex-row`}>
                                    <select
                                        value={statusFilter}
                                        onChange={(e) => {
                                            setStatusFilter(e.target.value);
                                            setCurrentPage(1);
                                        }}
                                        className={`${ThemisNomos_INPUT} w-full md:w-auto py-2.5 text-[10px] uppercase tracking-[0.1em]`}
                                    >
                                        <option value="All">Status: All</option>
                                        <option value="Pending Review">Pending Review</option>
                                        <option value="Recommended">Recommended</option>
                                        <option value="Assigned">Assigned</option>
                                        <option value="Active">Active</option>
                                        <option value="Solved">Solved</option>
                                        <option value="Closed">Closed</option>
                                        <option value="Rejected">Rejected</option>
                                    </select>
                                </motion.div>

                                {error && (
                                    <div className="flex items-center gap-2 rounded-xl border-2 border-red-600/40 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                                        <Icon name="AlertTriangle" size={14} />
                                        <span>{error}</span>
                                    </div>
                                )}

                                {loading ? (
                                    <motion.div variants={fadeUp} className={`${ThemisNomos_CARD} p-8 text-center text-black/60`}>
                                        Loading cases...
                                    </motion.div>
                                ) : (
                                    <>
                                        <motion.div variants={fadeUp} className="space-y-3">
                                            {paginatedCases.length > 0 ? (
                                                paginatedCases.map((c) => (
                                                    <motion.div
                                                        key={c.case_id}
                                                        className={`${ThemisNomos_CARD} cursor-pointer p-4 transition-all hover:shadow-lg`}
                                                        onClick={() => setSelectedCase(c)}
                                                        whileHover={{ scale: 1.01 }}
                                                    >
                                                        <div className="flex items-start justify-between">
                                                            <div className="flex-1">
                                                                <div className="text-xs font-bold uppercase tracking-[0.12em] text-accent">BLR-{String(c.case_id).padStart(3, "0")}</div>
                                                                <div className="mt-1 text-sm font-semibold text-black">{c.title}</div>
                                                                <div className="mt-1 text-xs text-black/60">{c.location}</div>
                                                            </div>
                                                                                                                         <div className={`rounded-full px-3 py-1 text-[10px] font-bold uppercase tracking-[0.08em] ${
                                                                 c.status === "Active" ? "border border-amber-500 bg-amber-50 text-amber-900" :
                                                                 c.status === "Solved" ? "border border-emerald-600 bg-emerald-50 text-emerald-900" :
                                                                 c.status === "Pending Review" ? "border border-blue-500 bg-blue-50 text-blue-900" :
                                                                 c.status === "Recommended" ? "border border-purple-500 bg-purple-50 text-purple-900" :
                                                                 c.status === "Assigned" ? "border border-indigo-500 bg-indigo-50 text-indigo-900" :
                                                                 c.status === "Rejected" ? "border border-red-500 bg-red-50 text-red-900" :
                                                                 "border border-black/20 bg-black/5 text-black/60"
                                                             }`}>
                                                                {c.status}
                                                            </div>
                                                        </div>
                                                    </motion.div>
                                                ))
                                            ) : (
                                                <motion.div variants={fadeUp} className={`${ThemisNomos_CARD} p-8 text-center text-black/60`}>
                                                    No cases found.
                                                </motion.div>
                                            )}
                                        </motion.div>

                                        {/* PAGINATION */}
                                        {totalPages > 1 && (
                                            <motion.div variants={fadeUp} className="flex items-center justify-center gap-2">
                                                <button
                                                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                                                    disabled={currentPage === 1}
                                                    className="rounded-full border-2 border-black/20 px-3 py-1 text-[10px] disabled:opacity-50"
                                                >
                                                    ←
                                                </button>
                                                <span className="text-xs text-black/60">Page {currentPage} of {totalPages}</span>
                                                <button
                                                    onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                                                    disabled={currentPage === totalPages}
                                                    className="rounded-full border-2 border-black/20 px-3 py-1 text-[10px] disabled:opacity-50"
                                                >
                                                    →
                                                </button>
                                            </motion.div>
                                        )}
                                    </>
                                )}
                            </>
                        )}
                    </motion.div>

                    {/* CASE DETAIL MODAL */}
                    <AnimatePresence>
                        {selectedCase && (
                            <motion.div
                                className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 overflow-y-auto"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                onClick={() => setSelectedCase(null)}
                            >
                                <motion.div
                                    className={`${ThemisNomos_CARD} w-full max-w-3xl my-8 overflow-y-auto max-h-[85vh] p-6`}
                                    initial={{ scale: 0.9, opacity: 0 }}
                                    animate={{ scale: 1, opacity: 1 }}
                                    exit={{ scale: 0.9, opacity: 0 }}
                                    onClick={(e) => e.stopPropagation()}
                                >
                                    <div className="mb-4 flex items-start justify-between border-b-2 border-black/10 pb-4">
                                        <div>
                                            <div className="text-xs font-bold uppercase tracking-[0.12em] text-black">BLR-{String(selectedCase.case_id).padStart(3, "0")}</div>
                                            <h2 className="mt-1 text-lg font-bold text-black">{selectedCase.title}</h2>
                                        </div>
                                        <button onClick={() => setSelectedCase(null)} className="text-black/50 hover:text-black flex-shrink-0">✕</button>
                                    </div>
                                    
                                    {/* MODAL TAB NAVIGATION */}
                                    <div className="flex flex-wrap border-b-2 border-black/10 mb-4 text-[10px] font-semibold uppercase tracking-[0.1em]">
                                        <button 
                                            type="button" 
                                            onClick={() => setModalTab("details")} 
                                            className={`pb-2 px-4 border-b-2 transition-all ${modalTab === "details" ? "border-accent text-black font-bold" : "border-transparent text-black/75 hover:text-black"}`}
                                        >
                                            Details & Narrative
                                        </button>
                                        <button 
                                            type="button" 
                                            onClick={() => setModalTab("timeline")} 
                                            className={`pb-2 px-4 border-b-2 transition-all ${modalTab === "timeline" ? "border-accent text-black font-bold" : "border-transparent text-black/75 hover:text-black"}`}
                                        >
                                            Timeline
                                        </button>
                                        <button 
                                            type="button" 
                                            onClick={() => setModalTab("evidence")} 
                                            className={`pb-2 px-4 border-b-2 transition-all ${modalTab === "evidence" ? "border-accent text-black font-bold" : "border-transparent text-black/75 hover:text-black"}`}
                                        >
                                            Evidence
                                        </button>
                                    </div>

                                    {modalTab === "details" && (
                                        <div className="space-y-4 text-xs">
                                            {/* CASE DETAILS */}
                                            <div className="grid grid-cols-2 gap-3 rounded-lg border-2 border-black/20 bg-white p-3">
                                                <div>
                                                    <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-black">Status</div>
                                                    <div className="mt-1 font-semibold text-black">{selectedCase.status}</div>
                                                </div>
                                                <div>
                                                    <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-black">Crime Type</div>
                                                    <div className="mt-1 font-semibold text-black">{selectedCase.crime_type}</div>
                                                </div>
                                                <div className="col-span-2">
                                                    <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-black">Location</div>
                                                    <div className="mt-1 font-semibold text-black">{selectedCase.location}</div>
                                                </div>
                                            </div>

                                            {/* DESCRIPTION */}
                                            <div>
                                                <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.1em] text-black">Description</div>
                                                <div className="max-h-40 overflow-y-auto whitespace-pre-wrap rounded-lg border-2 border-black/20 bg-white p-3 text-xs font-medium text-black">
                                                    {selectedCase.description}
                                                </div>
                                            </div>

                                            {/* ASSIGNED OFFICERS */}
                                            <div className="rounded-lg border-2 border-accent/30 bg-accent/5 p-4">
                                                <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-black mb-3">Assigned Officers</div>
                                                {caseOfficers.length > 0 ? (
                                                    <div className="space-y-2">
                                                        {caseOfficers.map(off => (
                                                            <div key={off.officer_id} className="flex items-center justify-between rounded-lg border-2 border-black/10 bg-white p-2">
                                                                <div>
                                                                    <div className="text-xs font-semibold text-black">{off.name}</div>
                                                                    <div className="text-[10px] text-black/60">{off.rank} · {off.role}</div>
                                                                </div>
                                                                <button
                                                                    onClick={() => handleRemoveOfficer(selectedCase.case_id, off.officer_id)}
                                                                    disabled={reassignLoading}
                                                                    className="flex items-center gap-1 rounded-full border-2 border-red-500 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-red-600 hover:bg-red-50 disabled:opacity-50"
                                                                >
                                                                    <Icon name="Trash2" size={12} />
                                                                    Remove
                                                                </button>
                                                            </div>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <div className="text-xs text-black/60 italic">No officers assigned yet.</div>
                                                )}
                                            </div>

                                            {/* ADD OFFICER SECTION */}
                                            <div className="rounded-lg border-2 border-emerald-600/30 bg-emerald-50/50 p-4">
                                                <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-black mb-3">Add Officer to Case</div>
                                                {availableOfficers.length > 0 ? (
                                                    <div className="space-y-2">
                                                        <select
                                                            value={selectedOfficerToAdd || ""}
                                                            onChange={(e) => setSelectedOfficerToAdd(parseInt(e.target.value) || null)}
                                                            className={`${ThemisNomos_INPUT} w-full py-2 text-sm`}
                                                            disabled={reassignLoading}
                                                        >
                                                            <option value="">Select an officer...</option>
                                                            {availableOfficers.map(off => (
                                                                <option key={off.officer_id} value={off.officer_id}>
                                                                    {off.name} ({off.rank})
                                                                </option>
                                                            ))}
                                                        </select>
                                                        <button
                                                            onClick={() => selectedOfficerToAdd && handleAddOfficer(selectedCase.case_id, selectedOfficerToAdd)}
                                                            disabled={!selectedOfficerToAdd || reassignLoading}
                                                            className="w-full rounded-full border-2 border-emerald-600 bg-emerald-50 px-4 py-2 text-xs font-semibold uppercase tracking-[0.1em] text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                                        >
                                                            {reassignLoading ? "Adding..." : "Add Officer"}
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <div className="text-xs text-black/60 italic">All officers are already assigned to this case.</div>
                                                )}
                                            </div>

                                            {/* REQUEST DOSSIER EMAIL */}
                                            <div className="rounded-lg border-2 border-emerald-600/30 bg-emerald-50/5 p-4 flex flex-col gap-2">
                                                <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-black">Request Secure Dossier</div>
                                                <div className="text-[10px] text-black/60 leading-normal">
                                                    Request the latest case details, full teammate lists, and a high-resolution secure PDF dossier to be compiled and dispatched asynchronously to your official email.
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={() => handleRequestDossier(selectedCase.case_id)}
                                                    disabled={dossierLoading}
                                                    className="w-full flex items-center justify-center gap-1.5 rounded-full border-2 border-emerald-600 bg-emerald-50/20 py-2 text-xs font-semibold uppercase tracking-[0.1em] text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                                >
                                                    <Icon name={dossierLoading ? "Clock" : "Mail"} size={12} />
                                                    {dossierLoading ? "Requesting Dossier..." : "Email Updated Dossier"}
                                                </button>
                                                
                                                {dossierMessage && (
                                                    <div className="mt-1 flex items-center gap-2 rounded-lg border-2 border-emerald-600/30 bg-emerald-50 px-3 py-2 text-[10px] font-medium text-emerald-800">
                                                        <Icon name="CheckCircle" size={12} />
                                                        <span>{dossierMessage}</span>
                                                    </div>
                                                )}
                                                {dossierError && (
                                                    <div className="mt-1 flex items-center gap-2 rounded-lg border-2 border-red-600/40 bg-red-50 px-3 py-2 text-[10px] font-semibold text-red-700">
                                                        <Icon name="AlertTriangle" size={12} />
                                                        <span>{dossierError}</span>
                                                    </div>
                                                )}
                                            </div>

                                            {/* ERROR MESSAGE */}
                                            {reassignError && (
                                                <div className="flex items-center gap-2 rounded-lg border-2 border-red-600/40 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                                                    <Icon name="AlertTriangle" size={14} />
                                                    <span>{reassignError}</span>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* TIMELINE TAB */}
                                    {modalTab === "timeline" && (
                                        <div className="space-y-4 text-xs">
                                            <div className="rounded-xl border-2 border-accent/20 bg-accent/5 p-4">
                                                <div className={`${ThemisNomos_LABEL} mb-3`}>Investigation Updates (Timeline)</div>
                                                {timelineUpdates.length > 0 ? (
                                                    <div className="space-y-3 max-h-60 overflow-y-auto pr-1">
                                                        {timelineUpdates.map((update, idx) => (
                                                            <div key={update.update_id} className="relative pl-4 border-l-2 border-accent/30">
                                                                <div className="absolute -left-[5px] top-1.5 h-2 w-2 rounded-full bg-accent" />
                                                                <div className="text-[10px] text-black/50 font-medium">
                                                                    {update.officer_name} ({update.officer_rank}) · {new Date(update.created_at).toLocaleString()}
                                                                </div>
                                                                <div className="mt-0.5 text-xs text-black bg-white/50 border border-black/5 rounded-lg p-2 leading-relaxed">
                                                                    {update.update_text}
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                ) : (
                                                    <div className="text-xs text-black/50 italic py-2">No timeline updates recorded for this case yet.</div>
                                                )}
                                            </div>
                                            
                                            {/* APPEND TIMELINE FORM */}
                                            <div className="rounded-xl border-2 border-black/10 bg-white/70 p-4">
                                                <div className={`${ThemisNomos_LABEL} mb-2`}>Append Timeline Update</div>
                                                <textarea
                                                    value={newUpdateText}
                                                    onChange={e => setNewUpdateText(e.target.value)}
                                                    className={`${ThemisNomos_INPUT} w-full text-xs resize-none p-2`}
                                                    rows={3}
                                                    placeholder="Enter details of the investigation update to record in the timeline..."
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() => handleAddTimelineUpdate(selectedCase.case_id)}
                                                    disabled={dossierLoading || !newUpdateText.trim()}
                                                    className="mt-2 w-full flex items-center justify-center gap-1.5 rounded-full border-2 border-accent bg-accent/10 py-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-accent hover:bg-accent/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                                >
                                                    <Icon name={dossierLoading ? "Clock" : "Plus"} size={12} />
                                                    {dossierLoading ? "Appending..." : "Append Timeline Update"}
                                                </button>
                                                {actionError && (
                                                    <div className="mt-2 flex items-center gap-2 rounded-lg border-2 border-red-600/40 bg-red-50 px-3 py-2 text-[10px] font-semibold text-red-700">
                                                        <Icon name="AlertTriangle" size={12} />
                                                        <span>{actionError}</span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}

                                    {/* EVIDENCE TAB */}
                                    {modalTab === "evidence" && (
                                        <div className="space-y-4 text-xs">
                                            <div className="rounded-xl border-2 border-accent/20 bg-accent/5 p-4">
                                                <div className={`${ThemisNomos_LABEL} mb-3`}>Case Evidence Log</div>
                                                {evidenceItems.length > 0 ? (
                                                    <div className="space-y-3 max-h-60 overflow-y-auto pr-1">
                                                        {evidenceItems.map(item => {
                                                            const isImage = item.mime_type.startsWith("image/");
                                                            const isAudio = item.mime_type.startsWith("audio/");
                                                            const isVideo = item.mime_type.startsWith("video/");
                                                            
                                                            const kb = (item.file_size / 1024).toFixed(1);
                                                            const sessionParam = encodeURIComponent(officer?.session_token || getStoredSessionToken());
                                                            const secureUrl = `${API_BASE}/cases/evidence/file/${item.case_id}/${item.file_name}?X-Officer-Id=${officer?.officer_id}&X-Session-Token=${sessionParam}`;
                                                            const downloadUrl = `${API_BASE}/cases/${item.case_id}/evidence/${item.file_name}/download?X-Officer-Id=${officer?.officer_id}&X-Session-Token=${sessionParam}`;
                                                            
                                                            return (
                                                                <div key={item.evidence_id} className="flex flex-col gap-2 rounded-lg border-2 border-black/10 bg-white p-3">
                                                                    <div className="flex items-start justify-between">
                                                                        <div>
                                                                            <div className="text-xs font-semibold text-black flex items-center gap-1">
                                                                                <Icon name={isImage ? "Image" : isVideo ? "Video" : isAudio ? "Music" : "FileText"} size={12} />
                                                                                {item.original_name}
                                                                            </div>
                                                                            <div className="text-[10px] text-black/50 mt-0.5">
                                                                                Uploaded by: {item.officer_name} · {kb} KB · {new Date(item.created_at).toLocaleDateString()}
                                                                            </div>
                                                                            {item.description && (
                                                                                <div className="text-[10px] italic text-black/70 mt-1 bg-black/5 p-1 rounded">
                                                                                    {item.description}
                                                                                </div>
                                                                            )}
                                                                        </div>
                                                                        
                                                                        <div className="flex items-center gap-1.5">
                                                                            <a
                                                                                href={downloadUrl}
                                                                                className="rounded-full border border-black/10 p-1 text-black/60 hover:bg-black/5"
                                                                                title="Download Secure File"
                                                                            >
                                                                                <Icon name="Download" size={12} />
                                                                            </a>
                                                                            {(isAdmin() || officer?.officer_id === item.officer_id) && (
                                                                                <button
                                                                                    type="button"
                                                                                    onClick={() => handleDeleteEvidence(selectedCase.case_id, item.evidence_id)}
                                                                                    disabled={dossierLoading}
                                                                                    className="rounded-full border border-red-200 p-1 text-red-500 hover:bg-red-50 disabled:opacity-50"
                                                                                >
                                                                                    <Icon name="Trash2" size={12} />
                                                                                </button>
                                                                            )}
                                                                        </div>
                                                                    </div>
                                                                    
                                                                    <div className="mt-1 border border-black/5 rounded bg-black/5 overflow-hidden flex justify-center items-center">
                                                                        {isImage && (
                                                                            <img 
                                                                                src={secureUrl} 
                                                                                alt={item.original_name} 
                                                                                className="max-h-32 object-contain"
                                                                                onError={(e) => { e.target.style.display = 'none'; }}
                                                                            />
                                                                        )}
                                                                        {isVideo && (
                                                                            <video controls className="max-h-32 w-full object-contain">
                                                                                <source src={secureUrl} type={item.mime_type} />
                                                                            </video>
                                                                        )}
                                                                        {isAudio && (
                                                                            <audio controls className="w-full h-8">
                                                                                <source src={secureUrl} type={item.mime_type} />
                                                                            </audio>
                                                                        )}
                                                                        {!isImage && !isVideo && !isAudio && (
                                                                            <a 
                                                                                href={downloadUrl}
                                                                                download={item.original_name}
                                                                                className="text-[10px] font-semibold text-accent hover:underline py-2 flex items-center gap-1"
                                                                            >
                                                                                <Icon name="Download" size={12} />
                                                                                Download Secure Document
                                                                            </a>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                ) : (
                                                    <div className="text-xs text-black/50 italic py-2">No evidence items uploaded for this case yet.</div>
                                                )}
                                            </div>
                                            
                                            {/* UPLOAD EVIDENCE FORM */}
                                            <div className="rounded-xl border-2 border-black/10 bg-white/70 p-4 space-y-3">
                                                <div className={`${ThemisNomos_LABEL}`}>Upload New Evidence</div>
                                                
                                                <div>
                                                    <input
                                                        type="file"
                                                        id="evidence-file-input"
                                                        onChange={e => setEvidenceFile(e.target.files[0] || null)}
                                                        disabled={dossierLoading}
                                                        className="block w-full text-[10px] text-black/60
                                                            file:mr-4 file:py-1.5 file:px-3
                                                            file:rounded-full file:border-2
                                                            file:border-emerald-600 file:bg-emerald-50
                                                            file:text-[10px] file:font-semibold
                                                            file:text-emerald-700 hover:file:bg-emerald-100
                                                            cursor-pointer"
                                                    />
                                                    <div className="text-[9px] text-black/40 mt-1 leading-normal">
                                                        Allowed types: Images, Videos, Audio, PDFs, and standard Office documents. Size limit: 50 MB.
                                                    </div>
                                                </div>
                                                
                                                <div>
                                                    <input
                                                        type="text"
                                                        value={evidenceDesc}
                                                        onChange={e => setEvidenceDesc(e.target.value)}
                                                        placeholder="Add brief description or notes for this evidence..."
                                                        className={`${ThemisNomos_INPUT} w-full text-[10px] py-1.5 px-2`}
                                                        disabled={dossierLoading}
                                                    />
                                                </div>
                                                
                                                <button
                                                    type="button"
                                                    onClick={() => handleUploadEvidence(selectedCase.case_id)}
                                                    disabled={dossierLoading || !evidenceFile}
                                                    className="w-full flex items-center justify-center gap-1.5 rounded-full border-2 border-emerald-600 bg-emerald-50/20 py-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                                >
                                                    <Icon name={dossierLoading ? "Clock" : "Upload"} size={12} />
                                                    {dossierLoading ? "Uploading..." : "Upload Secure Evidence"}
                                                </button>
                                                {actionError && (
                                                    <div className="mt-2 flex items-center gap-2 rounded-lg border-2 border-red-600/40 bg-red-50 px-3 py-2 text-[10px] font-semibold text-red-700">
                                                        <Icon name="AlertTriangle" size={12} />
                                                        <span>{actionError}</span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </motion.div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </CrmsPageShell>
            );
        };

