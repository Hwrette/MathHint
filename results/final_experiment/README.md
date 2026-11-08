# MathHint 최종 실험 결과

**실험 응답 확보 완료: 성공 240/240개 응답.**

1. **군집별 실제 문항:** [8개 실험의 문항 배정 CSV](01_clustering/cluster_members.csv), [실험별 군집 원문 링크](01_clustering/experiments/), [군집 분석](01_clustering/analysis.md).
2. **Gemini80문항 세 조건:** [정답·A/B/C답·정오·토큰 한 행 비교](03_gemini/question_comparison.csv), [변화 문항](03_gemini/changed_questions.csv), [실제 입력](03_gemini/prompt_audit/), [B/C 토큰 나란히 비교](03_gemini/prompt_audit/token_comparison.md), [원본 응답](03_gemini/responses.jsonl).
3. **회귀 자체의 성능:** [MSE·MAE·코사인](02_regression/summary.csv), [문항별 상위토큰·오차](02_regression/question_comparison.csv), [실제·원시·보정 벡터](02_regression/vectors.json), [회귀 분석](02_regression/analysis.md).
4. **통합 문항 찾기:** [80문항 ID별 연결](04_case_studies/questions.md), [사례 요약](04_case_studies/selected_cases.md).
5. **연구 전체 해석:** [최종 한국어 보고서](final_report.md).

## 표와 그림

[군집 지표표](01_clustering/summary.csv) · [군집 그림](01_clustering/figures/) · [회귀 그림](02_regression/figures/) · [Gemini 집계](03_gemini/summary.csv) · [토큰 합계·평균](03_gemini/token_summary.csv) · [Gemini 그림](03_gemini/figures/)

[전체 산출물 검증](validation.json) · [핵심 테스트 실행 로그](test_results.txt) · [독립 ML 수식 감사](independent_ml_audit.json)

API 오류·미완료·채점불가는 오답으로 합치지 않는다. 원본 정답표와 AI 보조 보정 점수는 별도로 표시한다. C는 실제 해설 정보를 제공한 오라클 진단이며 서비스 성능이나 보장된 상한이 아니다. 코사인 유사도는 정답률이 아니다.

## 재집계

저장된 결과로만 표·그림·보고서를 다시 만들 때 `python -m mathhint_analysis.AnalyzeThreeWay`를 실행한다. 이 명령은 Gemini를 호출하거나 모델을 다시 학습하지 않는다. 전체 설치·실험 명령은 [프로젝트 README](../../README.md)를 따른다.
