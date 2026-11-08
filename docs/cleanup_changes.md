# 최종 저장소 정리 내역

## 실제 삭제 완료

이번 목록은 계획이 아니라 실제 파일 삭제 내역이다. 삭제 직전 각 파일 바이트가 `recovery/before-final-cleanup-20261108` 브랜치의 해당 blob과 일치하는 것을 확인했다. 복구 브랜치 커밋은 `aa1e61f519244ba2564c8f1035688d431948d17a`이며 정리 전 체크포인트 `5eca866`에 기록되어 있다.

| 삭제 파일 | 이유 |
|---|---|
| `examples/bow_sample.txt` | 초기 BoW 연습 자료; 현행 데이터·코드·검사에서 미사용 |
| `examples/bow_sample_2.txt` | 초기 BoW 연습 자료; 현행 데이터·코드·검사에서 미사용 |
| `.vscode/settings.json` | 개인 conda 편집기 설정 |
| `mathhint_preprocess/__main__.py` | 현재 HML 파이프라인에서 호출하지 않는 HWPX 전용 기능/검사 |
| `mathhint_preprocess/hwpx.py` | 현재 HML 파이프라인에서 호출하지 않는 HWPX 전용 기능/검사 |
| `mathhint_preprocess/models.py` | 현재 HML 파이프라인에서 호출하지 않는 HWPX 전용 기능/검사 |
| `mathhint_preprocess/segment.py` | 현재 HML 파이프라인에서 호출하지 않는 HWPX 전용 기능/검사 |
| `mathhint_preprocess/export.py` | 현재 HML 파이프라인에서 호출하지 않는 HWPX 전용 기능/검사 |
| `scripts/validate_latex.py` | 현재 HML 파이프라인에서 호출하지 않는 HWPX 전용 기능/검사 |
| `tests/test_hwpx.py` | 현재 HML 파이프라인에서 호출하지 않는 HWPX 전용 기능/검사 |
| `tests/test_export.py` | 현재 HML 파이프라인에서 호출하지 않는 HWPX 전용 기능/검사 |
| `requirements-learning.txt` | pyproject.toml의 learning 선택 의존성과 중복 |

`examples/`, `.vscode/`, `scripts/`는 위 파일 제거 후 비어 있어 폴더도 제거했다. 삭제 파일은 총 12개다.

복구할 때는 필요한 경로만 선택한다. 예를 들어:

```bash
git restore --source=recovery/before-final-cleanup-20261108 -- examples mathhint_preprocess/hwpx.py
```

브랜치를 사용할 수 없더라도 해당 커밋을 조회할 수 있는 저장소에서는 `--source=aa1e61f519244ba2564c8f1035688d431948d17a`로 복구할 수 있다. 원격 게시 여부는 `docs/WORK_PROGRESS.md`와 실제 원격 refs를 확인한다.

## 실제 수정 완료

- `pyproject.toml`: 폐기한 HWPX CLI `mathhint-preprocess`를 제거하고 HML 표준 명령 `mathhint-prepare-dataset`을 유지했다. 설명을 현재 연구 범위에 맞췄다. learning 의존성 네 개는 기존과 동일하게 유지했다.
- `mathhint_preprocess/__init__.py`, `equations.py`: HWPX 전용 소개를 HML 및 한글 수식 설명으로 갱신했다. 수식 변환 계산 규칙은 변경하지 않았다.

## 보존한 주요 항목

- `mathhint_preprocess/hml.py`, `equations.py`, `tests/test_hml.py`, `tests/test_equations.py`: 실제 HML 추출과 수식 변환을 수행하고 보호한다. HWPX 전용 기능과 구분해 보존했다.
- `PrepareDataset.py`, `BagOfWord.py`와 분할·BoW 핵심 검사: 고정 ID185/80 분할과 학습 전용 어휘를 재현한다.
- `data/` 전체, 기존 모델, 재사용 API 요청/응답 및 provenance, 최종 실험 결과: 연구 근거이므로 이번 정리에서 삭제하거나 덮어쓰지 않았다.
- `docs/FINAL_TASK_SPEC.md`, `WORK_PROGRESS.md`, 기존 취소 작업 체크포인트: 장기 재개와 복구 근거를 보존한다.
- `.env`: 읽거나 수정하지 않았다. 비밀 설정은 Git에 넣지 않았다.

