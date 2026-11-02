import { useEffect, useState, type FormEvent } from "react";
import "../../styles/words.css";
import { useWordsAnalytics } from "../hooks/useWordsAnalytics";
import type { EvaluationDataset } from "../types/evaluations";
import type { WordChunkMatch } from "../types/words";

type WordsMode = "corpus" | "question";
type WordsExperienceProps = {
  corpus: EvaluationDataset;
  onCorpusChange: (corpus: EvaluationDataset) => void;
};

function WordChunkList({
  chunks,
  isLoading,
}: {
  chunks: WordChunkMatch[];
  isLoading: boolean;
}) {
  if (isLoading) {
    return <p role="status">Loading matching chunks...</p>;
  }
  if (chunks.length === 0) {
    return <p>No matching chunks to show.</p>;
  }

  return (
    <ul className="word-matches-list">
      {chunks.map((chunk) => (
        <li key={chunk.chunk_id}>
          <div className="word-match-meta">
            <strong>{chunk.source}</strong>
            <span>Chunk {chunk.position + 1}</span>
            <span>{chunk.occurrence_count} occurrence(s)</span>
            {chunk.matched_words.length > 0 && (
              <span>Words: {chunk.matched_words.join(", ")}</span>
            )}
          </div>
          <p>{chunk.text}</p>
        </li>
      ))}
    </ul>
  );
}

