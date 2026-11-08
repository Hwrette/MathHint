# MathHint

수학 문제를 BoW(단어 빈도) 벡터로 표현하고, K-means 군집화와 선형회귀가 Gemini의 풀이 생성에 제공할 수 있는 정보를 검증하는 고2 연구 프로젝트다. 새로운 모델을 추가하기보다 기존 방법의 성능과 한계를 비교한다.

결과를 읽으려면 **[최종 실험 안내](results/final_experiment/README.md)**부터 연다. 문제와 풀이를 수식으로 읽는 화면은 **[문항별 비교 HTML](results/final_experiment/03_gemini/report.html)**이다. 전체 265문항을 검색하고, 테스트 80문항의 A/B/C 응답과 원문을 비교할 수 있다.

GitHub의 HTML 파일 페이지는 소스 보기다. 저장소를 ZIP으로 내려받아 압축을 푼 뒤 `results/final_experiment/03_gemini/report.html`을 브라우저로 연다. 읽기 화면만 옮길 때도 `03_gemini/report.html`과 그 옆 상위 폴더의 `viewer_assets/`를 같은 상대 위치로 함께 옮겨야 한다. 수식·Markdown 스크립트와 글꼴을 포함하므로 인터넷 연결이 필요 없다. CSV·감사 원본 링크까지 보려면 저장소 전체를 유지한다.

- **군집별 실제 문항:** [문항 배정 CSV](results/final_experiment/01_clustering/cluster_members.csv), [실험별 군집 목록](results/final_experiment/01_clustering/experiments/).
- **Gemini 80문항의 A/B/C 비교:** [정답·생성 답·정오·토큰 비교 CSV](results/final_experiment/03_gemini/question_comparison.csv).
- **회귀 자체의 성능:** [MSE·MAE·코사인 비교](results/final_experiment/02_regression/summary.csv), [문항별 비교](results/final_experiment/02_regression/question_comparison.csv), [실제·예측 벡터](results/final_experiment/02_regression/vectors.json).
- **연구 전체와 개별 사례:** [최종 보고서](results/final_experiment/final_report.md), [문항 ID별 연결](results/final_experiment/04_case_studies/questions.md).

## 설치와 실행

Python 3.10 이상을 사용하며 프로젝트 루트에서 실행한다.

```bash
python -m pip install -e '.[analysis,learning,solver]'
```

API를 실행할 때만 `.env.example`을 `.env`로 복사하고 `GEMINI_API_KEY`를 설정한다. 기존 환경변수가 우선하며 `.env`는 Git에 포함하지 않는다. 데이터 준비·모델 검증·보고서 생성에는 API 키가 필요 없다.

| 목적 | 명령 | 실행 범위 |
|---|---|---|
| 기존 결과 읽기·화면 재생성 | `python -m mathhint_learning.RunExperiment view` | 저장된 결과만 집계. 재추론·재학습·API 호출 없음. 인수 생략도 `view` |
| 지정한 기존 모델 평가 | `python -m mathhint_learning.RunExperiment evaluate` | 선택한 체크포인트로 예측·평가. 재학습·API 호출 없음 |
| 새 실험 학습 | `python -m mathhint_learning.RunExperiment train` | 별도로 지정한 빈 실험 경로에 학습·예측·평가·보고서 저장. API 호출 없음 |
| Gemini 입력 준비·검증 | `python -m mathhint_learning.RunExperiment prepare` | 선택한 모델·예측으로 완성 요청을 만들고 검증. API 호출 없음 |
| Gemini 실제 호출 | `python -m mathhint_learning.RunExperiment generate` | **명시적으로 선택할 때만 외부 API 호출.** 동일한 완료 요청은 재사용 |
| 군집화 비교 | `python -m mathhint_learning.FinalClustering` | 선택한 실험의 `01_clustering/`. 같은 입력·설정의 완료 결과는 검증 후 재사용 |
| 최종 연구 산출물 무결성 | `python -m mathhint_analysis.VerifyResults` | 게시된 최종 연구의 분할·벡터·군집·요청·표 대조. API 호출 없음 |
| 핵심 검사 | `python -m unittest discover -s tests -v` | 임시 가짜 자료와 저장 결과 사용. 연구 데이터 재학습·실제 API 호출 없음 |

