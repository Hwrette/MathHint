# Reviewed-key corrected Gemini scores

Source data, original saved scores, response logs and prompt hashes remain immutable.
Verified key correction: trig_1_010 changes from ④ to ② (9/5).
Independently verified wrong final answer: full265/trig_1_044/B produced 12, correct 13/③; original parser abstained, corrected score is wrong.
Other rows retain the existing original key; this is not independent proof for every solution.

|Split|Condition|Original graded|Corrected graded|Original correct|Corrected correct|Corrected accuracy|
|---|---|---:|---:|---:|---:|---:|
|all265|A|265|265|258|259|97.74%|
|all265|B|264|265|258|259|97.74%|
|all265|C|265|265|259|260|98.11%|
|all265|D|265|265|257|258|97.36%|
|train|A|185|185|180|180|97.30%|
|train|B|184|185|180|180|97.30%|
|train|C|185|185|181|181|97.84%|
|train|D|185|185|179|179|96.76%|
|test|A|80|80|78|79|98.75%|
|test|B|80|80|78|79|98.75%|
|test|C|80|80|78|79|98.75%|
|test|D|80|80|78|79|98.75%|

The full265 run includes 185 training (in-sample) and 80 test questions.
Pending requests are not counted as wrong. Partial completion is nonrandom.

Files: question_comparison.csv, summary.csv, paired_comparison.csv, audit.json.
Rebuild without API calls: python -m mathhint_analysis.VerifiedAnswerKey
