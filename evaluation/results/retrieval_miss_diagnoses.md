# V2 retrieval miss diagnoses

These observations use saved retrieval-only results. Ranks start at 1; chunk positions start at 0. All runs use MiniLM, cosine distance, and no distance threshold. No document filter is applied by the evaluation runner.

## kestrel q01 — 800/80

What does error KST-2044 mean and how do I fix it?

Hit@5: False; Recall@5: 0.0%; Recall@10: 100.0%.

### Expected evidence

- `support-runbook-errors.md`: “the Kestrel addresses are missing from it”
  Complete-quote positions: [4]; retrieved ranks within top 10: [7]; boundary split: False.
- `support-runbook-errors.md`: “add both 203.0.113.10 and 203.0.113.11 to the allowlist”
  Complete-quote positions: [4]; retrieved ranks within top 10: [7]; boundary split: False.

### Actual top five

| Rank | Chunk ID | Source | Distance |
|---:|---|---|---:|
| 1 | `b748a9c48e16::chunk_0008` | `support-runbook-errors.md` | 0.5369 |
| 2 | `b748a9c48e16::chunk_0006` | `support-runbook-errors.md` | 0.5707 |
| 3 | `b748a9c48e16::chunk_0003` | `support-runbook-errors.md` | 0.5789 |
| 4 | `b748a9c48e16::chunk_0000` | `support-runbook-errors.md` | 0.5854 |
| 5 | `b748a9c48e16::chunk_0005` | `support-runbook-errors.md` | 0.5982 |

### Retrieved text previews

1. (KST-5xxx) ### KST-5031 — Scheduled report not delivered **User sees:** the schedule shows "Last delivery failed". **Cause:** the report was generated but the e-mail was not sent. This error is raised by postroom, the service that sends all…
2. t is the same on every plan and cannot be raised. **Escalate:** to Analytics Engine only if a query that used to finish quickly suddenly times out for many datasets of the same customer. ### KST-3020 — Dataset refresh failed **User sees:** …
3. only does it after identity verification). **Escalate:** no. ### KST-1012 — SSO response rejected **User sees:** "Your identity provider returned an invalid response." **Cause:** the identity provider certificate has expired or was rotated,…
4. # Kestrel Analytics — Support Runbook: Error Codes Internal document · Owner: Customer Support · Last reviewed: 2 September 2026 ## How to use this runbook Every error shown to a Kestrel user carries a code of the form `KST-` followed by fo…
5. e connections can come from either address. **Escalate:** no. ### KST-2051 — Credentials rejected **User sees:** "The username or password for this data source is incorrect." **Cause:** the database password was changed, or the database use…

### Diagnosis

Verified: both quotes, including both IP addresses, occur together in position 4 and rank 7. Top-5 truncation excludes them; top 10 recovers them. Neither filtering nor a boundary split explains this miss. The smaller 400/40 configuration recovers neither quote within top 10.

Hypothesis: shared runbook/error-code vocabulary causes other error sections to rank above the exact code. Embedding rankings alone do not prove this lexical explanation.

### Words Analytics observations

Measured through the merged Words Question Mode API using `kestrel`, chunk size 800, overlap 80 (43 chunks). Token counts were independently checked against source text. This verifies the API used by the UI; no browser interaction is claimed.

- Query tokens absent from the corpus: `mean`, `i`, `fix`.
- Common query tokens: `and` occurs 122 times in source documents and in 43/43 chunks; `it` occurs 29 times in source documents and in 21/43 chunks; `do` occurs 10 times in source documents and in 12/43 chunks; `kst` occurs 23 times in source documents and in 12/43 chunks; `error` occurs 12 times in source documents and in 9/43 chunks.

| Expected chunk ID | Query-token occurrences inside this chunk |
|---|---|
| `b748a9c48e16::chunk_0004` | `kst`: 2, `2044`: 1, `and`: 4, `it`: 2 |

| Retrieval rank | Query-token occurrences inside the retrieved chunk |
|---:|---|
| 1 | `error`: 2, `kst`: 3, `and`: 1 |
| 2 | `error`: 1, `kst`: 4, `and`: 2, `do`: 1 |
| 3 | `does`: 1, `error`: 1, `kst`: 3, `and`: 1, `it`: 1 |
| 4 | `what`: 2, `error`: 2, `kst`: 1, `and`: 5, `how`: 1, `do`: 1, `it`: 2 |
| 5 | `kst`: 3, `and`: 4 |

