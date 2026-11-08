# 공부하면서 읽는 코드 안내

실행 파일의 상단 설정과 `main()`을 먼저 읽고, 그 안에서 호출하는 함수로 들어가면 된다. 파일마다 모든 문법을 한 번에 이해하려고 할 필요는 없다.

## 먼저 볼 세 파일

| 파일 | 먼저 이해할 부분 |
|---|---|
| [TorchRegression.py](../mathhint_learning/TorchRegression.py) | 입력 벡터 → 선형층 → 오차 → 역전파 → 가중치 갱신 |
| [TorchKMeans.py](../mathhint_learning/TorchKMeans.py) | 가까운 중심에 배정 → 묶음의 평균으로 중심 이동 |
| [TorchData.py](../mathhint_learning/TorchData.py) | JSON을 행렬로 읽고 같은 ID의 문제·해설을 연결 |

회귀 파일에서 `EPOCHS`, `LEARNING_RATE`를 바꿔 볼 수 있다. 군집 파일에서는 `N_CLUSTERS`를 바꾼다. `SEED`는 초기값을 재현하기 위한 난수 설정이다.

학습 자료의 `X`는 문제 벡터, `Y`는 원본 정답·해설 벡터다. 한 행은 문항 하나이고 한 열은 어휘 하나다. 현재 학습 행렬은 문제 185×346, 해설 185×431이다. 테스트 행렬은 각각 80행이다.

회귀 학습 함수는 학습 X·Y만 받는다. 테스트 자료는 학습을 마친 뒤 평가할 때 사용한다. 저장된 185/80 분할을 함수 안에서 다시 나누지 않는다.

## 프로젝트 전체 흐름

```text
HML 원본
  → 문항·분류·원본 해설 추출
  → ID를 유지한 학습/테스트 분할
  → 학습 전용 어휘와 빈도 벡터
  → 회귀 학습 / 군집 학습
  → 예측 상위 토큰 + 문제로 Gemini 입력 준비
  → 기본 풀이와 가이드 풀이 생성
  → 정답·토큰·풀이 검토를 비교
```

| 작업 | 읽을 파일 | 읽을 함수·내용 |
|---|---|---|
| 한 문제의 토큰 세기 | [BagOfWord.py](../mathhint_analysis/BagOfWord.py) | `split_math`, `count_tokens` |
| HML 문항 읽기 | [hml.py](../mathhint_preprocess/hml.py) | `read_hml` |
| 학습·테스트와 벡터 만들기 | [PrepareDataset.py](../mathhint_analysis/PrepareDataset.py) | `main` → `read_records` → `prepare_records` |
| 두 모델 학습·그림 생성 | [RunTraining.py](../mathhint_learning/RunTraining.py) | `main` → `run` |
| 두 방식의 입력 준비 | [CompareGeneration.py](../mathhint_solver/CompareGeneration.py) | `main`, `prepare_plan`, `serialize_hint` |
| 실제 API 실행과 재개 | [RateLimitedComparison.py](../mathhint_solver/RateLimitedComparison.py) | `RUN_API`, `main`, 호출 간격 처리 |
| API 한 번의 요청과 저장 | [CompareGeneration.py](../mathhint_solver/CompareGeneration.py) | `generate_one`, `save_result` |
| 최종 정답 비교 | [AnswerEvaluation.py](../mathhint_solver/AnswerEvaluation.py) | `evaluate_answer` |
| 풀이 적절성 검토 자료 | [SolutionReview.py](../mathhint_solver/SolutionReview.py) | `main`, `summarize_reviews` |
| 통계와 PDF | [AnalyzeExperiment.py](../mathhint_analysis/AnalyzeExperiment.py) | `main`, `analyze` |

`GenerationReport.py`와 `BuildComparisonViewer.py`는 화면·표시 기능이다. 학습 계산을 이해하는 동안에는 나중에 읽어도 된다.

