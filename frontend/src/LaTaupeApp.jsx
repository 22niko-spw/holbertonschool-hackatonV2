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
  X,
  Undo2,
  Settings,
  Wrench,
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
    amberCard: "border-amber-500/25 bg-amber-500/[0.04]",
    amberCardHover: "hover:bg-amber-500/[0.07]",
    amberText: "text-amber-400",
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
    amberCard: "border-amber-200 bg-amber-50",
    amberCardHover: "hover:bg-amber-100/70",
    amberText: "text-amber-600",
  },
};

const ThemeContext = createContext(TOKENS.dark);
const useT = () => useContext(ThemeContext);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Miroir de TOOL_DEFINITIONS dans src/rene_la_taupe/agent.py — noms exacts requis,
// ce sont eux qui sont envoyés au backend dans enabled_tools.
const AGENT_TOOLS = [
  { name: "search_corpus", label: "Recherche corpus", description: "Recherche dans les documents sains du corpus." },
  { name: "get_doc_metadata", label: "Métadonnées document", description: "Récupère les métadonnées d'un document." },
  { name: "list_quarantine", label: "Liste quarantaine", description: "Liste les documents en quarantaine du corpus." },
  { name: "read_quarantine_excerpt", label: "Lecture extrait quarantaine", description: "Lit l'extrait exact isolé, pour l'audit." },
  { name: "cite_sources", label: "Citation des sources", description: "Attache les citations à la réponse générée." },
  { name: "finalize_report", label: "Finalisation rapport", description: "Persiste le rapport final (seul outil à effet de bord)." },
];

const TOOLS_STORAGE_KEY = "la-taupe:enabled-tools";

function loadEnabledTools() {
  try {
    const raw = localStorage.getItem(TOOLS_STORAGE_KEY);
    if (!raw) return Object.fromEntries(AGENT_TOOLS.map((t) => [t.name, true]));
    const saved = JSON.parse(raw);
    return Object.fromEntries(AGENT_TOOLS.map((t) => [t.name, saved[t.name] !== false]));
  } catch (e) {
    return Object.fromEntries(AGENT_TOOLS.map((t) => [t.name, true]));
  }
}

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
// Tools settings — gear button (bottom-left) + panel to enable/disable the
// agent's tools. Persisted in localStorage, sent to /query as enabled_tools
// so the backend actually stops offering disabled tools to the model.
// ---------------------------------------------------------------------------

function ToolToggle({ tool, enabled, onChange }) {
  const T = useT();
  return (
    <div className="flex items-start justify-between gap-3 py-2.5">
      <div className="min-w-0">
        <p className={`text-[12.5px] font-medium ${T.textSecondary}`}>{tool.label}</p>
        <p className={`mt-0.5 text-[11px] leading-snug ${T.textFaint}`}>{tool.description}</p>
      </div>
      <button
        role="switch"
        aria-checked={enabled}
        aria-label={`${enabled ? "Désactiver" : "Activer"} ${tool.label}`}
        onClick={() => onChange(!enabled)}
        className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${
          enabled ? "bg-emerald-500" : "bg-neutral-700"
        }`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
            enabled ? "translate-x-[18px]" : "translate-x-0.5"
          }`}
        />
      </button>
    </div>
  );
}