The required chunk contains `2044` once and `kst` twice, but does not contain the query token `error`. The five higher-ranked previews share `kst` and generic runbook wording, and none contains `2044`. This confirms that the distinguishing exact identifier exists in the evidence but is not prioritized sufficiently by semantic ranking. It does not prove the embedding model’s internal cause. The absent generic verbs are not evidence that the answer is unavailable.

To reproduce visually: open Words → select this corpus → set the chunk size/overlap above → Question mode → select this question → Analyze. Word counts and matching chunks should agree with these observations.

## kestrel q08 — 800/80

Error KST-5031 happened on the last two scheduled reports. Which team should support contact, and where?

Hit@5: True; Recall@5: 50.0%; Recall@10: 50.0%.

### Expected evidence

- `support-runbook-errors.md`: “escalate to the team that owns postroom”
  Complete-quote positions: [8]; retrieved ranks within top 10: [1]; boundary split: False.
- `service-catalog.md`: “| Messaging | Inès Moreau | #oncall-messaging | 08:00–20:00, weekdays |”
  Complete-quote positions: [3]; retrieved ranks within top 10: []; boundary split: False.

### Actual top five

| Rank | Chunk ID | Source | Distance |
|---:|---|---|---:|
| 1 | `b748a9c48e16::chunk_0008` | `support-runbook-errors.md` | 0.3603 |
| 2 | `1382412bce5f::chunk_0011` | `product-guide.md` | 0.4113 |
| 3 | `b748a9c48e16::chunk_0000` | `support-runbook-errors.md` | 0.4661 |
| 4 | `b748a9c48e16::chunk_0001` | `support-runbook-errors.md` | 0.4947 |
| 5 | `b748a9c48e16::chunk_0006` | `support-runbook-errors.md` | 0.5024 |

### Retrieved text previews

1. (KST-5xxx) ### KST-5031 — Scheduled report not delivered **User sees:** the schedule shows "Last delivery failed". **Cause:** the report was generated but the e-mail was not sent. This error is raised by postroom, the service that sends all…
2. out personal data (access, correction, deletion) can be sent to privacy@kestrel.example. We answer within one month. ## 11. Getting help | Plan | Channels | First response target | |---|---|---| | Free | Help centre, community forum | Best …
3. # Kestrel Analytics — Support Runbook: Error Codes Internal document · Owner: Customer Support · Last reviewed: 2 September 2026 ## How to use this runbook Every error shown to a Kestrel user carries a code of the form `KST-` followed by fo…
4. ons go to the team that owns the service involved. The owning team of each service and its on-call channel are listed in the Service Catalog. ## Severity levels | Level | Meaning | Target first response | |---|---|---| | SEV-1 | Many custom…
5. t is the same on every plan and cannot be raised. **Escalate:** to Analytics Engine only if a query that used to finish quickly suddenly times out for many datasets of the same customer. ### KST-3020 — Dataset refresh failed **User sees:** …

### Diagnosis

Verified: runbook evidence is at rank 1, but the catalog channel quote is absent within top 10. Thus a hit still has only 50% labeled evidence recall. The 400/40 run recovers neither labeled quote within top 10.

The answer also needs the catalog passage linking postroom to its owner, Messaging. That link is not separately labeled in the supplied q08 evidence, so even 100% labeled recall would not guarantee complete two-hop evidence. The source contains the link; preserve the professor dataset and document this label limitation.

Hypothesis: the question names KST-5031 and reports, but not postroom or Messaging, weakening direct similarity to the catalog. This is a two-hop retrieval limitation, not a demonstrated generation failure.

### Words Analytics observations

Measured through the merged Words Question Mode API using `kestrel`, chunk size 800, overlap 80 (43 chunks). Token counts were independently checked against source text. This verifies the API used by the UI; no browser interaction is claimed.

- Query tokens absent from the corpus: `should`, `where`.
- Common query tokens: `and` occurs 122 times in source documents and in 43/43 chunks; `the` occurs 333 times in source documents and in 43/43 chunks; `on` occurs 58 times in source documents and in 37/43 chunks; `support` occurs 34 times in source documents and in 20/43 chunks; `kst` occurs 23 times in source documents and in 12/43 chunks.

