import type { Answer } from "../types/api";

type AnswerPanelProps = {
  answer: Answer;
};

export function AnswerPanel({ answer }: AnswerPanelProps) {
  if (answer.kind === "loading") {
    return (
      <div className="answer-placeholder">
        <span className="placeholder-mark" aria-hidden="true">
          ~
        </span>
        <p>Gathering the helpful bits...</p>
      </div>
    );
  }

  if (answer.kind === "error") {
    return (
      <div className="error">
        <p>{answer.text}</p>
      </div>
    );
  }

  if (answer.kind === "empty") {
    return (
      <div className="answer-placeholder">
        <span className="placeholder-mark" aria-hidden="true">
          ~
        </span>
        <p>{answer.text}</p>
      </div>
    );
  }

  if (answer.kind === "not_found") {
    return (
      <>
        <div className="answer-title">Not in your notes yet</div>
        <p className="answer-copy not-found">{answer.text}</p>
      </>
    );
  }

  return (
    <>
      <div className="answer-title">A little guidance</div>
      <p className="answer-copy">{answer.text}</p>
      {answer.references.length > 0 && (
        <div className="references">
          <h3>From your notes</h3>
          <ul>
            {answer.references.map((reference) => (
              <li key={`${reference.chunk_id}-${reference.position}`}>
                <span className="reference-meta">
                  {reference.source} · note {reference.position + 1}
                </span>
                <span className="reference-quote">“{reference.quote}”</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
