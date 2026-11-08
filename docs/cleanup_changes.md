# 최종 결과·저장소 정리 및 명세 재점검

이 문서는 최종 변경 내역의 통합 목록이다. 단계별 실행 이력은 [WORK_PROGRESS.md](WORK_PROGRESS.md)에 보존한다. 초기 정리 후 누락을 재점검하여 결과 탐색 경로와 구 실행 코드를 추가로 정리했다.

## 재점검에서 확인하고 보완한 부분

| 명세 요구 | 확인한 부족함 | 실제 보완·확인 경로 |
|---|---|---|
| 9-1·11-7 결과를 한곳에서 찾기 | results 상위 안내가 이전 실험만 연결 | [상위 결과 안내](../results/README.md)에서 최종 결과를 우선하고 구 폴더는 보존 영역으로 구분 |
| 8-2·11-4 중복 실행 제거 | 삭제한 RunTraining의 옛 경로를 쓰는 두 조건 main과 표시 모듈 잔존 | CompareGeneration은 공통 엔진, RateLimitedComparison은 제한기로 유지하고 구 main·경로·표시·검토 코드는 제거 |
| 9-5 실제 유형의 군집 사례 | 세부단원 사례만 큐레이션 | [군집 분석](../results/final_experiment/01_clustering/analysis.md)과 [통합 사례](../results/final_experiment/04_case_studies/selected_cases.md)에 두 방식의 유형 일치·혼합·분산 사례 추가 |
| 7-3 B/C 실제 입력 차이 | 전체 JSON은 있으나 토큰별 나란히 비교가 불편 | [전송 토큰 비교표](../results/final_experiment/03_gemini/prompt_audit/token_comparison.md) 3문항·77행: 실제 전송값·순위·공통/한쪽 포함을 대조 |
| 10-1 회귀 정보의 구체적 해석 | 수치와 문항 ID 중심 설명 | [회귀 분석](../results/final_experiment/02_regression/analysis.md)과 최종 보고서에 맞히거나 놓친 실제 토큰·빈도 사례 추가 |
| 9-2·9-3 그림 접근성 | 그림 파일은 있으나 직접 링크 부족 | 군집 8개 README에 히트맵·구성비, 회귀 사례에 해당 토큰 PNG 연결 |
| 10-2 사실과 표현 일치 | B와 C 모두 맞은 사례를 B에서만 개선이라고 표시 | A 대비 B 개선이라는 정확한 제목으로 수정하고 조건별 답을 함께 표시 |

## 최종 산출물 확인

| 요구 | 실제 자료 |
|---|---|
| 군집화 4분류×2거리, 지표·문항·분포·교차표·그림 | [01_clustering 안내](../results/final_experiment/01_clustering/README.md) |
| 회귀 3기준, 문항별 실수 벡터·오차·상위20·그림 | [02_regression 분석](../results/final_experiment/02_regression/analysis.md) |
| Gemini A/B/C 80문항·토큰·풀이·실제 입력/응답 감사 | [03_gemini 분석](../results/final_experiment/03_gemini/analysis.md), [문항별 표](../results/final_experiment/03_gemini/question_comparison.csv) |
| 문항 ID로 문제·모델·입력·출력 연결 | [80문항 연결](../results/final_experiment/04_case_studies/questions.md) |
| 11절 한국어 보고서·후속 연구 언급 | [최종 보고서](../results/final_experiment/final_report.md) |
| 재현 명령·환경변수·폴더 역할 | [프로젝트 README](../README.md), [코드 안내](code_guide_ko.md) |

## 누적 실제 삭제 목록

최종 명세 수령 시점의 Git 체크포인트 `620f4ce`와 비교한 추적 파일 삭제는 **24개**다. 초기 12개만 적었던 단계별 목록을 이 누적 목록으로 통합했다.

