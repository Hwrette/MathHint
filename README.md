# MathHint

HML 수학 문제를 문항별로 나누고, 빈도 벡터로 회귀·군집화를 학습한 뒤 Gemini 답변을 비교하는 탐구 프로젝트다.

현재 자료는 **미분 140문항 + 삼각함수 125문항 = 265문항**이다. 학습 **185개**, 테스트 **80개**, 세부 유형 **70개**다. 문제 어휘는 **346개**, 원본 정답·해설 어휘는 **431개**다.

## 코드를 읽는 방법

각 실행 파일은 **상단 설정 → 데이터 읽기 → 계산 → 평가 → 저장** 순서로 읽는다. 실행 옵션 대신 파일 위쪽의 경로·학습률·학습 횟수 등을 수정한다.

모델을 공부하려면 다음 두 파일부터 보면 된다. 데이터는 이미 준비되어 있어 다시 가공할 필요가 없다.

```bash
python -m mathhint_learning.TorchRegression
python -m mathhint_learning.TorchKMeans
```

- `TorchRegression.py`: 선형층, 오차 계산, 역전파와 가중치 갱신.
- `TorchKMeans.py`: 가까운 중심에 배정하고 군집 평균으로 중심을 옮기는 반복.
- `TorchData.py`: 같은 ID의 문제·해설을 읽고, 저장된 학습·테스트 분할을 확인.

자세한 읽기 순서는 [코드 안내](docs/code_guide_ko.md)에 정리했다.

## 설치와 API 키

Python 3.10 이상을 사용한다.

```bash
python -m pip install -e '.[analysis,learning,solver]'
```

`.env.example`을 프로젝트 루트의 `.env`로 복사해 `GEMINI_API_KEY`를 설정한다. 기존 환경변수가 있으면 그 값을 우선하며, `.env`는 Git에서 제외한다. 데이터 가공·모델 학습·보고서 생성에는 Gemini API가 필요하지 않다.

## 전체 작업 순서

실행 전 해당 파일 맨 위의 설정값을 확인한다. 아래 명령은 프로젝트 폴더에서 실행한다.

| 단계 | 실행할 모듈 | 주요 결과 |
|---|---|---|
| 1. HML 문항 분리·분할·벡터화 | `mathhint_analysis.PrepareDataset` | `data/processed/`, `data/vectors/` |
| 2. 두 모델 학습·시각화 | `mathhint_learning.RunTraining` | `outputs/model_comparison/training/` |
| 3. 두 조건의 생성 입력 준비 | `mathhint_solver.CompareGeneration` | `outputs/model_comparison/generation_top_tokens/` |
| 4. Gemini 답변 생성 | `mathhint_solver.RateLimitedComparison` | 같은 폴더의 문항별 응답·사용량 |
| 5. 풀이 적절성 검토 | `mathhint_solver.SolutionReview` | `outputs/model_comparison/solution_review/` |
| 6. 통계·흑백 PDF | `mathhint_analysis.AnalyzeExperiment` | `outputs/model_comparison/report_top_tokens/` |
| 7. 문항별 비교 화면 | `mathhint_analysis.BuildComparisonViewer` | 같은 보고서 폴더의 HTML |

예를 들어 두 모델의 학습과 그림을 함께 만들려면 다음을 실행한다.

```bash
python -m mathhint_learning.RunTraining
```

`RunTraining`은 학습용 두 파일의 함수를 재사용한다. 개별 모델을 실행하면 `outputs/regression/`, `outputs/kmeans/`에 저장하고, 전체 비교 실험은 `RunTraining`이 만든 `outputs/model_comparison/training/`을 사용한다.

`CompareGeneration`은 입력을 준비한다. 실제 API 실행은 `RateLimitedComparison.py`의 `RUN_API = True`로 정한 뒤 수행한다. 기본값은 `False`다. 한 문제만 풀어 보는 `GoogleAPI.py`는 직접 실행하면 API를 호출한다.

보고서로 이전 실험을 읽으려면 보고서 파일 상단의 `RUN_ROOT`를 그 실험 폴더로 바꾼다.

## 데이터와 문항 ID

