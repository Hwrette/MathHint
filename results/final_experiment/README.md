# MathHint 최종 결과 · [수식 읽기 화면](03_gemini/report.html)

<!-- clustering-additions:start -->
**군집화 추가 결과:** [기존185/80 분리 실험과 전체265 탐색 실험 선택](01_clustering/README.md) → [전체265의 ARI·NMI 비교·문항·사례](01_clustering/full_dataset_265/README.md). 기존 테스트80 혼동행렬8개와 새 전체265 설명용 혼동행렬8개는 각각의 실험 README에서 연다. 전체265 점수를 테스트 일반화 성능으로 해석하지 않는다. 기존 회귀·Gemini·분리 실험의 수치는 그대로다.
<!-- clustering-additions:end -->

**전체 265문항을 ID로 검색한다.** 테스트 80문항은 A 문제만 / B 예측 해설 토큰 / C 실제 해설 토큰을 비교하고, 학습 185문항은 ‘생성 실험 대상 아님’으로 표시한다. 문제·선택지·풀이의 수식과 Markdown을 읽고, 정오답 변화 필터로 관심 문항을 찾을 수 있다.

**실험 응답 확보 완료: 성공 240/240개 응답.**

GitHub 파일 페이지는 HTML 소스를 보여주며 읽기 화면을 실행하지 않는다. 저장소 ZIP 전체를 압축 해제하거나 clone한 뒤, 이 안내와 같은 폴더의 `03_gemini/report.html`을 브라우저에서 연다. 화면만 보려면 `report.html`과 그 파일 기준 `../viewer_assets/`를 같은 상대 구조로 함께 보존해야 한다. HTML 하나만 내려받으면 수식·Markdown 표시 파일이 빠진다. 원문·CSV 링크까지 사용하려면 저장소 전체가 필요하다. 렌더러와 글꼴은 로컬에 포함되어 외부 인터넷 연결은 필요하지 않다.

## 처음 → 다음 → 근거

|순서|바로 열 자료|
|---|---|
|처음: 전체 흐름|[최종 한국어 보고서](final_report.md) · [군집 ARI·NMI](01_clustering/summary.csv) · [회귀 MSE·MAE·코사인](02_regression/summary.csv) · [Gemini 정답률](03_gemini/summary.csv) · [토큰 합계·평균](03_gemini/token_summary.csv)|
|다음: 관심 문항 선택|[수식 읽기 화면](03_gemini/report.html) · [80문항 A/B/C 한 행 비교](03_gemini/question_comparison.csv) · [정오답·답변 변화](03_gemini/changed_questions.csv) · [실제·예측 토큰과 오차](02_regression/question_comparison.csv) · [대표 사례](04_case_studies/selected_cases.md)|
|문제 하나의 전체 결과|[80문항 ID별 근거 연결](04_case_studies/questions.md) · [전체 문항 군집 배정 CSV](01_clustering/cluster_members.csv)|
|자세한 근거|[실제 A/B/C 요청 전문](03_gemini/prompt_audit/requests/) · [B/C 전송 토큰 비교](03_gemini/prompt_audit/token_comparison.md) · [응답 원문](03_gemini/responses.jsonl) · [실제·원시·보정 벡터](02_regression/vectors.json) · [데이터·모델 연결](experiment.json)|

## 8개 군집 실험의 실제 문항

군집 목록의 문항 ID를 누르면 수식 읽기 화면으로 연결된다. 학습/테스트 구분과 실제 과목·단원·세부단원·유형을 함께 확인한다.

|실제 분류 수준|유클리드 군집별 문제|코사인(구면) 군집별 문제|
|---|---|---|
|과목|[군집 목록](01_clustering/experiments/curriculum_euclidean/clusters.md)|[군집 목록](01_clustering/experiments/curriculum_spherical/clusters.md)|
|단원|[군집 목록](01_clustering/experiments/unit_euclidean/clusters.md)|[군집 목록](01_clustering/experiments/unit_spherical/clusters.md)|
|세부단원|[군집 목록](01_clustering/experiments/subunit_euclidean/clusters.md)|[군집 목록](01_clustering/experiments/subunit_spherical/clusters.md)|
|문제 유형|[군집 목록](01_clustering/experiments/type_euclidean/clusters.md)|[군집 목록](01_clustering/experiments/type_spherical/clusters.md)|

[군집 해석](01_clustering/analysis.md) · [회귀 해석](02_regression/analysis.md) · [Gemini 해석](03_gemini/analysis.md)

## 표·그림과 검증 기록

[군집 그림](01_clustering/figures/) · [회귀 그림](02_regression/figures/) · [Gemini 그림](03_gemini/figures/)

[전체 산출물 검증](validation.json) · [읽기 화면 브라우저 검증](reader_validation.json) · [핵심 테스트 로그](test_results.txt) · [독립 ML 수식 감사](independent_ml_audit.json)

API 오류·미완료·채점불가는 오답이나 0토큰으로 합치지 않는다. 원본 정답표와 AI 보조 보정 점수는 별도다. C는 실제 해설 정보를 제공한 오라클 진단이며 서비스 성능이나 보장된 상한이 아니다. 코사인 유사도는 정답률이 아니다.

## 화면과 안내 다시 만들기

`python -m mathhint_learning.RunExperiment view`는 저장된 결과만 읽어 화면·표·안내를 다시 만든다. 학습·모델 재추론·Gemini API 호출은 하지 않으며 보존된 원본 감사 기록을 다시 쓰지 않는다. 설치와 별도 평가·학습·API 준비 명령은 [프로젝트 README](../../README.md)를 따른다.
