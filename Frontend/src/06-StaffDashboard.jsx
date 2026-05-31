        // ─── STAFF DASHBOARD ──────────────────────────────────────────────────
        const StaffDashboard = ({ onNavigate, userRole, officer, onLogout }) => {
            // Filter States
            const [statusFilter, setStatusFilter] = useState("All");
            const [typeFilter, setTypeFilter] = useState("All");
            const [searchQuery, setSearchQuery] = useState("");
            
            // Core Data & Pagination States
            const [cases, setCases] = useState([]);
            const [currentPage, setCurrentPage] = useState(1);
            const [totalPages, setTotalPages] = useState(1);
            const [totalRecords, setTotalRecords] = useState(0);
            const [caseRefreshTick, setCaseRefreshTick] = useState(0);
            
            const [loading, setLoading] = useState(false);
            const [error, setError] = useState(null);
            const [selectedCase, setSelectedCase] = useState(null);
            const [dossierLoading, setDossierLoading] = useState(false);
            const [dossierMessage, setDossierMessage] = useState(null);
            const [dossierError, setDossierError] = useState(null);
            const [modalTab, setModalTab] = useState("details");
            const [timelineUpdates, setTimelineUpdates] = useState([]);
            const [evidenceItems, setEvidenceItems] = useState([]);
            const [newUpdateText, setNewUpdateText] = useState("");
            const [evidenceFile, setEvidenceFile] = useState(null);
            const [evidenceDesc, setEvidenceDesc] = useState("");

            // Tab State
            const [activeSubTab, setActiveSubTab] = useState("dossiers");
            
            // Access Requests States
            const [requests, setRequests] = useState([]);
            const [requestsLoading, setRequestsLoading] = useState(false);
            const [requestsError, setRequestsError] = useState(null);
            const [decidingRequestId, setDecidingRequestId] = useState(null);
            const [requestActionMessage, setRequestActionMessage] = useState(null);

            // Authorization state for access requests
            const [accessRequestAuthStatus, setAccessRequestAuthStatus] = useState({});

            // Helper: Check if officer is admin
            const isAdmin = () => (officer?.role || "").toLowerCase() === "admin";

            // Helper: Check if officer can approve/reject access requests for a case
            const canDecideAccessRequest = async (caseId) => {
                // Admins can always decide
                if (isAdmin()) return true;
                // Fetch assigned officers and determine highest-ranked officer
                try {
                    const res = await apiFetch(`/cases/${caseId}/officers`, {
                        headers: { "X-Officer-Id": officer?.officer_id?.toString() }
                    });
                    if (res.success) {
                        const officersList = res.data?.officers || [];
                        if (!officersList.length) return false;

                        const rankValue = (r) => {
                            switch ((r || "").toLowerCase()) {
                                case "inspector": return 4;
                                case "sub-inspector": return 3;
                                case "head constable": return 2;
                                case "constable": return 1;
                                default: return 0;
                            }
                        };

                        let highest = officersList[0];
                        for (const o of officersList) {
                            if (rankValue(o.rank) > rankValue(highest.rank)) highest = o;
                        }

                        return officer?.officer_id && highest && officer.officer_id === highest.officer_id;
                    }
                } catch (err) {
                    console.error("Error checking access request authorization:", err);
                }
                return false;
            };

            const loadAccessRequests = async () => {
                setRequestsLoading(true);
                setRequestsError(null);
                try {
                    const response = await apiFetch("/api/access-requests", {
                        headers: {
                            "X-Officer-Id": officer?.officer_id?.toString()
                        }
                    });
                    if (response.success) {
                        setRequests(response.data || []);
                        // Check authorization for each request's case
                        const authStatus = {};
                        for (const req of (response.data || [])) {
                            authStatus[req.case_id] = await canDecideAccessRequest(req.case_id);
                        }
                        setAccessRequestAuthStatus(authStatus);
                    } else {
                        setRequestsError(response.error || "Failed to load access requests.");
                    }
                } catch (err) {
                    console.error("[Themis's Domain Engine] Requests load error:", err);
                    setRequestsError(err.message || "Failed to contact authorization server.");
                } finally {
                    setRequestsLoading(false);
                }
            };

            useEffect(() => {
                if (officer) {
                    loadAccessRequests();
                }
            }, [activeSubTab, officer]);

            const handleDecide = async (requestId, action) => {
                setDecidingRequestId(requestId);
                setRequestActionMessage(null);
                try {
                    const response = await apiFetch(`/api/access-requests/${requestId}/${action}`, {
                        method: "POST",
                        headers: {
                            "X-Officer-Id": officer?.officer_id?.toString()
                        }
                    });
                    if (response.success) {
                        setRequestActionMessage(response.message || `Request ${action === "approve" ? "approved" : "declined"}.`);
                        await loadAccessRequests();
                    } else {
                        setRequestsError(response.error || "Action failed.");
                    }
                } catch (err) {
                    setRequestsError(err.message || "Action failed.");
                } finally {
                    setDecidingRequestId(null);
                }
            };

            const requestStatusBadge = (status) => {
                const styles = {
                    Pending: "bg-amber-100 text-amber-900 border-amber-400",
                    Accepted: "bg-emerald-100 text-emerald-900 border-emerald-500",
                    Rejected: "bg-rose-100 text-rose-900 border-rose-400",
                };
                return (
                    <span className={`rounded-full border-2 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${styles[status] || styles.Pending}`}>
                        {status}
                    </span>
                );
            };
            
            const pendingCount = requests.filter(r => r.status === "Pending").length;


            // Fetch live data from backend whenever filters or page changes
            useEffect(() => {
                const loadCases = async () => {
                    setLoading(true);
                    setError(null);
                    try {
                        let queryParams = new URLSearchParams({
                            page: currentPage,
                            limit: 16
                        });
                        
                        if (statusFilter !== "All") queryParams.append("status", statusFilter);
                        if (typeFilter !== "All") queryParams.append("crime_type", typeFilter);
                        if (searchQuery.trim() !== "") queryParams.append("search", searchQuery.trim());

                        const response = await apiFetch(`/api/cases?${queryParams.toString()}`, {
                            headers: {
                                "X-Officer-Id": officer?.officer_id?.toString()
                            }
                        });
                        if (response.success) {
                            setCases(response.data || []);
                            if (response.pagination) {
                                setTotalPages(response.pagination.total_pages || 1);
                                setTotalRecords(response.pagination.total_records || 0);
                            }
                        } else {
                            setError(response.error || "Failed to sync system records.");
                        }
                    } catch (err) {
                        console.error("[Themis's Domain Engine] Sync error:", err);
                        setError(err.message || "Network isolation protocol failure.");
                    } finally {
                        setLoading(false);
                    }
                };

                loadCases();
            }, [statusFilter, typeFilter, searchQuery, currentPage, caseRefreshTick]);

            useEffect(() => {
                if (!officer) return;
                const refreshCases = () => setCaseRefreshTick(tick => tick + 1);
                const refreshVisibleCases = () => {
                    if (!document.hidden) refreshCases();
                };
                const intervalId = setInterval(refreshCases, 45000);
                window.addEventListener("focus", refreshCases);
                document.addEventListener("visibilitychange", refreshVisibleCases);
                return () => {
                    clearInterval(intervalId);
                    window.removeEventListener("focus", refreshCases);
                    document.removeEventListener("visibilitychange", refreshVisibleCases);
                };
            }, [officer]);

            // Reset back to page 1 if search or status filters change
            const handleFilterChange = (type, val) => {
                setCurrentPage(1);
                if (type === "status") setStatusFilter(val);
                if (type === "type") setTypeFilter(val);
            };

            // Handle case status update
            const handleCaseStatusUpdate = async (caseId, newStatus) => {
                try {
                    const response = await apiFetch(`/cases/${caseId}`, {
                        method: "PATCH",
                        headers: {
                            "Content-Type": "application/json",
                            "X-Officer-Id": officer?.officer_id?.toString()
                        },
                        body: JSON.stringify({ status: newStatus })
                    });

                    if (response.success) {
                        // Update the selected case in the modal
                        setSelectedCase(prev => ({
                            ...prev,
                            status: newStatus
                        }));
                        
                        // Reload cases to reflect the change
                        setCurrentPage(1);
                        setStatusFilter("All");
                        setTypeFilter("All");
                        setSearchQuery("");
                        
                        // Show success message
                        console.log(`[CASE UPDATE] Case ${caseId} status updated to ${newStatus}`);
                    } else {
                        setError(response.error || "Failed to update case status");
                        console.error("[CASE UPDATE] Error:", response.error);
                    }
                } catch (err) {
                    setError(`Failed to update case status: ${err.message}`);
                    console.error("[CASE UPDATE] Network error:", err);
                }
            };

            // Handle updated dossier request
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

            const [actionError, setActionError] = useState(null);

            useEffect(() => {
                if (selectedCase) {
                    if (modalTab === "timeline") {
                        loadCaseTimeline(selectedCase.case_id);
                    } else if (modalTab === "evidence") {
                        loadCaseEvidence(selectedCase.case_id);
                    }
                } else {
                    setModalTab("details");
                }
            }, [selectedCase, modalTab]);

            return (
                <CrmsPageShell
                    title="Bengaluru Police · Intralink"
                    subtitle="Officer Command Dashboard"
                    onBack={() => onNavigate("landing")}
                    scrim="bg-white/42"
                >
                    <div className="border-b-2 border-ink/80 bg-paper/85 backdrop-blur-sm">
                        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-3 px-5 py-3 sm:px-8">
                            <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-muted font-sans sm:text-xs">
                                Operator: <span className="text-ink-black">{officer?.name || "UNKNOWN"}</span>
                                <span className="text-accent"> ({userRole?.toUpperCase()})</span>
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
                            <p className="kicker mb-1">Officer Command</p>
                            <h2 className="headline text-3xl sm:text-4xl md:text-5xl">The Case Desk</h2>
                        </motion.div>

                        {/* SUB TAB NAVIGATION BAR */}
                        <motion.div variants={fadeUp} custom={0} className="mb-6 flex flex-wrap gap-6 border-b border-ink/20 sm:gap-8">
                            <button
                                type="button"
                                onClick={() => setActiveSubTab("dossiers")}
                                className={`pb-3 text-[10px] font-bold uppercase tracking-[0.16em] transition-all border-b-2 sm:text-xs font-sans ${
                                    activeSubTab === "dossiers"
                                        ? "border-accent text-ink-black"
                                        : "border-transparent text-ink/50 hover:text-accent"
                                }`}
                            >
                                Case Dossiers
                            </button>
                            <button
                                type="button"
                                onClick={() => setActiveSubTab("requests")}
                                className={`relative pb-3 text-[10px] font-bold uppercase tracking-[0.16em] transition-all border-b-2 sm:text-xs font-sans ${
                                    activeSubTab === "requests"
                                        ? "border-accent text-ink-black"
                                        : "border-transparent text-ink/50 hover:text-accent"
                                }`}
                            >
                                Access Requests
                                {pendingCount > 0 && (
                                    <span className="ml-2 animate-pulse border border-accent bg-accent px-2 py-0.5 text-[10px] font-bold text-paper">
                                        {pendingCount}
                                    </span>
                                )}
                            </button>
                        </motion.div>

                        {activeSubTab === "dossiers" && (
                            <>
                            {/* CONTROL CONSOLE */}

                        <motion.div variants={fadeUp} custom={1} className={`${ThemisNomos_CARD} flex flex-col items-center justify-between gap-4 p-4 md:flex-row`}>
                            <div className="relative w-full md:w-96">
                                <input 
                                    type="text" 
                                    placeholder="Search dossier records..." 
                                    value={searchQuery}
                                    onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                                    className={`${ThemisNomos_INPUT} pl-10 py-2.5 text-xs`}
                                />
                                <span className="absolute left-3 top-3 text-accent text-sm">+</span>
                            </div>
                            
                            <div className="flex w-full flex-wrap items-center gap-3 md:w-auto">
                                <select 
                                    value={statusFilter} 
                                    onChange={(e) => handleFilterChange("status", e.target.value)}
                                    className={`${ThemisNomos_INPUT} w-auto py-2.5 text-[10px] uppercase tracking-[0.1em]`}
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

                                <select 
                                    value={typeFilter} 
                                    onChange={(e) => handleFilterChange("type", e.target.value)}
                                    className={`${ThemisNomos_INPUT} w-auto py-2.5 text-[10px] uppercase tracking-[0.1em]`}
                                >
                                    <option value="All">Classification: All</option>
                                    <option value="Cyber Fraud">Cyber Fraud</option>
                                    <option value="Theft">Theft</option>
                                    <option value="Assault">Assault</option>
                                    <option value="Fraud">Financial Fraud</option>
                                    <option value="Other">Other</option>
                                </select>
                            </div>
                        </motion.div>

                        {error && (
                            <div className="flex items-center gap-2 rounded-xl border-2 border-red-600/40 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                                <Icon name="AlertTriangle" size={14} />
                                <span>{error}</span>
                            </div>
                        )}

                        {/* CASE DOSSIER GRID */}
                        {loading ? (
                            <div className={`${ThemisNomos_CARD} flex h-96 w-full flex-col items-center justify-center space-y-3`}>
                                <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-black/60">Querying central database...</p>
                            </div>
                        ) : cases.length === 0 ? (
                            <div className={`${ThemisNomos_CARD} flex h-96 w-full flex-col items-center justify-center space-y-2 border-dashed`}>
                                <p className="text-sm font-semibold uppercase tracking-[0.12em] text-black">No dossiers found</p>
                                <p className="text-xs font-semibold uppercase tracking-[0.1em] text-black/55">No entries match your current filters.</p>
                            </div>
                        ) : (
                            <div className="space-y-6">
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                                    {cases.map((c) => {
                                        const statusColors = {
                                            Active: "bg-amber-100 text-amber-900 border-amber-400",
                                            Solved: "bg-emerald-100 text-emerald-900 border-emerald-500",
                                            Closed: "bg-black/5 text-black/60 border-black/20",
                                            "Pending Review": "bg-blue-100 text-blue-900 border-blue-400",
                                            Recommended: "bg-purple-100 text-purple-900 border-purple-400",
                                            Assigned: "bg-indigo-100 text-indigo-900 border-indigo-400",
                                            Rejected: "bg-red-100 text-red-900 border-red-400"
                                        };
                                        return (
                                            <div 
                                                key={c.case_id} 
                                                onClick={() => setSelectedCase(c)}
                                                className={`${ThemisNomos_CARD} group relative flex cursor-pointer flex-col justify-between p-5 transition-all hover:shadow-xl`}
                                            >
                                                <div>
                                                    <div className="mb-3 flex items-center justify-between">
                                                        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-black/60 transition-colors group-hover:text-accent">
                                                            {c.display_id || `BLR-${String(c.case_id).padStart(3, '0')}`}
                                                        </span>
                                                        <span className={`rounded-full border-2 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] ${statusColors[c.status] || statusColors.Active}`}>
                                                            {c.status}
                                                        </span>
                                                    </div>
                                                    <h3 className="mb-1 line-clamp-1 text-[15px] font-semibold text-black group-hover:text-accent">
                                                        {c.title}
                                                    </h3>
                                                    <p className="mb-4 line-clamp-2 text-xs font-medium leading-relaxed text-black/65">
                                                        {c.description || "No file logs details provided."}
                                                    </p>
                                                </div>
                                                
                                                <div className="mt-2 flex items-center justify-between border-t-2 border-black/10 pt-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-black/55">
                                                    <div><span className="text-accent">+</span> {c.crime_type}</div>
                                                    <div className="flex items-center gap-1">
                                                        <Icon name="MapPin" size={12} className="text-accent" />
                                                        {c.location || "N/A"}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>

                                {/* INDUSTRIAL PAGINATION BAR */}
                                <div className={`${ThemisNomos_CARD} flex flex-wrap items-center justify-between gap-3 px-6 py-4 text-xs`}>
                                    <div className="font-semibold uppercase tracking-[0.1em] text-black/65">
                                        Showing <span className="text-black">{cases.length}</span> of <span className="text-black">{totalRecords}</span> entries
                                    </div>
                                    
                                    <div className="flex items-center gap-2">
                                        <button 
                                            type="button"
                                            disabled={currentPage === 1}
                                            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                            className="rounded-full border-2 border-black bg-white/80 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-black transition-all hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                                        >
                                            Prev
                                        </button>
                                        
                                        <div className="select-none rounded-full border-2 border-black/20 bg-white/60 px-4 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-black/70">
                                            Page <span className="text-accent">{currentPage}</span> / {totalPages}
                                        </div>

                                        <button 
                                            type="button"
                                            disabled={currentPage === totalPages}
                                            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                            className="rounded-full border-2 border-black bg-white/80 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-black transition-all hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                                        >
                                            Next
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                            </>
                        )}

                        {activeSubTab === "requests" && (
                            <div className="space-y-4">
                                {requestActionMessage && (
                                    <div className="rounded-xl border-2 border-emerald-500/40 bg-emerald-50 px-4 py-3 text-xs font-semibold text-emerald-800">
                                        {requestActionMessage}
                                    </div>
                                )}
                                {requestsError && (
                                    <div className="flex items-center gap-2 rounded-xl border-2 border-red-600/40 bg-red-50 px-4 py-3 text-xs font-semibold text-red-700">
                                        <Icon name="AlertTriangle" size={14} />
                                        <span>{requestsError}</span>
                                    </div>
                                )}
                                {requestsLoading ? (
                                    <div className={`${ThemisNomos_CARD} flex h-96 w-full flex-col items-center justify-center space-y-3`}>
                                        <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
                                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-black/60">Syncing access requests...</p>
                                    </div>
                                ) : requests.length === 0 ? (
                                    <div className={`${ThemisNomos_CARD} flex h-64 w-full flex-col items-center justify-center space-y-2 border-dashed`}>
                                        <p className="text-sm font-semibold uppercase tracking-[0.12em] text-black">No access requests</p>
                                        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-black/55">Citizen requests for your cases will appear here.</p>
                                    </div>
                                ) : (
                                    <div className="space-y-4">
                                        {requests.map((req) => (
                                            <div key={req.request_id} className={ThemisNomos_CARD}>
                                                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                                                    <div className="flex-1 space-y-2">
                                                        <div className="flex flex-wrap items-center gap-3">
                                                            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent">
                                                                {req.case_id_display || `BLR-${String(req.case_id).padStart(3, "0")}`}
                                                            </span>
                                                            {requestStatusBadge(req.status)}
                                                        </div>
                                                        <h3 className="text-base font-semibold text-black">
                                                            {req.case_title || "Case dossier access request"}
                                                        </h3>
                                                        <p className="text-xs font-medium text-black/70">
                                                            <span className="font-semibold uppercase tracking-[0.08em] text-black/50">Requester:</span>{" "}
                                                            {req.requester_name} · {req.requester_email} · {req.requester_number}
                                                        </p>
                                                        <p className="rounded-xl border-2 border-black/10 bg-white/70 p-3 text-xs leading-relaxed text-black/80">
                                                            {req.reason}
                                                        </p>
                                                        <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-black/50">
                                                            Filed: {req.requested_at ? new Date(req.requested_at).toLocaleString() : "N/A"}
                                                            {req.decided_by_name ? ` · Decided by ${req.decided_by_name}` : ""}
                                                        </p>
                                                    </div>
                                                    {req.status === "Pending" && accessRequestAuthStatus[req.case_id] && (
                                                        <div className="flex shrink-0 gap-2">
                                                            <button
                                                                type="button"
                                                                onClick={() => handleDecide(req.request_id, "approve")}
                                                                disabled={decidingRequestId === req.request_id}
                                                                className="rounded-full border-2 border-emerald-600 bg-emerald-50 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-900 transition-all hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
                                                            >
                                                                {decidingRequestId === req.request_id ? "Processing..." : "Approve"}
                                                            </button>
                                                            <button
                                                                type="button"
                                                                onClick={() => handleDecide(req.request_id, "reject")}
                                                                disabled={decidingRequestId === req.request_id}
                                                                className="rounded-full border-2 border-rose-500 bg-rose-50 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-rose-900 transition-all hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-50"
                                                            >
                                                                Decline
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                    {/* RENDER DETAILED VIEW MODAL */}
                    {selectedCase && (
                        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
                            <motion.div
                                className={`max-h-[90vh] w-full max-w-2xl overflow-y-auto ${ThemisNomos_CARD}`}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.35 }}
                            >
                                <div className="mb-4 flex items-center justify-between border-b-2 border-black/10 pb-4">
                                    <span className="text-xs font-bold uppercase tracking-[0.14em] text-black">
                                        Case: {selectedCase.display_id || `BLR-${String(selectedCase.case_id).padStart(3, '0')}`}
                                    </span>
                                    <button type="button" onClick={() => setSelectedCase(null)} className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-black text-black hover:bg-black hover:text-white">
                                        <Icon name="X" size={14} />
                                    </button>
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

                                {/* DETAILS & NARRATIVE TAB */}
                                {modalTab === "details" && (
                                    <div className="space-y-4 text-xs">
                                        <div>
                                            <div className={ThemisNomos_LABEL}>Incident Heading</div>
                                            <div className="mt-0.5 text-sm font-semibold text-black">{selectedCase.title}</div>
                                        </div>
                                        <div className="grid grid-cols-2 gap-4 border-y-2 border-black/10 py-3">
                                            <div>
                                                <div className={ThemisNomos_LABEL}>Classification</div>
                                                <div className="mt-0.5 font-medium text-black">{selectedCase.crime_type}</div>
                                            </div>
                                            <div>
                                                <div className={ThemisNomos_LABEL}>Status</div>
                                                <div className="mt-0.5 font-medium text-black">{selectedCase.status}</div>
                                            </div>
                                            <div>
                                                <div className={ThemisNomos_LABEL}>Location</div>
                                                <div className="mt-0.5 font-medium text-black">{selectedCase.location || "Not Registered"}</div>
                                            </div>
                                            <div>
                                                <div className={ThemisNomos_LABEL}>Record Date</div>
                                                <div className="mt-0.5 font-medium text-black">{selectedCase.date_added || "N/A"}</div>
                                            </div>
                                        </div>
                                        <div>
                                            <div className={ThemisNomos_LABEL}>Case Narrative</div>
                                            <div className="mt-1 whitespace-pre-wrap rounded-xl border-2 border-black/20 bg-white p-3 text-sm font-medium leading-relaxed text-black">
                                                {selectedCase.description || "No documentation detailed."}
                                            </div>
                                        </div>
                                        <div className="rounded-xl border-2 border-black/10 bg-white/70 p-3">
                                            <div className={`${ThemisNomos_LABEL} mb-1`}>Complainant</div>
                                            <div className="font-medium text-black">Name: <span className="font-bold text-black">{selectedCase.complainant_name || "Anonymous / Guarded"}</span></div>
                                            <div className="font-medium text-black">Contact: <span className="font-bold text-black">{selectedCase.complainant_contact || "N/A"}</span></div>
                                            <div className="font-medium text-black">Aadhaar (Last 4): <span className="font-bold text-black">{selectedCase.complainant_aadhaar || "XXXX"}</span></div>
                                        </div>

                                        {isAdmin() && (
                                            <div className="rounded-xl border-2 border-accent/30 bg-accent/5 p-4">
                                                <div className={`${ThemisNomos_LABEL} mb-2`}>Update Case Status</div>
                                                <div className="flex flex-wrap items-center gap-2">
                                                    {["Pending Review", "Recommended", "Assigned", "Active", "Solved", "Closed", "Rejected"].map(statusOption => (
                                                        <button
                                                            key={statusOption}
                                                            type="button"
                                                            onClick={() => handleCaseStatusUpdate(selectedCase.case_id, statusOption)}
                                                            disabled={selectedCase.status === statusOption}
                                                            className={`rounded-full border-2 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.1em] transition-all ${
                                                                selectedCase.status === statusOption
                                                                    ? "cursor-not-allowed border-black/20 bg-black/5 text-black/40 opacity-50"
                                                                    : statusOption === "Active"
                                                                    ? "border-amber-500 bg-amber-50 text-amber-900 hover:bg-amber-100"
                                                                    : statusOption === "Solved"
                                                                    ? "border-emerald-600 bg-emerald-50 text-emerald-900 hover:bg-emerald-100"
                                                                    : statusOption === "Pending Review"
                                                                    ? "border-blue-500 bg-blue-50 text-blue-900 hover:bg-blue-100"
                                                                    : statusOption === "Recommended"
                                                                    ? "border-purple-500 bg-purple-50 text-purple-900 hover:bg-purple-100"
                                                                    : statusOption === "Assigned"
                                                                    ? "border-indigo-500 bg-indigo-50 text-indigo-900 hover:bg-indigo-100"
                                                                    : statusOption === "Rejected"
                                                                    ? "border-red-500 bg-red-50 text-red-900 hover:bg-red-100"
                                                                    : "border-black/30 bg-white/80 text-black hover:bg-black hover:text-white"
                                                            }`}
                                                        >
                                                            {statusOption}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* REQUEST DOSSIER EMAIL */}
                                        <div className="rounded-xl border-2 border-emerald-600/30 bg-emerald-50/5 p-4 flex flex-col gap-2">
                                            <div className={`${ThemisNomos_LABEL}`}>Request Secure Dossier</div>
                                            <div className="text-[10px] text-black/60 leading-normal">
                                                Request the latest case details, full teammate lists, and a high-resolution secure PDF dossier to be compiled and dispatched asynchronously to your official email.
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => handleRequestDossier(selectedCase.case_id)}
                                                disabled={dossierLoading}
                                                className="w-full flex items-center justify-center gap-1.5 rounded-full border-2 border-emerald-600 bg-emerald-50/20 py-2.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-emerald-700 hover:bg-emerald-100 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
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
                        </div>
                    )}
                    </motion.div>
                </CrmsPageShell>
            );
        };

