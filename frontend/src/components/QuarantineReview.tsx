import { useState } from "react";
import type { QuarantineFinding, QuarantineItem } from "../types/api";

/** Plain-language reasons for each scanner rule (rule IDs stay in the trace). */
const RULE_LABELS: Record<string, string> = {
  instruction_override: "Tries to override the assistant’s instructions",
  role_impersonation: "Pretends to be a system or developer message",
  secret_extraction: "Asks for secrets or hidden instructions",
  external_exfiltration: "Asks to send data to a web address",
  assistant_redirect: "Gives orders to an AI assistant",
  context_escape: "Contains markers used to break out of a prompt",
  policy_reset: "Claims to replace the assistant’s rules",
};

function findingLabel(finding: QuarantineFinding): string {
  return RULE_LABELS[finding.rule_id] ?? finding.message;
}

type QuarantineReviewProps = {
  items: QuarantineItem[];
  loadError: string;
  onRetryLoad: () => void;
  onRelease: (item: QuarantineItem) => Promise<void>;
  onReject: (item: QuarantineItem) => Promise<void>;
};

/** Documents the scanner held back, with what it found and the review actions. */
export function QuarantineReview({
  items,
  loadError,
  onRetryLoad,
  onRelease,
  onReject,
}: QuarantineReviewProps) {
  if (loadError) {
    return (
      <div className="quarantine library-error" role="alert">
        <p>{loadError}</p>
        <button type="button" className="button secondary" onClick={onRetryLoad}>
          Try again
        </button>
      </div>
    );
  }

  if (items.length === 0) {
    return null;
  }

  return (
    <section className="quarantine" aria-labelledby="quarantine-title">
      <div className="library-label">
        <span id="quarantine-title">Held for review</span>
        <span className="document-count quarantine-count">{items.length}</span>
      </div>
      <p className="quarantine-help">
        These documents contain text that looks like instructions aimed at an
        AI assistant. Such text could change how answers are written, so
        BakeFix doesn’t search them until you decide.
      </p>
      <ul className="quarantine-list">
        {items.map((item) => (
          <QuarantineEntry
            key={item.id}
            item={item}
            onRelease={onRelease}
            onReject={onReject}
          />
        ))}
      </ul>
    </section>
  );
}

function QuarantineEntry({
  item,
  onRelease,
  onReject,
}: {
  item: QuarantineItem;
  onRelease: (item: QuarantineItem) => Promise<void>;
  onReject: (item: QuarantineItem) => Promise<void>;
}) {
  const [trusted, setTrusted] = useState(false);
  const [confirmingDiscard, setConfirmingDiscard] = useState(false);
  const [busy, setBusy] = useState<"release" | "reject" | null>(null);
  const count = item.findings.length;

  async function run(action: "release" | "reject") {
    setBusy(action);
    try {
      await (action === "release" ? onRelease(item) : onReject(item));
    } finally {
      setBusy(null);
    }
  }

  return (
    <li className="quarantine-item">
      <details>
        <summary>
          <span className="document-name" title={item.source}>
            {item.source}
          </span>
          <span className="quarantine-meta">
            {count === 1 ? "1 suspicious passage" : `${count} suspicious passages`}{" "}
            · Review
          </span>
        </summary>

        <ol className="quarantine-findings">
          {item.findings.map((finding, index) => (
            <li key={`${finding.rule_id}-${finding.line}-${index}`}>
              <span className="finding-label">
                {findingLabel(finding)}
                <span className={`finding-severity ${finding.severity}`}>
                  {finding.severity === "high" ? "High risk" : "Medium risk"}
                </span>
              </span>
              <span className="finding-line">Line {finding.line}</span>
              <q className="finding-excerpt">{finding.excerpt}</q>
            </li>
          ))}
        </ol>

        {item.status === "releasing" && (
          <p className="quarantine-note">
            Adding this document was approved but didn’t finish. You can try
            adding it again.
          </p>
        )}

        <label className="quarantine-trust">
          <input
            type="checkbox"
            checked={trusted}
            onChange={(event) => setTrusted(event.target.checked)}
            disabled={busy !== null}
          />
          I’ve read these passages and trust this document.
        </label>

        <div className="quarantine-actions">
          <button
            type="button"
            className="button secondary"
            disabled={!trusted || busy !== null}
            onClick={() => void run("release")}
          >
            {busy === "release" ? "Adding…" : "Add anyway"}
          </button>

          {confirmingDiscard ? (
            <span className="delete-confirm">
              <span>Delete its text for good?</span>
              <button
                type="button"
                className="delete-doc danger"
                disabled={busy !== null}
                onClick={() => void run("reject")}
              >
                {busy === "reject" ? "Discarding…" : "Discard"}
              </button>
              <button
                type="button"
                className="delete-doc"
                disabled={busy !== null}
                onClick={() => setConfirmingDiscard(false)}
              >
                Cancel
              </button>
            </span>
          ) : (
            <button
              type="button"
              className="delete-doc"
              disabled={busy !== null || item.status !== "quarantined"}
              onClick={() => setConfirmingDiscard(true)}
            >
              Discard
            </button>
          )}
        </div>
      </details>
    </li>
  );
}
