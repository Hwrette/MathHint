# Reviewed-key corrected Gemini scores

Source data, original saved scores, response logs and prompt hashes remain immutable.
Verified correction: trig_1_010 changes from ④ to ② (9/5).
Other rows retain the existing original key; this is not independent proof for every solution.

|Split|Condition|Gradable|Original correct|Corrected correct|Corrected accuracy|
|---|---|---:|---:|---:|---:|
|all265|A|206|201|202|98.06%|
|all265|B|129|127|128|99.22%|
|all265|C|129|127|128|99.22%|
|all265|D|128|126|127|99.22%|
|train|A|126|123|123|97.62%|
|train|B|49|49|49|100.00%|
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
