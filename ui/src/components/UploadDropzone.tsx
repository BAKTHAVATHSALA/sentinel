import { useRef, useState, type DragEvent } from "react";
import { extractRecordCandidates, parseTransactionDocument, type ParsedRecordError } from "../lib/documentParser";
import type { Transaction } from "../lib/types";

type UploadStage = "idle" | "dragover" | "uploading" | "extracting" | "validating" | "error";

const STAGE_LABEL: Record<UploadStage, string> = {
  idle: "",
  dragover: "",
  uploading: "Uploading...",
  extracting: "Extracting...",
  validating: "Validating...",
  error: "",
};

/**
 * The public console's only input surface (build.md Section 6): a
 * click-or-drop upload zone accepting PDF/DOCX, running the deterministic
 * client-side parser (lib/documentParser.ts) and handing the parent the
 * result. Never auto-runs an investigation -- the parent always shows a
 * preview first (Section 6: "Do not automatically run transactions
 * immediately after file upload").
 */
export function UploadDropzone({
  onParsed,
}: {
  onParsed: (transactions: Transaction[], errors: ParsedRecordError[], fileName: string) => void;
}) {
  const [stage, setStage] = useState<UploadStage>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [parseErrors, setParseErrors] = useState<ParsedRecordError[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setErrorMessage(null);
    setParseErrors([]);
    setStage("uploading");
    try {
      setStage("extracting");
      const candidates = await extractRecordCandidates(file);
      setStage("validating");
      const { transactions, errors } = parseTransactionDocument(candidates);

      if (transactions.length === 0) {
        setParseErrors(errors);
        setErrorMessage(errors.length > 0 ? "No valid transactions could be extracted from this file." : "No transactions were found in this file.");
        setStage("error");
        return;
      }

      setStage("idle");
      onParsed(transactions, errors, file.name);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Could not read this file.");
      setStage("error");
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setStage("idle");
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  }

  const busy = stage === "uploading" || stage === "extracting" || stage === "validating";

  return (
    <div className="flex flex-col gap-2">
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload transactions"
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (!busy && (e.key === "Enter" || e.key === " ")) inputRef.current?.click();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          if (!busy) setStage("dragover");
        }}
        onDragLeave={() => setStage((s) => (s === "dragover" ? "idle" : s))}
        onDrop={busy ? undefined : onDrop}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 border border-dashed p-12 text-center transition-colors ${
          stage === "dragover"
            ? "border-[var(--color-stable)] bg-[var(--color-stable-soft)]"
            : stage === "error"
              ? "border-[var(--color-critical)] bg-[var(--color-critical-soft)]"
              : "border-[var(--color-rule-strong)] bg-[var(--color-surface)] hover:border-[var(--color-text-muted)]"
        }`}
      >
        <input
          ref={inputRef}
          data-testid="file-input"
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void handleFile(file);
          }}
        />

        {busy ? (
          <p className="text-[14px] text-[var(--color-text)]">{STAGE_LABEL[stage]}</p>
        ) : stage === "error" ? (
          <>
            <p className="text-[14px] text-[var(--color-critical)]">{errorMessage}</p>
            {parseErrors.length > 0 && (
              <ul className="mt-1 max-h-32 overflow-y-auto text-left text-[12px] text-[var(--color-critical)]">
                {parseErrors.map((e, i) => (
                  <li key={i}>
                    TRANSACTION {e.recordLabel}: {e.reason}
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-2 text-[12px] text-[var(--color-text-muted)]">Click to try a different file.</p>
          </>
        ) : (
          <>
            <p className="text-[15px] text-[var(--color-text)]">Upload transactions</p>
            <p className="text-[13px] text-[var(--color-text-muted)]">Drop your transaction file here or browse</p>
            <p className="text-[11px] text-[var(--color-text-faint)]">PDF &middot; DOCX</p>
          </>
        )}
      </div>
    </div>
  );
}