## 검증 상태

아래 결과는 정리 직후 실행한 검증을 반영한다. README와 코드 안내는 아래 두 번째 정리 단계에서 현행 실행 경로로 갱신했다. 다른 중복 진입점은 해당 담당자와 의존 관계를 조정하기 전에는 삭제하지 않았다.

삭제 수행 시점(UTC): 2026-11-08T16:38:25.571510+00:00

- HML·수식·분할·BoW·빈도벡터 핵심 테스트: 65개 실행, 실패 0개, 오류 0개, 건너뜀 0개.
- 핵심 4개 모듈 import 및 pyproject CLI 구성 검사: PASS.
- 실제 외부 API 호출: 0회.

## 이전 통합 학습 진입점의 실제 삭제

- 삭제: `mathhint_learning/RunTraining.py`. 자료군 `subject` 및 고정 2·8·70 군집을 사용하던 과거 통합 실행이다. 최종 군집화의 네 교육과정 단계·유클리드/구면 비교는 `FinalClustering.py`, 선형 학습은 `TorchRegression.py`, 기존 실수 예측 검증은 `VectorComparison.py`가 담당하므로 중복 진입점을 제거했다.
- 복구 근거: 삭제 직전 파일 전체 바이트가 `recovery/before-final-cleanup-20261108`의 blob과 동일한 것을 확인했다. 브랜치 커밋 `aa1e61f519244ba2564c8f1035688d431948d17a`, 파일 SHA-256 `2e1f6c2b407f637b185c9865041882cc36ca1b57ef44cda428fe522f20bb95d1`.
- 수정: `tests/test_fixed_training.py`의 import를 `TorchRegression.train_regression`, `TorchData.load_fixed_dataset`, `FinalClustering.majority_labels`로 바꿨다. 분할·행 ID·학습 어휘·테스트 정답 비사용·대표 라벨 동률 처리의 핵심 검사 7개를 모두 보존했다.
- 검증: 고정 분할 학습 검사 7개 및 기존 개별 학습 진입점 검사 2개가 통과했다. 현재 실행 Python/pyproject에서 `RunTraining` 참조가 남아 있지 않음을 `rg`로 확인했다. README·학습 안내의 이전 실행 명령은 별도 문서 통합 단계에서 교체하며, 조사 기록 `repository_inventory.md`는 조사 시점의 상태다.
- 원본 데이터·기존 모델·과거 실험 결과·최종 실험 결과는 수정하지 않았다. 새로운 외부 API 호출은 없다.

검증 시점(UTC): 2026-11-08T16:43:10.928298+00:00


## 최종 보고서 경로 통합

- 삭제: `mathhint_analysis/AnalyzeExperiment.py`(이전 두 조건 전용 집계·중복 PDF), `mathhint_analysis/BuildComparisonViewer.py`(이전 화면 생성기). 기존 게시 결과와 원본 응답은 삭제하지 않았다. 삭제 전 파일은 Git 이력으로 복구한다.
- 통합: 공통 4종 통계와 필수 보조 함수는 `mathhint_analysis/ExperimentMetrics.py`로 이동했다. 최종 보고서·CSV·그림은 `mathhint_analysis/AnalyzeThreeWay.py`를 표준 진입점으로 사용한다. PDF·base64 이미지 사본은 추가 생성하지 않는다.
- 수정: `tests/test_experiment_report.py`를 현재 기능 8개 검사로 정리했다. 오류/미채점 제외, 미제공 토큰 null, 실제 0값 보존, skipped 재시도 제외, 재사용의 신규 사용량 분리, 원본·AI 보조 정답표 분리 및 출처 해시, 빈 C조건 CSV, 대응 비교 분모를 검증한다.
- 실제 검증: `python -m unittest discover -s tests -p test_experiment_report.py -v` 8/8 통과. 최종 보고서 생성은 API 호출·재학습 없이 기존160응답으로 실행했다. C가 미실행이면 80문항의 C결과를 비워 두고 미완료로 표시한다. C실행 완료 후 같은 명령으로 재집계한다.


