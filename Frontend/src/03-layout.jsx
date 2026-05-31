        const HeroVideoBackground = ({ scrim = "bg-white/30" }) => (
            <div className="pointer-events-none absolute inset-0 z-0 overflow-hidden" aria-hidden="true">
                <video
                    className="absolute inset-0 h-full w-full object-cover"
                    src={LANDING_VIDEO_URL}
                    autoPlay
                    loop
                    muted
                    playsInline
                />
                <div className={`absolute inset-0 ${scrim}`} />
                <div className="crms-spin-orb absolute -left-24 top-1/4 h-[22rem] w-[22rem] rounded-full bg-gradient-to-br from-accent/25 via-purple-400/15 to-transparent blur-3xl sm:h-[28rem] sm:w-[28rem]" />
                <div className="crms-spin-orb absolute -right-32 bottom-0 h-[18rem] w-[18rem] rounded-full bg-gradient-to-tl from-accent/20 via-violet-300/10 to-transparent blur-3xl" style={{ animationDirection: "reverse", animationDuration: "36s" }} />
            </div>
        );

        const CrmsPageHeader = ({ title, subtitle, onBack }) => (
            <motion.header
                className="relative z-20 border-b-2 border-ink/80 bg-paper/85 backdrop-blur-sm"
                initial="hidden"
                animate="visible"
                variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.08 } } }}
            >
                {/* Top hairline strip — date line / edition marker, newspaper style */}
                <div className="mx-auto flex max-w-6xl items-center justify-between px-4 pt-2 sm:px-8">
                    <span className="hidden text-[9px] font-semibold uppercase tracking-[0.22em] text-ink-muted font-sans sm:block">
                        Bengaluru · Karnataka
                    </span>
                    <span className="text-[9px] font-semibold uppercase tracking-[0.22em] text-ink-muted font-sans">
                        Confidential Briefing
                    </span>
                    <span className="hidden text-[9px] font-semibold uppercase tracking-[0.22em] text-ink-muted font-sans sm:block">
                        {new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "long", year: "numeric" })}
                    </span>
                </div>
                <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-8">
                    <motion.div variants={fadeDown} custom={0} className="flex items-center gap-3">
                        <div className="flex h-11 w-11 items-center justify-center rounded-full border-2 border-ink bg-paper-card">
                            <Icon name="Shield" size={18} className="text-accent" />
                        </div>
                        <div>
                            <div className="font-display text-lg font-extrabold leading-none tracking-tight text-ink-black sm:text-2xl line-clamp-1">{title}</div>
                            {subtitle && (
                                <div className="mt-0.5 text-[8px] sm:text-[10px] font-semibold uppercase tracking-[0.22em] text-ink-muted font-sans line-clamp-1">{subtitle}</div>
                            )}
                        </div>
                    </motion.div>
                    {onBack && (
                        <motion.button
                            type="button"
                            variants={fadeDown}
                            custom={1}
                            onClick={onBack}
                            className="flex items-center gap-1.5 text-[9px] sm:text-[10px] font-semibold uppercase tracking-[0.16em] text-ink transition-colors hover:text-accent shrink-0 font-sans"
                        >
                            <Icon name="ArrowLeft" size={12} />
                            Back to Home
                        </motion.button>
                    )}
                </div>
            </motion.header>
        );

        const CrmsPageShell = ({ children, title, subtitle, onBack, scrim, className = "" }) => {
            return (
                <div className={`landing-hero-text paper-texture relative min-h-screen min-h-[100dvh] ${className}`}>
                    <CrmsPageHeader title={title} subtitle={subtitle} onBack={onBack} />
                    <div className="relative z-10">{children}</div>
                </div>
            );
        };

