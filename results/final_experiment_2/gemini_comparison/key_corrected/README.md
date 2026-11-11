# Reviewed-key corrected Gemini scores

원본 HML·메타데이터·API 응답·원본 자동채점은 변경하지 않았다. 검증된 단 하나의 정답 오류 trig_1_010만 ④ → ②(9/5)로 바로잡아 별도 결과에 반영한다.

|범위|조건|채점 가능|기존 정답|정정 정답|정정 정답률|
|---|---|---:|---:|---:|---:|
|test|A|80|78|79|98.75%|
|test|B|80|78|79|98.75%|
|test|C|80|78|79|98.75%|
|test|D|80|78|79|98.75%|

정정되지 않은 나머지 264문항은 기존 답안을 유지한 것으로, 모든 풀이를 독립적으로 증명한 것은 아니다. 미완료 API 응답은 오답으로 세지 않는다.

[문항별 원본·보정 판정](question_comparison.csv) · [정정 요약](summary.csv) · [McNemar 대응검정](paired_comparison.csv) · [출처·무결성 기록](audit.json)

재생성(새 Gemini API 호출 없음): python -m mathhint_analysis.VerifiedAnswerKey