| Expected chunk ID | Query-token occurrences inside this chunk |
|---|---|
| `b748a9c48e16::chunk_0008` | `error`: 2, `kst`: 3, `5031`: 1, `on`: 2, `the`: 10, `last`: 1, `two`: 1, `scheduled`: 1, `team`: 1, `support`: 1, `and`: 1 |
| `2490e5184d68::chunk_0003` | `on`: 2, `the`: 1, `team`: 1, `and`: 2 |

| Retrieval rank | Query-token occurrences inside the retrieved chunk |
|---:|---|
| 1 | `error`: 2, `kst`: 3, `5031`: 1, `on`: 2, `the`: 10, `last`: 1, `two`: 1, `scheduled`: 1, `team`: 1, `support`: 1, `and`: 1 |
| 2 | `error`: 1, `kst`: 1, `happened`: 1, `the`: 3, `team`: 1, `support`: 1, `contact`: 2, `and`: 1 |
| 3 | `error`: 2, `kst`: 1, `happened`: 1, `on`: 1, `the`: 14, `last`: 1, `team`: 3, `support`: 3, `and`: 5 |
| 4 | `kst`: 2, `on`: 4, `the`: 7, `team`: 2, `support`: 1, `and`: 1 |
| 5 | `error`: 1, `kst`: 4, `on`: 3, `the`: 10, `support`: 2, `and`: 2 |

The expected catalog table chunk shares only `on`, `the`, `team`, and `and` with the query. The query itself contains neither `postroom` nor `messaging`; the runbook is needed to discover that connection. This supports a vocabulary-gap/two-hop diagnosis. Generic query words also occur widely in unrelated chunks. Increasing k from 5 to 10 did not recover the catalog evidence.

To reproduce visually: open Words → select this corpus → set the chunk size/overlap above → Question mode → select this question → Analyze. Word counts and matching chunks should agree with these observations.

## baking B04 — 400/40

I have no weighing scale. How can I fill a cup with flour without accidentally adding too much?

Hit@5: False; Recall@5: 0.0%; Recall@10: 100.0%.

### Expected evidence

- `general/how_to_measure_flour.md`: “Stir the flour gently in its bag or container with a spoon to loosen it.”
  Complete-quote positions: [4]; retrieved ranks within top 10: [6]; boundary split: False.
- `general/how_to_measure_flour.md`: “Spoon the loosened flour into the measuring cup until it overflows.”
  Complete-quote positions: [5]; retrieved ranks within top 10: [7]; boundary split: False.

### Actual top five

| Rank | Chunk ID | Source | Distance |
|---:|---|---|---:|
| 1 | `48b29066ef44::chunk_0009` | `general/how_to_measure_flour.md` | 0.2882 |
| 2 | `48b29066ef44::chunk_0002` | `general/how_to_measure_flour.md` | 0.3007 |
| 3 | `48b29066ef44::chunk_0008` | `general/how_to_measure_flour.md` | 0.3081 |
| 4 | `48b29066ef44::chunk_0003` | `general/how_to_measure_flour.md` | 0.3094 |
| 5 | `48b29066ef44::chunk_0007` | `general/how_to_measure_flour.md` | 0.3276 |

### Retrieved text previews

1. into the cup, and leveled carefully. ## Key takeaway For consistent baking, weigh flour using the amount specified in the recipe. If using volume measurements, loosen the flour, spoon it into the cup, and level without packing. When trouble…
2. se flour and recipes, **1 cup corresponds to 120 g**. A tightly packed cup can contain as much as **160 g**, adding substantially more flour than intended. Use the flour weight specified in your particular recipe when available; not every r…
3. om the bag with the measuring cup? The flour may pack together and you may add too much. A tightly packed cup of all-purpose flour can weigh up to 160 g instead of the intended 120 g in the King Arthur method. ### Do I need a scale to bake …
4. the scale and set the unit to grams. 2. Place the empty bowl or container on the scale. 3. Press **Tare** to reset the display to zero with the container on it. 4. Add flour until the display reaches the weight required by the recipe. 5. If…
5. or use the fluff, sprinkle, and scrape technique when measuring by volume. ### Is 1 cup of flour always 120 g? No. **120 g is King Arthur Baking's standard for a cup of its all-purpose flour.** Follow the recipe's listed gram weight when pr…

### Diagnosis