기본 결과 경로는 `results/final_experiment/`다. `AnalyzeThreeWay`는 `view`, `VectorComparison`은 `evaluate`, `ThreeWayGeneration`은 `prepare`에 해당하는 개별 진입점이다. 아래의 단일 설정을 함께 사용한다. 요청 간격·제한된 재시도·할당량 중단 기능은 유지한다. API 실행을 중단하려면 선택한 결과 폴더의 `03_gemini/stop_requested` 파일을 만들고 재개 전에 제거한다.

## 다음 실험의 데이터·모델 선택

[Experiment.py](mathhint_learning/Experiment.py)의 `EXPERIMENT` 한곳에서 이름·데이터·결과·체크포인트·예측 경로와 학습 설정을 고른다. 기본값은 기존 연구의 검증된 모델·예측을 명시적으로 선택한다. 실행 시 선택 경로를 출력하고, 결과 폴더의 `experiment.json`에 데이터 신원·모델·예측 해시를 남긴다.

나중에 새 선형회귀 실험을 하기로 정했다면 설정을 예컨대 `EXPERIMENT = Experiment(name="linear_next_01")`로 바꾸고 `train`을 실행한다. `results/linear_next_01/`의 모델→예측→평가→보고서가 연결된다. 이후 `prepare`는 그 예측을 사용한다. 기존 모델을 별도 폴더에서 다시 평가하려면 새 이름과 `checkpoint`를 명시하고 `evaluate`를 실행한다. 다른 데이터를 쓰려면 같은 설정의 `data_root`에 전처리된 데이터 폴더를 지정한다. 이번 보완에서는 새 연구 학습·Gemini 실험을 실행하지 않았다.

어휘의 내용과 순서, 문항 ID·행 순서, 고정 분할, 데이터 파일 해시, 모델·예측 해시를 검사한다. 차원만 같아도 어휘 순서가 다르면 중단한다. 필요한 파일이 없으면 과거 결과를 대신 사용하지 않는다. `train`은 최종 연구·보존 폴더나 이미 결과가 있는 회귀 폴더를 덮어쓰지 않는다. 원시 빈도는 정수, 회귀 예측은 실수로 보존하며 기존 음수 보정·전송 소수점 규칙을 유지한다.

데이터를 원본에서 새로 만들거나 학습 코드를 공부할 때는 다음 명령을 사용한다. 현재 저장 데이터와 모델 결과를 읽는 데는 다시 실행할 필요가 없다.

```bash
python -m mathhint_analysis.PrepareDataset
```

`PrepareDataset`은 HML 추출→문항 분리→고정 분할→학습 어휘→벡터를 생성한다. 기본 `OVERWRITE=False`이므로 기존 데이터가 있으면 교체하지 않는다. 재생성이 필요하면 상단 설정에서 새 출력 경로를 지정한다. 학습은 위의 별도 실험 설정과 `RunExperiment train`을 사용한다.

## 데이터와 문항 ID

확정 데이터는 HML 6개의 **265문항(미분140·삼각함수125)**이다. 기존 학습185개·테스트80개 분할을 유지한다. 문제 어휘346개와 해설 어휘431개는 각각 학습 데이터에서만 만든다. 테스트에서 새로 나온 토큰은 어휘에 추가하지 않는다.

```text
data/
├── raw/                 # 그림 문항을 제외한 확정 HML 원본
├── provenance/          # 번호 대조표·그림 제거 기록·수식 전사 근거
├── processed/
│   ├── annotated/       # ID·분류·출처 + 문제·원본 해설
│   ├── problems/        # 문제 본문
│   ├── solutions/       # 원본 정답·해설
│   ├── metadata.json    # 분류·출처·원래/현재 번호
│   └── splits/          # train.json 185개 / test.json 80개
└── vectors/
    ├── problems/        # vocabulary.json, train/test_vectors.json
    └── solutions/       # 같은 구조, 별도의 해설 어휘
```

예를 들어 `diff_3_017`은 미분 자료3의 **삭제 전 원래17번**이다. 현재 번호는 메타데이터에 따로 저장한다. TXT 파일명·분할 ID·벡터의 `documents[].id`·모델 결과를 이 ID로 연결한다. 단원·유형·출처는 확인용 자료와 평가 라벨에 보존하고 문제/해설 벡터에는 넣지 않는다.

