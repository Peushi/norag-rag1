import type { GraphStatus } from "../types/api";
import { documentTitle } from "../utils/documentNames";
import { TraceDetails } from "./TraceDetails";

type GraphBuildPanelProps = {
  status: GraphStatus;
  isStarting: boolean;
  startError: { message: string; traceId: string | null } | null;
  onBuild: () => void;
};

function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const sameDay = date.toDateString() === new Date().toDateString();
  return sameDay
    ? `today at ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
    : date.toLocaleDateString([], { day: "numeric", month: "short" });
}

function formatSeconds(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${Math.round(seconds - minutes * 60)} s`;
}

/** "Last update: 12 passages in 4 s (4 at a time)." Shown so build speed is visible. */
function lastBuild(status: GraphStatus): string | null {
  if (status.last_build_seconds === null || !status.last_build_llm_calls) return null;
  const passages = status.last_build_llm_calls === 1 ? "1 passage" : `${status.last_build_llm_calls} passages`;
  const pace = status.last_build_rate_limited
    ? "slowed down by the LLM’s rate limit"
    : `${status.concurrency} at a time`;
  return `Last update: ${passages} in ${formatSeconds(status.last_build_seconds)} (${pace}).`;
}

function calls(count: number): string {
  return count === 1 ? "1 LLM call" : `${count} LLM calls`;
}

function listTitles(sources: string[]): string {
  const titles = sources.map((source) => `“${documentTitle(source)}”`);
  if (titles.length <= 2) return titles.join(" and ");
  return `${titles.slice(0, 2).join(", ")} and ${titles.length - 2} more`;
}

/**
 * Build or update the concept map of the user's own documents: what it will
 * cost, progress while it runs, and what is out of date afterwards.
 */
export function GraphBuildPanel({ status, isStarting, startError, onBuild }: GraphBuildPanelProps) {
  const needed = status.llm_calls_needed;
  const capped = needed > status.max_llm_calls_per_build;

  if (status.building) {
    const total = Math.max(status.progress_total, 1);
    const percent = Math.round((status.progress_done / total) * 100);
    return (
      <div className="graph-build building" role="status" aria-live="polite">
        <p>
          Reading your documents for concepts and how they connect…{" "}
          <strong>
            {status.progress_done} of {status.progress_total}
          </strong>{" "}
          passages
          {status.progress_elapsed_seconds !== null
            ? ` · ${formatSeconds(status.progress_elapsed_seconds)}`
            : ""}
        </p>
        <div className="graph-progress" aria-hidden="true">
          <span style={{ width: `${percent}%` }} />
        </div>
        <TraceDetails key={status.build_trace_id ?? "none"} traceId={status.build_trace_id} />
      </div>
    );
  }

  const changes: string[] = [];
  if (status.new_documents.length) changes.push(`${listTitles(status.new_documents)} ${status.new_documents.length === 1 ? "isn’t" : "aren’t"} in the map yet`);
  if (status.changed_documents.length) changes.push(`${listTitles(status.changed_documents)} changed`);
  if (status.removed_documents.length) changes.push(`${listTitles(status.removed_documents)} ${status.removed_documents.length === 1 ? "was" : "were"} removed`);

  return (
    <div className={`graph-build ${status.built ? "built" : "empty"}`}>
      {!status.built ? (
        <>
          <p className="graph-build-title">Map how your documents connect</p>
          <p>
            BakeFix reads your documents once and links the things they talk
            about (dishes, ingredients, techniques, problems, products and more),
            with the passage behind each link. You can then explore the map and
            use it in search.
          </p>
        </>
      ) : status.settings_changed ? (
        <p>Your “Search options” passage settings changed, so the map needs rebuilding.</p>
      ) : changes.length > 0 ? (
        <p>{changes.join("; ")}.</p>
      ) : (
        <p className="graph-build-summary">
          Up to date: {status.triple_count} links from {status.document_count}{" "}
          {status.document_count === 1 ? "document" : "documents"}
          {status.built_at ? `, updated ${formatTime(status.built_at)}` : ""}.
          {lastBuild(status) && <span className="graph-build-timing"> {lastBuild(status)}</span>}
        </p>
      )}

      {status.last_error && (
        <p className="error" role="alert">
          {status.last_error}
        </p>
      )}
      {startError && (
        <div role="alert">
          <p className="error">{startError.message}</p>
          <TraceDetails key={startError.traceId ?? "none"} traceId={startError.traceId} />
        </div>
      )}

      {(!status.built || !status.up_to_date) && (
        <>
          <button type="button" className="button graph-build-button" disabled={isStarting} onClick={onBuild}>
            {isStarting ? "Starting…" : status.built ? "Update the map" : "Build the concept map"}
          </button>
          <p className="graph-build-cost">
            {needed === 0
              ? "No LLM calls needed: only removals to apply."
              : capped
                ? `Needs ${calls(needed)}; this run makes up to ${status.max_llm_calls_per_build}, and the rest can be added with another update.`
                : `Uses about ${calls(needed)} to your configured LLM. Only new or changed documents are read.`}
          </p>
        </>
      )}

      {status.build_trace_id && !status.last_error && status.built && (
        <TraceDetails key={status.build_trace_id} traceId={status.build_trace_id} label="Details of the last build" />
      )}
    </div>
  );
}
