import { useState, useEffect, useRef } from "react";
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

// ─── DUMMY DATA ───────────────────────────────────────────────────────────────
const OFFICERS_DATA = [
  { officer_id: 1, name: "Ravi Kumar", rank: "Inspector" },
  { officer_id: 2, name: "Priya Nair", rank: "Sub-Inspector" },
  { officer_id: 3, name: "Arjun Shetty", rank: "Deputy Commissioner" },
  { officer_id: 4, name: "Deepa Rao", rank: "Inspector" },
  { officer_id: 5, name: "Kiran Reddy", rank: "Constable" },
  { officer_id: 6, name: "Meena Pillai", rank: "Sub-Inspector" },
  { officer_id: 7, name: "Suresh Gowda", rank: "Inspector" },
  { officer_id: 8, name: "Anil Patel", rank: "Constable" },
];

const CASES_DATA = [
  { case_id: 1, title: "UPI Phishing Ring – Koramangala", description: "Victim received fraudulent UPI payment requests mimicking BBMP tax portal. Rs 2.4L transferred before detection.", crime_type: "Cyber Fraud", status: "Active", date_reported: "2025-01-14", location: "Koramangala", complaint_mode: "Online", last_updated: "2025-04-10", officers: [1, 2] },
  { case_id: 2, title: "Armed Robbery – Commercial Street", description: "Three suspects robbed a jewellery store at knifepoint. CCTV footage obtained.", crime_type: "Theft", status: "Solved", date_reported: "2025-02-03", location: "Commercial Street", complaint_mode: "Offline", last_updated: "2025-03-28", officers: [3, 4] },
  { case_id: 3, title: "Assault – Indiranagar Bar Fight", description: "Physical altercation resulting in serious injury. Two suspects identified.", crime_type: "Assault", status: "Active", date_reported: "2025-02-18", location: "Indiranagar", complaint_mode: "Offline", last_updated: "2025-04-15", officers: [5] },
  { case_id: 4, title: "Investment Fraud – Whitefield Tech Hub", description: "Ponzi scheme targeting IT employees. 47 victims. Rs 62L collected by fraudsters.", crime_type: "Fraud", status: "Active", date_reported: "2025-03-01", location: "Whitefield", complaint_mode: "Online", last_updated: "2025-04-20", officers: [1, 6, 7] },
  { case_id: 5, title: "Vehicle Theft – Malleshwaram", description: "High-end motorcycle stolen from apartment complex parking. Tracking device recovered.", crime_type: "Theft", status: "Solved", date_reported: "2025-03-09", location: "Malleshwaram", complaint_mode: "Offline", last_updated: "2025-04-01", officers: [8] },
  { case_id: 6, title: "Deepfake Extortion – HSR Layout", description: "Victim blackmailed using AI-generated intimate images. Digital forensics underway.", crime_type: "Cyber Fraud", status: "Active", date_reported: "2025-03-22", location: "HSR Layout", complaint_mode: "Online", last_updated: "2025-04-22", officers: [2, 4] },
  { case_id: 7, title: "Domestic Violence – Jayanagar", description: "Repeated domestic assault. Victim placed in shelter. Suspect in custody.", crime_type: "Assault", status: "Closed", date_reported: "2025-01-05", location: "Jayanagar", complaint_mode: "Offline", last_updated: "2025-02-10", officers: [6] },
  { case_id: 8, title: "SIM Swap Fraud – MG Road", description: "Victim's SIM cloned, bank accounts drained. Telecom company cooperation obtained.", crime_type: "Cyber Fraud", status: "Solved", date_reported: "2025-04-01", location: "MG Road", complaint_mode: "Online", last_updated: "2025-04-18", officers: [1, 3] },
  { case_id: 9, title: "Bag Snatching – Cubbon Park", description: "Tourist's bag containing passport and Rs 30K cash snatched near park entrance.", crime_type: "Theft", status: "Active", date_reported: "2025-04-05", location: "Cubbon Park", complaint_mode: "Offline", last_updated: "2025-04-21", officers: [5, 8] },
  { case_id: 10, title: "Ransomware – Rajajinagar Factory", description: "Small manufacturing unit's systems encrypted. Rs 8L ransom demanded in crypto.", crime_type: "Cyber Fraud", status: "Active", date_reported: "2025-04-12", location: "Rajajinagar", complaint_mode: "Online", last_updated: "2025-04-23", officers: [7] },
  { case_id: 11, title: "Chain Snatching – Electronic City", description: "Victim on morning walk targeted by two-wheeler riders. Gold chain valued at Rs 1.8L.", crime_type: "Theft", status: "Active", date_reported: "2025-04-14", location: "Electronic City", complaint_mode: "Online", last_updated: "2025-04-22", officers: [4, 5] },
  { case_id: 12, title: "Fake Job Offer Fraud – BTM Layout", description: "Recruitment scam targeting freshers. Victims charged Rs 50K for non-existent positions.", crime_type: "Fraud", status: "Closed", date_reported: "2025-01-29", location: "BTM Layout", complaint_mode: "Online", last_updated: "2025-03-15", officers: [2, 6] },
];

const MONTHLY_DATA = [
  { month: "Nov", cases: 18, cyber: 7 },
  { month: "Dec", cases: 22, cyber: 9 },
  { month: "Jan", cases: 31, cyber: 14 },
  { month: "Feb", cases: 27, cyber: 11 },
  { month: "Mar", cases: 35, cyber: 16 },
  { month: "Apr", cases: 29, cyber: 13 },
];

const CRIME_DIST = [
  { name: "Cyber Fraud", value: 4, color: "#6366f1" },
  { name: "Theft", value: 4, color: "#22d3ee" },
  { name: "Fraud", value: 2, color: "#f59e0b" },
  { name: "Assault", value: 2, color: "#ef4444" },
];

const ZONE_DATA = [
  { zone: "South", active: 3, solved: 2, closed: 1 },
  { zone: "North", active: 2, solved: 1, closed: 0 },
  { zone: "East", active: 4, solved: 2, closed: 1 },
  { zone: "West", active: 2, solved: 1, closed: 1 },
  { zone: "Central", active: 1, solved: 1, closed: 0 },
];

