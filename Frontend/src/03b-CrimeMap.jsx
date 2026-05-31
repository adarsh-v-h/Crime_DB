        // ─── CRIME MAP (Leaflet + OpenStreetMap) ────────────────────────────────
        // Admin map of Bengaluru: green pins = police stations, red pins = case
        // locations. Coordinates come pre-resolved from the server (DB geocode
        // cache), so the map renders instantly. If the server is still warming the
        // cache for never-seen places ("pending" > 0), we poll a few times to pick
        // up the freshly-geocoded coordinates — no client-side geocoding at all.
        const CrimeMap = ({ officer }) => {
            const mapElRef = useRef(null);     // the <div> the map mounts into
            const mapRef = useRef(null);       // the Leaflet map instance
            const layerRef = useRef(null);     // marker layer group (cleared on redraw)

            const [status, setStatus] = useState("loading");   // loading | warming | ready | error
            const [error, setError] = useState(null);
            const [counts, setCounts] = useState({ stations: 0, locations: 0, pending: 0 });

            // Coloured map pin as a div icon (no external image assets), styled to
            // match the editorial palette. `count` shows inside the pin.
            const makeIcon = (color, count) => window.L.divIcon({
                className: "",
                html: `<div style="position:relative;width:26px;height:34px;">
                        <div style="position:absolute;left:50%;top:0;transform:translateX(-50%) rotate(-45deg);
                             width:24px;height:24px;border-radius:50% 50% 50% 0;
                             background:${color};border:2px solid #fffdf8;
                             box-shadow:0 2px 5px rgba(28,26,23,0.45);"></div>
                        <span style="position:absolute;left:50%;top:8px;transform:translateX(-50%);
                              font-family:'Inter',sans-serif;font-size:10px;font-weight:800;
                              color:#fffdf8;line-height:1;">${count != null ? count : ""}</span>
                       </div>`,
                iconSize: [26, 34],
                iconAnchor: [13, 34],
                popupAnchor: [0, -32],
            });

            // Draw all markers that have coordinates; returns the plotted counts.
            const draw = (stations, caseLocations) => {
                if (!layerRef.current) return { stations: 0, locations: 0 };
                layerRef.current.clearLayers();
                const bounds = [];
                let stationMarks = 0, caseMarks = 0;

                stations.forEach((s) => {
                    if (s.lat == null || s.lng == null) return;
                    window.L.marker([s.lat, s.lng], { icon: makeIcon("#3f6b4a", s.officer_count) })
                        .bindPopup(`<strong>${s.station}</strong><br/>Police station · ${s.officer_count} officer(s)`)
                        .addTo(layerRef.current);
                    bounds.push([s.lat, s.lng]);
                    stationMarks++;
                });
                caseLocations.forEach((c) => {
                    if (c.lat == null || c.lng == null) return;
                    window.L.marker([c.lat, c.lng], { icon: makeIcon("#8a1c1c", c.case_count) })
                        .bindPopup(`<strong>${c.location}</strong><br/>${c.case_count} case(s)`
                            + ` · ${c.active_count} active · ${c.solved_count} solved`)
                        .addTo(layerRef.current);
                    bounds.push([c.lat, c.lng]);
                    caseMarks++;
                });

                if (bounds.length && mapRef.current) {
                    try { mapRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 }); }
                    catch { /* single point / fitBounds edge cases — ignore */ }
                }
                return { stations: stationMarks, locations: caseMarks };
            };

            useEffect(() => {
                let cancelled = false;
                let pollTimer = null;
                const MAX_POLLS = 8;   // ~ a few seconds apart; bounded so we never loop forever

                const fetchData = async () => {
                    const res = await apiFetch("/admin/map-data", {
                        headers: { "X-Officer-Id": officer?.officer_id?.toString() },
                    });
                    if (!res.success) throw new Error(res.error || "Failed to load map data");
                    return res.data;
                };

                const run = async () => {
                    if (!window.L) {
                        setStatus("error");
                        setError("Map library failed to load. Check your network connection.");
                        return;
                    }

                    // Create the map once, centred on Bengaluru.
                    if (!mapRef.current && mapElRef.current) {
                        mapRef.current = window.L.map(mapElRef.current).setView(
                            [BENGALURU_CENTER.lat, BENGALURU_CENTER.lng], 12
                        );
                        window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                            attribution: "© OpenStreetMap contributors",
                            maxZoom: 19,
                        }).addTo(mapRef.current);
                        layerRef.current = window.L.layerGroup().addTo(mapRef.current);
                    }
                    setTimeout(() => mapRef.current && mapRef.current.invalidateSize(), 100);

                    let polls = 0;
                    const load = async () => {
                        if (cancelled) return;
                        let data;
                        try {
                            data = await fetchData();
                        } catch (err) {
                            if (cancelled) return;
                            setStatus("error");
                            setError(err.message);
                            return;
                        }
                        if (cancelled) return;

                        const stations = data.stations || [];
                        const caseLocations = data.case_locations || [];
                        const plotted = draw(stations, caseLocations);
                        const pending = data.pending || 0;

                        setCounts({ stations: plotted.stations, locations: plotted.locations, pending });

                        if (pending > 0 && polls < MAX_POLLS) {
                            // Server is still warming the cache for new places — poll again.
                            polls++;
                            setStatus("warming");
                            pollTimer = setTimeout(load, 2500);
                        } else {
                            setStatus("ready");
                        }
                    };

                    await load();
                };

                run();

                return () => {
                    cancelled = true;
                    if (pollTimer) clearTimeout(pollTimer);
                    if (mapRef.current) {
                        mapRef.current.remove();
                        mapRef.current = null;
                        layerRef.current = null;
                    }
                };
            // eslint-disable-next-line react-hooks/exhaustive-deps
            }, []);

            return (
                <motion.div variants={fadeUp} custom={1} className={`${ThemisNomos_CARD} p-4 sm:p-5`}>
                    {/* Header + legend */}
                    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-ink/15 pb-3">
                        <div>
                            <p className="kicker mb-1">Geospatial Intelligence</p>
                            <h3 className="headline text-2xl sm:text-3xl">Bengaluru Operations Map</h3>
                        </div>
                        <div className="flex items-center gap-4 text-[11px] font-sans font-semibold text-ink-muted">
                            <span className="flex items-center gap-1.5">
                                <span className="inline-block h-3 w-3 rounded-full border border-paper" style={{ background: "#3f6b4a" }}></span>
                                Police stations
                            </span>
                            <span className="flex items-center gap-1.5">
                                <span className="inline-block h-3 w-3 rounded-full border border-paper" style={{ background: "#8a1c1c" }}></span>
                                Case locations
                            </span>
                        </div>
                    </div>

                    {/* Status line */}
                    {status === "warming" && (
                        <p className="mb-2 text-[11px] font-sans text-ink-muted">
                            Resolving {counts.pending} new location(s) on the server…
                            <span className="ml-1 italic">they're cached once resolved, so this only happens the first time.</span>
                        </p>
                    )}
                    {status === "ready" && (
                        <p className="mb-2 text-[11px] font-sans text-ink-muted">
                            {counts.stations} station(s) · {counts.locations} case location(s) plotted
                            {counts.pending > 0 && ` · ${counts.pending} could not be located`}
                        </p>
                    )}
                    {status === "error" && (
                        <div className="mb-2 flex items-center gap-2 border-l-4 border-red-warn bg-red-warn/5 px-3 py-2 text-xs font-semibold text-red-warn font-sans">
                            <Icon name="AlertTriangle" size={14} /> {error}
                        </div>
                    )}

                    {/* The map canvas */}
                    <div className="crms-map relative">
                        {(status === "loading" || status === "warming") && (
                            <div className="pointer-events-none absolute inset-0 z-[500] flex items-center justify-center">
                                <div className="rounded-full border-2 border-ink/15 bg-paper-card/90 px-4 py-2 text-[11px] font-sans font-semibold text-ink-muted shadow">
                                    {status === "loading" ? "Loading map…" : "Resolving new locations…"}
                                </div>
                            </div>
                        )}
                        <div
                            ref={mapElRef}
                            className="h-[60vh] min-h-[420px] w-full overflow-hidden rounded border border-ink/20"
                            style={{ background: "#e8e4d8" }}
                        />
                    </div>
                </motion.div>
            );
        };
