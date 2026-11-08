# 문항 ID로 모든 결과 찾기

**먼저 [전체 265문항 수식 읽기 화면](../03_gemini/report.html)을 연다.** 이 문서는 Gemini 비교 대상 80문항의 근거 연결이다. 학습 문항은 읽기 화면에서 검색하며 ‘생성 실험 대상 아님’으로 표시된다. 학습 문항에 누락 응답이 있다는 뜻이 아니다.

읽기 화면에서 ID를 검색하고 조건별 정오답·답변 변화 필터로 관심 문항을 고른 뒤, 아래의 원본 문제·해설·A/B/C 요청·회귀·군집 링크로 근거를 확인한다. 원문을 여러 번 복사하지 않고 고정 ID로 연결했다. 군집 번호는 임의 번호이며 서로 다른 실험의 같은 번호가 같은 그룹을 뜻하지 않는다.

[군집 성공·실패 관찰](../01_clustering/analysis.md) · [회귀 성공·실패 관찰](../02_regression/analysis.md) · [Gemini 정오답 변화](../03_gemini/changed_questions.csv)

## diff_1_005

10 미적분1 / 01 함수의 극한 / 03 극한식의 해석 / 04 해석4 (함수 구하기. 인수정리)

[읽기 화면](../03_gemini/report.html#diff_1_005) · [원본 문제](../../../data/processed/problems/diff_1_005.txt) · [원본 해설](../../../data/processed/solutions/diff_1_005.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_005.txt)

출처: 2026년 교육청 고3공통 10월 > 9 [4점] · 원본 번호 5 · 현재 번호 5

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|792|[A 요청](../03_gemini/prompt_audit/requests/diff_1_005/A.json)|
|B 예측 상위20토큰|⑤|정답|1,202|[B 요청](../03_gemini/prompt_audit/requests/diff_1_005/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|1,260|[C 요청](../03_gemini/prompt_audit/requests/diff_1_005/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_005)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_005` 검색.

회귀: 음수 보정 MSE 5.080, 코사인 0.896, 상위20 공통 토큰 17/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|6|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|23|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|1|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|65|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|29|False|

## diff_1_011

10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)

[읽기 화면](../03_gemini/report.html#diff_1_011) · [원본 문제](../../../data/processed/problems/diff_1_011.txt) · [원본 해설](../../../data/processed/solutions/diff_1_011.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_011.txt)

출처: 2025년(2026학년도) 평가원 고3공통 11월 > 공통범위 > 4 [3점] · 원본 번호 11 · 현재 번호 11

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|③|정답|534|[A 요청](../03_gemini/prompt_audit/requests/diff_1_011/A.json)|
|B 예측 상위20토큰|③|정답|691|[B 요청](../03_gemini/prompt_audit/requests/diff_1_011/B.json)|
|C 실제 해설 상위20토큰|③|정답|652|[C 요청](../03_gemini/prompt_audit/requests/diff_1_011/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_011)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_011` 검색.

회귀: 음수 보정 MSE 0.286, 코사인 0.960, 상위20 공통 토큰 19/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|7|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|0|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|7|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|7|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|7|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|7|True|

## diff_1_012

10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)

[읽기 화면](../03_gemini/report.html#diff_1_012) · [원본 문제](../../../data/processed/problems/diff_1_012.txt) · [원본 해설](../../../data/processed/solutions/diff_1_012.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_012.txt)

출처: 2026년 교육청 고3공통 3월 > 공통범위 > 4 [3점] · 원본 번호 12 · 현재 번호 12

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|②|정답|536|[A 요청](../03_gemini/prompt_audit/requests/diff_1_012/A.json)|
|B 예측 상위20토큰|②|정답|686|[B 요청](../03_gemini/prompt_audit/requests/diff_1_012/B.json)|
|C 실제 해설 상위20토큰|②|정답|642|[C 요청](../03_gemini/prompt_audit/requests/diff_1_012/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_012)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_012` 검색.

회귀: 음수 보정 MSE 0.339, 코사인 0.929, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|7|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|0|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|7|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|7|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|7|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|7|True|

## diff_1_014

10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)

[읽기 화면](../03_gemini/report.html#diff_1_014) · [원본 문제](../../../data/processed/problems/diff_1_014.txt) · [원본 해설](../../../data/processed/solutions/diff_1_014.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_014.txt)

출처: 2026년(2027학년도) 평가원 고3공통 9월 > 4 [3점] · 원본 번호 14 · 현재 번호 14

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|②|정답|440|[A 요청](../03_gemini/prompt_audit/requests/diff_1_014/A.json)|
|B 예측 상위20토큰|②|정답|651|[B 요청](../03_gemini/prompt_audit/requests/diff_1_014/B.json)|
|C 실제 해설 상위20토큰|②|정답|672|[C 요청](../03_gemini/prompt_audit/requests/diff_1_014/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_014)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_014` 검색.

회귀: 음수 보정 MSE 0.827, 코사인 0.906, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|7|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|0|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|7|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|7|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|7|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|7|True|

## diff_1_018

10 미적분1 / 03 미분계수와 도함수 / 01 미분계수 / 02 미분계수2 (평균변화율과 미분계수)

[읽기 화면](../03_gemini/report.html#diff_1_018) · [원본 문제](../../../data/processed/problems/diff_1_018.txt) · [원본 해설](../../../data/processed/solutions/diff_1_018.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_018.txt)

출처: 2026년 교육청 고2공통 10월 > 24 [3점] · 원본 번호 18 · 현재 번호 18

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|3|정답|472|[A 요청](../03_gemini/prompt_audit/requests/diff_1_018/A.json)|
|B 예측 상위20토큰|3|정답|690|[B 요청](../03_gemini/prompt_audit/requests/diff_1_018/B.json)|
|C 실제 해설 상위20토큰|3|정답|649|[C 요청](../03_gemini/prompt_audit/requests/diff_1_018/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_018)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_018` 검색.

회귀: 음수 보정 MSE 1.838, 코사인 0.672, 상위20 공통 토큰 10/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|5|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|23|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|37|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|36|False|

## diff_1_022

10 미적분1 / 03 미분계수와 도함수 / 02 도함수의 정의와 미분법 공식 / 06 미분법 공식5 (곱의 미분법, 극한식의 해석)

[읽기 화면](../03_gemini/report.html#diff_1_022) · [원본 문제](../../../data/processed/problems/diff_1_022.txt) · [원본 해설](../../../data/processed/solutions/diff_1_022.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_022.txt)

출처: 2026년 교육청 고3공통 5월 > 공통범위 > 9 [4점] · 원본 번호 22 · 현재 번호 22

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|①|정답|632|[A 요청](../03_gemini/prompt_audit/requests/diff_1_022/A.json)|
|B 예측 상위20토큰|①|정답|878|[B 요청](../03_gemini/prompt_audit/requests/diff_1_022/B.json)|
|C 실제 해설 상위20토큰|①|정답|825|[C 요청](../03_gemini/prompt_audit/requests/diff_1_022/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_022)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_022` 검색.

회귀: 음수 보정 MSE 3.876, 코사인 0.908, 상위20 공통 토큰 15/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|3|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|6|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|9|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|1|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|54|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|29|False|

## diff_1_026

10 미적분1 / 04 접선의 방정식 / 01 접선의 방정식 / 01 접점1 (접선의 방정식)

[읽기 화면](../03_gemini/report.html#diff_1_026) · [원본 문제](../../../data/processed/problems/diff_1_026.txt) · [원본 해설](../../../data/processed/solutions/diff_1_026.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_026.txt)

출처: 2026년 교육청 고3 공통 07월 > 9 [4점] · 원본 번호 26 · 현재 번호 26

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|632|[A 요청](../03_gemini/prompt_audit/requests/diff_1_026/A.json)|
|B 예측 상위20토큰|⑤|정답|831|[B 요청](../03_gemini/prompt_audit/requests/diff_1_026/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|771|[C 요청](../03_gemini/prompt_audit/requests/diff_1_026/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_026)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_026` 검색.

회귀: 음수 보정 MSE 1.602, 코사인 0.849, 상위20 공통 토큰 17/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|0|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|20|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|27|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|27|False|

## diff_1_028

10 미적분1 / 04 접선의 방정식 / 01 접선의 방정식 / 07 곡선 밖의 점1 (접선의 방정식)

[읽기 화면](../03_gemini/report.html#diff_1_028) · [원본 문제](../../../data/processed/problems/diff_1_028.txt) · [원본 해설](../../../data/processed/solutions/diff_1_028.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_028.txt)

출처: 2027년(2028학년도) 평가원 고3공통 수능 예시 문항 > 11 [3점] · 원본 번호 28 · 현재 번호 28

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|①|정답|685|[A 요청](../03_gemini/prompt_audit/requests/diff_1_028/A.json)|
|B 예측 상위20토큰|①|정답|773|[B 요청](../03_gemini/prompt_audit/requests/diff_1_028/B.json)|
|C 실제 해설 상위20토큰|①|정답|782|[C 요청](../03_gemini/prompt_audit/requests/diff_1_028/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_028)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_028` 검색.

회귀: 음수 보정 MSE 1.016, 코사인 0.841, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|6|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|2|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|23|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|46|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|23|False|

## diff_1_030

10 미적분1 / 05 함수의 증가와 감소 / 02 함수의 극대와 극소 / 02 극대와 극소2 (삼차함수의 극대와 극소)

[읽기 화면](../03_gemini/report.html#diff_1_030) · [원본 문제](../../../data/processed/problems/diff_1_030.txt) · [원본 해설](../../../data/processed/solutions/diff_1_030.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_030.txt)

출처: 2026년(2027학년도) 평가원 고3 공통 6월 > 7 [3점] · 원본 번호 30 · 현재 번호 30

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|②|정답|488|[A 요청](../03_gemini/prompt_audit/requests/diff_1_030/A.json)|
|B 예측 상위20토큰|②|정답|711|[B 요청](../03_gemini/prompt_audit/requests/diff_1_030/B.json)|
|C 실제 해설 상위20토큰|②|정답|679|[C 요청](../03_gemini/prompt_audit/requests/diff_1_030/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_030)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_030` 검색.

회귀: 음수 보정 MSE 0.414, 코사인 0.950, 상위20 공통 토큰 18/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|5|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|5|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|37|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|37|True|

## diff_1_036

10 미적분1 / 05 함수의 증가와 감소 / 02 함수의 극대와 극소 / 02 극대와 극소2 (삼차함수의 극대와 극소)

[읽기 화면](../03_gemini/report.html#diff_1_036) · [원본 문제](../../../data/processed/problems/diff_1_036.txt) · [원본 해설](../../../data/processed/solutions/diff_1_036.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_036.txt)

출처: 2025년(2026학년도) 평가원 고3공통 11월 > 공통범위 > 9 [4점] · 원본 번호 36 · 현재 번호 36

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|④|정답|759|[A 요청](../03_gemini/prompt_audit/requests/diff_1_036/A.json)|
|B 예측 상위20토큰|④|정답|1,000|[B 요청](../03_gemini/prompt_audit/requests/diff_1_036/B.json)|
|C 실제 해설 상위20토큰|④|정답|956|[C 요청](../03_gemini/prompt_audit/requests/diff_1_036/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_036)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_036` 검색.

회귀: 음수 보정 MSE 8.231, 코사인 0.873, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|6|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|23|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|9|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|65|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|65|True|

## diff_1_038

10 미적분1 / 05 함수의 증가와 감소 / 02 함수의 극대와 극소 / 02 극대와 극소2 (삼차함수의 극대와 극소)

[읽기 화면](../03_gemini/report.html#diff_1_038) · [원본 문제](../../../data/processed/problems/diff_1_038.txt) · [원본 해설](../../../data/processed/solutions/diff_1_038.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_038.txt)

출처: 2025년 교육청 고3공통 10월 > 공통범위 > 19 [3점] · 원본 번호 38 · 현재 번호 38

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|11|정답|608|[A 요청](../03_gemini/prompt_audit/requests/diff_1_038/A.json)|
|B 예측 상위20토큰|11|정답|859|[B 요청](../03_gemini/prompt_audit/requests/diff_1_038/B.json)|
|C 실제 해설 상위20토큰|11|정답|784|[C 요청](../03_gemini/prompt_audit/requests/diff_1_038/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_038)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_038` 검색.

회귀: 음수 보정 MSE 1.322, 코사인 0.912, 상위20 공통 토큰 17/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|5|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|5|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|36|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|37|True|

## diff_1_039

10 미적분1 / 05 함수의 증가와 감소 / 04 함수의 최대와 최소 / 03 최대와 최소3 (Mm 조건 해석)

[읽기 화면](../03_gemini/report.html#diff_1_039) · [원본 문제](../../../data/processed/problems/diff_1_039.txt) · [원본 해설](../../../data/processed/solutions/diff_1_039.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_039.txt)

출처: 2026년 교육청 고3공통 3월 > 공통범위 > 9 [4점] · 원본 번호 39 · 현재 번호 39

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|③|정답|614|[A 요청](../03_gemini/prompt_audit/requests/diff_1_039/A.json)|
|B 예측 상위20토큰|③|정답|868|[B 요청](../03_gemini/prompt_audit/requests/diff_1_039/B.json)|
|C 실제 해설 상위20토큰|③|정답|814|[C 요청](../03_gemini/prompt_audit/requests/diff_1_039/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_039)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_039` 검색.

회귀: 음수 보정 MSE 3.058, 코사인 0.711, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|5|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|5|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|46|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|46|True|

## diff_1_041

10 미적분1 / 05 함수의 증가와 감소 / 04 함수의 최대와 최소 / 03 최대와 최소3 (Mm 조건 해석)

[읽기 화면](../03_gemini/report.html#diff_1_041) · [원본 문제](../../../data/processed/problems/diff_1_041.txt) · [원본 해설](../../../data/processed/solutions/diff_1_041.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_1_041.txt)

출처: 2026년 교육청 고3공통 10월 > 19 [3점] · 원본 번호 41 · 현재 번호 41

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|62|정답|961|[A 요청](../03_gemini/prompt_audit/requests/diff_1_041/A.json)|
|B 예측 상위20토큰|62|정답|1,034|[B 요청](../03_gemini/prompt_audit/requests/diff_1_041/B.json)|
|C 실제 해설 상위20토큰|62|정답|991|[C 요청](../03_gemini/prompt_audit/requests/diff_1_041/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_1_041)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_1_041` 검색.

회귀: 음수 보정 MSE 4.487, 코사인 0.808, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|5|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|5|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|37|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|37|False|

## diff_2_004

10 미적분1 / 01 함수의 극한 / 03 극한식의 해석 / 03 해석3 (함수 구하기. 차수 결정)

[읽기 화면](../03_gemini/report.html#diff_2_004) · [원본 문제](../../../data/processed/problems/diff_2_004.txt) · [원본 해설](../../../data/processed/solutions/diff_2_004.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_004.txt)

출처: 2023년 교육청 고2공통 9월 > 26 [4점] · 원본 번호 4 · 현재 번호 4

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|20|정답|1,118|[A 요청](../03_gemini/prompt_audit/requests/diff_2_004/A.json)|
|B 예측 상위20토큰|20|정답|968|[B 요청](../03_gemini/prompt_audit/requests/diff_2_004/B.json)|
|C 실제 해설 상위20토큰|20|정답|1,076|[C 요청](../03_gemini/prompt_audit/requests/diff_2_004/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_004)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_004` 검색.

회귀: 음수 보정 MSE 1.576, 코사인 0.945, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|3|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|6|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|23|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|1|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|64|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|29|True|

## diff_2_006

10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)

[읽기 화면](../03_gemini/report.html#diff_2_006) · [원본 문제](../../../data/processed/problems/diff_2_006.txt) · [원본 해설](../../../data/processed/solutions/diff_2_006.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_006.txt)

출처: 2023년(2024학년도) 평가원 고3공통 11월 > 공통범위 > 4 [3점] · 원본 번호 6 · 현재 번호 6

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|①|정답|534|[A 요청](../03_gemini/prompt_audit/requests/diff_2_006/A.json)|
|B 예측 상위20토큰|①|정답|678|[B 요청](../03_gemini/prompt_audit/requests/diff_2_006/B.json)|
|C 실제 해설 상위20토큰|①|정답|627|[C 요청](../03_gemini/prompt_audit/requests/diff_2_006/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_006)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_006` 검색.

회귀: 음수 보정 MSE 0.432, 코사인 0.869, 상위20 공통 토큰 17/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|6|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|0|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|14|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|14|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|14|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|14|True|

## diff_2_007

10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)

[읽기 화면](../03_gemini/report.html#diff_2_007) · [원본 문제](../../../data/processed/problems/diff_2_007.txt) · [원본 해설](../../../data/processed/solutions/diff_2_007.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_007.txt)

출처: 2024년(2025학년도) 평가원 고3공통 9월 > 공통범위 > 7 [3점] · 원본 번호 7 · 현재 번호 7

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|③|정답|521|[A 요청](../03_gemini/prompt_audit/requests/diff_2_007/A.json)|
|B 예측 상위20토큰|③|정답|758|[B 요청](../03_gemini/prompt_audit/requests/diff_2_007/B.json)|
|C 실제 해설 상위20토큰|③|정답|740|[C 요청](../03_gemini/prompt_audit/requests/diff_2_007/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_007)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_007` 검색.

회귀: 음수 보정 MSE 1.026, 코사인 0.820, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|6|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|0|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|14|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|14|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|14|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|14|True|

## diff_2_010

10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)

[읽기 화면](../03_gemini/report.html#diff_2_010) · [원본 문제](../../../data/processed/problems/diff_2_010.txt) · [원본 해설](../../../data/processed/solutions/diff_2_010.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_010.txt)

출처: 2024년(2025학년도) 평가원 고3공통 6월 > 공통범위 > 9 [4점] · 원본 번호 10 · 현재 번호 10

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|③|정답|669|[A 요청](../03_gemini/prompt_audit/requests/diff_2_010/A.json)|
|B 예측 상위20토큰|③|정답|884|[B 요청](../03_gemini/prompt_audit/requests/diff_2_010/B.json)|
|C 실제 해설 상위20토큰|③|정답|810|[C 요청](../03_gemini/prompt_audit/requests/diff_2_010/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_010)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_010` 검색.

회귀: 음수 보정 MSE 3.965, 코사인 0.918, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|6|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|1|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|14|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|1|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|27|False|

## diff_2_013

10 미적분1 / 03 미분계수와 도함수 / 01 미분계수 / 04 미분계수4 (극한식의 해석, 무한소로 갈때)

[읽기 화면](../03_gemini/report.html#diff_2_013) · [원본 문제](../../../data/processed/problems/diff_2_013.txt) · [원본 해설](../../../data/processed/solutions/diff_2_013.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_013.txt)

출처: 2024년 교육청 고3공통 5월 > 공통범위 > 4 [3점] · 원본 번호 13 · 현재 번호 13

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|③|정답|559|[A 요청](../03_gemini/prompt_audit/requests/diff_2_013/A.json)|
|B 예측 상위20토큰|③|정답|771|[B 요청](../03_gemini/prompt_audit/requests/diff_2_013/B.json)|
|C 실제 해설 상위20토큰|③|정답|750|[C 요청](../03_gemini/prompt_audit/requests/diff_2_013/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_013)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_013` 검색.

회귀: 음수 보정 MSE 0.980, 코사인 0.858, 상위20 공통 토큰 15/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|11|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|20|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|44|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|20|False|

## diff_2_014

10 미적분1 / 03 미분계수와 도함수 / 02 도함수의 정의와 미분법 공식 / 05 미분법 공식4 (곱의 미분법)

[읽기 화면](../03_gemini/report.html#diff_2_014) · [원본 문제](../../../data/processed/problems/diff_2_014.txt) · [원본 해설](../../../data/processed/solutions/diff_2_014.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_014.txt)

출처: 2023년 교육청 고2공통 11월 > 12 [3점] · 원본 번호 14 · 현재 번호 14

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|②|정답|532|[A 요청](../03_gemini/prompt_audit/requests/diff_2_014/A.json)|
|B 예측 상위20토큰|②|정답|740|[B 요청](../03_gemini/prompt_audit/requests/diff_2_014/B.json)|
|C 실제 해설 상위20토큰|②|정답|688|[C 요청](../03_gemini/prompt_audit/requests/diff_2_014/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_014)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_014` 검색.

회귀: 음수 보정 MSE 2.114, 코사인 0.762, 상위20 공통 토큰 13/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|3|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|6|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|9|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|9|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|54|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|54|True|

## diff_2_016

10 미적분1 / 03 미분계수와 도함수 / 02 도함수의 정의와 미분법 공식 / 05 미분법 공식4 (곱의 미분법)

[읽기 화면](../03_gemini/report.html#diff_2_016) · [원본 문제](../../../data/processed/problems/diff_2_016.txt) · [원본 해설](../../../data/processed/solutions/diff_2_016.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_016.txt)

출처: 2023년 교육청 고3공통 10월 > 공통범위 > 17 [3점] · 원본 번호 16 · 현재 번호 16

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|22|정답|483|[A 요청](../03_gemini/prompt_audit/requests/diff_2_016/A.json)|
|B 예측 상위20토큰|22|정답|773|[B 요청](../03_gemini/prompt_audit/requests/diff_2_016/B.json)|
|C 실제 해설 상위20토큰|22|정답|629|[C 요청](../03_gemini/prompt_audit/requests/diff_2_016/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_016)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_016` 검색.

회귀: 음수 보정 MSE 1.317, 코사인 0.878, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|3|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|6|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|9|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|9|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|63|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|63|True|

## diff_2_018

10 미적분1 / 03 미분계수와 도함수 / 04 미분가능성과 연속성 / 04 미분가능조건1 (구간정의함수)

[읽기 화면](../03_gemini/report.html#diff_2_018) · [원본 문제](../../../data/processed/problems/diff_2_018.txt) · [원본 해설](../../../data/processed/solutions/diff_2_018.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_018.txt)

출처: 2023년 교육청 고2공통 11월 > 6 [3점] · 원본 번호 18 · 현재 번호 18

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|③|정답|656|[A 요청](../03_gemini/prompt_audit/requests/diff_2_018/A.json)|
|B 예측 상위20토큰|③|정답|866|[B 요청](../03_gemini/prompt_audit/requests/diff_2_018/B.json)|
|C 실제 해설 상위20토큰|③|정답|828|[C 요청](../03_gemini/prompt_audit/requests/diff_2_018/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_018)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_018` 검색.

회귀: 음수 보정 MSE 4.486, 코사인 0.894, 상위20 공통 토큰 17/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|6|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|0|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|14|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|14|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|14|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|14|False|

## diff_2_020

10 미적분1 / 04 접선의 방정식 / 01 접선의 방정식 / 03 접점3 (해석)

[읽기 화면](../03_gemini/report.html#diff_2_020) · [원본 문제](../../../data/processed/problems/diff_2_020.txt) · [원본 해설](../../../data/processed/solutions/diff_2_020.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_020.txt)

출처: 2024년(2025학년도) 평가원 고3공통 6월 > 공통범위 > 11 [4점] · 원본 번호 20 · 현재 번호 20

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|831|[A 요청](../03_gemini/prompt_audit/requests/diff_2_020/A.json)|
|B 예측 상위20토큰|⑤|정답|1,033|[B 요청](../03_gemini/prompt_audit/requests/diff_2_020/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|995|[C 요청](../03_gemini/prompt_audit/requests/diff_2_020/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_020)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_020` 검색.

회귀: 음수 보정 MSE 4.071, 코사인 0.946, 상위20 공통 토큰 17/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|6|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|11|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|11|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|61|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|61|False|

## diff_2_023

10 미적분1 / 04 접선의 방정식 / 02 접선의 방정식의 활용 / 01 활용1 (접선과 교점의 관계)

[읽기 화면](../03_gemini/report.html#diff_2_023) · [원본 문제](../../../data/processed/problems/diff_2_023.txt) · [원본 해설](../../../data/processed/solutions/diff_2_023.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_023.txt)

출처: 2023년 교육청 고3공통 7월 > 공통범위 > 19 [3점] · 원본 번호 23 · 현재 번호 23

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|22|정답|739|[A 요청](../03_gemini/prompt_audit/requests/diff_2_023/A.json)|
|B 예측 상위20토큰|22|정답|897|[B 요청](../03_gemini/prompt_audit/requests/diff_2_023/B.json)|
|C 실제 해설 상위20토큰|22|정답|978|[C 요청](../03_gemini/prompt_audit/requests/diff_2_023/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_023)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_023` 검색.

회귀: 음수 보정 MSE 3.581, 코사인 0.784, 상위20 공통 토큰 13/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|0|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|15|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|24|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|68|True|

## diff_2_024

10 미적분1 / 04 접선의 방정식 / 02 접선의 방정식의 활용 / 05 활용5 (함수 구하기)

[읽기 화면](../03_gemini/report.html#diff_2_024) · [원본 문제](../../../data/processed/problems/diff_2_024.txt) · [원본 해설](../../../data/processed/solutions/diff_2_024.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_024.txt)

출처: 2023년(2024학년도) 평가원 고3공통 9월 > 공통범위 > 10 [4점] · 원본 번호 24 · 현재 번호 24

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|③|정답|908|[A 요청](../03_gemini/prompt_audit/requests/diff_2_024/A.json)|
|B 예측 상위20토큰|③|정답|1,099|[B 요청](../03_gemini/prompt_audit/requests/diff_2_024/B.json)|
|C 실제 해설 상위20토큰|③|정답|1,359|[C 요청](../03_gemini/prompt_audit/requests/diff_2_024/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_024)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_024` 검색.

회귀: 음수 보정 MSE 3.301, 코사인 0.805, 상위20 공통 토큰 13/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|11|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|11|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|44|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|44|False|

## diff_2_029

10 미적분1 / 05 함수의 증가와 감소 / 02 함수의 극대와 극소 / 02 극대와 극소2 (삼차함수의 극대와 극소)

[읽기 화면](../03_gemini/report.html#diff_2_029) · [원본 문제](../../../data/processed/problems/diff_2_029.txt) · [원본 해설](../../../data/processed/solutions/diff_2_029.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_029.txt)

출처: 2023년 교육청 고3공통 4월(5_10시행) > 공통범위 > 4 [3점] · 원본 번호 29 · 현재 번호 29

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|①|정답|432|[A 요청](../03_gemini/prompt_audit/requests/diff_2_029/A.json)|
|B 예측 상위20토큰|①|정답|618|[B 요청](../03_gemini/prompt_audit/requests/diff_2_029/B.json)|
|C 실제 해설 상위20토큰|①|정답|581|[C 요청](../03_gemini/prompt_audit/requests/diff_2_029/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_029)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_029` 검색.

회귀: 음수 보정 MSE 0.564, 코사인 0.852, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|2|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|5|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|46|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|46|False|

## diff_2_030

10 미적분1 / 05 함수의 증가와 감소 / 02 함수의 극대와 극소 / 02 극대와 극소2 (삼차함수의 극대와 극소)

[읽기 화면](../03_gemini/report.html#diff_2_030) · [원본 문제](../../../data/processed/problems/diff_2_030.txt) · [원본 해설](../../../data/processed/solutions/diff_2_030.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_030.txt)

출처: 2023년(2024학년도) 평가원 고3공통 6월 > 공통범위 > 18 [3점] · 원본 번호 30 · 현재 번호 30

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|6|정답|581|[A 요청](../03_gemini/prompt_audit/requests/diff_2_030/A.json)|
|B 예측 상위20토큰|6|정답|803|[B 요청](../03_gemini/prompt_audit/requests/diff_2_030/B.json)|
|C 실제 해설 상위20토큰|6|정답|778|[C 요청](../03_gemini/prompt_audit/requests/diff_2_030/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_030)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_030` 검색.

회귀: 음수 보정 MSE 1.302, 코사인 0.871, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|5|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|5|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|36|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|36|True|

## diff_2_031

10 미적분1 / 05 함수의 증가와 감소 / 02 함수의 극대와 극소 / 02 극대와 극소2 (삼차함수의 극대와 극소)

[읽기 화면](../03_gemini/report.html#diff_2_031) · [원본 문제](../../../data/processed/problems/diff_2_031.txt) · [원본 해설](../../../data/processed/solutions/diff_2_031.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_031.txt)

출처: 2024년 교육청 고3공통 7월 > 공통범위 > 7 [3점] · 원본 번호 31 · 현재 번호 31

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|②|정답|534|[A 요청](../03_gemini/prompt_audit/requests/diff_2_031/A.json)|
|B 예측 상위20토큰|②|정답|764|[B 요청](../03_gemini/prompt_audit/requests/diff_2_031/B.json)|
|C 실제 해설 상위20토큰|②|정답|753|[C 요청](../03_gemini/prompt_audit/requests/diff_2_031/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_031)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_031` 검색.

회귀: 음수 보정 MSE 0.804, 코사인 0.915, 상위20 공통 토큰 15/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|11|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|11|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|68|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|40|True|

## diff_2_036

10 미적분1 / 06 방부등식과 직선운동 / 01 방정식과 미분 / 01 방정식과 미분1 (삼차방정식의 근의 판별)

[읽기 화면](../03_gemini/report.html#diff_2_036) · [원본 문제](../../../data/processed/problems/diff_2_036.txt) · [원본 해설](../../../data/processed/solutions/diff_2_036.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_036.txt)

출처: 2024년(2025학년도) 평가원 고3공통 6월 > 공통범위 > 7 [3점] · 원본 번호 36 · 현재 번호 36

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|④|정답|577|[A 요청](../03_gemini/prompt_audit/requests/diff_2_036/A.json)|
|B 예측 상위20토큰|④|정답|797|[B 요청](../03_gemini/prompt_audit/requests/diff_2_036/B.json)|
|C 실제 해설 상위20토큰|④|정답|779|[C 요청](../03_gemini/prompt_audit/requests/diff_2_036/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_036)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_036` 검색.

회귀: 음수 보정 MSE 2.584, 코사인 0.556, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|11|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|20|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|68|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|20|False|

## diff_2_037

10 미적분1 / 06 방부등식과 직선운동 / 01 방정식과 미분 / 04 방정식과 미분4 (다항함수, 방정식의 동치변형)

[읽기 화면](../03_gemini/report.html#diff_2_037) · [원본 문제](../../../data/processed/problems/diff_2_037.txt) · [원본 해설](../../../data/processed/solutions/diff_2_037.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_037.txt)

출처: 2023년(2024학년도) 평가원 고3공통 6월 > 공통범위 > 8 [3점] · 원본 번호 37 · 현재 번호 37

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|③|정답|591|[A 요청](../03_gemini/prompt_audit/requests/diff_2_037/A.json)|
|B 예측 상위20토큰|③|정답|784|[B 요청](../03_gemini/prompt_audit/requests/diff_2_037/B.json)|
|C 실제 해설 상위20토큰|③|정답|758|[C 요청](../03_gemini/prompt_audit/requests/diff_2_037/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_037)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_037` 검색.

회귀: 음수 보정 MSE 1.703, 코사인 0.787, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|2|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|0|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|21|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|32|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|21|False|

## diff_2_040

10 미적분1 / 06 방부등식과 직선운동 / 03 속도, 가속도와 미분 / 02 속도와 가속도의 해석1 (주어진 위치함수)

[읽기 화면](../03_gemini/report.html#diff_2_040) · [원본 문제](../../../data/processed/problems/diff_2_040.txt) · [원본 해설](../../../data/processed/solutions/diff_2_040.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_040.txt)

출처: 2024년(2025학년도) 평가원 고3공통 9월 > 공통범위 > 11 [4점] · 원본 번호 40 · 현재 번호 40

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|①|정답|659|[A 요청](../03_gemini/prompt_audit/requests/diff_2_040/A.json)|
|B 예측 상위20토큰|①|정답|904|[B 요청](../03_gemini/prompt_audit/requests/diff_2_040/B.json)|
|C 실제 해설 상위20토큰|①|정답|793|[C 요청](../03_gemini/prompt_audit/requests/diff_2_040/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_040)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_040` 검색.

회귀: 음수 보정 MSE 7.599, 코사인 0.903, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|1|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|2|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|15|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|15|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|59|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|59|True|

## diff_2_041

10 미적분1 / 06 방부등식과 직선운동 / 03 속도, 가속도와 미분 / 05 속도와 가속도의 해석4 (운동방향)

[읽기 화면](../03_gemini/report.html#diff_2_041) · [원본 문제](../../../data/processed/problems/diff_2_041.txt) · [원본 해설](../../../data/processed/solutions/diff_2_041.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_2_041.txt)

출처: 2023년 교육청 고3공통 4월(5_10시행) > 공통범위 > 19 [3점] · 원본 번호 41 · 현재 번호 41

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|6|정답|739|[A 요청](../03_gemini/prompt_audit/requests/diff_2_041/A.json)|
|B 예측 상위20토큰|6|정답|1,010|[B 요청](../03_gemini/prompt_audit/requests/diff_2_041/B.json)|
|C 실제 해설 상위20토큰|6|정답|801|[C 요청](../03_gemini/prompt_audit/requests/diff_2_041/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_2_041)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_2_041` 검색.

회귀: 음수 보정 MSE 1.528, 코사인 0.929, 상위20 공통 토큰 15/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|2|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|0|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|15|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|35|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|69|True|

## diff_3_001

10 미적분1 / 01 함수의 극한 / 02 극한의 성질과 계산 / 07 부정형6 (함수의 극한의 대소 관계)

[읽기 화면](../03_gemini/report.html#diff_3_001) · [원본 문제](../../../data/processed/problems/diff_3_001.txt) · [원본 해설](../../../data/processed/solutions/diff_3_001.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_3_001.txt)

출처: 2022년 교육청 고2공통 11월 > 4 [3점] · 원본 번호 1 · 현재 번호 1

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|456|[A 요청](../03_gemini/prompt_audit/requests/diff_3_001/A.json)|
|B 예측 상위20토큰|⑤|정답|749|[B 요청](../03_gemini/prompt_audit/requests/diff_3_001/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|653|[C 요청](../03_gemini/prompt_audit/requests/diff_3_001/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_3_001)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_3_001` 검색.

회귀: 음수 보정 MSE 3.932, 코사인 0.848, 상위20 공통 토큰 15/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|11|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|20|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|68|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|61|False|

## diff_3_004

10 미적분1 / 01 함수의 극한 / 02 극한의 성질과 계산 / 08 부정형7 (부정형과 극한의 성질)

[읽기 화면](../03_gemini/report.html#diff_3_004) · [원본 문제](../../../data/processed/problems/diff_3_004.txt) · [원본 해설](../../../data/processed/solutions/diff_3_004.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_3_004.txt)

출처: 2022년 교육청 고2공통 9월 > 26 [4점] · 원본 번호 4 · 현재 번호 4

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|16|정답|878|[A 요청](../03_gemini/prompt_audit/requests/diff_3_004/A.json)|
|B 예측 상위20토큰|32|오답|841|[B 요청](../03_gemini/prompt_audit/requests/diff_3_004/B.json)|
|C 실제 해설 상위20토큰|32|오답|853|[C 요청](../03_gemini/prompt_audit/requests/diff_3_004/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_3_004)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_3_004` 검색.

회귀: 음수 보정 MSE 6.671, 코사인 0.899, 상위20 공통 토큰 15/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|6|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|1|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|1|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|61|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|61|False|

## diff_3_005

10 미적분1 / 01 함수의 극한 / 03 극한식의 해석 / 03 해석3 (함수 구하기. 차수 결정)

[읽기 화면](../03_gemini/report.html#diff_3_005) · [원본 문제](../../../data/processed/problems/diff_3_005.txt) · [원본 해설](../../../data/processed/solutions/diff_3_005.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_3_005.txt)

출처: 2021년 교육청 고2공통 9월 > 26 [4점] · 원본 번호 5 · 현재 번호 5

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|9|정답|701|[A 요청](../03_gemini/prompt_audit/requests/diff_3_005/A.json)|
|B 예측 상위20토큰|9|정답|1,022|[B 요청](../03_gemini/prompt_audit/requests/diff_3_005/B.json)|
|C 실제 해설 상위20토큰|9|정답|979|[C 요청](../03_gemini/prompt_audit/requests/diff_3_005/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_3_005)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_3_005` 검색.

회귀: 음수 보정 MSE 3.614, 코사인 0.958, 상위20 공통 토큰 19/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|6|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|23|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|1|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|61|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|1|False|

## diff_3_008

10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)

[읽기 화면](../03_gemini/report.html#diff_3_008) · [원본 문제](../../../data/processed/problems/diff_3_008.txt) · [원본 해설](../../../data/processed/solutions/diff_3_008.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_3_008.txt)

출처: 2021년(2022학년도) 평가원 고3공통 9월 > 공통범위 > 4 [3점] · 원본 번호 8 · 현재 번호 8

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|④|정답|466|[A 요청](../03_gemini/prompt_audit/requests/diff_3_008/A.json)|
|B 예측 상위20토큰|④|정답|637|[B 요청](../03_gemini/prompt_audit/requests/diff_3_008/B.json)|
|C 실제 해설 상위20토큰|④|정답|589|[C 요청](../03_gemini/prompt_audit/requests/diff_3_008/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_3_008)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_3_008` 검색.

회귀: 음수 보정 MSE 0.362, 코사인 0.949, 상위20 공통 토큰 17/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|7|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|0|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|7|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|7|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|7|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|7|True|

## diff_3_012

10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)

[읽기 화면](../03_gemini/report.html#diff_3_012) · [원본 문제](../../../data/processed/problems/diff_3_012.txt) · [원본 해설](../../../data/processed/solutions/diff_3_012.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_3_012.txt)

출처: 2021년 교육청 고3공통 3월 > 공통범위 > 6 [3점] · 원본 번호 12 · 현재 번호 12

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|749|[A 요청](../03_gemini/prompt_audit/requests/diff_3_012/A.json)|
|B 예측 상위20토큰|⑤|정답|913|[B 요청](../03_gemini/prompt_audit/requests/diff_3_012/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|917|[C 요청](../03_gemini/prompt_audit/requests/diff_3_012/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_3_012)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_3_012` 검색.

회귀: 음수 보정 MSE 2.131, 코사인 0.883, 상위20 공통 토큰 15/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|6|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|14|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|14|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|47|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|47|True|

## diff_3_022

10 미적분1 / 03 미분계수와 도함수 / 02 도함수의 정의와 미분법 공식 / 02 미분법 공식1 (공식과 미분계수)

[읽기 화면](../03_gemini/report.html#diff_3_022) · [원본 문제](../../../data/processed/problems/diff_3_022.txt) · [원본 해설](../../../data/processed/solutions/diff_3_022.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_3_022.txt)

출처: 2021년(2022학년도) 평가원 고3공통 9월 > 공통범위 > 19 [3점] · 원본 번호 22 · 현재 번호 21

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|11|정답|805|[A 요청](../03_gemini/prompt_audit/requests/diff_3_022/A.json)|
|B 예측 상위20토큰|11|정답|1,016|[B 요청](../03_gemini/prompt_audit/requests/diff_3_022/B.json)|
|C 실제 해설 상위20토큰|11|정답|943|[C 요청](../03_gemini/prompt_audit/requests/diff_3_022/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_3_022)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_3_022` 검색.

회귀: 음수 보정 MSE 8.325, 코사인 0.720, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|5|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|5|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|36|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|36|False|

## diff_3_028

10 미적분1 / 03 미분계수와 도함수 / 04 미분가능성과 연속성 / 04 미분가능조건1 (구간정의함수)

[읽기 화면](../03_gemini/report.html#diff_3_028) · [원본 문제](../../../data/processed/problems/diff_3_028.txt) · [원본 해설](../../../data/processed/solutions/diff_3_028.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_3_028.txt)

출처: 2021년 교육청 고2공통 11월 > 12 [3점] · 원본 번호 28 · 현재 번호 27

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|④|정답|591|[A 요청](../03_gemini/prompt_audit/requests/diff_3_028/A.json)|
|B 예측 상위20토큰|④|정답|840|[B 요청](../03_gemini/prompt_audit/requests/diff_3_028/B.json)|
|C 실제 해설 상위20토큰|④|정답|781|[C 요청](../03_gemini/prompt_audit/requests/diff_3_028/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_3_028)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_3_028` 검색.

회귀: 음수 보정 MSE 2.228, 코사인 0.920, 상위20 공통 토큰 17/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|7|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|0|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|7|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|7|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|7|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|7|False|

## diff_3_039

10 미적분1 / 05 함수의 증가와 감소 / 02 함수의 극대와 극소 / 02 극대와 극소2 (삼차함수의 극대와 극소)

[읽기 화면](../03_gemini/report.html#diff_3_039) · [원본 문제](../../../data/processed/problems/diff_3_039.txt) · [원본 해설](../../../data/processed/solutions/diff_3_039.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_3_039.txt)

출처: 2022년(2023학년도) 평가원 고3공통 9월 > 공통범위 > 6 [3점] · 원본 번호 39 · 현재 번호 38

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|498|[A 요청](../03_gemini/prompt_audit/requests/diff_3_039/A.json)|
|B 예측 상위20토큰|⑤|정답|709|[B 요청](../03_gemini/prompt_audit/requests/diff_3_039/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|676|[C 요청](../03_gemini/prompt_audit/requests/diff_3_039/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_3_039)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_3_039` 검색.

회귀: 음수 보정 MSE 1.058, 코사인 0.857, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|11|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|11|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|68|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|40|True|

## diff_3_044

10 미적분1 / 06 방부등식과 직선운동 / 01 방정식과 미분 / 02 방정식과 미분2 (삼차방정식의 실근의 범위)

[읽기 화면](../03_gemini/report.html#diff_3_044) · [원본 문제](../../../data/processed/problems/diff_3_044.txt) · [원본 해설](../../../data/processed/solutions/diff_3_044.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_3_044.txt)

출처: 2022년(2023학년도) 평가원 고3공통 11월 > 공통범위 > 19 [3점] · 원본 번호 44 · 현재 번호 43

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|7|정답|740|[A 요청](../03_gemini/prompt_audit/requests/diff_3_044/A.json)|
|B 예측 상위20토큰|7|정답|1,028|[B 요청](../03_gemini/prompt_audit/requests/diff_3_044/B.json)|
|C 실제 해설 상위20토큰|1|오답|969|[C 요청](../03_gemini/prompt_audit/requests/diff_3_044/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_3_044)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_3_044` 검색.

회귀: 음수 보정 MSE 9.273, 코사인 0.838, 상위20 공통 토큰 17/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|2|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|2|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|57|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|57|False|

## diff_3_048

10 미적분1 / 06 방부등식과 직선운동 / 02 부등식과 미분 / 01 부등식과 미분1 (모든 실수)

[읽기 화면](../03_gemini/report.html#diff_3_048) · [원본 문제](../../../data/processed/problems/diff_3_048.txt) · [원본 해설](../../../data/processed/solutions/diff_3_048.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_3_048.txt)

출처: 2022년 교육청 고3공통 3월 > 공통범위 > 19 [3점] · 원본 번호 48 · 현재 번호 47

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|32|정답|641|[A 요청](../03_gemini/prompt_audit/requests/diff_3_048/A.json)|
|B 예측 상위20토큰|32|정답|870|[B 요청](../03_gemini/prompt_audit/requests/diff_3_048/B.json)|
|C 실제 해설 상위20토큰|32|정답|790|[C 요청](../03_gemini/prompt_audit/requests/diff_3_048/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_3_048)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_3_048` 검색.

회귀: 음수 보정 MSE 0.874, 코사인 0.880, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|2|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|2|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|57|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|2|True|

## diff_3_049

10 미적분1 / 06 방부등식과 직선운동 / 02 부등식과 미분 / 03 부등식과 미분3 (부등식의 동치변형)

[읽기 화면](../03_gemini/report.html#diff_3_049) · [원본 문제](../../../data/processed/problems/diff_3_049.txt) · [원본 해설](../../../data/processed/solutions/diff_3_049.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/diff_3_049.txt)

출처: 2022년(2023학년도) 평가원 고3공통 6월 > 공통범위 > 9 [4점] · 원본 번호 49 · 현재 번호 48

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|670|[A 요청](../03_gemini/prompt_audit/requests/diff_3_049/A.json)|
|B 예측 상위20토큰|⑤|정답|859|[B 요청](../03_gemini/prompt_audit/requests/diff_3_049/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|757|[C 요청](../03_gemini/prompt_audit/requests/diff_3_049/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#diff_3_049)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `diff_3_049` 검색.

회귀: 음수 보정 MSE 1.691, 코사인 0.840, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|11|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|11|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|68|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|40|False|

## trig_1_004

09 대수 / 05 삼각함수의 정의 / 02 삼각함수의 정의 및 활용 / 06 정의6 (삼각함수 사이의 관계. 값 구하기)

[읽기 화면](../03_gemini/report.html#trig_1_004) · [원본 문제](../../../data/processed/problems/trig_1_004.txt) · [원본 해설](../../../data/processed/solutions/trig_1_004.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_004.txt)

출처: 2026년 교육청 고3공통 10월 > 6 [3점] · 원본 번호 4 · 현재 번호 4

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|①|정답|476|[A 요청](../03_gemini/prompt_audit/requests/trig_1_004/A.json)|
|B 예측 상위20토큰|①|정답|678|[B 요청](../03_gemini/prompt_audit/requests/trig_1_004/B.json)|
|C 실제 해설 상위20토큰|①|정답|652|[C 요청](../03_gemini/prompt_audit/requests/trig_1_004/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_004)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_004` 검색.

회귀: 음수 보정 MSE 0.904, 코사인 0.887, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|0|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|4|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|17|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|17|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|33|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|33|True|

## trig_1_007

09 대수 / 05 삼각함수의 정의 / 02 삼각함수의 정의 및 활용 / 06 정의6 (삼각함수 사이의 관계. 값 구하기)

[읽기 화면](../03_gemini/report.html#trig_1_007) · [원본 문제](../../../data/processed/problems/trig_1_007.txt) · [원본 해설](../../../data/processed/solutions/trig_1_007.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_007.txt)

출처: 2025년 교육청 고2공통 6월 > 7 [3점] · 원본 번호 7 · 현재 번호 7

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|①|정답|616|[A 요청](../03_gemini/prompt_audit/requests/trig_1_007/A.json)|
|B 예측 상위20토큰|①|정답|825|[B 요청](../03_gemini/prompt_audit/requests/trig_1_007/B.json)|
|C 실제 해설 상위20토큰|①|정답|791|[C 요청](../03_gemini/prompt_audit/requests/trig_1_007/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_007)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_007` 검색.

회귀: 음수 보정 MSE 0.409, 코사인 0.967, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|0|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|4|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|17|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|17|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|33|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|33|True|

## trig_1_009

09 대수 / 05 삼각함수의 정의 / 02 삼각함수의 정의 및 활용 / 06 정의6 (삼각함수 사이의 관계. 값 구하기)

[읽기 화면](../03_gemini/report.html#trig_1_009) · [원본 문제](../../../data/processed/problems/trig_1_009.txt) · [원본 해설](../../../data/processed/solutions/trig_1_009.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_009.txt)

출처: 2026년(2027학년도) 경찰대학 고3공통 7월 > 2 [3점] · 원본 번호 9 · 현재 번호 9

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|④|정답|923|[A 요청](../03_gemini/prompt_audit/requests/trig_1_009/A.json)|
|B 예측 상위20토큰|④|정답|1,073|[B 요청](../03_gemini/prompt_audit/requests/trig_1_009/B.json)|
|C 실제 해설 상위20토큰|④|정답|1,070|[C 요청](../03_gemini/prompt_audit/requests/trig_1_009/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_009)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_009` 검색.

회귀: 음수 보정 MSE 7.054, 코사인 0.916, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|0|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|2|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|17|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|21|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|39|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|21|False|

## trig_1_010

09 대수 / 05 삼각함수의 정의 / 02 삼각함수의 정의 및 활용 / 09 활용3 (삼각함수 사이의 관계)

[읽기 화면](../03_gemini/report.html#trig_1_010) · [원본 문제](../../../data/processed/problems/trig_1_010.txt) · [원본 해설](../../../data/processed/solutions/trig_1_010.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_010.txt)

출처: 2025년 교육청 고2공통 6월 > 13 [3점] · 원본 번호 10 · 현재 번호 10

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|②|오답|799|[A 요청](../03_gemini/prompt_audit/requests/trig_1_010/A.json)|
|B 예측 상위20토큰|②|오답|1,047|[B 요청](../03_gemini/prompt_audit/requests/trig_1_010/B.json)|
|C 실제 해설 상위20토큰|②|오답|1,005|[C 요청](../03_gemini/prompt_audit/requests/trig_1_010/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_010)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_010` 검색.

회귀: 음수 보정 MSE 5.999, 코사인 0.825, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|0|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|2|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|10|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|10|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|39|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|60|False|

## trig_1_011

09 대수 / 06 삼각함수의 그래프 / 01 삼각함수의 그래프 / 01 그래프1 (주기)

[읽기 화면](../03_gemini/report.html#trig_1_011) · [원본 문제](../../../data/processed/problems/trig_1_011.txt) · [원본 해설](../../../data/processed/solutions/trig_1_011.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_011.txt)

출처: 2025년 교육청 고2공통 6월 > 25 [3점] · 원본 번호 11 · 현재 번호 11

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|7|정답|564|[A 요청](../03_gemini/prompt_audit/requests/trig_1_011/A.json)|
|B 예측 상위20토큰|7|정답|816|[B 요청](../03_gemini/prompt_audit/requests/trig_1_011/B.json)|
|C 실제 해설 상위20토큰|7|정답|726|[C 요청](../03_gemini/prompt_audit/requests/trig_1_011/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_011)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_011` 검색.

회귀: 음수 보정 MSE 0.800, 코사인 0.895, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|6|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|2|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|1|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|37|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|65|False|

## trig_1_013

09 대수 / 06 삼각함수의 그래프 / 01 삼각함수의 그래프 / 04 그래프4 (표준형 그래프에서 Mm)

[읽기 화면](../03_gemini/report.html#trig_1_013) · [원본 문제](../../../data/processed/problems/trig_1_013.txt) · [원본 해설](../../../data/processed/solutions/trig_1_013.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_013.txt)

출처: 2024년 교육청 고3공통 5월 > 공통범위 > 8 [3점] · 원본 번호 13 · 현재 번호 13

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|671|[A 요청](../03_gemini/prompt_audit/requests/trig_1_013/A.json)|
|B 예측 상위20토큰|⑤|정답|893|[B 요청](../03_gemini/prompt_audit/requests/trig_1_013/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|727|[C 요청](../03_gemini/prompt_audit/requests/trig_1_013/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_013)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_013` 검색.

회귀: 음수 보정 MSE 1.001, 코사인 0.909, 상위20 공통 토큰 13/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|1|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|18|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|18|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|18|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|56|True|

## trig_1_018

09 대수 / 06 삼각함수의 그래프 / 01 삼각함수의 그래프 / 04 그래프4 (표준형 그래프에서 Mm)

[읽기 화면](../03_gemini/report.html#trig_1_018) · [원본 문제](../../../data/processed/problems/trig_1_018.txt) · [원본 해설](../../../data/processed/solutions/trig_1_018.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_018.txt)

출처: 2026년 교육청 고2 공통 06월 > 26 [4점] · 원본 번호 18 · 현재 번호 18

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|12|정답|767|[A 요청](../03_gemini/prompt_audit/requests/trig_1_018/A.json)|
|B 예측 상위20토큰|12|정답|951|[B 요청](../03_gemini/prompt_audit/requests/trig_1_018/B.json)|
|C 실제 해설 상위20토큰|12|정답|885|[C 요청](../03_gemini/prompt_audit/requests/trig_1_018/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_018)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_018` 검색.

회귀: 음수 보정 MSE 1.513, 코사인 0.756, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|1|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|3|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|5|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|37|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|65|False|

## trig_1_020

09 대수 / 06 삼각함수의 그래프 / 01 삼각함수의 그래프 / 04 그래프4 (표준형 그래프에서 Mm)

[읽기 화면](../03_gemini/report.html#trig_1_020) · [원본 문제](../../../data/processed/problems/trig_1_020.txt) · [원본 해설](../../../data/processed/solutions/trig_1_020.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_020.txt)

출처: 2026년 교육청 고2공통 9월 > 25 [3점] · 원본 번호 20 · 현재 번호 20

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|2|정답|550|[A 요청](../03_gemini/prompt_audit/requests/trig_1_020/A.json)|
|B 예측 상위20토큰|2|정답|817|[B 요청](../03_gemini/prompt_audit/requests/trig_1_020/B.json)|
|C 실제 해설 상위20토큰|2|정답|761|[C 요청](../03_gemini/prompt_audit/requests/trig_1_020/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_020)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_020` 검색.

회귀: 음수 보정 MSE 1.333, 코사인 0.742, 상위20 공통 토큰 13/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|1|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|2|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|18|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|67|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|16|False|

## trig_1_021

09 대수 / 06 삼각함수의 그래프 / 01 삼각함수의 그래프 / 04 그래프4 (표준형 그래프에서 Mm)

[읽기 화면](../03_gemini/report.html#trig_1_021) · [원본 문제](../../../data/processed/problems/trig_1_021.txt) · [원본 해설](../../../data/processed/solutions/trig_1_021.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_021.txt)

출처: 2026년 교육청 고3공통 10월 > 18 [3점] · 원본 번호 21 · 현재 번호 21

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|7|정답|616|[A 요청](../03_gemini/prompt_audit/requests/trig_1_021/A.json)|
|B 예측 상위20토큰|7|정답|802|[B 요청](../03_gemini/prompt_audit/requests/trig_1_021/B.json)|
|C 실제 해설 상위20토큰|7|정답|676|[C 요청](../03_gemini/prompt_audit/requests/trig_1_021/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_021)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_021` 검색.

회귀: 음수 보정 MSE 0.800, 코사인 0.832, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|1|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|5|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|6|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|37|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|6|False|

## trig_1_028

09 대수 / 06 삼각함수의 그래프 / 02 삼각함수의 그래프 활용 / 01 각 변형1 (각 변형 규칙)

[읽기 화면](../03_gemini/report.html#trig_1_028) · [원본 문제](../../../data/processed/problems/trig_1_028.txt) · [원본 해설](../../../data/processed/solutions/trig_1_028.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_028.txt)

출처: 2025년(2026학년도) 평가원 고3공통 6월 > 공통범위 > 8 [3점] · 원본 번호 28 · 현재 번호 28

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|522|[A 요청](../03_gemini/prompt_audit/requests/trig_1_028/A.json)|
|B 예측 상위20토큰|⑤|정답|754|[B 요청](../03_gemini/prompt_audit/requests/trig_1_028/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|740|[C 요청](../03_gemini/prompt_audit/requests/trig_1_028/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_028)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_028` 검색.

회귀: 음수 보정 MSE 0.454, 코사인 0.958, 상위20 공통 토큰 15/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|0|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|4|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|10|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|22|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|17|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|22|False|

## trig_1_032

09 대수 / 06 삼각함수의 그래프 / 02 삼각함수의 그래프 활용 / 01 각 변형1 (각 변형 규칙)

[읽기 화면](../03_gemini/report.html#trig_1_032) · [원본 문제](../../../data/processed/problems/trig_1_032.txt) · [원본 해설](../../../data/processed/solutions/trig_1_032.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_032.txt)

출처: 2025년(2026학년도) 평가원 고3공통 11월 > 공통범위 > 8 [3점] · 원본 번호 32 · 현재 번호 32

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|①|정답|567|[A 요청](../03_gemini/prompt_audit/requests/trig_1_032/A.json)|
|B 예측 상위20토큰|①|정답|744|[B 요청](../03_gemini/prompt_audit/requests/trig_1_032/B.json)|
|C 실제 해설 상위20토큰|①|정답|648|[C 요청](../03_gemini/prompt_audit/requests/trig_1_032/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_032)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_032` 검색.

회귀: 음수 보정 MSE 3.926, 코사인 0.912, 상위20 공통 토큰 17/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|0|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|4|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|10|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|22|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|17|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|33|False|

## trig_1_035

09 대수 / 06 삼각함수의 그래프 / 02 삼각함수의 그래프 활용 / 01 각 변형1 (각 변형 규칙)

[읽기 화면](../03_gemini/report.html#trig_1_035) · [원본 문제](../../../data/processed/problems/trig_1_035.txt) · [원본 해설](../../../data/processed/solutions/trig_1_035.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_035.txt)

출처: 2026년 교육청 고3 공통 07월 > 8 [3점] · 원본 번호 35 · 현재 번호 35

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|④|정답|499|[A 요청](../03_gemini/prompt_audit/requests/trig_1_035/A.json)|
|B 예측 상위20토큰|④|정답|748|[B 요청](../03_gemini/prompt_audit/requests/trig_1_035/B.json)|
|C 실제 해설 상위20토큰|④|정답|712|[C 요청](../03_gemini/prompt_audit/requests/trig_1_035/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_035)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_035` 검색.

회귀: 음수 보정 MSE 0.661, 코사인 0.910, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|0|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|4|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|17|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|22|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|17|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|22|False|

## trig_1_039

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 04 삼각방정식4 (대칭성과 실근)

[읽기 화면](../03_gemini/report.html#trig_1_039) · [원본 문제](../../../data/processed/problems/trig_1_039.txt) · [원본 해설](../../../data/processed/solutions/trig_1_039.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_039.txt)

출처: 2024년 교육청 고2공통 9월 > 8 [3점] · 원본 번호 39 · 현재 번호 39

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|④|정답|475|[A 요청](../03_gemini/prompt_audit/requests/trig_1_039/A.json)|
|B 예측 상위20토큰|④|정답|729|[B 요청](../03_gemini/prompt_audit/requests/trig_1_039/B.json)|
|C 실제 해설 상위20토큰|④|정답|621|[C 요청](../03_gemini/prompt_audit/requests/trig_1_039/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_039)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_039` 검색.

회귀: 음수 보정 MSE 0.963, 코사인 0.812, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|5|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|4|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|4|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|50|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|50|True|

## trig_1_042

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 04 삼각방정식4 (대칭성과 실근)

[읽기 화면](../03_gemini/report.html#trig_1_042) · [원본 문제](../../../data/processed/problems/trig_1_042.txt) · [원본 해설](../../../data/processed/solutions/trig_1_042.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_042.txt)

출처: 2025년 교육청 고2공통 10월 > 13 [3점] · 원본 번호 42 · 현재 번호 42

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|②|정답|640|[A 요청](../03_gemini/prompt_audit/requests/trig_1_042/A.json)|
|B 예측 상위20토큰|②|정답|883|[B 요청](../03_gemini/prompt_audit/requests/trig_1_042/B.json)|
|C 실제 해설 상위20토큰|②|정답|781|[C 요청](../03_gemini/prompt_audit/requests/trig_1_042/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_042)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_042` 검색.

회귀: 음수 보정 MSE 2.169, 코사인 0.857, 상위20 공통 토큰 13/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|2|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|18|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|21|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|18|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|21|False|

## trig_1_043

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 04 삼각방정식4 (대칭성과 실근)

[읽기 화면](../03_gemini/report.html#trig_1_043) · [원본 문제](../../../data/processed/problems/trig_1_043.txt) · [원본 해설](../../../data/processed/solutions/trig_1_043.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_043.txt)

출처: 2026년 교육청 고2공통 9월 > 27 [4점] · 원본 번호 43 · 현재 번호 43

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|4|정답|1,292|[A 요청](../03_gemini/prompt_audit/requests/trig_1_043/A.json)|
|B 예측 상위20토큰|4|정답|1,381|[B 요청](../03_gemini/prompt_audit/requests/trig_1_043/B.json)|
|C 실제 해설 상위20토큰|4|정답|1,331|[C 요청](../03_gemini/prompt_audit/requests/trig_1_043/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_043)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_043` 검색.

회귀: 음수 보정 MSE 4.023, 코사인 0.368, 상위20 공통 토큰 8/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|5|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|23|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|37|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|65|False|

## trig_1_046

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 06 삼각부등식1 (일차식꼴)

[읽기 화면](../03_gemini/report.html#trig_1_046) · [원본 문제](../../../data/processed/problems/trig_1_046.txt) · [원본 해설](../../../data/processed/solutions/trig_1_046.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_1_046.txt)

출처: 2024년 교육청 고2공통 9월 > 25 [3점] · 원본 번호 46 · 현재 번호 46

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|20|정답|514|[A 요청](../03_gemini/prompt_audit/requests/trig_1_046/A.json)|
|B 예측 상위20토큰|20|정답|728|[B 요청](../03_gemini/prompt_audit/requests/trig_1_046/B.json)|
|C 실제 해설 상위20토큰|9|오답|773|[C 요청](../03_gemini/prompt_audit/requests/trig_1_046/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_1_046)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_1_046` 검색.

회귀: 음수 보정 MSE 2.032, 코사인 0.877, 상위20 공통 토큰 11/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|5|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|4|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|0|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|0|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|0|False|

## trig_2_003

09 대수 / 05 삼각함수의 정의 / 02 삼각함수의 정의 및 활용 / 01 정의1 (삼각함수의 뜻)

[읽기 화면](../03_gemini/report.html#trig_2_003) · [원본 문제](../../../data/processed/problems/trig_2_003.txt) · [원본 해설](../../../data/processed/solutions/trig_2_003.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_2_003.txt)

출처: 2022년 교육청 고2공통 11월 > 13 [3점] · 원본 번호 3 · 현재 번호 3

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|②|정답|679|[A 요청](../03_gemini/prompt_audit/requests/trig_2_003/A.json)|
|B 예측 상위20토큰|②|정답|960|[B 요청](../03_gemini/prompt_audit/requests/trig_2_003/B.json)|
|C 실제 해설 상위20토큰|②|정답|891|[C 요청](../03_gemini/prompt_audit/requests/trig_2_003/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_2_003)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_2_003` 검색.

회귀: 음수 보정 MSE 2.815, 코사인 0.948, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|1|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|2|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|21|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|21|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|21|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|21|True|

## trig_2_007

09 대수 / 05 삼각함수의 정의 / 02 삼각함수의 정의 및 활용 / 06 정의6 (삼각함수 사이의 관계. 값 구하기)

[읽기 화면](../03_gemini/report.html#trig_2_007) · [원본 문제](../../../data/processed/problems/trig_2_007.txt) · [원본 해설](../../../data/processed/solutions/trig_2_007.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_2_007.txt)

출처: 2021년 교육청 고2공통 11월 > 16 [4점] · 원본 번호 7 · 현재 번호 7

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|699|[A 요청](../03_gemini/prompt_audit/requests/trig_2_007/A.json)|
|B 예측 상위20토큰|⑤|정답|902|[B 요청](../03_gemini/prompt_audit/requests/trig_2_007/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|815|[C 요청](../03_gemini/prompt_audit/requests/trig_2_007/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_2_007)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_2_007` 검색.

회귀: 음수 보정 MSE 0.501, 코사인 0.964, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|0|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|4|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|17|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|17|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|33|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|17|False|

## trig_2_014

09 대수 / 06 삼각함수의 그래프 / 01 삼각함수의 그래프 / 04 그래프4 (표준형 그래프에서 Mm)

[읽기 화면](../03_gemini/report.html#trig_2_014) · [원본 문제](../../../data/processed/problems/trig_2_014.txt) · [원본 해설](../../../data/processed/solutions/trig_2_014.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_2_014.txt)

출처: 2021년 교육청 고2공통 11월 > 11 [3점] · 원본 번호 14 · 현재 번호 14

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|①|정답|452|[A 요청](../03_gemini/prompt_audit/requests/trig_2_014/A.json)|
|B 예측 상위20토큰|①|정답|662|[B 요청](../03_gemini/prompt_audit/requests/trig_2_014/B.json)|
|C 실제 해설 상위20토큰|①|정답|645|[C 요청](../03_gemini/prompt_audit/requests/trig_2_014/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_2_014)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_2_014` 검색.

회귀: 음수 보정 MSE 0.432, 코사인 0.777, 상위20 공통 토큰 15/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|1|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|5|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|18|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|37|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|55|True|

## trig_2_016

09 대수 / 06 삼각함수의 그래프 / 02 삼각함수의 그래프 활용 / 01 각 변형1 (각 변형 규칙)

[읽기 화면](../03_gemini/report.html#trig_2_016) · [원본 문제](../../../data/processed/problems/trig_2_016.txt) · [원본 해설](../../../data/processed/solutions/trig_2_016.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_2_016.txt)

출처: 2022년(2023학년도) 평가원 고3공통 11월 > 공통범위 > 5 [3점] · 원본 번호 16 · 현재 번호 16

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|624|[A 요청](../03_gemini/prompt_audit/requests/trig_2_016/A.json)|
|B 예측 상위20토큰|⑤|정답|812|[B 요청](../03_gemini/prompt_audit/requests/trig_2_016/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|772|[C 요청](../03_gemini/prompt_audit/requests/trig_2_016/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_2_016)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_2_016` 검색.

회귀: 음수 보정 MSE 0.547, 코사인 0.968, 상위20 공통 토큰 18/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|0|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|4|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|22|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|22|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|22|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|22|False|

## trig_2_017

09 대수 / 06 삼각함수의 그래프 / 02 삼각함수의 그래프 활용 / 01 각 변형1 (각 변형 규칙)

[읽기 화면](../03_gemini/report.html#trig_2_017) · [원본 문제](../../../data/processed/problems/trig_2_017.txt) · [원본 해설](../../../data/processed/solutions/trig_2_017.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_2_017.txt)

출처: 2023년(2024학년도) 평가원 고3공통 11월 > 공통범위 > 3 [3점] · 원본 번호 17 · 현재 번호 17

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|②|정답|561|[A 요청](../03_gemini/prompt_audit/requests/trig_2_017/A.json)|
|B 예측 상위20토큰|②|정답|779|[B 요청](../03_gemini/prompt_audit/requests/trig_2_017/B.json)|
|C 실제 해설 상위20토큰|②|정답|735|[C 요청](../03_gemini/prompt_audit/requests/trig_2_017/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_2_017)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_2_017` 검색.

회귀: 음수 보정 MSE 0.300, 코사인 0.963, 상위20 공통 토큰 16/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|0|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|4|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|17|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|17|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|60|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|17|True|

## trig_2_022

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 02 삼각방정식2 (이차식꼴)

[읽기 화면](../03_gemini/report.html#trig_2_022) · [원본 문제](../../../data/processed/problems/trig_2_022.txt) · [원본 해설](../../../data/processed/solutions/trig_2_022.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_2_022.txt)

출처: 2021년 교육청 고3공통 4월 > 공통범위 > 11 [4점] · 원본 번호 22 · 현재 번호 22

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|①|오답|643|[A 요청](../03_gemini/prompt_audit/requests/trig_2_022/A.json)|
|B 예측 상위20토큰|③|정답|889|[B 요청](../03_gemini/prompt_audit/requests/trig_2_022/B.json)|
|C 실제 해설 상위20토큰|③|정답|787|[C 요청](../03_gemini/prompt_audit/requests/trig_2_022/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_2_022)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_2_022` 검색.

회귀: 음수 보정 MSE 0.456, 코사인 0.915, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|5|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|4|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|4|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|50|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|50|False|

## trig_2_024

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 04 삼각방정식4 (대칭성과 실근)

[읽기 화면](../03_gemini/report.html#trig_2_024) · [원본 문제](../../../data/processed/problems/trig_2_024.txt) · [원본 해설](../../../data/processed/solutions/trig_2_024.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_2_024.txt)

출처: 2021년(2022학년도) 사관학교 고3공통 7월 > 공통범위 > 17 [3점] · 원본 번호 24 · 현재 번호 24

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|12|정답|499|[A 요청](../03_gemini/prompt_audit/requests/trig_2_024/A.json)|
|B 예측 상위20토큰|12|정답|835|[B 요청](../03_gemini/prompt_audit/requests/trig_2_024/B.json)|
|C 실제 해설 상위20토큰|12|정답|758|[C 요청](../03_gemini/prompt_audit/requests/trig_2_024/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_2_024)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_2_024` 검색.

회귀: 음수 보정 MSE 2.398, 코사인 0.842, 상위20 공통 토큰 10/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|5|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|4|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|16|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|0|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|42|False|

## trig_2_025

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 04 삼각방정식4 (대칭성과 실근)

[읽기 화면](../03_gemini/report.html#trig_2_025) · [원본 문제](../../../data/processed/problems/trig_2_025.txt) · [원본 해설](../../../data/processed/solutions/trig_2_025.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_2_025.txt)

출처: 2022년 교육청 고2공통 11월 > 5 [3점] · 원본 번호 25 · 현재 번호 25

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|③|정답|496|[A 요청](../03_gemini/prompt_audit/requests/trig_2_025/A.json)|
|B 예측 상위20토큰|③|정답|705|[B 요청](../03_gemini/prompt_audit/requests/trig_2_025/B.json)|
|C 실제 해설 상위20토큰|③|정답|701|[C 요청](../03_gemini/prompt_audit/requests/trig_2_025/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_2_025)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_2_025` 검색.

회귀: 음수 보정 MSE 0.831, 코사인 0.888, 상위20 공통 토큰 11/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|5|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|18|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|16|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|50|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|50|True|

## trig_2_030

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 05 삼각방정식5 (실근의 개수)

[읽기 화면](../03_gemini/report.html#trig_2_030) · [원본 문제](../../../data/processed/problems/trig_2_030.txt) · [원본 해설](../../../data/processed/solutions/trig_2_030.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_2_030.txt)

출처: 2023년 교육청 고3공통 7월 > 공통범위 > 10 [4점] · 원본 번호 30 · 현재 번호 30

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|③|정답|581|[A 요청](../03_gemini/prompt_audit/requests/trig_2_030/A.json)|
|B 예측 상위20토큰|③|정답|826|[B 요청](../03_gemini/prompt_audit/requests/trig_2_030/B.json)|
|C 실제 해설 상위20토큰|③|정답|702|[C 요청](../03_gemini/prompt_audit/requests/trig_2_030/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_2_030)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_2_030` 검색.

회귀: 음수 보정 MSE 1.303, 코사인 0.641, 상위20 공통 토큰 8/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|3|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|4|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|21|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|4|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|68|False|

## trig_2_035

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 07 삼각부등식2 (이차식꼴)

[읽기 화면](../03_gemini/report.html#trig_2_035) · [원본 문제](../../../data/processed/problems/trig_2_035.txt) · [원본 해설](../../../data/processed/solutions/trig_2_035.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_2_035.txt)

출처: 2023년(2024학년도) 평가원 고3공통 11월 > 공통범위 > 19 [3점] · 원본 번호 35 · 현재 번호 35

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|32|정답|994|[A 요청](../03_gemini/prompt_audit/requests/trig_2_035/A.json)|
|B 예측 상위20토큰|32|정답|1,357|[B 요청](../03_gemini/prompt_audit/requests/trig_2_035/B.json)|
|C 실제 해설 상위20토큰|32|정답|1,154|[C 요청](../03_gemini/prompt_audit/requests/trig_2_035/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_2_035)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_2_035` 검색.

회귀: 음수 보정 MSE 47.426, 코사인 0.842, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|5|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|6|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|23|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|1|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|65|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|29|False|

## trig_3_002

09 대수 / 05 삼각함수의 정의 / 02 삼각함수의 정의 및 활용 / 09 활용3 (삼각함수 사이의 관계)

[읽기 화면](../03_gemini/report.html#trig_3_002) · [원본 문제](../../../data/processed/problems/trig_3_002.txt) · [원본 해설](../../../data/processed/solutions/trig_3_002.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_002.txt)

출처: 2020년 교육청 고2공통 11월 > 27 [4점] · 원본 번호 2 · 현재 번호 2

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|20|정답|642|[A 요청](../03_gemini/prompt_audit/requests/trig_3_002/A.json)|
|B 예측 상위20토큰|20|정답|797|[B 요청](../03_gemini/prompt_audit/requests/trig_3_002/B.json)|
|C 실제 해설 상위20토큰|20|정답|746|[C 요청](../03_gemini/prompt_audit/requests/trig_3_002/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_002)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_002` 검색.

회귀: 음수 보정 MSE 1.420, 코사인 0.740, 상위20 공통 토큰 11/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|2|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|24|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|51|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|25|False|

## trig_3_010

09 대수 / 06 삼각함수의 그래프 / 02 삼각함수의 그래프 활용 / 01 각 변형1 (각 변형 규칙)

[읽기 화면](../03_gemini/report.html#trig_3_010) · [원본 문제](../../../data/processed/problems/trig_3_010.txt) · [원본 해설](../../../data/processed/solutions/trig_3_010.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_010.txt)

출처: 2016년 교육청 고3이과 10월 > 2 [2점] · 원본 번호 10 · 현재 번호 10

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|307|[A 요청](../03_gemini/prompt_audit/requests/trig_3_010/A.json)|
|B 예측 상위20토큰|⑤|정답|512|[B 요청](../03_gemini/prompt_audit/requests/trig_3_010/B.json)|
|C 실제 해설 상위20토큰|⑤|정답|463|[C 요청](../03_gemini/prompt_audit/requests/trig_3_010/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_010)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_010` 검색.

회귀: 음수 보정 MSE 1.156, 코사인 0.882, 상위20 공통 토큰 15/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|0|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|4|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|10|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|17|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|39|True|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|60|True|

## trig_3_011

09 대수 / 06 삼각함수의 그래프 / 02 삼각함수의 그래프 활용 / 03 각 변형3 (각 변형 규칙의 활용)

[읽기 화면](../03_gemini/report.html#trig_3_011) · [원본 문제](../../../data/processed/problems/trig_3_011.txt) · [원본 해설](../../../data/processed/solutions/trig_3_011.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_011.txt)

출처: 2020년 교육청 고3이과 3월 > 26 [4점] · 원본 번호 11 · 현재 번호 11

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|80|정답|841|[A 요청](../03_gemini/prompt_audit/requests/trig_3_011/A.json)|
|B 예측 상위20토큰|80|정답|1,082|[B 요청](../03_gemini/prompt_audit/requests/trig_3_011/B.json)|
|C 실제 해설 상위20토큰|80|정답|992|[C 요청](../03_gemini/prompt_audit/requests/trig_3_011/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_011)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_011` 검색.

회귀: 음수 보정 MSE 3.302, 코사인 0.827, 상위20 공통 토큰 9/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|1|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|2|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|21|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|21|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|21|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|21|False|

## trig_3_014

09 대수 / 06 삼각함수의 그래프 / 02 삼각함수의 그래프 활용 / 06 활용3 (치환을 이용한 Mm)

[읽기 화면](../03_gemini/report.html#trig_3_014) · [원본 문제](../../../data/processed/problems/trig_3_014.txt) · [원본 해설](../../../data/processed/solutions/trig_3_014.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_014.txt)

출처: 2019년 교육청 고2문과 6월 > 27 [4점] · 원본 번호 14 · 현재 번호 14

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|6|정답|768|[A 요청](../03_gemini/prompt_audit/requests/trig_3_014/A.json)|
|B 예측 상위20토큰|6|정답|1,038|[B 요청](../03_gemini/prompt_audit/requests/trig_3_014/B.json)|
|C 실제 해설 상위20토큰|6|정답|917|[C 요청](../03_gemini/prompt_audit/requests/trig_3_014/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_014)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_014` 검색.

회귀: 음수 보정 MSE 5.781, 코사인 0.846, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|3|False|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|6|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|23|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|9|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|64|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|64|False|

## trig_3_015

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 01 삼각방정식1 (일차식꼴)

[읽기 화면](../03_gemini/report.html#trig_3_015) · [원본 문제](../../../data/processed/problems/trig_3_015.txt) · [원본 해설](../../../data/processed/solutions/trig_3_015.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_015.txt)

출처: 2017년(2018학년도) 평가원 고3이과 9월 > 6 [3점] · 원본 번호 15 · 현재 번호 15

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|③|정답|522|[A 요청](../03_gemini/prompt_audit/requests/trig_3_015/A.json)|
|B 예측 상위20토큰|③|정답|678|[B 요청](../03_gemini/prompt_audit/requests/trig_3_015/B.json)|
|C 실제 해설 상위20토큰|③|정답|616|[C 요청](../03_gemini/prompt_audit/requests/trig_3_015/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_015)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_015` 검색.

회귀: 음수 보정 MSE 0.690, 코사인 0.865, 상위20 공통 토큰 13/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|5|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|4|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|16|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|50|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|50|False|

## trig_3_017

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 02 삼각방정식2 (이차식꼴)

[읽기 화면](../03_gemini/report.html#trig_3_017) · [원본 문제](../../../data/processed/problems/trig_3_017.txt) · [원본 해설](../../../data/processed/solutions/trig_3_017.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_017.txt)

출처: 2019년(2020학년도) 평가원 고3이과 11월 > 7 [3점] · 원본 번호 17 · 현재 번호 17

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|②|정답|788|[A 요청](../03_gemini/prompt_audit/requests/trig_3_017/A.json)|
|B 예측 상위20토큰|②|정답|1,014|[B 요청](../03_gemini/prompt_audit/requests/trig_3_017/B.json)|
|C 실제 해설 상위20토큰|②|정답|911|[C 요청](../03_gemini/prompt_audit/requests/trig_3_017/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_017)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_017` 검색.

회귀: 음수 보정 MSE 0.885, 코사인 0.915, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|5|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|4|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|4|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|50|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|50|False|

## trig_3_021

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 03 삼각방정식3 (교점)

[읽기 화면](../03_gemini/report.html#trig_3_021) · [원본 문제](../../../data/processed/problems/trig_3_021.txt) · [원본 해설](../../../data/processed/solutions/trig_3_021.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_021.txt)

출처: 2020년 교육청 고3문과 10월 > 7 [3점] · 원본 번호 21 · 현재 번호 21

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|②|정답|506|[A 요청](../03_gemini/prompt_audit/requests/trig_3_021/A.json)|
|B 예측 상위20토큰|②|정답|682|[B 요청](../03_gemini/prompt_audit/requests/trig_3_021/B.json)|
|C 실제 해설 상위20토큰|②|정답|644|[C 요청](../03_gemini/prompt_audit/requests/trig_3_021/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_021)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_021` 검색.

회귀: 음수 보정 MSE 1.389, 코사인 0.870, 상위20 공통 토큰 12/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|5|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|18|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|16|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|50|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|50|False|

## trig_3_026

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 04 삼각방정식4 (대칭성과 실근)

[읽기 화면](../03_gemini/report.html#trig_3_026) · [원본 문제](../../../data/processed/problems/trig_3_026.txt) · [원본 해설](../../../data/processed/solutions/trig_3_026.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_026.txt)

출처: 2016년(2017학년도) 평가원 고3이과 11월 > 25 [3점] · 원본 번호 26 · 현재 번호 26

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|7|정답|484|[A 요청](../03_gemini/prompt_audit/requests/trig_3_026/A.json)|
|B 예측 상위20토큰|7|정답|768|[B 요청](../03_gemini/prompt_audit/requests/trig_3_026/B.json)|
|C 실제 해설 상위20토큰|7|정답|684|[C 요청](../03_gemini/prompt_audit/requests/trig_3_026/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_026)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_026` 검색.

회귀: 음수 보정 MSE 7.360, 코사인 0.719, 상위20 공통 토큰 13/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|2|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|5|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|57|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|42|False|

## trig_3_034

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 05 삼각방정식5 (실근의 개수)

[읽기 화면](../03_gemini/report.html#trig_3_034) · [원본 문제](../../../data/processed/problems/trig_3_034.txt) · [원본 해설](../../../data/processed/solutions/trig_3_034.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_034.txt)

출처: 2020년 교육청 고2공통 6월 > 15 [4점] · 원본 번호 34 · 현재 번호 34

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|⑤|정답|1,045|[A 요청](../03_gemini/prompt_audit/requests/trig_3_034/A.json)|
|B 예측 상위20토큰|②|오답|1,163|[B 요청](../03_gemini/prompt_audit/requests/trig_3_034/B.json)|
|C 실제 해설 상위20토큰|④|오답|1,153|[C 요청](../03_gemini/prompt_audit/requests/trig_3_034/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_034)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_034` 검색.

회귀: 음수 보정 MSE 1.772, 코사인 0.689, 상위20 공통 토큰 9/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|5|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|2|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|24|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|46|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|16|True|

## trig_3_035

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 05 삼각방정식5 (실근의 개수)

[읽기 화면](../03_gemini/report.html#trig_3_035) · [원본 문제](../../../data/processed/problems/trig_3_035.txt) · [원본 해설](../../../data/processed/solutions/trig_3_035.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_035.txt)

출처: 2016년 교육청 고3이과 4월 > 26 [4점] · 원본 번호 35 · 현재 번호 35

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|30|정답|922|[A 요청](../03_gemini/prompt_audit/requests/trig_3_035/A.json)|
|B 예측 상위20토큰|30|정답|1,003|[B 요청](../03_gemini/prompt_audit/requests/trig_3_035/B.json)|
|C 실제 해설 상위20토큰|30|정답|1,023|[C 요청](../03_gemini/prompt_audit/requests/trig_3_035/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_035)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_035` 검색.

회귀: 음수 보정 MSE 3.070, 코사인 0.666, 상위20 공통 토큰 11/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|1|False|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|2|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|7|False|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|2|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|2|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|57|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|57|False|

## trig_3_039

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 08 방부등식의 활용1 (이차함수의 활용)

[읽기 화면](../03_gemini/report.html#trig_3_039) · [원본 문제](../../../data/processed/problems/trig_3_039.txt) · [원본 해설](../../../data/processed/solutions/trig_3_039.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_039.txt)

출처: 2018년(2019학년도) 평가원 고3이과 11월 > 11 [3점] · 원본 번호 39 · 현재 번호 39

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|④|정답|756|[A 요청](../03_gemini/prompt_audit/requests/trig_3_039/A.json)|
|B 예측 상위20토큰|④|정답|952|[B 요청](../03_gemini/prompt_audit/requests/trig_3_039/B.json)|
|C 실제 해설 상위20토큰|④|정답|948|[C 요청](../03_gemini/prompt_audit/requests/trig_3_039/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_039)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_039` 검색.

회귀: 음수 보정 MSE 3.530, 코사인 0.806, 상위20 공통 토큰 13/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|0|False|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|5|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|18|True|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|16|True|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|42|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|42|False|

## trig_3_040

09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식 / 09 방부등식의 활용2 (부등식의 성립조건)

[읽기 화면](../03_gemini/report.html#trig_3_040) · [원본 문제](../../../data/processed/problems/trig_3_040.txt) · [원본 해설](../../../data/processed/solutions/trig_3_040.txt) · [출처·분류 포함 텍스트](../../../data/processed/annotated/trig_3_040.txt)

출처: 2020년 교육청 고2공통 9월 > 12 [3점] · 원본 번호 40 · 현재 번호 40

|조건|답|원본 정오|전체 토큰|실제 입력|
|---|---|---|---:|---|
|A 문제만|①|정답|509|[A 요청](../03_gemini/prompt_audit/requests/trig_3_040/A.json)|
|B 예측 상위20토큰|①|정답|825|[B 요청](../03_gemini/prompt_audit/requests/trig_3_040/B.json)|
|C 실제 해설 상위20토큰|①|정답|732|[C 요청](../03_gemini/prompt_audit/requests/trig_3_040/C.json)|

[수식이 표시되는 세 조건 읽기 화면](../03_gemini/report.html#trig_3_040)에서 문항 ID로 검색하거나 [응답 JSONL](../03_gemini/responses.jsonl)에서 `trig_3_040` 검색.

회귀: 음수 보정 MSE 4.126, 코사인 0.739, 상위20 공통 토큰 14/20. [벡터·토큰 전체](../02_regression/question_comparison.csv)와 [수치 벡터](../02_regression/vectors.json)에서 ID로 찾는다.

|군집 실험|배정 군집|학습 다수 라벨과 일치|
|---|---:|---|
|[curriculum_euclidean](../01_clustering/experiments/curriculum_euclidean/clusters.md)|1|True|
|[curriculum_spherical](../01_clustering/experiments/curriculum_spherical/clusters.md)|0|True|
|[unit_euclidean](../01_clustering/experiments/unit_euclidean/clusters.md)|4|True|
|[unit_spherical](../01_clustering/experiments/unit_spherical/clusters.md)|4|True|
|[subunit_euclidean](../01_clustering/experiments/subunit_euclidean/clusters.md)|10|False|
|[subunit_spherical](../01_clustering/experiments/subunit_spherical/clusters.md)|10|False|
|[type_euclidean](../01_clustering/experiments/type_euclidean/clusters.md)|10|False|
|[type_spherical](../01_clustering/experiments/type_spherical/clusters.md)|39|False|

