# 공부하면서 읽는 코드 안내

한 행은 문항 하나, 한 열은 어휘 하나다. 현재 학습 입력 `X`는185×346 문제 벡터이고 목표 `Y`는185×431 해설 벡터다. 테스트는 별도의80행이며 기존 분할을 다시 나누지 않는다.

실행 파일은 상단 설정→맨 아래 실행 진입점(`main()` 또는 `run()`)→호출 함수 순서로 읽는다. 실제 명령과 결과 안내는 [프로젝트 README](../README.md), 개별 문항은 [최종 결과](../results/final_experiment/README.md)를 따른다.

## 처음 볼 세 파일

| 파일 | 이해할 흐름 |
|---|---|
| [TorchData.py](../mathhint_learning/TorchData.py) | 고정 분할 JSON 읽기→ID·어휘·행 순서 확인→행렬 |
| [TorchRegression.py](../mathhint_learning/TorchRegression.py) | 문제 벡터→선형층→평균제곱오차→역전파→가중치 갱신 |
| [TorchKMeans.py](../mathhint_learning/TorchKMeans.py) | 중심에 배정→군집 중심 갱신→수렴 확인 |

회귀의 `train_regression`은 학습 X·Y만 받는다. 테스트 실제 해설은 평가 단계에만 사용한다. 손실이 감소했다는 사실과 테스트 벡터 예측이 좋다는 사실은 별개다. 실제 해설 빈도는 정수지만 예측값은 실수이며 MSE·MAE·코사인 평가 전에 반올림하지 않는다.

유클리드 K-means는 원시 횟수와 중심의 거리를 사용하고 중심을 산술평균으로 갱신한다. Spherical K-means는 입력과 중심을 L2 정규화하고 코사인 유사도로 배정한다. 중심 갱신 뒤에도 다시 정규화한다. 군집 번호는 임의 번호이므로 원본 유형 번호와 숫자 그대로 비교하지 않는다.

## 전체 흐름

```text
HML 원본 → 문항·분류·출처·원본 해설
  → 같은 ID를 유지한 학습185 / 테스트80
  → 학습 전용 어휘와 문제/해설 BoW
  → 군집화 비교 / 해설 벡터 회귀
  → A 문제만 / B 예측 상위토큰 / C 실제 해설 상위토큰
  → Gemini 답·토큰·풀이 검토 비교
```

| 역할 | 읽을 파일과 핵심 함수 |
|---|---|
| HML 문항 추출 | [hml.py](../mathhint_preprocess/hml.py)의 `read_hml` |
| 한글 수식→LaTeX | [equations.py](../mathhint_preprocess/equations.py)의 `convert_equation` |
| 한국어·수식 토큰화 | [BagOfWord.py](../mathhint_analysis/BagOfWord.py)의 `split_math`, `count_tokens` |
| 분할·학습 어휘·벡터 생성 | [PrepareDataset.py](../mathhint_analysis/PrepareDataset.py)의 `read_records`, `split_records`, `prepare_records` |
| 4단계×2방법 군집화 | [FinalClustering.py](../mathhint_learning/FinalClustering.py)의 `run`과 학습 집합 대표 라벨 계산 |
| 군집 안의 실제 문제 출력 | [ClusterReport.py](../mathhint_learning/ClusterReport.py) |
| 실제·예측 벡터 평가 | [VectorComparison.py](../mathhint_learning/VectorComparison.py)의 `vector_metrics`, `top_tokens`, `token_overlap` |
| A/B/C 입력·재사용·호출 | [ThreeWayGeneration.py](../mathhint_solver/ThreeWayGeneration.py)의 `prepare_plan`, `prepare`, `run_experiment` |
| API 요청·응답 저장 | [CompareGeneration.py](../mathhint_solver/CompareGeneration.py)의 `make_request`, `generate_one`, `save_result` |
| 호출 간격·재시도·할당량 중단 | [RateLimitedComparison.py](../mathhint_solver/RateLimitedComparison.py)의 `GlobalRateLimiter` |
| 실제 요청·응답 사후 감사 | [GenerationAudit.py](../mathhint_solver/GenerationAudit.py)의 `audit_generation` |
| 저장된 표·벡터 무결성 | [VerifyResults.py](../mathhint_analysis/VerifyResults.py)의 `verify` |
| 최종 답 평가 | [AnswerEvaluation.py](../mathhint_solver/AnswerEvaluation.py)의 `evaluate_answer` |
| 풀이 검토 근거 | [SolutionReview.py](../mathhint_solver/SolutionReview.py) |
| 통계와 최종 결과 생성 | [ExperimentMetrics.py](../mathhint_analysis/ExperimentMetrics.py), [AnalyzeThreeWay.py](../mathhint_analysis/AnalyzeThreeWay.py) |

