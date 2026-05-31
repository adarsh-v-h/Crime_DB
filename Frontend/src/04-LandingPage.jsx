        // ─── LANDING PAGE ─────────────────────────────────────────────────────
        const LandingPage = ({ onNavigate, officer }) => {
            const [liveStats, setLiveStats] = useState({
                active_cases: null, solved_cases: null,
                total_officers: null, cyber_cases: null
            });
            useEffect(() => {
                apiFetch("/stats").then(r => setLiveStats(r.data || r)).catch(() => {});
            }, []);

            useEffect(() => {
                document.body.classList.add("landing-hero");
                return () => document.body.classList.remove("landing-hero");
            }, []);

            const heroStats = [
                { label: "Active Cases", value: liveStats.active_cases },
                { label: "Officers Deployed", value: liveStats.total_officers },
                { label: "Cases Solved", value: liveStats.solved_cases },
            ];

            const headingWords = ["Serve", "Protect", "Justice"];

            const todayLine = new Date().toLocaleDateString("en-GB", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });

            return (
                <div className="landing-hero-text paper-texture relative flex min-h-screen min-h-[100dvh] flex-col overflow-hidden">
                    {/* ── MASTHEAD / NAMEPLATE ───────────────────────────────── */}
                    <motion.header
                        className="relative z-20 border-b-2 border-ink/80 px-5 pt-4 sm:px-8"
                        initial="hidden"
                        animate="visible"
                        variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.08 } } }}
                    >
                        <motion.div variants={fadeDown} custom={0} className="mx-auto flex max-w-6xl items-center justify-between text-[9px] font-semibold uppercase tracking-[0.24em] text-ink-muted font-sans">
                            <span className="hidden sm:block">Vol. MMXXVI · No. 1</span>
                            <span>{todayLine}</span>
                            <span className="hidden sm:block">Bengaluru Edition</span>
                        </motion.div>
                        <motion.div variants={fadeDown} custom={1} className="mx-auto max-w-6xl">
                            <h1 className="font-display text-center text-[clamp(2.4rem,7vw,5.5rem)] font-black uppercase leading-[0.9] tracking-tight text-ink-black">
                                Themis&rsquo;s Domain
                            </h1>
                            <div className="mx-auto mt-1 mb-3 flex items-center justify-center gap-3 text-[10px] font-semibold uppercase tracking-[0.3em] text-accent font-sans">
                                <span className="h-px w-8 bg-accent/50" />
                                Bengaluru Police Intelligence Command
                                <span className="h-px w-8 bg-accent/50" />
                            </div>
                        </motion.div>
                    </motion.header>

                    {/* ── PRESS TEXTURE BAND ─────────────────────────────────── */}
                    <motion.div
                        variants={fadeDown}
                        initial="hidden"
                        animate="visible"
                        custom={2}
                        className="relative z-10 mx-auto w-full max-w-6xl overflow-hidden border-b-2 border-ink/80"
                        aria-hidden="true"
                    >
                        <div className="relative h-20 sm:h-28">
                            <img
                                src={EDITORIAL_IMG.press}
                                alt=""
                                loading="lazy"
                                className="h-full w-full object-cover opacity-[0.18] grayscale contrast-125"
                            />
                            <div className="absolute inset-0 flex items-center justify-center">
                                <p className="eyebrow text-center text-ink-muted">
                                    Records · Coordination · Accountability · Investigative Intelligence
                                </p>
                            </div>
                        </div>
                    </motion.div>

                    {/* ── LEAD STORY GRID ────────────────────────────────────── */}
                    <motion.section
                        className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col px-5 py-8 sm:px-8 sm:py-10"
                        initial="hidden"
                        animate="visible"
                        variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.1 } } }}
                    >
                        <div className="grid flex-1 gap-8 lg:grid-cols-[1.6fr_1fr] lg:gap-10">
                            {/* Lead column */}
                            <div className="flex flex-col justify-center border-ink/15 lg:border-r lg:pr-10">
                                <motion.p variants={fadeUp} custom={0} className="kicker mb-3">
                                    The Lead · Command Briefing
                                </motion.p>
                                <div className="overflow-hidden">
                                    {headingWords.map((word, i) => (
                                        <div key={word} className="overflow-hidden">
                                            <motion.h2
                                                variants={slideUpReveal}
                                                initial="hidden"
                                                animate="visible"
                                                custom={i}
                                                className="font-display text-[clamp(3rem,12vw,9rem)] font-black uppercase leading-[0.84] tracking-tight text-ink-black"
                                            >
                                                {word}
                                            </motion.h2>
                                        </div>
                                    ))}
                                </div>
                                <motion.p
                                    variants={fadeUp}
                                    custom={2}
                                    className="dropcap mt-6 max-w-xl font-editorial text-base leading-relaxed text-ink sm:text-lg"
                                >
                                    An advanced intelligence platform for real-time case tracking, officer coordination,
                                    and cybercrime analytics across the city of Bengaluru — uniting the field and the
                                    command room under a single, accountable record.
                                </motion.p>

                                <motion.div variants={fadeUp} custom={3} className="mt-7 flex flex-wrap gap-3">
                                    <button
                                        type="button"
                                        onClick={() => onNavigate("public")}
                                        className="inline-flex items-center gap-2 border-2 border-ink bg-ink-black px-7 py-3 text-[11px] font-bold uppercase tracking-[0.18em] text-paper transition-colors hover:bg-accent hover:border-accent font-sans"
                                    >
                                        <Icon name="Globe" size={16} />
                                        Public Portal
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            if (officer) {
                                                const targetView = (officer.role || "").toLowerCase() === "admin" ? "admin" : "staff";
                                                onNavigate(targetView);
                                            } else {
                                                onNavigate("login");
                                            }
                                        }}
                                        className="inline-flex items-center gap-2 border-2 border-ink bg-transparent px-7 py-3 text-[11px] font-bold uppercase tracking-[0.18em] text-ink transition-colors hover:bg-ink hover:text-paper font-sans"
                                    >
                                        <Icon name="Shield" size={16} />
                                        Staff Dashboard
                                    </button>
                                </motion.div>
                            </div>

                            {/* Sidebar — statistics as editorial pull quotes */}
                            <motion.aside variants={fadeUp} custom={1} className="flex flex-col justify-center">
                                {/* Photo plate — government records archive */}
                                <figure className="mb-6 overflow-hidden border border-ink/20">
                                    <div className="relative">
                                        <img
                                            src={EDITORIAL_IMG.archive}
                                            alt="Rows of departmental case files in the records archive"
                                            loading="lazy"
                                            className="h-44 w-full object-cover grayscale-[35%] sepia-[12%] contrast-[1.05]"
                                        />
                                        <span className="absolute left-0 top-0 bg-ink-black/85 px-2 py-1 text-[8px] font-bold uppercase tracking-[0.22em] text-paper font-sans">
                                            From the Archive
                                        </span>
                                    </div>
                                    <figcaption className="border-t border-ink/15 bg-paper-card px-3 py-2 font-editorial text-[11px] italic text-ink-muted">
                                        Case records, held under departmental custody.
                                    </figcaption>
                                </figure>
                                <p className="eyebrow mb-1 border-b-2 border-ink pb-2">By the Numbers</p>
                                <div className="divide-y divide-ink/15">
                                    {heroStats.map((stat, i) => (
                                        <motion.div
                                            key={stat.label}
                                            variants={fadeUp}
                                            custom={i}
                                            className="flex items-baseline justify-between gap-4 py-5"
                                        >
                                            <p className="max-w-[7rem] text-[10px] font-semibold uppercase leading-tight tracking-[0.18em] text-ink-muted font-sans">
                                                {stat.label}
                                            </p>
                                            <div className="pull-quote text-5xl sm:text-6xl">
                                                {stat.value === null
                                                    ? <span className="inline-block h-10 w-16 animate-pulse rounded bg-ink/10" />
                                                    : <AnimatedCounter value={stat.value} />}
                                            </div>
                                        </motion.div>
                                    ))}
                                </div>
                                <p className="mt-4 font-editorial text-xs italic leading-relaxed text-ink-muted">
                                    Figures drawn live from active departmental records and updated continuously.
                                </p>
                            </motion.aside>
                        </div>
                    </motion.section>

                    {/* ── FOOTER RULE ────────────────────────────────────────── */}
                    <footer className="relative z-10 mx-auto w-full max-w-6xl border-t-2 border-ink/80 px-5 py-3 text-center text-[9px] font-semibold uppercase tracking-[0.24em] text-ink-muted font-sans sm:px-8">
                        Published under authority · Bengaluru Police Department
                    </footer>
                </div>
            );
        };