```text
data/
├── raw/                  # 그림 문항을 제외한 HML 원본 6개
├── provenance/           # 원래 번호 대조표·삭제 내역·수식 전사 근거
├── processed/
│   ├── annotated/        # ID·단원·유형·출처 + 문제·원본 해설
│   ├── problems/         # 문제 본문만
│   ├── solutions/        # 원본 정답·해설만
│   ├── metadata.json     # 문항별 분류·출처·수식 기록
│   └── splits/           # train.json 185개 / test.json 80개
└── vectors/
    ├── problems/         # 문제 어휘와 학습·테스트 벡터
    └── solutions/        # 해설 어휘와 학습·테스트 벡터
```

`diff_3_017`은 미분 자료 3의 **삭제 전 원래 17번**이다. 현재 HML에서는 16번이지만 ID는 유지한다. 텍스트 파일명·분할 목록·메타데이터·벡터 행이 모두 이 ID로 연결된다. 그림 때문에 제외한 `diff_3_016`은 포함하지 않는다.

단원·유형·출처는 확인용 자료에 보존하고 벡터에는 넣지 않는다. 문제와 해설을 별도 벡터로 만들며, 각 어휘는 **학습 데이터에서만** 생성한다. 테스트는 같은 어휘 순서로 변환한다.

같은 출처·본문의 문항은 같은 집합으로 묶는다. 단원별 테스트 비율을 약 30%로 맞추고, 분리할 수 있는 유형은 양쪽에 포함한다. 한 문항뿐인 유형은 학습에 둔다. 분할 기준과 제약은 `splits/report.json`에 남긴다.

`PrepareDataset`의 `OVERWRITE` 기본값은 `False`다. 이미 있는 데이터를 다시 만들 때만 값을 바꾼다. 임시 폴더에서 완성한 뒤 결과를 함께 교체하므로 중간 실패 시 이전 결과를 복구한다.

## 실험 조건과 평가

- 회귀는 문제 벡터에서 원본 해설 벡터를 예측한다. MSE·MAE·코사인 유사도로 평가한다.
- K-means는 학습 자료로 중심을 만들고 테스트 문항을 배정한다. 실제 과목·단원·유형과 ARI·NMI 등을 비교한다.
- Gemini는 같은 문제·모델·생성 설정으로 기본 풀이와 회귀 가이드를 비교한다. 가이드는 예측 빈도가 높은 **상위 20개 토큰**이다.
- 실제 테스트 정답·해설·유형은 API 입력에 넣지 않는다.
- 정답 일치, 풀이의 수학적 적절성, 교과 범위는 별도로 평가한다. AI 보조 검토와 사람 검토도 구분한다.

문항별 폴더에는 실제 입력·시스템 지시·출력·원본 정답해설·토큰 사용량·채점 근거를 저장한다. API가 제공하지 않은 사용량은 `null`로 남긴다.

요청 시작 간격은 기본 5초이며, 429의 대기 시간과 503의 재시도 대기를 따른다. 성공한 응답은 재요청하지 않는다. 설정이나 입력이 달라지면 새 실험 폴더를 사용한다. 안전하게 중단하려면 생성 폴더에 `stop_requested` 파일을 만들고, 재개 전 제거한다.

## 상세 구현과 보조 도구

- `hml.py`, `equations.py`: 원본 구조와 수식 문법을 읽는다. 검증한 수식 전사 46건은 `data/provenance/latex_transcriptions.json`에 보존한다.
- `BagOfWord.py`: 한국어는 Kiwi, 수식은 LaTeX 명령·숫자·기호로 나눠 원시 횟수를 센다.
- `BuildFrequencyVectors.py`: 별도 TXT 폴더를 분석할 때 쓰는 보조 도구다. 현재 기본값은 저장된 학습 어휘를 재사용한다.
- `GenerationReport.py`: 답변 생성 결과의 CSV·HTML·그래프 표시를 맡는다.
- `AnswerEvaluation.py`: 명시적인 최종 정답을 읽어 원본 정답과 비교한다.
- HWPX 읽기와 `scripts/validate_latex.py`는 별도 보조 기능이다. 현재 HML 데이터 준비에는 사용하지 않는다.

수식 비교 화면은 선택 패키지 `latex2mathml`이 있으면 수식을 렌더링하고, 없으면 원문 LaTeX를 표시한다. 컴파일이나 수식 렌더링 성공 자체가 원본과의 수학적 동치를 증명하지는 않는다.

## 검사

```bash
python -m unittest discover -s tests -v
```

검사에서는 데이터 연결·학습/테스트 분리·모델 계산·응답 저장·집계 결과를 확인한다. 실제 Gemini 호출 없이 수행한다.
