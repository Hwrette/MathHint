# Reviewed-key corrected Gemini scores

Source data, original saved scores, response logs and prompt hashes remain immutable.
Verified correction: trig_1_010 changes from ④ to ② (9/5).
Other rows retain the existing original key; this is not independent proof for every solution.

|Split|Condition|Gradable|Original correct|Corrected correct|Corrected accuracy|
|---|---|---:|---:|---:|---:|
|all265|A|265|258|259|97.74%|
|all265|B|228|223|224|98.25%|
|all265|C|129|127|128|99.22%|
|all265|D|128|126|127|99.22%|
|train|A|185|180|180|97.30%|
|train|B|148|145|145|97.97%|
|train|C|49|49|49|100.00%|
|train|D|48|48|48|100.00%|
|test|A|80|78|79|98.75%|
|test|B|80|78|79|98.75%|
|test|C|80|78|79|98.75%|
|test|D|80|78|79|98.75%|

The full265 run includes 185 training (in-sample) and 80 test questions.
Pending requests are not counted as wrong. Partial completion is nonrandom.

Files: question_comparison.csv, summary.csv, paired_comparison.csv, audit.json.
Rebuild without API calls: python -m mathhint_analysis.VerifiedAnswerKey
