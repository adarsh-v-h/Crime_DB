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


        // ─── MAP CONSTANTS ──────────────────────────────────────────────────────
        // Geocoding now happens server-side (DB-cached); see Backend/geocode.py.
        // The map endpoint returns coordinates directly, so the client only needs
        // a sensible default centre for the city.
        const BENGALURU_CENTER = { lat: 12.9716, lng: 77.5946 };