## 최종 실행 경로로 대체된 보조 도구 정리

- 실제 삭제: `mathhint_solver/GoogleAPI.py`, `tests/test_solver.py`. 단일 문제 전용 API 진입점을 제거했다. 최종 실제 SDK 경계·입력/응답·중단 재개 검사는 `ThreeWayGeneration`과 공통 API 검사에서 유지한다. `ThreeWayGeneration.py` 안의 GoogleAPI 설명은 당시 소스 검토 기록이며 실행 import가 아니다. 해시 고정된 API 실행 코드는 수정하지 않았다.
- 실제 삭제: `mathhint_analysis/BuildFrequencyVectors.py`, `tests/test_frequency_vectors.py`. 임의 TXT 폴더용 보조 진입점을 제거하고, 최종 데이터 준비는 `PrepareDataset.py`로 통일했다. `test_bow.py`가 한국어/LaTeX 토큰 대응·수식 경계·미완성 수식 오류를 검사하고, `test_dataset_pipeline.py`가 학습 전용 어휘·OOV 제외·문제/해설 행 ID·메타데이터 제외를 검사하므로 현행 경로의 핵심 검사는 유지된다.
- 네 파일 모두 삭제 직전 바이트가 복구 브랜치의 blob과 동일했다. 필요한 파일은 `git restore --source=recovery/before-final-cleanup-20261108 -- <경로>`로 복구할 수 있다.
- `pyproject.toml`: 폐기한 수식 뷰어 전용 `viewer` extra 및 `all`의 `latex2mathml` 의존성을 제거했다. 기본 설치 경로는 `pip install -e '.[analysis,learning,solver]'`이며 실제 명령은 README에 기록했다.
- `README.md`, `docs/code_guide_ko.md`: 현행 단일 데이터 준비·4단계 군집화·실수 회귀 검증·A/B/C 입력 준비·선택 API 실행·저장 결과 재집계 경로로 교체한다. 신규 API 실행은 소스의 상수를 편집하지 않고 프로세스 안에서 `run.RUN_API = True`로 지정하도록 안내해 입력/소스 해시 가드를 유지한다.

두 번째 삭제 수행 시점(UTC): 2026-11-08T16:45:16.080444+00:00

- 두 번째 정리 후 HML·수식·분할·BoW 핵심 검사: 56개 실행, 실패0개, 오류0개, 건너뜀0개.
- README의6개 모듈이 실제 존재하고 main/run 실행 진입점을 제공함을 확인했다. 이 확인을 위해 API나 재학습을 실행하지 않았다.
- README/코드 안내의 모든 로컬 링크 존재 및 설치 extra/폐기 viewer 의존성 제거 검사: PASS.
- 두 번째 검증 시점(UTC): 2026-11-08T16:48:18.631166+00:00

## 취소 초안 복구 ZIP의 Git 이력 이동

- `docs/checkpoints/cancelled_before_final.zip`, `docs/checkpoints/README.md`를 현재 트리에서 삭제했다. ZIP은 로컬 및 원격 main 이력의 `588d86f`와 완전히 같은 바이트임을 확인했다(SHA256 `56cc3b6aad2ea6d5b3b0784a820f1f3549d4138fae557adcec2e3f862055756c`).
- 복구: `git show 588d86f:docs/checkpoints/cancelled_before_final.zip > /tmp/mathhint_cancelled_checkpoint.zip`. 이 이력은 원격 게시 확인된5eca866의 조상이다. 새 최종 실험에 채택되지 않은 정수·전체벡터 초안의 중복 백업을 작업 공간에 남기지 않는다.
- 기존 `results/model_comparison_2026-11-07/`는 재사용 API160개·AI검토·모델·학습기록·930파일 manifest를 연결하는 불변 근거 묶음으로 보존한다. 새 최종 안내는 `results/final_experiment/README.md` 하나를 사용한다. 오래된 정답/입력/응답을 새 실험으로 가장하지 않는다.
- `.env`는 내용과 해시를 수집하지 않고 Git 제외 상태로 보존했다. 원본 데이터·분할·어휘·기존 결과는 삭제하지 않았다.
