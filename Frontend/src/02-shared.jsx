        // ─── ANIMATED COUNTER ─────────────────────────────────────────────────
        const AnimatedCounter = ({ value, duration = 2000, prefix = "", suffix = "" }) => {
            const [display, setDisplay] = useState(0);
            const ref = useRef(null);
            const [hasAnimated, setHasAnimated] = useState(false);

            useEffect(() => {
                const observer = new IntersectionObserver(
                    ([entry]) => {
                        if (entry.isIntersecting && !hasAnimated) {
                            setHasAnimated(true);
                            const startTime = Date.now();
                            const animate = () => {
                                const elapsed = Date.now() - startTime;
                                const progress = Math.min(elapsed / duration, 1);
                                const eased = 1 - Math.pow(1 - progress, 3);
                                setDisplay(Math.floor(eased * value));
                                if (progress < 1) requestAnimationFrame(animate);
                            };
                            requestAnimationFrame(animate);
                        }
                    },
                    { threshold: 0.3 }
                );
                if (ref.current) observer.observe(ref.current);
                return () => observer.disconnect();
            }, [value, duration, hasAnimated]);

            return (
                <span ref={ref} className="metric-value">{prefix}{display.toLocaleString()}{suffix}</span>
            );
        };

        // ─── PARTICLES ────────────────────────────────────────────────────────
        const Particles = ({ count = 30 }) => {
            const particles = useMemo(() => {
                return Array.from({ length: count }, (_, i) => ({
                    id: i,
                    x: Math.random() * 100,
                    y: Math.random() * 100,
                    size: Math.random() * 3 + 1,
                    duration: Math.random() * 20 + 10,
                    delay: Math.random() * 5,
                    opacity: Math.random() * 0.3 + 0.1,
                }));
            }, [count]);

            return (
                <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
                    {particles.map(p => (
                        <div
                            key={p.id}
                            className="particle"
                            style={{
                                left: `${p.x}%`,
                                top: `${p.y}%`,
                                width: p.size,
                                height: p.size,
                                background: `rgba(0, 229, 255, ${p.opacity})`,
                                animation: `float ${p.duration}s ease-in-out ${p.delay}s infinite`,
                            }}
                        />
                    ))}
                </div>
            );
        };

        // ─── LANDING MOTION VARIANTS ────────────────────────────────────────────
        const LANDING_VIDEO_URL = "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260517_222138_3e3205be-3364-417b-a64a-bfe087acbec4.mp4";

        // ─── EDITORIAL PHOTOGRAPHY ──────────────────────────────────────────────
        // Royalty-free press/archive imagery (Unsplash License — free for commercial
        // use, no attribution required). Subjects verified: newspaper print, government
        // archive boxes, and an institutional records library. These reinforce the
        // investigative-journalism / intelligence-archive atmosphere.
        const EDITORIAL_IMG = {
            // "newspaper article lot" — dense print texture
            press:   "https://images.unsplash.com/photo-1566378246598-5b11a0d486cc?q=80&w=1400&auto=format&fit=crop",
            // "rows of white archive boxes on wooden shelves" — government records
            archive: "https://images.unsplash.com/photo-1762627105132-f6ed848a23bf?q=80&w=1200&auto=format&fit=crop",
            // "a long row of shelves filled with lots of books" — institutional library
            registry:"https://images.unsplash.com/photo-1721046013656-0a0980264689?q=80&w=1400&auto=format&fit=crop",
        };

        const fadeDown = {
            hidden: { opacity: 0, y: -24 },
            visible: (i = 0) => ({
                opacity: 1,
                y: 0,
                transition: { duration: 0.6, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] },
            }),
        };

        const fadeUp = {
            hidden: { opacity: 0, y: 32 },
            visible: (i = 0) => ({
                opacity: 1,
                y: 0,
                transition: { duration: 0.7, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] },
            }),
        };

        const slideUpReveal = {
            hidden: { opacity: 0, y: "110%" },
            visible: (i = 0) => ({
                opacity: 1,
                y: 0,
                transition: { duration: 0.85, delay: 0.15 + i * 0.12, ease: [0.22, 1, 0.36, 1] },
            }),
        };

        const ThemisNomos_INPUT = "crms-input w-full border border-ink/30 bg-paper-card px-4 py-3 text-sm font-medium text-ink placeholder-ink/35 transition-all focus:border-accent";
        const ThemisNomos_LABEL = "mb-2 block text-[10px] font-bold uppercase tracking-[0.2em] text-ink-muted font-sans";
        const ThemisNomos_CARD = "border border-ink/15 bg-paper-card p-6 shadow-[0_1px_0_rgba(28,26,23,0.04),0_18px_40px_-32px_rgba(28,26,23,0.55)] sm:p-8";


        // ─── GEOCODING (OpenStreetMap Nominatim) ────────────────────────────────
        // Resolves a free-text place (e.g. "JP Nagar") to { lat, lng } the way a
        // Google search would, by anchoring it to Bengaluru. Results are cached in
        // localStorage so a place is only ever geocoded once. Nominatim asks for at
        // most ~1 request/second, so callers should geocode sequentially.
        const GEOCODE_CACHE_KEY = "CRMS_GEOCODE_CACHE_V1";
        // Sensible fallback so the map always centres on the city.
        const BENGALURU_CENTER = { lat: 12.9716, lng: 77.5946 };

        const _readGeocodeCache = () => {
            try { return JSON.parse(localStorage.getItem(GEOCODE_CACHE_KEY) || "{}"); }
            catch { return {}; }
        };
        const _writeGeocodeCache = (cache) => {
            try { localStorage.setItem(GEOCODE_CACHE_KEY, JSON.stringify(cache)); }
            catch { /* storage full / disabled — non-fatal */ }
        };

        // Returns { lat, lng } or null. Caches both hits and misses (misses as null)
        // to avoid hammering the geocoder for unresolvable strings.
        // `kind` ("station" | "case") tweaks how we normalise the query: station
        // names often carry suffixes like "PS" / "Police Station" or are org units
        // ("Cyber Crime Division") that geocode better as the bare area name.
        const geocodePlace = async (rawPlace, kind = "case") => {
            const place = (rawPlace || "").trim();
            if (!place) return null;

            const cacheKey = `${kind}:${place}`;
            const cache = _readGeocodeCache();
            if (Object.prototype.hasOwnProperty.call(cache, cacheKey)) {
                return cache[cacheKey];   // may be a coord object or null
            }

            // Build an ordered list of query variants; first hit wins.
            const variants = [];
            const addVariant = (s) => {
                const v = s.trim().replace(/\s+/g, " ");
                if (v && !variants.includes(v)) variants.push(v);
            };

            if (kind === "station") {
                // Strip common station suffixes to get the underlying locality.
                const base = place
                    .replace(/\bpolice station\b/ig, "")
                    .replace(/\bp\.?s\.?\b/ig, "")
                    .trim();
                addVariant(`${place} Police Station`); // exact station, if mapped
                if (base) addVariant(base);            // bare locality, e.g. "Whitefield"
                addVariant(place);                     // raw, last resort
            } else {
                addVariant(place);
            }

            let result = null;
            for (const v of variants) {
                const query = `${v}, Bengaluru, Karnataka, India`;
                try {
                    const res = await fetch(
                        `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(query)}`,
                        { headers: { "Accept": "application/json" } }
                    );
                    if (!res.ok) throw new Error("geocode http " + res.status);
                    const data = await res.json();
                    if (Array.isArray(data) && data.length > 0) {
                        const lat = parseFloat(data[0].lat);
                        const lng = parseFloat(data[0].lon);
                        if (!Number.isNaN(lat) && !Number.isNaN(lng)) {
                            result = { lat, lng };
                            break;
                        }
                    }
                } catch (err) {
                    console.warn("[geocode] failed for", v, err.message);
                    // network hiccup: don't cache, just stop trying further variants
                    return null;
                }
                // Space out multi-variant attempts (Nominatim politeness).
                if (variants.length > 1) await sleep(1100);
            }

            cache[cacheKey] = result;   // cache hit OR confirmed miss (null)
            _writeGeocodeCache(cache);
            return result;
        };

        // Small delay helper so we can space out geocode calls (Nominatim politeness).
        const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
