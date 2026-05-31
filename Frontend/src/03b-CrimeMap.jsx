        // ─── CRIME MAP (Leaflet + OpenStreetMap) ────────────────────────────────
        // Admin map of Bengaluru: green markers = police stations, red markers =
        // case locations. Free-text places (e.g. "JP Nagar") are geocoded via
        // Nominatim, anchored to Bengaluru, and cached so they resolve once.
        const CrimeMap = ({ officer }) => {
            const mapElRef = useRef(null);     // the <div> the map mounts into
            const mapRef = useRef(null);       // the Leaflet map instance
            const layerRef = useRef(null);     // marker layer group (for clean redraws)

            const [status, setStatus] = useState("loading");   // loading | geocoding | ready | error
            const [error, setError] = useState(null);
            const [progress, setProgress] = useState({ done: 0, total: 0 });
            const [counts, setCounts] = useState({ stations: 0, locations: 0, unresolved: 0 });

            // Build a coloured map pin as a div icon (no external image assets),
            // styled to match the editorial palette. `count` shows inside the pin.
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

            useEffect(() => {
                let cancelled = false;

                const init = async () => {
                    // Guard: Leaflet must have loaded from the CDN.
                    if (!window.L) {
                        setStatus("error");
                        setError("Map library failed to load. Check your network connection.");
                        return;
                    }

                    // 1. Fetch aggregated station + case-location data.
                    let data;
                    try {
                        const res = await apiFetch("/admin/map-data", {
                            headers: { "X-Officer-Id": officer?.officer_id?.toString() },
                        });
                        if (!res.success) throw new Error(res.error || "Failed to load map data");
                        data = res.data;
                    } catch (err) {
                        if (cancelled) return;
                        setStatus("error");
                        setError(err.message);
                        return;
                    }

                    const stations = data.stations || [];
                    const caseLocations = data.case_locations || [];

                    // 2. Create the map once (centred on Bengaluru).
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
                    // Map div may have been sized after creation; nudge Leaflet to recalc.
                    setTimeout(() => mapRef.current && mapRef.current.invalidateSize(), 100);

                    // 3. Geocode every unique place sequentially (Nominatim politeness).
                    const unique = [
                        ...stations.map((s) => ({ kind: "station", name: s.station, meta: s })),
                        ...caseLocations.map((c) => ({ kind: "case", name: c.location, meta: c })),
                    ];
                    setProgress({ done: 0, total: unique.length });
                    setStatus("geocoding");

                    const bounds = [];
                    let unresolved = 0;
                    let stationMarks = 0;
                    let caseMarks = 0;

                    for (let i = 0; i < unique.length; i++) {
                        if (cancelled) return;
                        const item = unique[i];
                        const coord = await geocodePlace(item.name, item.kind);
                        setProgress({ done: i + 1, total: unique.length });

                        if (!coord) { unresolved++; }
                        else if (layerRef.current) {
                            const isStation = item.kind === "station";
                            const color = isStation ? "#3f6b4a" : "#8a1c1c";  // editorial green / oxblood
                            const badgeCount = isStation ? item.meta.officer_count : item.meta.case_count;
                            const popup = isStation
                                ? `<strong>${item.name}</strong><br/>Police station · ${item.meta.officer_count} officer(s)`
                                : `<strong>${item.name}</strong><br/>${item.meta.case_count} case(s)`
                                  + ` · ${item.meta.active_count} active · ${item.meta.solved_count} solved`;
                            window.L.marker([coord.lat, coord.lng], { icon: makeIcon(color, badgeCount) })
                                .bindPopup(popup)
                                .addTo(layerRef.current);
                            bounds.push([coord.lat, coord.lng]);
                            if (isStation) stationMarks++; else caseMarks++;
                        }

                        // Only pause between actual network calls. Cached lookups are instant;
                        // we approximate by always sleeping a short, polite interval.
                        await sleep(1100);
                    }

                    if (cancelled) return;
                    setCounts({ stations: stationMarks, locations: caseMarks, unresolved });
                    if (bounds.length && mapRef.current) {
                        try { mapRef.current.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 }); }
                        catch { /* single point / fitBounds edge cases — ignore */ }
                    }
                    setStatus("ready");
                };

                init();

                // Cleanup: stop in-flight loop and tear down the map on unmount.
                return () => {
                    cancelled = true;
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
                    {status === "geocoding" && (
                        <p className="mb-2 text-[11px] font-sans text-ink-muted">
                            Mapping locations… {progress.done}/{progress.total}
                            <span className="ml-1 italic">(first load geocodes each place once, then caches it)</span>
                        </p>
                    )}
                    {status === "ready" && (
                        <p className="mb-2 text-[11px] font-sans text-ink-muted">
                            {counts.stations} station(s) · {counts.locations} case location(s) plotted
                            {counts.unresolved > 0 && ` · ${counts.unresolved} could not be located`}
                        </p>
                    )}
                    {status === "error" && (
                        <div className="mb-2 flex items-center gap-2 border-l-4 border-red-warn bg-red-warn/5 px-3 py-2 text-xs font-semibold text-red-warn font-sans">
                            <Icon name="AlertTriangle" size={14} /> {error}
                        </div>
                    )}

                    {/* The map canvas */}
                    <div className="crms-map relative">
                        {(status === "loading" || status === "geocoding") && (
                            <div className="pointer-events-none absolute inset-0 z-[500] flex items-center justify-center">
                                <div className="rounded-full border-2 border-ink/15 bg-paper-card/90 px-4 py-2 text-[11px] font-sans font-semibold text-ink-muted shadow">
                                    {status === "loading" ? "Loading map…" : "Plotting markers…"}
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