`equations.py`는 분수·첨자·괄호 등 한글 수식 문법을 읽는 별도 파서다. 이 파일의 분기들은 실제 원본 문법을 처리하므로 실행 옵션이나 반복 검사와 성격이 다르다.

## 파일과 JSON이 연결되는 방법

문항 ID가 `diff_3_017`이면 다음 위치에서 같은 문제를 찾을 수 있다.

```text
data/processed/annotated/diff_3_017.txt
data/processed/problems/diff_3_017.txt
data/processed/solutions/diff_3_017.txt
metadata.json의 records[].id
splits/train.json 또는 test.json
벡터 JSON의 documents[].id
```

이 ID는 삭제 전 원래 번호다. 현재 HML에서 몇 번으로 보이는지는 메타데이터의 `current_number`에 따로 저장한다.

- `annotated`: 단원·유형·출처와 문제·원본 정답해설을 사람이 확인.
- `problems`, `solutions`: 각각의 본문만 벡터화.
- `vocabulary.json`: 벡터 열의 뜻과 순서.
- `train_vectors.json`, `test_vectors.json`: 같은 어휘 순서의 문항별 횟수.
- `metadata.json`: 분류 평가와 출처 확인. 빈도 벡터나 Gemini 입력에 넣지 않는다.

공통 어휘는 학습에서만 만든다. 테스트에 처음 나온 단어가 있어도 어휘를 늘리지 않는다. 이 규칙을 지켜야 테스트의 정보를 미리 학습에 쓰지 않게 된다.

## 서로 다른 세 평가

1. **회귀 성능:** 예측한 해설 벡터와 원본 해설 벡터의 오차. MSE·MAE는 작을수록 좋고 코사인 유사도는 클수록 좋다.
2. **군집 성능:** 비슷한 벡터끼리 묶였는지, 그 군집이 실제 단원·유형과 맞는지 ARI·NMI 등으로 확인한다. 군집 번호 자체가 유형 번호는 아니다.
3. **Gemini 성능:** 생성한 최종 답의 정답률과 실제 API 사용 토큰을 비교한다. 답이 맞아도 과정이 틀릴 수 있어 풀이 검토를 별도로 남긴다.

AI 보조 검토와 사람 검토, 원본 정답표 점수와 근거를 둔 보조 보정 점수는 합치지 않는다. 보고서의 검증 코드는 이런 자료가 잘못 섞이는 것을 막는다.

## 토큰이라는 말의 두 뜻

`BagOfWord.py`의 토큰은 한국어 형태소와 LaTeX 명령·숫자·기호다. `kiwi:함수`, `latex:x`처럼 분석 출처를 붙이고 등장 횟수를 센다.

Gemini 토큰은 API가 사용량으로 돌려주는 모델의 입력·출력 단위다. 빈도 벡터의 숫자를 모두 더한 값과 같지 않다. API가 제공하지 않은 항목은 `null`이다.

## 설정을 바꾸고 실행하기

현재 파일들은 실행 옵션 대신 맨 위의 상수를 사용한다. 프로젝트 폴더에서 다음처럼 실행한다.

```bash
python -m mathhint_learning.TorchRegression
python -m mathhint_analysis.PrepareDataset
```

데이터는 이미 준비되어 있으므로 모델을 공부할 때 전처리를 다시 실행할 필요가 없다. `PrepareDataset`의 기존 결과 교체는 `OVERWRITE`로 정한다.

전체 실험을 새로 만들 때는 `RunTraining` → `CompareGeneration` → `RateLimitedComparison` 순서다. 비교 생성은 `RateLimitedComparison.RUN_API = True`일 때 실제 API를 사용한다. 모델·입력·설정을 바꾼 새 실험은 결과 폴더도 구분한다.

원본 HWPX 보조 기능과 선택적 LaTeX 컴파일 검사는 현재 HML 자료의 학습 흐름을 이해한 뒤 살펴봐도 된다.