| 삭제 파일 | 이유 |
|---|---|
| `.vscode/settings.json` | 개인 편집기 설정 |
| `docs/checkpoints/README.md` | 취소 초안 복구본을 Git 이력으로 이동; 아래 복구 방법 보존 |
| `docs/checkpoints/cancelled_before_final.zip` | 취소 초안 복구본을 Git 이력으로 이동; 아래 복구 방법 보존 |
| `examples/bow_sample.txt` | 최종 실행·검사에서 사용하지 않는 초기 BoW 연습 자료 |
| `examples/bow_sample_2.txt` | 최종 실행·검사에서 사용하지 않는 초기 BoW 연습 자료 |
| `mathhint_analysis/AnalyzeExperiment.py` | 구 2조건 보고서; 공통 통계는 ExperimentMetrics로 통합 |
| `mathhint_analysis/BuildComparisonViewer.py` | 구 2조건 화면; 최종 세 조건 열람 화면으로 대체 |
| `mathhint_analysis/BuildFrequencyVectors.py` | 일반 TXT 보조 실행; 고정 데이터 준비로 통일 |
| `mathhint_learning/RunTraining.py` | 구 통합 실행; 현행 군집화·회귀 실행으로 분리 |
| `mathhint_preprocess/__main__.py` | 현재 HML 파이프라인에서 사용하지 않는 HWPX 전용 기능 |
| `mathhint_preprocess/export.py` | 현재 HML 파이프라인에서 사용하지 않는 HWPX 전용 기능 |
| `mathhint_preprocess/hwpx.py` | 현재 HML 파이프라인에서 사용하지 않는 HWPX 전용 기능 |
| `mathhint_preprocess/models.py` | 현재 HML 파이프라인에서 사용하지 않는 HWPX 전용 기능 |
| `mathhint_preprocess/segment.py` | 현재 HML 파이프라인에서 사용하지 않는 HWPX 전용 기능 |
| `mathhint_solver/GenerationReport.py` | 사용하지 않는 구 2조건 표·그림 생성 |
| `mathhint_solver/GoogleAPI.py` | 별도 단일 문제 API 실행; 최종 세 조건 실행으로 통일 |
| `mathhint_solver/SolutionReview.py` | 사용하지 않는 구 수동 검토 실행; 현행 review_evidence 검사로 통합 |
| `requirements-learning.txt` | pyproject 선택 의존성과 중복 |
| `scripts/validate_latex.py` | 현재 HML 경로에서 사용하지 않는 HWPX 보조 실행 |
| `tests/test_export.py` | 폐기 기능 전용 검사 제거; 현행 파서·데이터·API·검토 보호 검사는 유지/교체 |
| `tests/test_frequency_vectors.py` | 폐기 기능 전용 검사 제거; 현행 파서·데이터·API·검토 보호 검사는 유지/교체 |
| `tests/test_hwpx.py` | 폐기 기능 전용 검사 제거; 현행 파서·데이터·API·검토 보호 검사는 유지/교체 |
| `tests/test_solution_review.py` | 폐기 기능 전용 검사 제거; 현행 파서·데이터·API·검토 보호 검사는 유지/교체 |
| `tests/test_solver.py` | 폐기 기능 전용 검사 제거; 현행 파서·데이터·API·검토 보호 검사는 유지/교체 |

최종 작업 도중 생성했다가 통합한 임시 파생 표는 별도 2개다: `03_gemini/comparison.csv`, `03_gemini/summary.json`. 원본 응답을 삭제한 것이 아니며 `question_comparison.csv`, `summary.csv`, `token_summary.csv`, `analysis.json`으로 역할을 통합했다. 취소된 미추적 정수 회귀 테스트 초안은 현행 실수 벡터 비교 검사로 교체했다.

## 통합·수정·추가한 핵심 코드