// ─── HELPERS ──────────────────────────────────────────────────────────────────
const STATUS_CONFIG = {
  Active: { bg: "rgba(99,102,241,0.15)", color: "#818cf8", border: "rgba(99,102,241,0.4)" },
  Solved: { bg: "rgba(34,211,238,0.12)", color: "#22d3ee", border: "rgba(34,211,238,0.35)" },
  Closed: { bg: "rgba(100,116,139,0.15)", color: "#94a3b8", border: "rgba(100,116,139,0.3)" },
};
const CRIME_CONFIG = {
  "Cyber Fraud": { color: "#818cf8", icon: "🌐" },
  Theft: { color: "#22d3ee", icon: "🔓" },
  Fraud: { color: "#f59e0b", icon: "⚠️" },
  Assault: { color: "#ef4444", icon: "⚡" },
  Other: { color: "#94a3b8", icon: "📋" },
};

const getInitials = (name) => name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
const fmtDate = (d) => new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

const AVATAR_COLORS = ["#6366f1","#22d3ee","#f59e0b","#ec4899","#10b981","#f97316","#8b5cf6","#06b6d4"];

// ─── STYLE CONSTANTS ──────────────────────────────────────────────────────────
const css = {
  bg: "#09090f",
  bgCard: "rgba(255,255,255,0.04)",
  bgCardHover: "rgba(255,255,255,0.07)",
  border: "rgba(255,255,255,0.08)",
  borderGlow: "rgba(99,102,241,0.35)",
  accent: "#6366f1",
  accentCyan: "#22d3ee",
  text: "#f1f5f9",
  textMuted: "#64748b",
  textSub: "#94a3b8",
};

