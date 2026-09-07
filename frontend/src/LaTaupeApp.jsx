import React, {
  useState,
  useRef,
  useContext,
  createContext,
  useCallback,
} from "react";
import {
  ShieldAlert,
  ShieldCheck,
  FileText,
  Upload,
  CheckCircle2,
  AlertTriangle,
  Terminal,
  Clock,
  Activity,
  FileWarning,
  Copy,
  Check,
  Sun,
  Moon,
  Loader2,
  ArrowUp,
  Undo2,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Theme tokens
// ---------------------------------------------------------------------------

const TOKENS = {
  dark: {
    page: "bg-neutral-950 text-neutral-100",
    header: "bg-neutral-950/95 border-neutral-800",
    card: "bg-neutral-950 border-neutral-800",
    cardAlt: "bg-neutral-900/50 border-neutral-800",
    chip: "bg-neutral-900 border-neutral-800",
    chipHover: "hover:border-neutral-700 hover:bg-neutral-900",
    hoverBg: "hover:bg-neutral-900/60",
    divider: "bg-neutral-800",
    textPrimary: "text-neutral-100",
    textSecondary: "text-neutral-300",
    textMuted: "text-neutral-400",
    textFaint: "text-neutral-500",
    textFainter: "text-neutral-600",
    healthySelected: "border-neutral-700 bg-neutral-900",
    healthyIdle: "border-neutral-800 bg-neutral-950",
    dropIdle: "border-neutral-800 bg-neutral-950 hover:border-neutral-700 hover:bg-neutral-900/50",
    dropActive: "border-neutral-500 bg-neutral-900",
    tabInactive: "text-neutral-500 hover:text-neutral-300",
    tabActive: "text-neutral-100",
    tabUnderline: "bg-neutral-100",
    tag: "border-neutral-800 bg-neutral-900 text-neutral-400",
    composerFocus: "focus-within:border-neutral-600",
    primaryBtn: "bg-neutral-100 text-neutral-900 hover:bg-white",
    badge: {
      emerald: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
      rose: "bg-rose-500/10 text-rose-400 border-rose-500/20",
      amber: "bg-amber-500/10 text-amber-400 border-amber-500/20",
      neutral: "bg-neutral-800 text-neutral-400 border-neutral-700",
    },
    roseCard: "border-rose-500/25 bg-rose-500/[0.04]",
    roseCardSelected: "border-rose-500/40 bg-rose-500/[0.07]",
    roseCardHover: "hover:bg-rose-500/[0.07]",
    roseDivider: "border-rose-500/15",
    roseText: "text-rose-400",
    roseTextDim: "text-rose-300/90",
    roseIconWrap: "border-rose-500/25 bg-rose-500/10",
  },
  light: {
    page: "bg-neutral-50 text-neutral-900",
    header: "bg-white/95 border-neutral-200",
    card: "bg-white border-neutral-200",
    cardAlt: "bg-neutral-50 border-neutral-200",
    chip: "bg-white border-neutral-200",
    chipHover: "hover:border-neutral-300 hover:bg-neutral-50",
    hoverBg: "hover:bg-neutral-50",
    divider: "bg-neutral-200",
    textPrimary: "text-neutral-900",
    textSecondary: "text-neutral-700",
    textMuted: "text-neutral-500",
    textFaint: "text-neutral-500",
    textFainter: "text-neutral-400",
    healthySelected: "border-neutral-300 bg-neutral-100",
    healthyIdle: "border-neutral-200 bg-white",
    dropIdle: "border-neutral-300 bg-white hover:border-neutral-400 hover:bg-neutral-50",
    dropActive: "border-neutral-400 bg-neutral-100",
    tabInactive: "text-neutral-500 hover:text-neutral-700",
    tabActive: "text-neutral-900",
    tabUnderline: "bg-neutral-900",
    tag: "border-neutral-200 bg-neutral-100 text-neutral-600",
    composerFocus: "focus-within:border-neutral-400",
    primaryBtn: "bg-neutral-900 text-white hover:bg-neutral-800",
    badge: {
      emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
      rose: "bg-rose-50 text-rose-700 border-rose-200",
      amber: "bg-amber-50 text-amber-700 border-amber-200",
      neutral: "bg-neutral-100 text-neutral-600 border-neutral-200",
    },
    roseCard: "border-rose-200 bg-rose-50",
    roseCardSelected: "border-rose-300 bg-rose-100",
    roseCardHover: "hover:bg-rose-100/70",
    roseDivider: "border-rose-200",
    roseText: "text-rose-600",
    roseTextDim: "text-rose-300/90",
    roseIconWrap: "border-rose-200 bg-rose-100",
  },
};

const ThemeContext = createContext(TOKENS.dark);
const useT = () => useContext(ThemeContext);

// ---------------------------------------------------------------------------
// Small building blocks
// ---------------------------------------------------------------------------

function Badge({ tone, children, icon: Icon }) {
  const T = useT();
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium tracking-wide whitespace-nowrap ${T.badge[tone]}`}
    >
      {Icon && <Icon size={12} strokeWidth={2.5} />}
      {children}
    </span>
  );
}

function StatusDot({ tone = "emerald" }) {
  const colors = { emerald: "bg-emerald-400", rose: "bg-rose-400" };
  return (
    <span className="relative flex h-2 w-2">
      <span className={`absolute inline-flex h-full w-full rounded-full ${colors[tone]} opacity-60 animate-ping`} />
      <span className={`relative inline-flex h-2 w-2 rounded-full ${colors[tone]}`} />
    </span>
  );
}

function ThemeToggle({ dark, setDark }) {
  const T = useT();
  return (
    <button
      onClick={() => setDark((v) => !v)}
      aria-label="Toggle theme"
      className={`flex h-[30px] w-[30px] items-center justify-center rounded-md border transition-colors ${T.chip} ${T.chipHover}`}
    >
      {dark ? (
        <Sun size={14} className={T.textMuted} strokeWidth={2} />
      ) : (
        <Moon size={14} className={T.textMuted} strokeWidth={2} />
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Reusable dropzone (visual only — file handling passed in via props)
// ---------------------------------------------------------------------------

function Dropzone({ onFiles, big, disabled }) {
  const T = useT();
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragOver(false);
      if (disabled) return;
      if (e.dataTransfer.files?.length) onFiles(e.dataTransfer.files);
    },
    [onFiles, disabled]
  );

  if (disabled) {
    return (
      <div
        className={`rounded-lg border border-dashed text-center cursor-not-allowed opacity-50 ${
          big ? "px-6 py-12" : "px-5 py-8"
        } ${T.dropIdle}`}
      >
        <div className={`mx-auto mb-3 flex items-center justify-center rounded-md border ${T.chip} ${big ? "h-11 w-11" : "h-9 w-9"}`}>
          <Upload size={big ? 18 : 16} className={T.textMuted} strokeWidth={2} />
        </div>
        <p className={`${big ? "text-[15px]" : "text-sm"} ${T.textSecondary}`}>Analyse de corpus</p>
        <p className={`mt-1 text-xs ${T.textFaint}`}>Disponible à un palier ultérieur — pas encore branché au backend</p>
      </div>
    );
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.txt,.md"
        className="hidden"
        onChange={(e) => {
          if (e.target.files?.length) onFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`rounded-lg border border-dashed text-center transition-colors cursor-pointer ${
          big ? "px-6 py-12" : "px-5 py-8"
        } ${dragOver ? T.dropActive : T.dropIdle}`}
      >
        <div className={`mx-auto mb-3 flex items-center justify-center rounded-md border ${T.chip} ${big ? "h-11 w-11" : "h-9 w-9"}`}>
          <Upload size={big ? 18 : 16} className={T.textMuted} strokeWidth={2} />
        </div>
        <p className={`${big ? "text-[15px]" : "text-sm"} ${T.textSecondary}`}>
          {dragOver ? "Release to add to corpus" : "Drag and drop corpus files"}
        </p>
        <p className={`mt-1 text-xs ${T.textFaint}`}>
          PDF, TXT, MD — or{" "}
          <span className={`${T.textSecondary} underline underline-offset-2`}>click to browse</span>
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// HOME PAGE
// ---------------------------------------------------------------------------

function HomePage({ dark, setDark, question, setQuestion, onLaunch, launching }) {
  const T = useT();

  const canLaunch = question.trim().length > 0 && !launching;

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canLaunch) onLaunch();
    }
  };

  return (
    <div className={`min-h-screen w-full font-sans transition-colors ${T.page}`}>
      <style>{`
        .font-sans { font-family: 'Inter', ui-sans-serif, system-ui, sans-serif; }
        .font-mono { font-family: 'JetBrains Mono', ui-monospace, 'Fira Code', monospace; }
      `}</style>

      <header className={`border-b px-6 py-4 ${T.header}`}>
        <div className="mx-auto max-w-[1400px] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`flex h-8 w-8 items-center justify-center rounded-md border ${T.chip}`}>
              <ShieldCheck size={16} className={T.textMuted} strokeWidth={2} />
            </div>
            <h1 className={`text-[14.5px] font-semibold tracking-tight ${T.textPrimary}`}>
              LA TAUPE
              <span className={`ml-2 font-normal ${T.textFaint}`}>· Document Security &amp; Analysis</span>
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <div className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 ${T.chip}`}>
              <StatusDot tone="emerald" />
              <span className={`text-[12px] ${T.textMuted}`}>Engine Active — ReAct v1.0</span>
            </div>
            <ThemeToggle dark={dark} setDark={setDark} />
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-2xl flex-col items-center justify-center px-6 py-20">
        <div className={`mb-5 flex h-12 w-12 items-center justify-center rounded-xl border ${T.chip}`}>
          <ShieldAlert size={22} className={T.textMuted} strokeWidth={1.75} />
        </div>
        <h2 className={`text-[22px] font-semibold tracking-tight text-center ${T.textPrimary}`}>
          Pose ta question à La Taupe
        </h2>
        <p className={`mt-2 mb-8 text-center text-[13.5px] leading-relaxed ${T.textMuted}`}>
          Socle du Palier 2 : ta question part vers un vrai modèle. L'analyse
          de corpus et l'isolation des documents piégés arrivent aux paliers suivants.
        </p>

        <div className="w-full space-y-3">
          <Dropzone big disabled />

          <div className={`rounded-xl border transition-colors ${T.card} ${T.composerFocus}`}>
            <textarea
              rows={2}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Pose ta question…"
              className={`w-full resize-none bg-transparent px-3.5 pt-3 pb-1 text-[13.5px] outline-none ${T.textPrimary} placeholder:${T.textFaint}`}
            />
            <div className="flex items-center justify-between px-3.5 pb-2.5 pt-1">
              <span className={`text-[11px] ${T.textFainter}`}>
                Réponse générée par un vrai appel au modèle — aucune analyse de corpus à ce stade
              </span>
              <button
                onClick={onLaunch}
                disabled={!canLaunch}
                aria-label="Lancer l'analyse"
                className={`flex h-7 w-7 items-center justify-center rounded-full transition-colors disabled:opacity-30 disabled:cursor-not-allowed ${T.primaryBtn}`}
              >
                {launching ? (
                  <Loader2 size={14} strokeWidth={2.5} className="animate-spin" />
                ) : (
                  <ArrowUp size={14} strokeWidth={2.5} />
                )}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Left column: document cards (dashboard)
// ---------------------------------------------------------------------------

function HealthyCard({ doc, selected, onSelect }) {
  const T = useT();
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left rounded-lg border px-3.5 py-3 transition-colors ${
        selected ? T.healthySelected : `${T.healthyIdle} ${T.hoverBg}`
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2.5 min-w-0">
          {doc.status === "processing" ? (
            <Loader2 size={15} className={`mt-0.5 shrink-0 animate-spin ${T.textFaint}`} strokeWidth={1.75} />
          ) : (
            <FileText size={15} className={`mt-0.5 shrink-0 ${T.textFaint}`} strokeWidth={1.75} />
          )}
          <div className="min-w-0">
            <p className={`truncate font-mono text-[13px] ${T.textSecondary}`}>{doc.name}</p>
            <p className={`mt-0.5 text-[11px] ${T.textFaint}`}>
              {doc.size}
              {doc.duration ? ` · ${doc.duration}` : ""}
            </p>
          </div>
        </div>
        {doc.status === "processing" ? (
          <Badge tone="neutral">SCANNING</Badge>
        ) : (
          <Badge tone="emerald" icon={CheckCircle2}>
            VERIFIED
          </Badge>
        )}
      </div>
    </button>
  );
}

function QuarantinedCard({ doc, selected, onSelect }) {
  const T = useT();
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left rounded-lg border px-3.5 py-3 transition-colors ${
        selected ? T.roseCardSelected : `${T.roseCard} ${T.roseCardHover}`
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2.5 min-w-0">
          <FileWarning size={15} className={`mt-0.5 shrink-0 ${T.roseText}`} strokeWidth={1.75} />
          <div className="min-w-0">
            <p className={`truncate font-mono text-[13px] ${T.textSecondary}`}>{doc.name}</p>
            <p className={`mt-0.5 text-[11px] ${T.textFaint}`}>
              {doc.size}
              {doc.duration ? ` · ${doc.duration}` : ""}
            </p>
          </div>
        </div>
        <Badge tone="rose" icon={AlertTriangle}>
          THREAT DETECTED
        </Badge>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Right column: aggregated summary
// ---------------------------------------------------------------------------

function renderInline(text, T) {
  const parts = text.split(/(\[[\w.-]+\])/g);
  return parts.map((part, idx) =>
    /^\[[\w.-]+\]$/.test(part) ? (
      <span key={idx} className={`mx-0.5 rounded border px-1.5 py-0.5 font-mono text-[11px] ${T.tag}`}>
        {part.slice(1, -1)}
      </span>
    ) : (
      part
    )
  );
}

function AggregatedSummary({ question, answer, loading, error }) {
  const T = useT();
  const lines = (answer || "").split("\n");

  return (
    <div className={`rounded-lg border p-5 ${T.card}`}>
      <div className={`mb-4 border-b pb-3 ${T.card}`}>
        <div className="flex items-center justify-between">
          <h2 className={`text-sm font-medium ${T.textPrimary}`}>Réponse</h2>
          <Badge tone="neutral">LLM</Badge>
        </div>
        {question ? (
          <p className={`mt-1.5 text-[12px] italic ${T.textMuted}`}>« {question} »</p>
        ) : (
          <p className={`mt-0.5 text-[11px] ${T.textFaint}`}>Pose une question pour lancer l'analyse</p>
        )}
      </div>

      {loading && (
        <div className={`flex items-center gap-2 text-[13.5px] ${T.textMuted}`}>
          <Loader2 size={14} className="animate-spin" />
          Génération de la réponse…
        </div>
      )}

      {!loading && error && (
        <p className="text-[13.5px] leading-relaxed text-rose-400">Erreur : {error}</p>
      )}

      {!loading && !error && answer && (
        <div>
          {lines.map((line, i) => {
            if (line.startsWith("## ")) {
              return (
                <h3 key={i} className={`mt-5 mb-2 text-[13px] font-semibold uppercase tracking-wide first:mt-0 ${T.textSecondary}`}>
                  {line.slice(3)}
                </h3>
              );
            }
            if (line.startsWith("- ")) {
              return (
                <li key={i} className={`ml-4 list-disc text-[13.5px] leading-relaxed ${T.textMuted}`}>
                  {renderInline(line.slice(2), T)}
                </li>
              );
            }
            if (line.trim() === "") return <div key={i} className="h-1" />;
            return (
              <p key={i} className={`text-[13.5px] leading-relaxed ${T.textMuted}`}>
                {renderInline(line, T)}
              </p>
            );
          })}
        </div>
      )}

      {!loading && !error && !answer && (
        <p className={`text-[13.5px] italic ${T.textFainter}`}>Aucune réponse pour l'instant.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Right column: security audit panel
// ---------------------------------------------------------------------------

function SecurityAudit({ doc }) {
  const T = useT();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(doc.payload || "");
    } catch (e) {
      // clipboard may be unavailable in this environment — fail silently
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="space-y-4">
      <div className={`rounded-lg border p-5 ${T.roseCard}`}>
        <div className="mb-4 flex items-start gap-3">
          <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border ${T.roseIconWrap}`}>
            <ShieldAlert size={16} className={T.roseText} strokeWidth={2} />
          </div>
          <div>
            <p className={`text-sm font-medium ${T.textPrimary}`}>{doc.category}</p>
            <p className={`mt-0.5 text-[12px] ${T.textFaint}`}>Isolated before entering the aggregation pipeline</p>
          </div>
        </div>

        <dl className={`grid grid-cols-2 gap-x-4 gap-y-3 border-t pt-4 ${T.roseDivider}`}>
          <div>
            <dt className={`text-[10.5px] uppercase tracking-wide ${T.textFaint}`}>Target document</dt>
            <dd className={`mt-1 font-mono text-[12.5px] ${T.textSecondary}`}>{doc.name}</dd>
          </div>
          <div>
            <dt className={`text-[10.5px] uppercase tracking-wide ${T.textFaint}`}>Timestamp</dt>
            <dd className={`mt-1 flex items-center gap-1.5 font-mono text-[12.5px] ${T.textSecondary}`}>
              <Clock size={11} className={T.textFaint} />
              {doc.timestamp}
            </dd>
          </div>
          <div className="col-span-2">
            <dt className={`text-[10.5px] uppercase tracking-wide ${T.textFaint}`}>Reason for isolation</dt>
            <dd className={`mt-1 text-[13px] leading-relaxed ${T.textMuted}`}>{doc.reason}</dd>
          </div>
        </dl>
      </div>

      {/* Payload viewer stays dark regardless of theme — a terminal pane, not page chrome */}
      <div className="rounded-lg border border-neutral-800 bg-neutral-950 overflow-hidden">
        <div className="flex items-center justify-between border-b border-neutral-800 bg-neutral-900/60 px-4 py-2.5">
          <div className="flex items-center gap-2">
            <Terminal size={13} className="text-neutral-500" />
            <span className="text-[12px] text-neutral-400">Extracted payload</span>
          </div>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded border border-neutral-800 px-2 py-1 text-[11px] text-neutral-400 hover:text-neutral-200 hover:border-neutral-700 transition-colors"
          >
            {copied ? (
              <>
                <Check size={11} /> Copied
              </>
            ) : (
              <>
                <Copy size={11} /> Copy
              </>
            )}
          </button>
        </div>
        <pre className="overflow-x-auto p-4 text-[12.5px] leading-relaxed">
          <code className="font-mono text-rose-300/90 whitespace-pre-wrap">{doc.payload}</code>
        </pre>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DASHBOARD PAGE
// ---------------------------------------------------------------------------

function Dashboard({ dark, setDark, docs, question, answer, loading, error, onBack }) {
  const T = useT();
  const [activeTab, setActiveTab] = useState("summary");
  const [selectedDoc, setSelectedDoc] = useState(null);

  const healthy = docs.filter((d) => d.status === "healthy");
  const quarantined = docs.filter((d) => d.status === "quarantined");
  const processing = docs.filter((d) => d.status === "processing");

  const selectedQuarantinedDoc = quarantined.find((d) => d.id === selectedDoc) || quarantined[0];

  return (
    <div className={`min-h-screen w-full font-sans transition-colors ${T.page}`}>
      <style>{`
        .font-sans { font-family: 'Inter', ui-sans-serif, system-ui, sans-serif; }
        .font-mono { font-family: 'JetBrains Mono', ui-monospace, 'Fira Code', monospace; }
      `}</style>

      <header className={`border-b px-6 py-4 sticky top-0 z-10 backdrop-blur ${T.header}`}>
        <div className="mx-auto max-w-[1400px]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={onBack}
                aria-label="Nouvelle analyse"
                className={`flex h-8 w-8 items-center justify-center rounded-md border transition-colors ${T.chip} ${T.chipHover}`}
              >
                <Undo2 size={14} className={T.textMuted} strokeWidth={2} />
              </button>
              <div className={`flex h-8 w-8 items-center justify-center rounded-md border ${T.chip}`}>
                <ShieldCheck size={16} className={T.textMuted} strokeWidth={2} />
              </div>
              <h1 className={`text-[14.5px] font-semibold tracking-tight ${T.textPrimary}`}>
                LA TAUPE
                <span className={`ml-2 font-normal ${T.textFaint}`}>· Document Security &amp; Analysis</span>
              </h1>
            </div>

            <div className="flex items-center gap-2">
              <div className={`flex items-center gap-2 rounded-md border px-2.5 py-1.5 ${T.chip}`}>
                <StatusDot tone="emerald" />
                <span className={`text-[12px] ${T.textMuted}`}>Engine Active — ReAct v1.0</span>
              </div>
              <ThemeToggle dark={dark} setDark={setDark} />
            </div>
          </div>

          <div className={`mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border px-4 py-2.5 ${T.cardAlt}`}>
            <div className="flex items-center gap-1.5">
              <Activity size={13} className={T.textFaint} />
              <span className={`text-[12.5px] ${T.textSecondary}`}>{docs.length} Documents Analyzed</span>
            </div>
            <div className={`h-3 w-px ${T.divider}`} />
            <div className="flex items-center gap-1.5">
              <CheckCircle2 size={13} className="text-emerald-400" />
              <span className={`text-[12.5px] ${T.textSecondary}`}>{healthy.length} Clean</span>
            </div>
            <div className={`h-3 w-px ${T.divider}`} />
            <div className="flex items-center gap-1.5">
              <AlertTriangle size={13} className="text-rose-400" />
              <span className={`text-[12.5px] ${T.textSecondary}`}>{quarantined.length} Quarantined</span>
            </div>
            {processing.length > 0 && (
              <>
                <div className={`h-3 w-px ${T.divider}`} />
                <div className="flex items-center gap-1.5">
                  <Loader2 size={13} className={`animate-spin ${T.textFaint}`} />
                  <span className={`text-[12.5px] ${T.textSecondary}`}>{processing.length} Scanning</span>
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-[35%_65%] gap-5">
          <div className="space-y-5">
            <Dropzone disabled />

            <div>
              <div className="mb-2 flex items-center gap-2">
                <h2 className={`text-[12px] font-medium uppercase tracking-wide ${T.textFaint}`}>Healthy Corpus</h2>
                <span className={`text-[11px] ${T.textFainter}`}>({healthy.length})</span>
              </div>
              <div className="space-y-2">
                {healthy.length === 0 && processing.length === 0 && (
                  <p className={`text-[12px] italic ${T.textFainter}`}>No verified documents yet.</p>
                )}
                {[...processing, ...healthy].map((doc) => (
                  <HealthyCard
                    key={doc.id}
                    doc={doc}
                    selected={selectedDoc === doc.id}
                    onSelect={() => {
                      setSelectedDoc(doc.id);
                      setActiveTab("summary");
                    }}
                  />
                ))}
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center gap-2">
                <h2 className={`text-[12px] font-medium uppercase tracking-wide ${T.roseText}`}>
                  Quarantined / Threats
                </h2>
                <span className={`text-[11px] ${T.textFainter}`}>({quarantined.length})</span>
              </div>
              <div className="space-y-2">
                {quarantined.length === 0 && (
                  <p className={`text-[12px] italic ${T.textFainter}`}>No threats detected.</p>
                )}
                {quarantined.map((doc) => (
                  <QuarantinedCard
                    key={doc.id}
                    doc={doc}
                    selected={selectedDoc === doc.id}
                    onSelect={() => {
                      setSelectedDoc(doc.id);
                      setActiveTab("audit");
                    }}
                  />
                ))}
              </div>
            </div>
          </div>

          <div>
            <div className={`mb-4 flex items-center gap-1 border-b ${T.card}`}>
              <button
                onClick={() => setActiveTab("summary")}
                className={`relative px-3.5 py-2.5 text-[13px] transition-colors ${
                  activeTab === "summary" ? T.tabActive : T.tabInactive
                }`}
              >
                Aggregated Summary
                {activeTab === "summary" && <span className={`absolute bottom-0 left-0 right-0 h-[2px] ${T.tabUnderline}`} />}
              </button>
              <button
                onClick={() => setActiveTab("audit")}
                disabled={quarantined.length === 0}
                className={`relative flex items-center gap-1.5 px-3.5 py-2.5 text-[13px] transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                  activeTab === "audit" ? T.tabActive : T.tabInactive
                }`}
              >
                Security Audit &amp; Injection Logs
                {quarantined.length > 0 && (
                  <span className="flex h-4 w-4 items-center justify-center rounded-full bg-rose-500/15 text-[10px] text-rose-400">
                    {quarantined.length}
                  </span>
                )}
                {activeTab === "audit" && <span className={`absolute bottom-0 left-0 right-0 h-[2px] ${T.tabUnderline}`} />}
              </button>
            </div>

            {activeTab === "summary" || !selectedQuarantinedDoc ? (
              <AggregatedSummary question={question} answer={answer} loading={loading} error={error} />
            ) : (
              <SecurityAudit doc={selectedQuarantinedDoc} />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// APP (view switch: home -> dashboard)
// ---------------------------------------------------------------------------

export default function LaTaupeApp() {
  const [dark, setDark] = useState(true);
  const T = dark ? TOKENS.dark : TOKENS.light;

  const [view, setView] = useState("home");
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // No corpus ingestion yet — docs stays empty until a real /ingest route exists.
  const docs = [];

  const launchAnalysis = async () => {
    const trimmed = question.trim();
    if (!trimmed) return;

    setAskedQuestion(trimmed);
    setAnswer("");
    setError("");
    setLoading(true);
    setView("dashboard");

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Erreur inconnue");
      setAnswer(data.reply);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const backToHome = () => {
    setQuestion("");
    setAskedQuestion("");
    setAnswer("");
    setError("");
    setView("home");
  };

  return (
    <ThemeContext.Provider value={T}>
      {view === "home" ? (
        <HomePage
          dark={dark}
          setDark={setDark}
          question={question}
          setQuestion={setQuestion}
          onLaunch={launchAnalysis}
          launching={loading}
        />
      ) : (
        <Dashboard
          dark={dark}
          setDark={setDark}
          docs={docs}
          question={askedQuestion}
          answer={answer}
          loading={loading}
          error={error}
          onBack={backToHome}
        />
      )}
    </ThemeContext.Provider>
  );
}