export function WordsExperience({
  corpus,
  onCorpusChange,
}: WordsExperienceProps) {
  const [mode, setMode] = useState<WordsMode>("corpus");
  const [question, setQuestion] = useState("");
  const [selectedQuestionId, setSelectedQuestionId] = useState("");
  const [wordSearch, setWordSearch] = useState("");
  const [submittedWordSearch, setSubmittedWordSearch] = useState("");
  const [selectedWord, setSelectedWord] = useState("");
  const [chunkSizeInput, setChunkSizeInput] = useState("800");
  const [overlapInput, setOverlapInput] = useState("80");
  const chunkSize = Number(chunkSizeInput);
  const overlap = Number(overlapInput);
  const validChunking =
    Number.isInteger(chunkSize) &&
    chunkSize >= 100 &&
    chunkSize <= 2000 &&
    Number.isInteger(overlap) &&
    overlap >= 0 &&
    overlap < chunkSize &&
    overlap <= 1000;
  const analytics = useWordsAnalytics(corpus, chunkSize, overlap);

  useEffect(() => {
    if (!validChunking) {
      return;
    }
    setSelectedWord("");
    setSelectedQuestionId("");
    setWordSearch("");
    setSubmittedWordSearch("");
    analytics.clearResults();
    void analytics.loadVocabulary();
  }, [corpus, chunkSize, overlap]);

  useEffect(() => {
    void analytics.loadQuestions();
  }, [corpus]);

  function submitWordSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validChunking) {
      return;
    }
    setSubmittedWordSearch(wordSearch.trim());
    void analytics.loadVocabulary(wordSearch.trim());
  }

  function changePage(offset: number) {
    if (!validChunking) {
      return;
    }
    void analytics.loadVocabulary(submittedWordSearch, offset);
  }

  function selectQuestion(questionId: string) {
    setSelectedQuestionId(questionId);
    analytics.clearResults();
    const savedQuestion = analytics.questions.find(
      (item) => item.id === questionId,
    );
    if (savedQuestion) {
      setQuestion(savedQuestion.question);
    }
  }

  function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validChunking) {
      return;
    }
    void analytics.analyzeQuestion(question);
  }

  return (
    <main className="card words-card">
      <div className="section-heading">
        <span className="section-icon" aria-hidden="true">
          Aa
        </span>
        <div>
          <h1>Words</h1>
          <p>Explore vocabulary and its matching chunks.</p>
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

      <div className="words-chunk-settings">
        <label>
          Chunk size
          <input
            type="number"
            min="100"
            max="2000"
            value={chunkSizeInput}
            onChange={(event) => setChunkSizeInput(event.target.value)}
          />
        </label>
        <label>
          Overlap
          <input
            type="number"
            min="0"
            max="1000"
            value={overlapInput}
            onChange={(event) => setOverlapInput(event.target.value)}
          />
        </label>
        <span>
          Uses the same chunking function and IDs as retrieval/evaluation.
        </span>
      </div>
      {!validChunking && (
        <p className="error" role="alert">
          Chunk size must be 100–2000, and overlap must be from 0 to 1000 and
          smaller than chunk size.
        </p>
      )}

      {analytics.error && (
        <p className="error words-error" role="alert">
          {analytics.error}
        </p>
      )}

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
                Total occurrences in source documents and the number of chunks
                containing each word. Overlap can make per-chunk counts add up
                to more than the corpus total.
              </p>
            </div>
          </div>

          <form className="word-search-form" onSubmit={submitWordSearch}>
            <label className="words-search-label" htmlFor="corpus-word-search">
              Find a word
            </label>
            <div className="word-search-controls">
              <input
                id="corpus-word-search"
                type="search"
                placeholder="Search vocabulary"
                value={wordSearch}
                onChange={(event) => setWordSearch(event.target.value)}
              />
              <button className="button secondary" type="submit">
                Search
              </button>
            </div>
          </form>

          <p className="words-integration-note" aria-live="polite">
            {analytics.vocabulary
              ? `${analytics.vocabulary.total_words} unique words in this corpus. Showing ${analytics.vocabulary.words.length} at a time.`
              : "Loading corpus vocabulary..."}
          </p>

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
                {analytics.isLoadingVocabulary ? (
                  <tr>
                    <td colSpan={3} className="words-empty-cell">
                      Loading vocabulary...
                    </td>
                  </tr>
                ) : analytics.vocabulary?.words.length ? (
                  analytics.vocabulary.words.map((entry) => (
                    <tr key={entry.word}>
                      <td>
                        <button
                          className="word-select-button"
                          type="button"
                          aria-pressed={selectedWord === entry.word}
                          onClick={() => {
                            setSelectedWord(entry.word);
                            if (validChunking) {
                              void analytics.loadWordChunks(entry.word);
                            }
                          }}
                        >
                          {entry.word}
                        </button>
                      </td>
                      <td>{entry.occurrence_count}</td>
                      <td>{entry.chunk_count}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={3} className="words-empty-cell">
                      No words match that search.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {analytics.vocabulary && (
            <div className="words-pagination">
              <button
                type="button"
                className="button secondary"
                disabled={
                  analytics.isLoadingVocabulary ||
                  analytics.vocabulary.offset === 0
                }
                onClick={() =>
                  changePage(
                    Math.max(0, analytics.vocabulary!.offset - 100),
                  )
                }
              >
                Previous
              </button>
              <span>
                {analytics.vocabulary.matching_words === 0
                  ? "0"
                  : analytics.vocabulary.offset + 1}
                –
                {analytics.vocabulary.offset +
                  analytics.vocabulary.words.length}{" "}
                of {analytics.vocabulary.matching_words}
              </span>
              <button
                type="button"
                className="button secondary"
                disabled={
                  analytics.isLoadingVocabulary ||
                  analytics.vocabulary.offset +
                    analytics.vocabulary.words.length >=
                    analytics.vocabulary.matching_words
                }
                onClick={() =>
                  changePage(analytics.vocabulary!.offset + 100)
                }
              >
                Next
              </button>
            </div>
          )}

          <section className="word-chunk-preview" aria-labelledby="word-chunks-title">
            <h3 id="word-chunks-title">
              {selectedWord
                ? `Chunks containing “${selectedWord}”`
                : "Matching chunks"}
            </h3>
            {selectedWord && analytics.wordChunks && (
              <p>
                {analytics.wordChunks.occurrence_count} occurrences across{" "}
                {analytics.wordChunks.chunk_count} chunks.
              </p>
            )}
            <WordChunkList
              chunks={analytics.wordChunks?.chunks ?? []}
              isLoading={analytics.isLoadingChunks}
            />
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
                Compare question words with the selected corpus using exact,
                case-insensitive word matching. Punctuation separates words, so
                KST-2044 is checked as “kst” and “2044”.
              </p>
            </div>
          </div>

          <form className="question-analysis-form" onSubmit={submitQuestion}>
            <label className="words-search-label" htmlFor="question-set">
              Choose a saved question
            </label>
            <select
              id="question-set"
              value={selectedQuestionId}
              onChange={(event) => selectQuestion(event.target.value)}
            >
              <option value="">Choose a question (optional)</option>
              {analytics.questions.map((savedQuestion) => (
                <option key={savedQuestion.id} value={savedQuestion.id}>
                  {savedQuestion.id}: {savedQuestion.question}
                </option>
              ))}
            </select>

            <label className="words-search-label" htmlFor="words-question">
              Or write a question
            </label>
            <textarea
              id="words-question"
              value={question}
              onChange={(event) => {
                setQuestion(event.target.value);
                analytics.clearResults();
              }}
              placeholder="For example: Why did my bread dough not rise?"
              rows={4}
            />
            <button
              className="button"
              type="submit"
              disabled={
                !question.trim() ||
                !validChunking ||
                analytics.isAnalyzingQuestion
              }
            >
              {analytics.isAnalyzingQuestion ? "Analyzing..." : "Analyze words"}
            </button>
          </form>

          {analytics.questionAnalysis && (
            <>
              <section className="question-word-preview">
                <h3>Words found in the corpus</h3>
                {analytics.questionAnalysis.words_found.length ? (
                  <ul>
                    {analytics.questionAnalysis.words_found.map((entry) => (
                      <li key={entry.word}>
                        {entry.word}: {entry.occurrence_count} occurrences in{" "}
                        {entry.chunk_count} chunks
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>No question words were found in this corpus.</p>
                )}
                <h3>Words not found in the corpus</h3>
                {analytics.questionAnalysis.words_missing.length ? (
                  <ul>
                    {analytics.questionAnalysis.words_missing.map((word) => (
                      <li key={word}>{word}</li>
                    ))}
                  </ul>
                ) : (
                  <p>All question words appear in the corpus.</p>
                )}
              </section>

              <section
                className="word-chunk-preview"
                aria-labelledby="question-chunks-title"
              >
                <h3 id="question-chunks-title">
                  Chunks containing question words
                </h3>
                <WordChunkList
                  chunks={analytics.questionAnalysis.matching_chunks}
                  isLoading={false}
                />
              </section>
            </>
          )}
        </section>
      )}
    </main>
  );
}