// ─── MICRO COMPONENTS ─────────────────────────────────────────────────────────
const StatusBadge = ({ status }) => {
  const c = STATUS_CONFIG[status] || STATUS_CONFIG.Closed;
  return (
    <span style={{ background: c.bg, color: c.color, border: `1px solid ${c.border}`, borderRadius: 6, padding: "2px 10px", fontSize: 11, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" }}>
      {status}
    </span>
  );
};

const CrimeBadge = ({ type }) => {
  const c = CRIME_CONFIG[type] || CRIME_CONFIG.Other;
  return (
    <span style={{ background: `${c.color}18`, color: c.color, border: `1px solid ${c.color}33`, borderRadius: 6, padding: "2px 10px", fontSize: 11, fontWeight: 500 }}>
      {c.icon} {type}
    </span>
  );
};

const MetricCard = ({ label, value, sub, color = "#6366f1", glow }) => (
  <div style={{
    background: css.bgCard,
    border: `1px solid ${glow ? color + "40" : css.border}`,
    borderRadius: 16,
    padding: "20px 24px",
    boxShadow: glow ? `0 0 24px ${color}18, inset 0 1px 0 rgba(255,255,255,0.06)` : "inset 0 1px 0 rgba(255,255,255,0.04)",
    position: "relative",
    overflow: "hidden",
    flex: 1,
  }}>
    <div style={{ position: "absolute", top: 0, right: 0, width: 120, height: 120, background: `radial-gradient(circle at 100% 0%, ${color}12 0%, transparent 70%)`, borderRadius: "0 16px 0 0" }} />
    <div style={{ fontSize: 12, color: css.textMuted, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>{label}</div>
    <div style={{ fontSize: 36, fontWeight: 700, color: css.text, lineHeight: 1, marginBottom: 6, fontFamily: "'JetBrains Mono', monospace" }}>{value}</div>
    {sub && <div style={{ fontSize: 12, color, fontWeight: 500 }}>{sub}</div>}
  </div>
);

const GlassPanel = ({ children, style }) => (
  <div style={{
    background: "rgba(255,255,255,0.03)",
    backdropFilter: "blur(12px)",
    border: `1px solid ${css.border}`,
    borderRadius: 16,
    ...style,
  }}>
    {children}
  </div>
);

const SectionHeader = ({ title, action }) => (
  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
    <div style={{ fontSize: 13, fontWeight: 700, color: css.textSub, textTransform: "uppercase", letterSpacing: "0.1em" }}>{title}</div>
    {action}
  </div>
);

// ─── TOAST ────────────────────────────────────────────────────────────────────
const Toast = ({ msg, onClose }) => (
  <div style={{
    position: "fixed", bottom: 28, right: 28, zIndex: 9999,
    background: "rgba(15,15,25,0.95)", border: `1px solid ${css.accentCyan}40`,
    borderRadius: 12, padding: "14px 20px", display: "flex", alignItems: "center", gap: 12,
    boxShadow: `0 0 30px ${css.accentCyan}20`, color: css.text, fontSize: 14,
    backdropFilter: "blur(20px)", animation: "slideUp 0.3s ease",
  }}>
    <span style={{ color: css.accentCyan, fontSize: 18 }}>✓</span>
    {msg}
    <button onClick={onClose} style={{ background: "none", border: "none", color: css.textMuted, cursor: "pointer", marginLeft: 8, fontSize: 18, lineHeight: 1 }}>×</button>
  </div>
);

// ─── MODAL ────────────────────────────────────────────────────────────────────
const Modal = ({ title, onClose, children }) => (
  <div style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,0.75)", backdropFilter: "blur(8px)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
    <div style={{ background: "#0f0f1a", border: `1px solid ${css.borderGlow}`, borderRadius: 20, padding: 32, width: "100%", maxWidth: 560, maxHeight: "85vh", overflow: "auto", boxShadow: `0 0 60px rgba(99,102,241,0.12)` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
        <div style={{ fontSize: 18, fontWeight: 700, color: css.text }}>{title}</div>
        <button onClick={onClose} style={{ background: "rgba(255,255,255,0.06)", border: "none", color: css.textSub, cursor: "pointer", borderRadius: 8, width: 32, height: 32, fontSize: 18, display: "flex", alignItems: "center", justifyContent: "center" }}>×</button>
      </div>
      {children}
    </div>
  </div>
);

const inputStyle = {
  width: "100%", background: "rgba(255,255,255,0.05)", border: `1px solid ${css.border}`,
  borderRadius: 10, padding: "10px 14px", color: css.text, fontSize: 14, outline: "none",
  boxSizing: "border-box", fontFamily: "inherit",
};
const labelStyle = { fontSize: 12, color: css.textMuted, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.07em", marginBottom: 6, display: "block" };
const btnPrimary = {
  background: css.accent, color: "#fff", border: "none", borderRadius: 10,
  padding: "10px 22px", fontSize: 14, fontWeight: 600, cursor: "pointer",
};
const btnSec = {
  background: "rgba(255,255,255,0.06)", color: css.textSub, border: `1px solid ${css.border}`,
  borderRadius: 10, padding: "10px 22px", fontSize: 14, fontWeight: 600, cursor: "pointer",
};

// ─── VIEWS ────────────────────────────────────────────────────────────────────

// DASHBOARD
function DashboardView({ cases, officers, onNavigate }) {
  const active = cases.filter(c => c.status === "Active").length;
  const solved = cases.filter(c => c.status === "Solved").length;
  const cyber = cases.filter(c => c.crime_type === "Cyber Fraud").length;

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{ background: "#0f0f1a", border: `1px solid ${css.border}`, borderRadius: 10, padding: "10px 16px" }}>
        <div style={{ color: css.textSub, fontSize: 12, marginBottom: 4 }}>{label}</div>
        {payload.map((p, i) => <div key={i} style={{ color: p.color, fontSize: 13, fontWeight: 600 }}>{p.name}: {p.value}</div>)}
      </div>
    );
  };

  return (
    <div>
      {/* METRICS */}
      <div style={{ display: "flex", gap: 16, marginBottom: 24, flexWrap: "wrap" }}>
        <MetricCard label="Total Cases" value={cases.length} sub="↑ 14% this month" color="#6366f1" glow />
        <MetricCard label="Active Cases" value={active} sub="Under investigation" color="#f59e0b" glow />
        <MetricCard label="Solved" value={solved} sub="↑ 22% solve rate" color="#22d3ee" glow />
        <MetricCard label="Cyber Crime" value={cyber} sub="▲ High priority" color="#ef4444" glow />
      </div>

      {/* CHARTS ROW */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, marginBottom: 16 }}>
        <GlassPanel style={{ padding: 24 }}>
          <SectionHeader title="Monthly Case Volume" />
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={MONTHLY_DATA}>
              <defs>
                <linearGradient id="cg1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="cg2" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="month" tick={{ fill: css.textMuted, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: css.textMuted, fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="cases" name="Total Cases" stroke="#6366f1" fill="url(#cg1)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="cyber" name="Cyber Cases" stroke="#22d3ee" fill="url(#cg2)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </GlassPanel>

        <GlassPanel style={{ padding: 24 }}>
          <SectionHeader title="Crime Distribution" />
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={CRIME_DIST} cx="50%" cy="50%" innerRadius={50} outerRadius={75} paddingAngle={4} dataKey="value">
                {CRIME_DIST.map((entry, i) => <Cell key={i} fill={entry.color} opacity={0.85} />)}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
            {CRIME_DIST.map((d, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: css.textSub }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: d.color, display: "inline-block" }} />
                {d.name}
              </div>
            ))}
          </div>
        </GlassPanel>
      </div>

      {/* ZONE + RECENT */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <GlassPanel style={{ padding: 24 }}>
          <SectionHeader title="Zone Activity" />
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={ZONE_DATA} barSize={10}>
              <XAxis dataKey="zone" tick={{ fill: css.textMuted, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: css.textMuted, fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="active" name="Active" fill="#6366f1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="solved" name="Solved" fill="#22d3ee" radius={[4, 4, 0, 0]} />
              <Bar dataKey="closed" name="Closed" fill="#475569" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </GlassPanel>

        <GlassPanel style={{ padding: 24 }}>
          <SectionHeader title="Recent Activity" action={<button onClick={() => onNavigate("cases")} style={{ ...btnSec, padding: "5px 14px", fontSize: 12 }}>All Cases →</button>} />
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {cases.slice(0, 5).map(c => (
              <div key={c.case_id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: `1px solid ${css.border}`, paddingBottom: 10 }}>
                <div>
                  <div style={{ fontSize: 13, color: css.text, fontWeight: 500, marginBottom: 2 }}>{c.title.slice(0, 36)}{c.title.length > 36 ? "…" : ""}</div>
                  <div style={{ fontSize: 11, color: css.textMuted }}>{c.location} · {fmtDate(c.date_reported)}</div>
                </div>
                <StatusBadge status={c.status} />
              </div>
            ))}
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}

// CASES VIEW
function CasesView({ cases, officers, setCases, showToast }) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [typeFilter, setTypeFilter] = useState("All");
  const [expanded, setExpanded] = useState(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newCase, setNewCase] = useState({ title: "", description: "", crime_type: "Cyber Fraud", status: "Active", location: "", complaint_mode: "Online" });

  const filtered = cases.filter(c => {
    const q = search.toLowerCase();
    return (
      (statusFilter === "All" || c.status === statusFilter) &&
      (typeFilter === "All" || c.crime_type === typeFilter) &&
      (!q || c.title.toLowerCase().includes(q) || c.location.toLowerCase().includes(q))
    );
  });

  const handleAdd = () => {
    if (!newCase.title.trim() || !newCase.location.trim()) { showToast("Title and Location are required."); return; }
    const id = Math.max(...cases.map(c => c.case_id)) + 1;
    setCases(prev => [{ ...newCase, case_id: id, date_reported: new Date().toISOString().split("T")[0], last_updated: new Date().toISOString().split("T")[0], officers: [] }, ...prev]);
    setShowAdd(false);
    setNewCase({ title: "", description: "", crime_type: "Cyber Fraud", status: "Active", location: "", complaint_mode: "Online" });
    showToast("Case registered successfully.");
  };

  const updateStatus = (id, status) => {
    setCases(prev => prev.map(c => c.case_id === id ? { ...c, status, last_updated: new Date().toISOString().split("T")[0] } : c));
    showToast(`Case status updated to ${status}`);
  };

  return (
    <div>
      {/* CONTROLS */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20, alignItems: "center", flexWrap: "wrap" }}>
        <input
          placeholder="Search cases, locations..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ ...inputStyle, flex: 1, minWidth: 200 }}
        />
        {["All", "Active", "Solved", "Closed"].map(s => (
          <button key={s} onClick={() => setStatusFilter(s)} style={{
            background: statusFilter === s ? css.accent : "rgba(255,255,255,0.05)",
            color: statusFilter === s ? "#fff" : css.textSub,
            border: `1px solid ${statusFilter === s ? css.accent : css.border}`,
            borderRadius: 8, padding: "7px 16px", fontSize: 12, fontWeight: 600, cursor: "pointer",
          }}>{s}</button>
        ))}
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} style={{ ...inputStyle, width: "auto", padding: "8px 14px" }}>
          {["All", "Cyber Fraud", "Theft", "Fraud", "Assault"].map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <button onClick={() => setShowAdd(true)} style={{ ...btnPrimary, whiteSpace: "nowrap" }}>+ New Case</button>
      </div>

      {/* CASE LIST */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {filtered.length === 0 && (
          <div style={{ textAlign: "center", padding: 60, color: css.textMuted }}>
            <div style={{ fontSize: 36, marginBottom: 12 }}>🔍</div>
            No cases match your filters.
          </div>
        )}
        {filtered.map(c => {
          const isExp = expanded === c.case_id;
          const caseOfficers = officers.filter(o => c.officers.includes(o.officer_id));
          return (
            <div key={c.case_id} style={{
              background: isExp ? "rgba(99,102,241,0.07)" : css.bgCard,
              border: `1px solid ${isExp ? css.borderGlow : css.border}`,
              borderRadius: 14, overflow: "hidden",
              boxShadow: isExp ? `0 0 20px rgba(99,102,241,0.1)` : "none",
              transition: "all 0.2s ease",
            }}>
              <div
                onClick={() => setExpanded(isExp ? null : c.case_id)}
                style={{ padding: "16px 20px", cursor: "pointer", display: "flex", alignItems: "center", gap: 16 }}
              >
                <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: css.textMuted, minWidth: 54 }}>BLR-{String(c.case_id).padStart(3, "0")}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: css.text, marginBottom: 4 }}>{c.title}</div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <span style={{ fontSize: 11, color: css.textMuted }}>📍 {c.location}</span>
                    <span style={{ fontSize: 11, color: css.textMuted }}>·</span>
                    <span style={{ fontSize: 11, color: css.textMuted }}>{fmtDate(c.date_reported)}</span>
                    <span style={{ fontSize: 11, color: css.textMuted }}>·</span>
                    <span style={{ fontSize: 11, color: c.complaint_mode === "Online" ? css.accentCyan : css.textMuted }}>{c.complaint_mode}</span>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <CrimeBadge type={c.crime_type} />
                  <StatusBadge status={c.status} />
                </div>
                <div style={{ color: css.textMuted, fontSize: 18, transition: "transform 0.2s", transform: isExp ? "rotate(180deg)" : "rotate(0deg)" }}>⌄</div>
              </div>
              {isExp && (
                <div style={{ padding: "0 20px 20px", borderTop: `1px solid ${css.border}`, marginTop: 4 }}>
                  <div style={{ paddingTop: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                    <div>
                      <div style={labelStyle}>Description</div>
                      <div style={{ fontSize: 13, color: css.textSub, lineHeight: 1.7 }}>{c.description || "No description available."}</div>
                      <div style={{ marginTop: 16 }}>
                        <div style={labelStyle}>Update Status</div>
                        <div style={{ display: "flex", gap: 8 }}>
                          {["Active", "Solved", "Closed"].map(s => (
                            <button key={s} onClick={() => updateStatus(c.case_id, s)} style={{
                              background: c.status === s ? STATUS_CONFIG[s].bg : "transparent",
                              color: c.status === s ? STATUS_CONFIG[s].color : css.textMuted,
                              border: `1px solid ${c.status === s ? STATUS_CONFIG[s].border : css.border}`,
                              borderRadius: 7, padding: "5px 14px", fontSize: 11, fontWeight: 600, cursor: "pointer",
                            }}>{s}</button>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div>
                      <div style={labelStyle}>Assigned Officers ({caseOfficers.length})</div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {caseOfficers.length === 0 && <div style={{ fontSize: 13, color: css.textMuted }}>No officers assigned.</div>}
                        {caseOfficers.map(o => (
                          <div key={o.officer_id} style={{ display: "flex", alignItems: "center", gap: 10, background: "rgba(255,255,255,0.03)", borderRadius: 8, padding: "8px 12px" }}>
                            <div style={{ width: 30, height: 30, borderRadius: "50%", background: AVATAR_COLORS[o.officer_id % 8], display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "#fff" }}>{getInitials(o.name)}</div>
                            <div>
                              <div style={{ fontSize: 13, color: css.text, fontWeight: 500 }}>{o.name}</div>
                              <div style={{ fontSize: 11, color: css.textMuted }}>{o.rank}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                        <div style={{ fontSize: 11, color: css.textMuted }}>Last updated: {fmtDate(c.last_updated)}</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* ADD MODAL */}
      {showAdd && (
        <Modal title="Register New Case" onClose={() => setShowAdd(false)}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label style={labelStyle}>Case Title *</label>
              <input style={inputStyle} value={newCase.title} onChange={e => setNewCase(p => ({ ...p, title: e.target.value }))} placeholder="Brief incident title" />
            </div>
            <div>
              <label style={labelStyle}>Description</label>
              <textarea style={{ ...inputStyle, height: 80, resize: "vertical" }} value={newCase.description} onChange={e => setNewCase(p => ({ ...p, description: e.target.value }))} placeholder="Detailed incident description..." />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={labelStyle}>Crime Type</label>
                <select style={inputStyle} value={newCase.crime_type} onChange={e => setNewCase(p => ({ ...p, crime_type: e.target.value }))}>
                  {["Cyber Fraud", "Theft", "Assault", "Fraud", "Other"].map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label style={labelStyle}>Status</label>
                <select style={inputStyle} value={newCase.status} onChange={e => setNewCase(p => ({ ...p, status: e.target.value }))}>
                  {["Active", "Solved", "Closed"].map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={labelStyle}>Location *</label>
                <input style={inputStyle} value={newCase.location} onChange={e => setNewCase(p => ({ ...p, location: e.target.value }))} placeholder="Bengaluru area" />
              </div>
              <div>
                <label style={labelStyle}>Complaint Mode</label>
                <select style={inputStyle} value={newCase.complaint_mode} onChange={e => setNewCase(p => ({ ...p, complaint_mode: e.target.value }))}>
                  <option>Online</option><option>Offline</option>
                </select>
              </div>
            </div>
            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end", marginTop: 8 }}>
              <button style={btnSec} onClick={() => setShowAdd(false)}>Cancel</button>
              <button style={btnPrimary} onClick={handleAdd}>Register Case</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// OFFICERS VIEW
function OfficersView({ officers, cases }) {
  const getCaseCount = (id) => cases.filter(c => c.officers.includes(id)).length;
  const getActiveCases = (id) => cases.filter(c => c.officers.includes(id) && c.status === "Active").length;
  const RANK_ORDER = ["Deputy Commissioner", "Inspector", "Sub-Inspector", "Constable"];

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
        {officers.map(o => {
          const total = getCaseCount(o.officer_id);
          const active = getActiveCases(o.officer_id);
          const workload = total > 0 ? Math.min(100, (active / 5) * 100) : 0;
          const av = AVATAR_COLORS[o.officer_id % 8];
          return (
            <div key={o.officer_id} style={{
              background: css.bgCard, border: `1px solid ${css.border}`, borderRadius: 16,
              padding: 24, display: "flex", flexDirection: "column", gap: 16,
              transition: "all 0.2s ease", cursor: "default",
            }}
              onMouseEnter={e => { e.currentTarget.style.border = `1px solid ${css.borderGlow}`; e.currentTarget.style.boxShadow = `0 0 20px rgba(99,102,241,0.1)`; }}
              onMouseLeave={e => { e.currentTarget.style.border = `1px solid ${css.border}`; e.currentTarget.style.boxShadow = "none"; }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                <div style={{ width: 54, height: 54, borderRadius: "50%", background: `linear-gradient(135deg, ${av}, ${av}99)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, fontWeight: 700, color: "#fff", boxShadow: `0 0 20px ${av}40`, flexShrink: 0 }}>
                  {getInitials(o.name)}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 15, fontWeight: 700, color: css.text, marginBottom: 4 }}>{o.name}</div>
                  <div style={{ background: `${av}20`, color: av, border: `1px solid ${av}40`, borderRadius: 6, padding: "2px 10px", fontSize: 11, fontWeight: 600, display: "inline-block" }}>{o.rank}</div>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 10, padding: "10px 14px", textAlign: "center" }}>
                  <div style={{ fontSize: 22, fontWeight: 700, color: css.text, fontFamily: "'JetBrains Mono', monospace" }}>{total}</div>
                  <div style={{ fontSize: 11, color: css.textMuted }}>Total Cases</div>
                </div>
                <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 10, padding: "10px 14px", textAlign: "center" }}>
                  <div style={{ fontSize: 22, fontWeight: 700, color: "#818cf8", fontFamily: "'JetBrains Mono', monospace" }}>{active}</div>
                  <div style={{ fontSize: 11, color: css.textMuted }}>Active</div>
                </div>
              </div>

              <div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: css.textMuted, marginBottom: 6 }}>
                  <span>Workload</span>
                  <span style={{ color: workload > 70 ? "#ef4444" : workload > 40 ? "#f59e0b" : "#22d3ee" }}>{Math.round(workload)}%</span>
                </div>
                <div style={{ height: 4, background: "rgba(255,255,255,0.08)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${workload}%`, background: workload > 70 ? "#ef4444" : workload > 40 ? "#f59e0b" : "#22d3ee", borderRadius: 2, transition: "width 0.5s ease" }} />
                </div>
              </div>

              <div style={{ fontSize: 11, color: css.textMuted }}>
                ID: <span style={{ fontFamily: "'JetBrains Mono', monospace", color: css.textSub }}>OFF-{String(o.officer_id).padStart(3, "0")}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ASSIGNMENTS VIEW
function AssignmentsView({ cases, officers }) {
  const [filter, setFilter] = useState("All");
  const assignments = [];
  cases.forEach(c => {
    c.officers.forEach(oid => {
      const o = officers.find(x => x.officer_id === oid);
      if (o) assignments.push({ case_id: c.case_id, case_title: c.title, crime_type: c.crime_type, status: c.status, location: c.location, officer_id: oid, officer_name: o.name, rank: o.rank });
    });
  });

  const filtered = filter === "All" ? assignments : assignments.filter(a => a.status === filter);

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {["All", "Active", "Solved", "Closed"].map(s => (
          <button key={s} onClick={() => setFilter(s)} style={{
            background: filter === s ? css.accent : "rgba(255,255,255,0.05)",
            color: filter === s ? "#fff" : css.textSub,
            border: `1px solid ${filter === s ? css.accent : css.border}`,
            borderRadius: 8, padding: "7px 16px", fontSize: 12, fontWeight: 600, cursor: "pointer",
          }}>{s}</button>
        ))}
        <div style={{ marginLeft: "auto", fontSize: 12, color: css.textMuted, display: "flex", alignItems: "center" }}>
          {filtered.length} assignments
        </div>
      </div>

      <GlassPanel style={{ overflow: "hidden" }}>
        <div style={{ padding: "14px 20px", borderBottom: `1px solid ${css.border}`, display: "grid", gridTemplateColumns: "90px 1fr 140px 120px 110px 100px", gap: 12 }}>
          {["Case ID", "Case / Officer", "Crime Type", "Location", "Status", "Rank"].map(h => (
            <div key={h} style={{ fontSize: 11, color: css.textMuted, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.07em" }}>{h}</div>
          ))}
        </div>
        {filtered.map((a, i) => (
          <div key={i} style={{
            padding: "14px 20px", borderBottom: `1px solid ${css.border}`,
            display: "grid", gridTemplateColumns: "90px 1fr 140px 120px 110px 100px", gap: 12,
            alignItems: "center", transition: "background 0.15s",
          }}
            onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.03)"}
            onMouseLeave={e => e.currentTarget.style.background = "transparent"}
          >
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: css.accentCyan }}>BLR-{String(a.case_id).padStart(3, "0")}</div>
            <div>
              <div style={{ fontSize: 13, color: css.text, fontWeight: 500, marginBottom: 2 }}>{a.case_title.slice(0, 40)}{a.case_title.length > 40 ? "…" : ""}</div>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 20, height: 20, borderRadius: "50%", background: AVATAR_COLORS[a.officer_id % 8], display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9, fontWeight: 700, color: "#fff" }}>{getInitials(a.officer_name)}</div>
                <span style={{ fontSize: 12, color: css.textSub }}>{a.officer_name}</span>
              </div>
            </div>
            <div><CrimeBadge type={a.crime_type} /></div>
            <div style={{ fontSize: 12, color: css.textMuted }}>📍 {a.location}</div>
            <div><StatusBadge status={a.status} /></div>
            <div style={{ fontSize: 12, color: css.textSub }}>{a.rank}</div>
          </div>
        ))}
      </GlassPanel>
    </div>
  );
}

// ANALYTICS VIEW
function AnalyticsView({ cases }) {
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={{ background: "#0f0f1a", border: `1px solid ${css.border}`, borderRadius: 10, padding: "10px 16px" }}>
        <div style={{ color: css.textSub, fontSize: 12, marginBottom: 4 }}>{label}</div>
        {payload.map((p, i) => <div key={i} style={{ color: p.color || css.accentCyan, fontSize: 13, fontWeight: 600 }}>{p.name}: {p.value}</div>)}
      </div>
    );
  };
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <GlassPanel style={{ padding: 24 }}>
        <SectionHeader title="Monthly Trends" />
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={MONTHLY_DATA}>
            <XAxis dataKey="month" tick={{ fill: css.textMuted, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: css.textMuted, fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Line type="monotone" dataKey="cases" name="Total Cases" stroke="#6366f1" strokeWidth={2.5} dot={{ fill: "#6366f1", strokeWidth: 0, r: 4 }} activeDot={{ r: 6 }} />
            <Line type="monotone" dataKey="cyber" name="Cyber Cases" stroke="#22d3ee" strokeWidth={2.5} dot={{ fill: "#22d3ee", strokeWidth: 0, r: 4 }} activeDot={{ r: 6 }} />
          </LineChart>
        </ResponsiveContainer>
      </GlassPanel>

      <GlassPanel style={{ padding: 24 }}>
        <SectionHeader title="Crime Type Breakdown" />
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={CRIME_DIST} barSize={36}>
            <XAxis dataKey="name" tick={{ fill: css.textMuted, fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: css.textMuted, fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="value" name="Cases" radius={[6, 6, 0, 0]}>
              {CRIME_DIST.map((entry, i) => <Cell key={i} fill={entry.color} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </GlassPanel>

      <GlassPanel style={{ padding: 24 }}>
        <SectionHeader title="Zone Intelligence" />
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={ZONE_DATA} layout="vertical">
            <XAxis type="number" tick={{ fill: css.textMuted, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="zone" tick={{ fill: css.textSub, fontSize: 12 }} axisLine={false} tickLine={false} width={52} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="active" name="Active" fill="#6366f1" radius={[0, 4, 4, 0]} barSize={10} />
            <Bar dataKey="solved" name="Solved" fill="#22d3ee" radius={[0, 4, 4, 0]} barSize={10} />
          </BarChart>
        </ResponsiveContainer>
      </GlassPanel>

      <GlassPanel style={{ padding: 24 }}>
        <SectionHeader title="Status Overview" />
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie
              data={[
                { name: "Active", value: cases.filter(c => c.status === "Active").length },
                { name: "Solved", value: cases.filter(c => c.status === "Solved").length },
                { name: "Closed", value: cases.filter(c => c.status === "Closed").length },
              ]}
              cx="50%" cy="50%" outerRadius={80} paddingAngle={5} dataKey="value"
            >
              <Cell fill="#6366f1" />
              <Cell fill="#22d3ee" />
              <Cell fill="#475569" />
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend formatter={(v) => <span style={{ color: css.textSub, fontSize: 12 }}>{v}</span>} />
          </PieChart>
        </ResponsiveContainer>
      </GlassPanel>
    </div>
  );
}

// ─── STAFF PORTAL ─────────────────────────────────────────────────────────────
function StaffPortal({ onExit }) {
  const [cases, setCases] = useState(CASES_DATA);
  const [view, setView] = useState("dashboard");
  const [toast, setToast] = useState(null);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3000); };

  const NAV = [
    { id: "dashboard", label: "Dashboard", icon: "⬡" },
    { id: "cases", label: "Cases", icon: "◈" },
    { id: "officers", label: "Officers", icon: "◉" },
    { id: "assignments", label: "Assignments", icon: "◎" },
    { id: "analytics", label: "Analytics", icon: "◆" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: css.bg, color: css.text, fontFamily: "'Inter', 'Segoe UI', system-ui, sans-serif", display: "flex" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap'); * { box-sizing: border-box; } ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-track { background: transparent; } ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; } @keyframes slideUp { from { transform: translateY(16px); opacity: 0; } to { transform: translateY(0); opacity: 1; } } @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }`}</style>

      {/* SIDEBAR */}
      <div style={{ width: 220, background: "rgba(255,255,255,0.02)", borderRight: `1px solid ${css.border}`, display: "flex", flexDirection: "column", padding: "0 0 20px", flexShrink: 0, position: "sticky", top: 0, height: "100vh", overflowY: "auto" }}>
        <div style={{ padding: "24px 20px 20px", borderBottom: `1px solid ${css.border}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: `linear-gradient(135deg, ${css.accent}, ${css.accentCyan})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 900, color: "#fff" }}>C</div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: css.text, letterSpacing: "0.05em" }}>CRMS</div>
              <div style={{ fontSize: 9, color: css.textMuted, textTransform: "uppercase", letterSpacing: "0.1em" }}>Bengaluru PD</div>
            </div>
          </div>
        </div>

        <nav style={{ padding: "16px 12px", flex: 1 }}>
          {NAV.map(n => (
            <button key={n.id} onClick={() => setView(n.id)} style={{
              display: "flex", alignItems: "center", gap: 10, width: "100%",
              padding: "9px 12px", marginBottom: 2, borderRadius: 10, border: "none", cursor: "pointer",
              background: view === n.id ? "rgba(99,102,241,0.15)" : "transparent",
              color: view === n.id ? "#818cf8" : css.textSub,
              fontSize: 13, fontWeight: view === n.id ? 600 : 400, textAlign: "left",
              borderLeft: view === n.id ? `2px solid ${css.accent}` : "2px solid transparent",
              transition: "all 0.15s",
            }}>
              <span style={{ fontSize: 16 }}>{n.icon}</span>
              {n.label}
            </button>
          ))}
        </nav>

        <div style={{ padding: "0 12px" }}>
          <div style={{ background: "rgba(99,102,241,0.08)", border: `1px solid rgba(99,102,241,0.2)`, borderRadius: 10, padding: "12px 14px", marginBottom: 10 }}>
            <div style={{ fontSize: 11, color: css.textMuted, marginBottom: 2 }}>Logged in as</div>
            <div style={{ fontSize: 13, color: css.text, fontWeight: 600 }}>Inspector P1</div>
            <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#22d3ee", display: "inline-block", animation: "pulse 2s infinite" }} />
              <span style={{ fontSize: 10, color: "#22d3ee" }}>Full Access</span>
            </div>
          </div>
          <button onClick={onExit} style={{ ...btnSec, width: "100%", fontSize: 12, padding: "8px 14px" }}>← Exit Portal</button>
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div style={{ flex: 1, overflow: "auto" }}>
        <div style={{ padding: "28px 32px" }}>
          <div style={{ marginBottom: 24 }}>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: css.text, letterSpacing: "-0.02em" }}>
              {NAV.find(n => n.id === view)?.label}
            </h1>
            <div style={{ fontSize: 12, color: css.textMuted, marginTop: 4 }}>
              Bengaluru Police Crime Intelligence Platform · {new Date().toLocaleDateString("en-IN", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
            </div>
          </div>

          {view === "dashboard" && <DashboardView cases={cases} officers={OFFICERS_DATA} onNavigate={setView} />}
          {view === "cases" && <CasesView cases={cases} officers={OFFICERS_DATA} setCases={setCases} showToast={showToast} />}
          {view === "officers" && <OfficersView officers={OFFICERS_DATA} cases={cases} />}
          {view === "assignments" && <AssignmentsView cases={cases} officers={OFFICERS_DATA} />}
          {view === "analytics" && <AnalyticsView cases={cases} />}
        </div>
      </div>

      {toast && <Toast msg={toast} onClose={() => setToast(null)} />}
    </div>
  );
}

// ─── PUBLIC PORTAL ────────────────────────────────────────────────────────────
function PublicPortal({ onEnterStaff }) {
  const [tab, setTab] = useState("home");
  const [form, setForm] = useState({ name: "", contact: "", crime_type: "Cyber Fraud", location: "", complaint_mode: "Online", description: "" });
  const [submitted, setSubmitted] = useState(false);
  const [refForm, setRefForm] = useState({ case_id: "", reason: "" });
  const [refSent, setRefSent] = useState(false);

  const stats = [
    { label: "Cases Registered", value: "2,847", trend: "+14%" },
    { label: "Solved This Year", value: "1,203", trend: "+22%" },
    { label: "Avg Resolution", value: "18 days", trend: "↓ 3 days" },
    { label: "Cyber Units Active", value: "12", trend: "" },
  ];

  const handleSubmit = () => {
    if (!form.name || !form.contact || !form.location || !form.description) return;
    setSubmitted(true);
  };

  return (
    <div style={{ minHeight: "100vh", background: "#050509", color: "#f1f5f9", fontFamily: "'Inter', system-ui, sans-serif" }}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@700&display=swap'); * { box-sizing: border-box; } @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-10px)} } @keyframes pulse2 { 0%,100%{opacity:0.4} 50%{opacity:1} } @keyframes scanline { 0% { transform: translateY(-100%); } 100% { transform: translateY(100vh); } }`}</style>

      {/* NAVBAR */}
      <nav style={{ position: "sticky", top: 0, zIndex: 100, background: "rgba(5,5,9,0.85)", backdropFilter: "blur(20px)", borderBottom: "1px solid rgba(255,255,255,0.06)", padding: "0 40px", display: "flex", alignItems: "center", height: 60 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
          <div style={{ width: 28, height: 28, borderRadius: 7, background: "linear-gradient(135deg, #6366f1, #22d3ee)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 900, color: "#fff" }}>C</div>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#f1f5f9" }}>CRMS</span>
          <span style={{ fontSize: 11, color: "#475569", marginLeft: 4 }}>Bengaluru Police Department</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {[["home", "Home"], ["complaint", "File Complaint"], ["access", "Request Access"]].map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)} style={{
              background: tab === id ? "rgba(99,102,241,0.15)" : "transparent",
              color: tab === id ? "#818cf8" : "#64748b",
              border: `1px solid ${tab === id ? "rgba(99,102,241,0.3)" : "transparent"}`,
              borderRadius: 8, padding: "6px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer",
            }}>{label}</button>
          ))}
          <button onClick={onEnterStaff} style={{ background: "#6366f1", color: "#fff", border: "none", borderRadius: 8, padding: "6px 16px", fontSize: 12, fontWeight: 700, cursor: "pointer", marginLeft: 8 }}>Staff Login →</button>
        </div>
      </nav>

      {tab === "home" && (
        <>
          {/* HERO */}
          <div style={{ position: "relative", minHeight: "85vh", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
            {/* Background orbs */}
            <div style={{ position: "absolute", top: "20%", left: "10%", width: 400, height: 400, borderRadius: "50%", background: "radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)", pointerEvents: "none" }} />
            <div style={{ position: "absolute", bottom: "15%", right: "10%", width: 300, height: 300, borderRadius: "50%", background: "radial-gradient(circle, rgba(34,211,238,0.08) 0%, transparent 70%)", pointerEvents: "none" }} />

            {/* Grid overlay */}
            <div style={{ position: "absolute", inset: 0, backgroundImage: "linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)", backgroundSize: "60px 60px", pointerEvents: "none" }} />

            <div style={{ textAlign: "center", maxWidth: 720, padding: "0 40px", position: "relative", zIndex: 1 }}>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.25)", borderRadius: 50, padding: "6px 16px", marginBottom: 32, fontSize: 12, color: "#818cf8" }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#22d3ee", display: "inline-block", animation: "pulse2 2s infinite" }} />
                Bengaluru Police Cyber Intelligence Division — Online
              </div>
              <h1 style={{ fontSize: 56, fontWeight: 900, margin: "0 0 20px", lineHeight: 1.1, letterSpacing: "-0.04em", color: "#f8fafc" }}>
                Crime Record<br />
                <span style={{ background: "linear-gradient(135deg, #6366f1, #22d3ee)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Management System</span>
              </h1>
              <p style={{ fontSize: 17, color: "#64748b", lineHeight: 1.7, marginBottom: 36, maxWidth: 520, margin: "0 auto 36px" }}>
                Bengaluru's unified intelligence platform for crime reporting, case tracking, and law enforcement coordination.
              </p>
              <div style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
                <button onClick={() => setTab("complaint")} style={{ background: "#6366f1", color: "#fff", border: "none", borderRadius: 12, padding: "14px 32px", fontSize: 15, fontWeight: 700, cursor: "pointer" }}>File a Complaint</button>
                <button onClick={() => setTab("access")} style={{ background: "transparent", color: "#94a3b8", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 12, padding: "14px 32px", fontSize: 15, fontWeight: 600, cursor: "pointer" }}>Request Case Access</button>
              </div>
            </div>
          </div>

          {/* STATS */}
          <div style={{ background: "rgba(255,255,255,0.02)", borderTop: "1px solid rgba(255,255,255,0.06)", borderBottom: "1px solid rgba(255,255,255,0.06)", padding: "36px 60px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 20, maxWidth: 900, margin: "0 auto" }}>
              {stats.map((s, i) => (
                <div key={i} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 30, fontWeight: 800, color: "#f1f5f9", fontFamily: "'JetBrains Mono', monospace", marginBottom: 4 }}>{s.value}</div>
                  <div style={{ fontSize: 12, color: "#64748b", marginBottom: 4 }}>{s.label}</div>
                  {s.trend && <div style={{ fontSize: 11, color: "#22d3ee", fontWeight: 600 }}>{s.trend}</div>}
                </div>
              ))}
            </div>
          </div>

          {/* FEATURES */}
          <div style={{ padding: "60px 60px", maxWidth: 1100, margin: "0 auto" }}>
            <h2 style={{ fontSize: 28, fontWeight: 800, textAlign: "center", marginBottom: 40, color: "#f1f5f9" }}>How It Works</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
              {[
                { icon: "📋", title: "File Your Complaint", desc: "Submit online or request offline registration. All complaints are logged with a unique case ID within minutes." },
                { icon: "🔍", title: "Track Your Case", desc: "Request access to monitor case progress, status updates, and assigned investigation officers." },
                { icon: "🛡️", title: "Secure & Confidential", desc: "End-to-end encrypted submissions with strict data protection protocols compliant with IT Act 2000." },
              ].map((f, i) => (
                <div key={i} style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 16, padding: 28 }}>
                  <div style={{ fontSize: 32, marginBottom: 14 }}>{f.icon}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 10, color: "#f1f5f9" }}>{f.title}</div>
                  <div style={{ fontSize: 13, color: "#64748b", lineHeight: 1.7 }}>{f.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {tab === "complaint" && (
        <div style={{ maxWidth: 640, margin: "0 auto", padding: "60px 24px" }}>
          {submitted ? (
            <div style={{ textAlign: "center", padding: "60px 40px", background: "rgba(34,211,238,0.05)", border: "1px solid rgba(34,211,238,0.2)", borderRadius: 20 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
              <h2 style={{ color: "#22d3ee", marginBottom: 12 }}>Complaint Submitted</h2>
              <p style={{ color: "#64748b", lineHeight: 1.7, marginBottom: 24 }}>Your complaint has been registered. A case ID will be sent to your contact within 24 hours.</p>
              <button onClick={() => { setSubmitted(false); setForm({ name: "", contact: "", crime_type: "Cyber Fraud", location: "", complaint_mode: "Online", description: "" }); }} style={btnPrimary}>File Another Complaint</button>
            </div>
          ) : (
            <div>
              <h2 style={{ fontSize: 26, fontWeight: 800, marginBottom: 8, color: "#f1f5f9" }}>File a Complaint</h2>
              <p style={{ color: "#64748b", marginBottom: 32, fontSize: 14 }}>All information is confidential and protected under the IT Act 2000.</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <div>
                    <label style={labelStyle}>Your Name *</label>
                    <input style={inputStyle} value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} placeholder="Full name" />
                  </div>
                  <div>
                    <label style={labelStyle}>Contact *</label>
                    <input style={inputStyle} value={form.contact} onChange={e => setForm(p => ({ ...p, contact: e.target.value }))} placeholder="Phone / Email" />
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <div>
                    <label style={labelStyle}>Crime Type</label>
                    <select style={inputStyle} value={form.crime_type} onChange={e => setForm(p => ({ ...p, crime_type: e.target.value }))}>
                      {["Cyber Fraud", "Theft", "Assault", "Fraud", "Other"].map(t => <option key={t}>{t}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Complaint Mode</label>
                    <select style={inputStyle} value={form.complaint_mode} onChange={e => setForm(p => ({ ...p, complaint_mode: e.target.value }))}>
                      <option>Online</option><option>Offline</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label style={labelStyle}>Location *</label>
                  <input style={inputStyle} value={form.location} onChange={e => setForm(p => ({ ...p, location: e.target.value }))} placeholder="Area in Bengaluru where incident occurred" />
                </div>
                <div>
                  <label style={labelStyle}>Incident Description *</label>
                  <textarea style={{ ...inputStyle, height: 120, resize: "vertical" }} value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} placeholder="Describe the incident in detail. Include date, time, and any witnesses..." />
                </div>
                <button onClick={handleSubmit} style={{ ...btnPrimary, padding: "13px", fontSize: 15 }}>Submit Complaint</button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "access" && (
        <div style={{ maxWidth: 560, margin: "0 auto", padding: "60px 24px" }}>
          {refSent ? (
            <div style={{ textAlign: "center", padding: "60px 40px", background: "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.2)", borderRadius: 20 }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>📬</div>
              <h2 style={{ color: "#818cf8", marginBottom: 12 }}>Request Received</h2>
              <p style={{ color: "#64748b", lineHeight: 1.7 }}>Your access request has been submitted for review by the station officer. You will be notified within 48 hours.</p>
            </div>
          ) : (
            <div>
              <h2 style={{ fontSize: 26, fontWeight: 800, marginBottom: 8, color: "#f1f5f9" }}>Request Case Access</h2>
              <p style={{ color: "#64748b", marginBottom: 32, fontSize: 14 }}>Complainants, witnesses, or legal representatives may request read access to case information.</p>
              <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                <div>
                  <label style={labelStyle}>Case ID</label>
                  <input style={inputStyle} value={refForm.case_id} onChange={e => setRefForm(p => ({ ...p, case_id: e.target.value }))} placeholder="e.g. BLR-042" />
                </div>
                <div>
                  <label style={labelStyle}>Reason for Access</label>
                  <textarea style={{ ...inputStyle, height: 100, resize: "vertical" }} value={refForm.reason} onChange={e => setRefForm(p => ({ ...p, reason: e.target.value }))} placeholder="Explain your relationship to the case and the reason for requesting access..." />
                </div>
                <button onClick={() => setRefSent(true)} style={{ ...btnPrimary, padding: "13px", fontSize: 15 }}>Submit Request</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── ROOT ─────────────────────────────────────────────────────────────────────
export default function App() {
  const [portal, setPortal] = useState("public");
  return portal === "public"
    ? <PublicPortal onEnterStaff={() => setPortal("staff")} />
    : <StaffPortal onExit={() => setPortal("public")} />;
}