Verified genuine top-5 miss: all five results come from the expected flour document, but neither labeled instruction is recovered. The fluffing instruction ranks 6 and spooning instruction ranks 7. Neither quote crosses a boundary. Top 10 recovers both.

With 800/80, both instructions occur together at rank 3, giving Recall@5=100%. Larger chunks preserve useful neighboring instructions in this case.

Hypothesis: broad flour-measurement passages share question vocabulary and outrank the specific procedural steps when separated into smaller chunks.

### Words Analytics observations

Measured through the merged Words Question Mode API using `baking`, chunk size 400, overlap 40 (131 chunks). Token counts were independently checked against source text. This verifies the API used by the UI; no browser interaction is claimed.

- Query tokens absent from the corpus: None.
- Common query tokens: `a` occurs 242 times in source documents and in 108/131 chunks; `can` occurs 75 times in source documents and in 58/131 chunks; `flour` occurs 91 times in source documents and in 52/131 chunks; `with` occurs 56 times in source documents and in 50/131 chunks; `i` occurs 42 times in source documents and in 35/131 chunks.

| Expected chunk ID | Query-token occurrences inside this chunk |
|---|---|
| `48b29066ef44::chunk_0004` | `no`: 1, `scale`: 1, `how`: 1, `a`: 1, `with`: 2, `flour`: 2 |
| `48b29066ef44::chunk_0005` | `a`: 2, `cup`: 3, `flour`: 3, `without`: 1, `too`: 1 |

| Retrieval rank | Query-token occurrences inside the retrieved chunk |
|---:|---|
| 1 | `cup`: 2, `flour`: 3, `without`: 1 |
| 2 | `scale`: 2, `how`: 1, `can`: 1, `a`: 3, `cup`: 3, `with`: 1, `flour`: 4, `adding`: 1, `much`: 1 |
| 3 | `i`: 1, `scale`: 2, `can`: 2, `a`: 3, `cup`: 3, `with`: 1, `flour`: 3, `too`: 1, `much`: 1 |
| 4 | `scale`: 2, `a`: 2, `cup`: 1, `with`: 1, `flour`: 2 |
| 5 | `i`: 1, `no`: 1, `can`: 1, `a`: 1, `cup`: 3, `with`: 1, `flour`: 4 |

All question tokens exist somewhere in the corpus; vocabulary absence is not the explanation. `flour` appears in 52/131 chunks, so its presence is weak evidence of the exact procedural passage. The expected spooning chunk contains `cup` three times and `flour` three times, yet ranks seventh. Higher-ranked chunks also contain these terms. This is a ranking/context-granularity miss under the quote labels, not an out-of-corpus question.

The top-ranked chunk includes a shorter paraphrase of the measuring procedure. Therefore this labeled-quote miss does not prove that a generated answer would fail. With 800/80, both labeled instructions are included together at rank 3.

To reproduce visually: open Words → select this corpus → set the chunk size/overlap above → Question mode → select this question → Analyze. Word counts and matching chunks should agree with these observations.

## baking B07 — 800/80

The edges of my pastry keep sliding down the pie dish during blind baking. How can I prevent this?

Hit@5: True; Recall@5: 33.3%; Recall@10: 33.3%.

### Expected evidence

- `pies/prebaking_pie_crust.md`: “to relax the dough and firm its fat, reducing shrinkage.”
  Complete-quote positions: [1]; retrieved ranks within top 10: []; boundary split: False.
- `pies/prebaking_pie_crust.md`: “Pastry can contract as it heats, especially if it has not been chilled.”
  Complete-quote positions: [3]; retrieved ranks within top 10: [1]; boundary split: False.
- `pies/prebaking_pie_crust.md`: “The upside-down arrangement uses gravity to keep the pastry toward the rim rather than letting it slump into the bottom.”
  Complete-quote positions: [4]; retrieved ranks within top 10: []; boundary split: False.

### Actual top five

| Rank | Chunk ID | Source | Distance |
|---:|---|---|---:|
| 1 | `8d9155c942e2::chunk_0003` | `pies/prebaking_pie_crust.md` | 0.3919 |
| 2 | `ff67c37ea967::chunk_0000` | `pies/soggy_pie_crust.md` | 0.4089 |
| 3 | `ff67c37ea967::chunk_0006` | `pies/soggy_pie_crust.md` | 0.4523 |
| 4 | `ff67c37ea967::chunk_0001` | `pies/soggy_pie_crust.md` | 0.4996 |
| 5 | `ff67c37ea967::chunk_0002` | `pies/soggy_pie_crust.md` | 0.5392 |