같은 출처나 본문은 같은 집합으로 묶는다. 단원별 약30%를 테스트로 배정하고 분리 가능한 유형을 양쪽에 포함한다. 한 문항뿐인 유형은 학습에 둔다. 분할 제약과 실제 개수는 [분할 보고서](data/processed/splits/report.json), 재생성 검증은 [데이터 검증 기록](docs/data_validation.json)에 있다.

## 실험의 비교 기준

**군집화:** 실제 과목(`curriculum`)·단원·세부단원·유형의 고유 경로를 사용한다. `subject`는 미분/삼각함수 자료군이다. 군집 수는 각 단계의 학습 라벨 수에서 도출하며 현재2·8·25·70개다. 원시 BoW의 유클리드 K-means와 입력·중심을 정규화하는 Spherical K-means를 비교한다. 중심과 대표 라벨은 학습 데이터로만 정하고 테스트를 배정한다. ARI·NMI·보조 정확도와 실제 군집 문항을 함께 본다.

**회귀:** 문제 벡터에서 해설 벡터를 예측하는 선형층을 사용한다. 학습 평균 기준선·원시 출력·음수 보정 출력을 MSE·MAE·코사인 유사도로 비교한다. 실제 빈도는 정수지만 예측 평가에서는 반올림하지 않는다. 코사인 유사도는 정답률이 아니다.

**Gemini:** 같은80문항과 모델 설정으로 다음 세 조건을 비교한다.

| 조건 | 전달 정보 |
|---|---|
| A | 문제만 |
| B | 문제 + 예측 해설 빈도 상위20토큰 |
| C | 문제 + 원본 해설 빈도 상위20토큰 |

B와 C는 고정된 학습 어휘와 동일한 선택·직렬화 규칙을 사용한다. 예측값은 음수를0으로 보정하고 반올림 전 값으로 정렬하며, 전송 값은 소수점 세 자리로 표시한다. **C는 정답 해설 정보를 미리 제공한 오라클 진단**이다. 실제 서비스의 예측 성능이나 보장된 성능 상한으로 해석하지 않는다.

실제 시스템 지시·문제·추가 토큰·최종 요청·응답·API 사용량을 기록하고 입력 해시가 일치하는 기존 A/B 응답을 재사용한다. API가 주지 않은 토큰 항목은 `null`로 둔다. 원본 정답표와 AI 보조 정답표 검토를 구분하며, 최종 답의 정오와 풀이의 타당성도 별도로 표시한다. 이전 테스트 결과를 본 뒤 설계한 후속 비교이고 문항 수와 반복 횟수에 한계가 있으므로 결과만으로 원인을 확정하지 않는다.

## 프로젝트 구조와 정리 기록

| 폴더 | 역할 |
|---|---|
| `mathhint_preprocess/` | HML 구조와 한글 수식 파싱 |
| `mathhint_analysis/` | BoW·데이터 준비·통계·최종 보고서 |
| `mathhint_learning/` | 고정 데이터 로딩·군집화·선형회귀·벡터 비교 |
| `mathhint_solver/` | Gemini 요청·제한 관리·응답 평가·풀이 검토 |
| `data/` | 원본·출처·분할·학습 어휘와 벡터 |
| `results/final_experiment/` | 최종 비교표·그림·문항별 결과·보고서 |
| `results/model_comparison_2026-11-07/` | 재사용 응답·모델·기존 연구 근거 |
| `tests/` | 현행 파서·분할·모델·입력·집계 핵심 검사 |
| `docs/` | 최종 명세·진행 기록·코드 안내·검증/정리 근거 |

공부할 때는 [코드 안내](docs/code_guide_ko.md)를 따른다. 실제 삭제·통합·보존 내역과 복구 방법은 [정리 기록](docs/cleanup_changes.md)에 있다. 새 세션에서는 `AGENTS.md`→[최종 명세](docs/FINAL_TASK_SPEC.md)→[진행 기록](docs/WORK_PROGRESS.md)→실제 Git/파일 상태 순서로 확인하고 미완료 단계부터 이어 간다.