- `TorchKMeans.py`, `FinalClustering.py`, `ClusterReport.py`: 유클리드/구면 비교, 학습 라벨 수로 k 결정, 문항·분포·그림 출력. 재점검에서는 사례·링크만 바꿨고 모델 학습 코드는 바꾸지 않았다.
- `TorchRegression.py`, `VectorComparison.py`: 고정 분할 학습과 실수 예측 평가, 기존 모델 재추론 검증·상위 토큰 비교. 정수 반올림 초안을 제거했다.
- `CompareGeneration.py`, `RateLimitedComparison.py`: 공통 입력·SDK·저장·재개·속도 제한을 유지한다. 이제 독립된 구 두 조건 main이나 구 보고서 생성 기능이 없다.
- `ThreeWayGeneration.py`, `GenerationAudit.py`: 유일한 최종 API 실행과 정확한 재사용, SDK 인자·응답 감사. 실행 당시 소스는 Git `4f67658`에서 복구하며 현재 소스의 유지보수 이력은 source_transition.json에 남긴다.
- `ExperimentMetrics.py`, `AnalyzeThreeWay.py`, `VerifyResults.py`: 공통 통계·최종 보고서·산출물 검증. 실제 풀이 검토는 현행 review_evidence에서 해시·인용과 AI/사람 구분을 확인한다.
- 현재 기능의 오류·재개·어휘·ID·음수/소수·SDK 입력·검토 근거 검사는 유지했다. 폐기된 검토 인터페이스 검사 대신 실제 최종 검토 경로의 핵심 4개 검사를 추가했다.
- `pyproject.toml`의 폐기 HWPX CLI·뷰어 의존성, README와 코드 안내를 정리했다. `.gitattributes`는 원래 HML `-text -diff` 규칙을 유지하고 CSV 표준 CRLF만 공백 검사에서 허용한다.

## 보존 범위와 복구

- 원본 HML 6개, 265문항·분류·출처, 번호 대조·그림 제거·수식 전사 근거, 고정 학습185/테스트80, 학습 전용 어휘346/431과 벡터를 보존한다.
- 기존 모델·원본 API160응답·검토·설정·재현 근거가 있는 `results/model_comparison_2026-11-07/`는 **931파일(자신을 제외한 manifest930개 SHA)의 불변 보존 묶음**이다. 과거 PNG/PDF도 이 묶음 안에 남겨 뒀다. 모든 과거 시각자료까지 삭제했다고 주장하지 않는다. 최종 결과를 읽을 때는 `final_experiment/`를 사용한다.
- 최종 세 조건의 원본 JSONL241행(성공240+최초시간초과1), 실제 요청240개·SDK기록81개·모델·벡터는 보존한다. 이번 재점검으로 API나 모델 학습을 다시 실행하지 않았다.
- `.env`와 인증값은 Git에 추가하지 않는다. 미추적 필수 원본을 복구 수단 없이 삭제하지 않았다.

코드 복구 지점은 원격에도 있는 `recovery/before-final-cleanup-20261108`와 `recovery/before-final-reaudit-20261108`다. 필요한 파일만 복구한다.

```bash
git restore --source=recovery/before-final-reaudit-20261108 -- <복구할_파일>
git show 588d86f:docs/checkpoints/cancelled_before_final.zip > /tmp/mathhint_cancelled_checkpoint.zip
```

취소 초안 ZIP의 SHA-256은 `56cc3b6aad2ea6d5b3b0784a820f1f3549d4138fae557adcec2e3f862055756c`이다. Git에 보존된 바이트와 일치함을 확인한 뒤 작업 트리에서 중복 복구본을 제거했다.

## 검증과 남긴 한계

최신 실행 결과는 [검증 JSON](../results/final_experiment/validation.json), [전체 테스트 로그](../results/final_experiment/test_results.txt), [API 사후 감사](../results/final_experiment/03_gemini/prompt_audit/response_audit.json), [진행 기록](WORK_PROGRESS.md)을 기준으로 확인한다. 재점검에서는 보호 대상336개 파일의 SHA 불변, 구 실행 참조 제거, 학습/API를 금지한 캐시 재사용, 링크·그림·실제 사례 수치를 대조한다.

PDF 생성, 사람의 확정 풀이 판정, 공식 교육과정 전수 대조는 이번 명세의 필수 완료 조건이 아니다. 실패 API의 전체 청구 비용은 확인할 수 없어 null로 남긴다. 이런 한계와 필수 산출물 누락을 혼동하지 않는다. 현재 preflight의 신규호출0은 완료된 실험의 캐시를 읽는 시점의 상태이며 과거 호출이 없었다는 뜻이 아니다.