### Retrieved text previews

1. e the lining and weights. 2. Prick the bottom of the crust with a fork to discourage bubbling. 3. Return it to the **375°F (about 190°C)** oven for another **20–25 minutes**, until golden throughout. 4. Let it cool as appropriate before add…
2. # Preventing a Soggy Pie Crust Source: King Arthur Baking, "Prevent soggy bottoms in pies with these baker secrets" Author: Rossi Anastopoulo Published: 2023-11-06 URL: https://www.kingarthurbaking.com/blog/2023/11/06/prevent-pie-soggy-bott…
3. ope These are prevention tips, not a guarantee that an already soggy baked crust can be made crisp. This document summarizes the linked King Arthur Baking article and does not provide a complete pie recipe or full blind-baking procedure.…
4. , helping the bottom crust bake more evenly. A metal pan is a useful choice when the underside of a pie tends to remain underbaked. ### 2. Prebake the crust when the pie allows it Prebaking (also called blind baking) lets the pastry set bef…
5. help both filled pies and crusts being prebaked. A baking sheet underneath the pie is another option mentioned in the source; it catches drips and can help direct heat toward the base. ### 4. Place a thin layer of frangipane or almond paste…

### Diagnosis

Verified partial-evidence miss: the first chunk matches the question closely and includes one expected quote, but two other labeled quotes are absent even at k=10. No quote crosses a boundary at 800/80. The first retrieved chunk may still contain useful advice: missing exact labels is not proof that generation cannot answer.

The 400/40 experiment still recovers only one quote and additionally splits the first labeled quote across boundaries.

### Words Analytics observations

Measured through the merged Words Question Mode API using `baking`, chunk size 800, overlap 80 (68 chunks). Token counts were independently checked against source text. This verifies the API used by the UI; no browser interaction is claimed.

- Query tokens absent from the corpus: `edges`, `sliding`.
- Common query tokens: `the` occurs 380 times in source documents and in 66/68 chunks; `can` occurs 75 times in source documents and in 47/68 chunks; `of` occurs 68 times in source documents and in 46/68 chunks; `baking` occurs 78 times in source documents and in 38/68 chunks; `i` occurs 42 times in source documents and in 27/68 chunks.

| Expected chunk ID | Query-token occurrences inside this chunk |
|---|---|
| `8d9155c942e2::chunk_0001` | `the`: 8, `pastry`: 1, `pie`: 8, `how`: 1, `can`: 1 |
| `8d9155c942e2::chunk_0003` | `the`: 12, `of`: 1, `my`: 1, `pastry`: 2, `down`: 2, `pie`: 2, `can`: 1 |
| `8d9155c942e2::chunk_0004` | `the`: 13, `pastry`: 2, `keep`: 1, `down`: 2, `pie`: 2, `during`: 1, `baking`: 2, `can`: 1, `i`: 1 |

| Retrieval rank | Query-token occurrences inside the retrieved chunk |
|---:|---|
| 1 | `the`: 12, `of`: 1, `my`: 1, `pastry`: 2, `down`: 2, `pie`: 2, `can`: 1 |
| 2 | `the`: 6, `of`: 1, `my`: 1, `pastry`: 1, `pie`: 4, `baking`: 2, `can`: 1, `prevent`: 2, `this`: 1 |
| 3 | `the`: 1, `pie`: 1, `blind`: 1, `baking`: 2, `can`: 1, `this`: 1 |
| 4 | `the`: 10, `of`: 2, `pastry`: 1, `pie`: 5, `blind`: 1, `baking`: 5, `can`: 1, `this`: 2 |
| 5 | `the`: 10, `of`: 1, `pastry`: 1, `pie`: 5, `baking`: 1, `how`: 1, `can`: 3 |

The exact query words `edges` and `sliding` do not occur in the corpus. Relevant chunks use other wording about shrinkage, slumping, and gravity. Common terms such as `baking` occur across many chunks, including less useful soggy-crust passages. This supports vocabulary mismatch as a plausible contributor, while the ranking and incomplete labeled evidence remain the verified findings.

To reproduce visually: open Words → select this corpus → set the chunk size/overlap above → Question mode → select this question → Analyze. Word counts and matching chunks should agree with these observations.
