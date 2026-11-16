# Answer style controls: evaluation (V4, Part B)

The V4 brief asks every menu feature to be traced, to state its cost and
latency per use, to show what the user sees on failures, and to be checked
"on several cases, including difficult ones". This is that check for answer
style controls (level, tone, length, "Explain it like I'm 12", glossary).

## Method

`python -m evaluation.style_evaluation`: 5 questions × 5 styles = 25 real
answers through the full pipeline (Dense + BM25 retrieval, redaction, Gemini
`gemini-3.5-flash-lite`, citation and glossary validation), each with its own
trace.

| Style | Level | Tone | Length | ELI12 |
| --- | --- | --- | --- | --- |
| short / medium / long | beginner | friendly | short / medium / long | no |
| eli12 | beginner | friendly | medium | yes |
| expert | expert | technical | medium | no |

| Question | Corpus | Why it's here |
| --- | --- | --- |
| S1 How do I stop my cookies from spreading? | Baking | Multi-step answer: does "short" really shorten it? |
| S2 Why are my brownies cakey instead of fudgy? | Baking | Short evidence: little room for length to vary |
| S3 What does error KST-2044 mean and how do I fix it? | Kestrel | Technical: hard for ELI12 |
| S4 Can I get a refund on my annual plan 45 days after it renewed? | Kestrel | Policy with dates: simplifying must not change the facts |
| S5 How long should I boil fresh pasta? | Baking | Not in the documents: no style may make it answer |

Measured per answer: outcome, words, Flesch reading ease (higher = easier;
60-70 is plain English, 80+ easy), validated citations, glossary entries,
tokens, cost and latency (from the answer's trace).

## First run: two problems found

Results: `answer_style_eval_before_fix.json`.

1. **Length was barely followed.** Mean words for short / medium / long: 73 / 88
   / 100; on S1 "short" was 122 words against 154 for "long". The instructions
   were vague ("Keep the answer brief").
2. **An ELI12 answer was rejected** (S2): ELI12 adds glossary terms, and one
   cited a retrieved passage the answer itself did not cite. Validation then
   rejected the whole, fully cited answer, so the user saw an error.

The style was also not recorded in the trace (only the model was).

## Fixes

- Length instructions now give concrete targets: short ≈ 60 words / 3
  sentences; medium ≈ 100-150; long ≈ 200-300 with numbered steps, "detail only
  from the retrieved chunks".
- A glossary entry that points to a retrieved but uncited passage is dropped
  (counted as `dropped_glossary_entries` in the trace) and the answer is kept.
  An entry pointing to an invented passage ID still rejects the answer.
- The `llm_generation` span records `style_level`, `style_tone`,
  `style_length`, `style_eli12`.

## Second run: results

Results: `answer_style_eval.json`.

| Style | Answered | Mean words | Mean Flesch | Mean output tokens | Mean cost | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| short | 3/5 | 43 | 54 | 182 | $0.00092 | 1.9 s |
| medium | 3/5 | 95 | 51 | 268 | $0.00113 | 3.0 s |
| long | 3/5 | 139 | 56 | 344 | $0.00133 | 2.2 s |
| eli12 | 3/5 | 95 | **73** | 298 | $0.00122 | 2.3 s |
| expert | 3/5 | 95 | **46** | 364 | $0.00137 | 2.1 s |

| Check | Result |
| --- | --- |
| Length orders short < medium < long | ✅ all 3 answered questions (S1: 54 / 128 / 203 words; S4: 33 / 110 / 144; S2: 41 / 48 / 71) |
| ELI12 reads easier than expert | ✅ all 3 (S1 66 vs 39, S2 63 vs 44, S4 90 vs 55) |
| Off-topic question refused in every style | ✅ S5 refused 5/5 |
| Every answer keeps valid citations | ✅ 15/15 answered |
| Rejected (invalid) answers | ✅ 0/25 (was 1/25) |
| Style recorded in the trace | ✅ 25/25 |

Read by hand: the 203-word "long" S1 answer only uses steps from the cookie
guide, each cited; the ELI12 S4 answer ("Since 45 days is less than 60 days,
you are still in luck!") matches the 2026 billing policy (refund within 60 days,
unused full months).

## Cost and latency per use

One answer costs about $0.0009 (short) to $0.0014 (expert); a longer or
expert answer costs up to 50% more because of output tokens. Latency is about
2-3 s per answer whatever the style; it varies more with the provider than
with the style. Styles add no extra LLM call: they are part of the one
generation prompt.

## What the user sees when it fails

- Invalid output (no valid citations, invented source): "BakeFix couldn't check
  this answer against your documents, so it didn't show it", with Try again.
- A glossary entry that can't be linked to a source: dropped silently; the
  answer stays.
- Not in the documents: "Not in your documents" with what to try, in any style.

## Limits

- 5 questions, one run each: indications, not precise measurements.
- Flesch is a rough readability proxy for English; it doesn't judge correctness.
- S3 (KST-2044) was refused in every style although the runbook explains it.
  This is the known over-refusal from the V2 manual grading, not a style
  effect; it remains our main generation failure.
- On short evidence (S2) length varies less: the prompt forbids padding with
  outside knowledge, which is the intended trade-off.
