export type CorpusWord = {
  word: string;
  occurrence_count: number;
  chunk_count: number;
};

export type WordChunkMatch = {
  chunk_id: string;
  source: string;
  position: number;
  text: string;
  occurrence_count: number;
};

export type QuestionWordMatch = {
  word: string;
  occurrence_count: number;
  chunk_count: number;
  chunks: WordChunkMatch[];
};

export type QuestionAnalysis = {
  words_found: QuestionWordMatch[];
  words_missing: string[];
  matching_chunks: WordChunkMatch[];
};