function ToolsSettings({ enabledTools, setToolEnabled }) {
  const T = useT();
  const [open, setOpen] = useState(false);
  const activeCount = Object.values(enabledTools).filter(Boolean).length;

  return (
    <div className="fixed bottom-4 left-4 z-20">
      {open && (
        <div className={`absolute bottom-12 left-0 w-80 rounded-lg border p-4 shadow-lg ${T.card}`}>
          <div className="mb-1 flex items-center gap-2">
            <Wrench size={13} className={T.textFaint} />
            <h3 className={`text-[12.5px] font-semibold ${T.textPrimary}`}>Outils de l'agent</h3>
          </div>
          <p className={`mb-2 text-[11px] ${T.textFaint}`}>
            {activeCount}/{AGENT_TOOLS.length} actifs — un outil désactivé n'est plus proposé au modèle.
          </p>
          <div className={`divide-y ${T.card}`}>
            {AGENT_TOOLS.map((tool) => (
              <ToolToggle
                key={tool.name}
                tool={tool}
                enabled={enabledTools[tool.name] !== false}
                onChange={(next) => setToolEnabled(tool.name, next)}
              />
            ))}
          </div>
        </div>
      )}
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Paramètres des outils"
        aria-expanded={open}
        className={`flex h-9 w-9 items-center justify-center rounded-full border shadow-sm transition-colors ${T.chip} ${T.chipHover}`}
      >
        <Settings size={16} className={T.textMuted} strokeWidth={2} />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dropzone — files picked here are uploaded to POST /ingest on launch
// ---------------------------------------------------------------------------

function Dropzone({ onFiles, big }) {
  const T = useT();
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragOver(false);
      if (e.dataTransfer.files?.length) onFiles(e.dataTransfer.files);
    },
    [onFiles]
  );

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.docx,.txt,.md,.json"
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
          PDF, DOCX, TXT, MD, JSON — or{" "}
          <span className={`${T.textSecondary} underline underline-offset-2`}>click to browse</span>
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// HOME PAGE
// ---------------------------------------------------------------------------

function StagedChip({ entry, onRemove }) {
  const T = useT();
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border pl-3 pr-1.5 py-1 text-[12px] ${T.chip}`}>
      <FileText size={12} className={T.textFaint} />
      <span className={`font-mono max-w-[160px] truncate ${T.textSecondary}`}>{entry.file.name}</span>
      <span className={T.textFainter}>{formatBytes(entry.file.size)}</span>
      <button
        onClick={() => onRemove(entry.id)}
        className={`flex h-4 w-4 items-center justify-center rounded-full ${T.hoverBg} ${T.textFaint}`}
        aria-label={`Remove ${entry.file.name}`}
      >
        <X size={11} />
      </button>
    </span>
  );
}

function HomePage({ dark, setDark, staged, addStaged, removeStaged, question, setQuestion, onLaunch, launching }) {
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
          Analyse ton corpus documentaire
        </h2>
        <p className={`mt-2 mb-8 text-center text-[13.5px] leading-relaxed ${T.textMuted}`}>
          Dépose tes fichiers, pose ta question. La Taupe isole les tentatives
          d'injection avant de synthétiser les documents sains. Sans fichier,
          ta question part directement vers le modèle.
        </p>

        <div className="w-full space-y-3">
          <Dropzone big onFiles={addStaged} />

          {staged.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {staged.map((entry) => (
                <StagedChip key={entry.id} entry={entry} onRemove={removeStaged} />
              ))}
            </div>
          )}

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
                {staged.length > 0
                  ? `${staged.length} fichier${staged.length > 1 ? "s" : ""} prêt${staged.length > 1 ? "s" : ""}`
                  : "Aucun fichier ajouté"}
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
            {doc.size && <p className={`mt-0.5 text-[11px] ${T.textFaint}`}>{doc.size}</p>}
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
            {doc.size && <p className={`mt-0.5 text-[11px] ${T.textFaint}`}>{doc.size}</p>}
          </div>
        </div>
        <Badge tone="rose" icon={AlertTriangle}>
          THREAT DETECTED
        </Badge>
      </div>
    </button>
  );
}

function ErrorCard({ doc }) {
  const T = useT();
  return (
    <div className={`w-full text-left rounded-lg border px-3.5 py-3 ${T.amberCard}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2.5 min-w-0">
          <FileWarning size={15} className={`mt-0.5 shrink-0 ${T.amberText}`} strokeWidth={1.75} />
          <div className="min-w-0">
            <p className={`truncate font-mono text-[13px] ${T.textSecondary}`}>{doc.name}</p>
            {doc.error && <p className={`mt-0.5 text-[11px] ${T.textFaint}`}>{doc.error}</p>}
          </div>
        </div>
        <Badge tone="amber">NON TRAITÉ</Badge>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Right column: answer + citations
// ---------------------------------------------------------------------------

function AggregatedSummary({ question, answer, citations, docsById, loading, loadingStage, error }) {
  const T = useT();
  const lines = (answer || "").split("\n");
  const sourceDocIds = [...new Set((citations || []).map((c) => c.doc_id))];

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
          {loadingStage === "ingesting" ? "Analyse des documents…" : "Génération de la réponse…"}
        </div>
      )}

      {!loading && error && <p className="text-[13.5px] leading-relaxed text-rose-400">Erreur : {error}</p>}

      {!loading && !error && answer && (
        <>
          <div>
            {lines.map((line, i) => {
              if (line.trim() === "") return <div key={i} className="h-1" />;
              if (line.startsWith("- ")) {
                return (
                  <li key={i} className={`ml-4 list-disc text-[13.5px] leading-relaxed ${T.textMuted}`}>
                    {line.slice(2)}
                  </li>
                );
              }
              return (
                <p key={i} className={`text-[13.5px] leading-relaxed ${T.textMuted}`}>
                  {line}
                </p>
              );
            })}
          </div>

          {sourceDocIds.length > 0 && (
            <div className={`mt-4 flex flex-wrap items-center gap-1.5 border-t pt-3 ${T.card}`}>
              <span className={`text-[11px] uppercase tracking-wide ${T.textFaint}`}>Sources</span>
              {sourceDocIds.map((docId) => (
                <span key={docId} className={`rounded border px-1.5 py-0.5 font-mono text-[11px] ${T.tag}`}>
                  {docsById[docId] || docId}
                </span>
              ))}
            </div>
          )}
        </>
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

function SecurityAudit({ doc, entries }) {
  const T = useT();
  const [copiedIndex, setCopiedIndex] = useState(null);

  const handleCopy = async (text, idx) => {
    try {
      await navigator.clipboard.writeText(text || "");
    } catch (e) {
      // clipboard may be unavailable in this environment — fail silently
    }
    setCopiedIndex(idx);
    setTimeout(() => setCopiedIndex(null), 1500);
  };

  return (
    <div className="space-y-4">
      <div className={`rounded-lg border p-5 ${T.roseCard}`}>
        <div className="flex items-start gap-3">
          <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md border ${T.roseIconWrap}`}>
            <ShieldAlert size={16} className={T.roseText} strokeWidth={2} />
          </div>
          <div>
            <p className={`text-sm font-medium ${T.textPrimary}`}>{doc.name}</p>
            <p className={`mt-0.5 text-[12px] ${T.textFaint}`}>
              Isolé avant la génération de la réponse — {entries.length} détection{entries.length > 1 ? "s" : ""}
            </p>
          </div>
        </div>
      </div>

      {entries.map((entry, idx) => (
        <div key={idx} className="rounded-lg border border-neutral-800 bg-neutral-950 overflow-hidden">
          <div className="flex items-center justify-between border-b border-neutral-800 bg-neutral-900/60 px-4 py-2.5">
            <div className="flex items-center gap-3 min-w-0">
              <Terminal size={13} className="shrink-0 text-neutral-500" />
              <span className="truncate text-[12px] font-mono text-neutral-400">{entry.technique}</span>
              <span className="shrink-0 text-[11px] text-neutral-500">
                confiance {(entry.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <button
              onClick={() => handleCopy(entry.excerpt, idx)}
              className="flex shrink-0 items-center gap-1.5 rounded border border-neutral-800 px-2 py-1 text-[11px] text-neutral-400 hover:text-neutral-200 hover:border-neutral-700 transition-colors"
            >
              {copiedIndex === idx ? (
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
            <code className="font-mono text-rose-300/90 whitespace-pre-wrap">{entry.excerpt}</code>
          </pre>
          <div className="flex items-center gap-1.5 px-4 pb-3 text-[11px] text-neutral-500">
            <Clock size={11} />
            {entry.detected_at}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Right column: agent execution trace (Palier 3 — tool calls)
// ---------------------------------------------------------------------------

function ToolTraceEntry({ entry }) {
  const T = useT();
  const hasError = Boolean(entry.error);

  return (
    <div className={`rounded-lg border p-4 ${hasError ? T.roseCard : T.card}`}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className={`shrink-0 text-[11px] font-mono ${T.textFainter}`}>#{entry.turn}</span>
          <Terminal size={13} className={`shrink-0 ${hasError ? T.roseText : T.textFaint}`} />
          <span className={`truncate font-mono text-[13px] ${T.textSecondary}`}>{entry.tool_name}</span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {hasError ? (
            <Badge tone="rose" icon={AlertTriangle}>
              ÉCHEC
            </Badge>
          ) : (
            <Badge tone="emerald" icon={CheckCircle2}>
              OK
            </Badge>
          )}
          <span className={`font-mono text-[11px] ${T.textFainter}`}>{entry.duration_ms.toFixed(1)} ms</span>
        </div>
      </div>

      <div className="mt-3 space-y-2.5">
        <div>
          <p className={`text-[10.5px] uppercase tracking-wide ${T.textFaint}`}>Arguments</p>
          <pre className={`mt-1 max-h-40 overflow-auto rounded border p-2 text-[11px] leading-relaxed ${T.cardAlt}`}>
            <code className={`font-mono ${T.textMuted}`}>{JSON.stringify(entry.arguments, null, 2)}</code>
          </pre>
        </div>

        {hasError ? (
          <div>
            <p className={`text-[10.5px] uppercase tracking-wide ${T.roseText}`}>Erreur</p>
            <p className={`mt-1 text-[12.5px] leading-relaxed ${T.roseTextDim}`}>{entry.error}</p>
          </div>
        ) : (
          <div>
            <p className={`text-[10.5px] uppercase tracking-wide ${T.textFaint}`}>Résultat</p>
            <pre className={`mt-1 max-h-40 overflow-auto rounded border p-2 text-[11px] leading-relaxed ${T.cardAlt}`}>
              <code className={`font-mono ${T.textMuted}`}>{JSON.stringify(entry.result, null, 2)}</code>
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

function AgentTrace({ trace }) {
  const T = useT();

  if (!trace || trace.length === 0) {
    return <p className={`text-[13px] italic ${T.textFainter}`}>Aucun appel d'outil enregistré pour cette réponse.</p>;
  }

  return (
    <div className="space-y-3">
      {trace.map((entry, i) => (
        <ToolTraceEntry key={i} entry={entry} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DASHBOARD PAGE
// ---------------------------------------------------------------------------

function Dashboard({
  dark,
  setDark,
  docs,
  question,
  answer,
  citations,
  quarantineEntries,
  trace,
  loading,
  loadingStage,
  error,
  onBack,
}) {
  const T = useT();
  const [activeTab, setActiveTab] = useState("summary");
  const [selectedDoc, setSelectedDoc] = useState(null);

  const healthy = docs.filter((d) => d.status === "clean");
  const quarantined = docs.filter((d) => d.status === "quarantined");
  const processing = docs.filter((d) => d.status === "processing");
  const errored = docs.filter((d) => d.status === "error");

  const docsById = Object.fromEntries(docs.map((d) => [d.id, d.name]));

  const selectedQuarantinedDoc = quarantined.find((d) => d.id === selectedDoc) || quarantined[0];
  const selectedEntries = selectedQuarantinedDoc
    ? quarantineEntries.filter((e) => e.doc_id === selectedQuarantinedDoc.id)
    : [];

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

            {errored.length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-2">
                  <h2 className={`text-[12px] font-medium uppercase tracking-wide ${T.amberText}`}>Non traités</h2>
                  <span className={`text-[11px] ${T.textFainter}`}>({errored.length})</span>
                </div>
                <div className="space-y-2">
                  {errored.map((doc) => (
                    <ErrorCard key={doc.id} doc={doc} />
                  ))}
                </div>
              </div>
            )}
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
                onClick={() => setActiveTab("trace")}
                disabled={!trace || trace.length === 0}
                className={`relative flex items-center gap-1.5 px-3.5 py-2.5 text-[13px] transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                  activeTab === "trace" ? T.tabActive : T.tabInactive
                }`}
              >
                Agent Trace
                {trace && trace.length > 0 && (
                  <span className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] ${T.tag}`}>
                    {trace.length}
                  </span>
                )}
                {activeTab === "trace" && <span className={`absolute bottom-0 left-0 right-0 h-[2px] ${T.tabUnderline}`} />}
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

            {activeTab === "trace" ? (
              <AgentTrace trace={trace} />
            ) : activeTab === "audit" && selectedQuarantinedDoc ? (
              <SecurityAudit doc={selectedQuarantinedDoc} entries={selectedEntries} />
            ) : (
              <AggregatedSummary
                question={question}
                answer={answer}
                citations={citations}
                docsById={docsById}
                loading={loading}
                loadingStage={loadingStage}
                error={error}
              />
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
  const [docs, setDocs] = useState([]);
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");
  const [staged, setStaged] = useState([]);
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState([]);
  const [quarantineEntries, setQuarantineEntries] = useState([]);
  const [trace, setTrace] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState(null);
  const [error, setError] = useState("");
  const [enabledTools, setEnabledTools] = useState(loadEnabledTools);

  const setToolEnabled = useCallback((name, value) => {
    setEnabledTools((prev) => {
      const next = { ...prev, [name]: value };
      try {
        localStorage.setItem(TOOLS_STORAGE_KEY, JSON.stringify(next));
      } catch (e) {
        // localStorage indisponible — le toggle reste actif pour la session en cours
      }
      return next;
    });
  }, []);

  const addStaged = useCallback((fileList) => {
    const entries = Array.from(fileList).map((file) => ({
      id: `stg_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      file,
    }));
    setStaged((prev) => [...prev, ...entries]);
  }, []);

  const removeStaged = useCallback((id) => {
    setStaged((prev) => prev.filter((e) => e.id !== id));
  }, []);

  const launchAnalysis = async () => {
    const trimmed = question.trim();
    if (!trimmed) return;

    const filesToUpload = staged.map((e) => e.file);

    setAskedQuestion(trimmed);
    setAnswer("");
    setCitations([]);
    setQuarantineEntries([]);
    setTrace([]);
    setError("");
    setStaged([]);
    setView("dashboard");
    setLoading(true);

    // No files: plain question, no corpus to search — direct LLM call, no agent loop, no trace.
    if (filesToUpload.length === 0) {
      setDocs([]);
      setLoadingStage("querying");
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
        setLoadingStage(null);
      }
      return;
    }

    // Files staged: real ingestion, then a real query against the corpus.
    setDocs(
      filesToUpload.map((file, i) => ({
        id: `pending_${i}`,
        name: file.name,
        status: "processing",
      }))
    );
    setLoadingStage("ingesting");

    try {
      const formData = new FormData();
      filesToUpload.forEach((file) => formData.append("files", file));

      const ingestRes = await fetch("/ingest", { method: "POST", body: formData });
      const ingestData = await ingestRes.json();
      if (!ingestRes.ok) throw new Error(ingestData.error || "Erreur lors de l'ingestion.");

      const newDocs = ingestData.documents.map((d, i) => ({
        id: d.doc_id || `error_${i}`,
        name: d.filename,
        status: d.status,
        error: d.error,
      }));
      setDocs(newDocs);

      setLoadingStage("querying");
      const activeTools = AGENT_TOOLS.map((t) => t.name).filter((name) => enabledTools[name] !== false);
      const queryRes = await fetch("/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ corpus_id: ingestData.corpus_id, question: trimmed, enabled_tools: activeTools }),
      });
      const report = await queryRes.json();
      if (!queryRes.ok) throw new Error(report.error || "Erreur lors de la génération de la réponse.");

      setAnswer(report.answer.answer);
      setCitations(report.answer.citations || []);
      setQuarantineEntries(report.quarantine || []);
      setTrace(report.trace || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setLoadingStage(null);
    }
  };

  const backToHome = () => {
    setDocs([]);
    setQuestion("");
    setAskedQuestion("");
    setAnswer("");
    setCitations([]);
    setQuarantineEntries([]);
    setTrace([]);
    setError("");
    setStaged([]);
    setView("home");
  };

  return (
    <ThemeContext.Provider value={T}>
      {view === "home" ? (
        <HomePage
          dark={dark}
          setDark={setDark}
          staged={staged}
          addStaged={addStaged}
          removeStaged={removeStaged}
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
          citations={citations}
          quarantineEntries={quarantineEntries}
          trace={trace}
          loading={loading}
          loadingStage={loadingStage}
          error={error}
          onBack={backToHome}
        />
      )}
      <ToolsSettings enabledTools={enabledTools} setToolEnabled={setToolEnabled} />
    </ThemeContext.Provider>
  );
}