각 모듈은 역할이 달라 별도 파일로 둔다. 수식 파서의 분기, 데이터 행 검사, API 재개·해시 검증은 실제 자료와 실험의 정확성을 지키는 기능이다.

## ID와 JSON의 연결

문항 `diff_3_017`을 고르면 다음이 같은 문제를 가리킨다.

```text
data/processed/annotated/diff_3_017.txt
data/processed/problems/diff_3_017.txt
data/processed/solutions/diff_3_017.txt
data/processed/metadata.json  → records[].id
data/processed/splits/*.json → 문항 ID 목록
data/vectors/*/*_vectors.json → documents[].id
results/final_experiment/ 각 CSV·JSON → id 열
```

이 ID는 삭제 전 원래 번호다. 현재 HML 번호는 `current_number`에 따로 남긴다. `annotated`에는 출처와 분류까지 있고 `problems`·`solutions`에는 각 본문만 있다. 메타데이터는 평가·확인용으로 사용하고 벡터 입력에서 제외한다.

`vocabulary.json`은 열의 뜻과 순서다. 문제와 해설은 서로 다른 어휘를 사용하고 각각 학습 자료에서만 만든다. 테스트에서 새 토큰이 나와도 열을 추가하지 않는다. 따라서 같은431차원 해설 벡터끼리 비교하고, 오라클 조건도 이 고정 어휘 안의 정보만 전달한다.

분류를 읽을 때 `curriculum`은 실제 과목이고 `subject`는 원본 자료군이다. 군집화에서는 과목/단원/세부단원/유형의 상위 경로까지 합친 라벨을 사용한다. 군집 수는 학습 집합의 실제 라벨 개수에서 계산한다.

## 세 가지 성능은 따로 읽기

1. **군집화:** ARI·NMI는 군집과 실제 분류의 일치도를 나타낸다. 점수와 함께 군집별 문항·라벨 구성을 직접 확인한다.
2. **회귀:** MSE·MAE는 벡터 오차이고 코사인은 방향의 유사도다. 코사인0.8을 정답률80%로 해석하지 않는다. 상위20토큰의 공통 개수도 함께 본다.
3. **Gemini:** 최종 답의 정답률과 API 토큰 사용량이다. 답이 맞아도 풀이가 틀릴 수 있으므로 풀이 검토를 분리한다. AI 검토·원본 정답표·사람 확정 판정도 구분한다.

BoW 토큰은 `kiwi:함수`, `latex:x`와 같은 형태소·수식 조각이다. API 토큰은 Gemini가 돌려주는 사용량 단위다. 두 숫자는 같지 않으며 API가 제공하지 않은 사용량은 `null`이다.

## 안전하게 다시 실행하기

데이터는 이미 준비되어 있다. 결과 확인에는 `FinalClustering`·`VectorComparison`·`AnalyzeThreeWay`를 사용하고, 학습 원리를 볼 때만 `TorchRegression`으로 새로 학습한다. `PrepareDataset`은 기본적으로 기존 결과를 덮어쓰지 않는다.

`python -m mathhint_solver.ThreeWayGeneration`은 입력 준비와 저장 응답 검증만 수행한다. 실제 API 실행은 README의 별도 명령을 사용한다. 기존 입력·설정·소스 해시를 보호하기 위해 실험 도중 소스의 `RUN_API`를 편집하지 않는다.

A는 문제만, B는 예측 해설 상위20토큰, C는 실제 해설 상위20토큰이다. C는 정답 해설 정보가 주어진 오라클 진단이므로 실제 예측 서비스와 같은 조건이 아니다. 완료된 요청은 해시가 일치할 때 재사용한다. 실험 상태는 [WORK_PROGRESS.md](WORK_PROGRESS.md)와 최종 결과 안내에서 확인한다.
