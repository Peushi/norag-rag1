import { useState } from "react";
import "../../styles/words.css";
import type { EvaluationDataset } from "../types/evaluations";

type WordsMode = "corpus" | "question";
type WordsExperienceProps = {
  corpus: EvaluationDataset;
  onCorpusChange: (corpus: EvaluationDataset) => void;
};

function extractQuestionWords(question: string): string[] {
  return [
    ...new Set(
      question.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [],
    ),
  ];
}

export function WordsExperience({
  corpus,
  onCorpusChange,
}: WordsExperienceProps) {
  const [mode, setMode] = useState<WordsMode>("corpus");
  const [question, setQuestion] = useState("");
  const questionWords = extractQuestionWords(question);

  return (
    <main className="card words-card">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">
          Aa
        </span>
        <div>
          <h1>Words</h1>
          <p>Explore the vocabulary in your knowledge base.</p>
        </div>
      </div>

      <label className="words-search-label" htmlFor="words-corpus">
        Corpus
      </label>
      <select
        id="words-corpus"
        value={corpus}
        onChange={(event) =>
          onCorpusChange(event.target.value === "kestrel" ? "kestrel" : "baking")
        }
      >
        <option value="baking">Baking</option>
        <option value="kestrel">Kestrel</option>
      </select>

      <div className="words-mode-tabs" role="tablist" aria-label="Words modes">
        <button
          id="corpus-mode-tab"
          type="button"
          role="tab"
          aria-selected={mode === "corpus"}
          aria-controls="corpus-mode-panel"
          onClick={() => setMode("corpus")}
        >
          Corpus mode
        </button>
        <button
          id="question-mode-tab"
          type="button"
          role="tab"
          aria-selected={mode === "question"}
          aria-controls="question-mode-panel"
          onClick={() => setMode("question")}
        >
          Question mode
        </button>
      </div>

      {mode === "corpus" ? (
        <section
          id="corpus-mode-panel"
          className="words-mode-panel"
          role="tabpanel"
          aria-labelledby="corpus-mode-tab"
        >
          <div className="words-panel-heading">
            <div>
              <h2>Corpus vocabulary</h2>
              <p>
                Browse words by their total occurrences and the number of
                chunks that contain them.
              </p>
            </div>
          </div>

          <label className="words-search-label" htmlFor="corpus-word-search">
            Find a word
          </label>
          <input
            id="corpus-word-search"
            type="search"
            placeholder="Search vocabulary"
            disabled
            aria-describedby="corpus-analytics-status"
          />

          <div className="words-table-wrap">
            <table className="words-table">
              <thead>
                <tr>
                  <th scope="col">Word</th>
                  <th scope="col">Occurrences</th>
                  <th scope="col">Chunks</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colSpan={3} className="words-empty-cell">
                    Vocabulary will appear when the word analytics API is
                    connected.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <p
            id="corpus-analytics-status"
            className="words-integration-note"
            role="status"
          >
            Corpus selection and word counts are waiting for the shared
            analytics contract.
          </p>

          <section className="word-chunk-preview" aria-labelledby="word-chunks-title">
            <h3 id="word-chunks-title">Matching chunks</h3>
            <p>Select a vocabulary word to inspect its matching chunks.</p>
          </section>
        </section>
      ) : (
        <section
          id="question-mode-panel"
          className="words-mode-panel"
          role="tabpanel"
          aria-labelledby="question-mode-tab"
        >
          <div className="words-panel-heading">
            <div>
              <h2>Words in a question</h2>
              <p>
                Enter a question to inspect its words against the selected
                corpus.
              </p>
            </div>
          </div>

          <label className="words-search-label" htmlFor="question-set">
            Choose a saved question
          </label>
          <select id="question-set" disabled>
            <option>Question sets will be connected after the team agrees on their format</option>
          </select>

          <label className="words-search-label" htmlFor="words-question">
            Or write a question
          </label>
          <textarea
            id="words-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="For example: Why did my bread dough not rise?"
            rows={4}
          />

          {questionWords.length > 0 && (
            <div className="question-word-preview">
              <h3>Words found in your question</h3>
              <ul aria-label="Unique words extracted from the question">
                {questionWords.map((word) => (
                  <li key={word}>{word}</li>
                ))}
              </ul>
              <p className="words-integration-note" role="status">
                These words are normalized locally. Corpus matches, per-word
                counts, and missing words will appear after the analytics API
                is connected.
              </p>
            </div>
          )}

          {questionWords.length === 0 && (
            <p className="words-empty-state">
              Enter a question to preview its normalized words.
            </p>
          )}

          <section className="word-chunk-preview" aria-labelledby="question-chunks-title">
            <h3 id="question-chunks-title">Matching chunks</h3>
            <p>
              Chunks containing question words and words absent from the corpus
              will appear here.
            </p>
          </section>
        </section>
      )}
    </main>
  );
}
