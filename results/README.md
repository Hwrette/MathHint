# 실험 결과 안내

<!-- final-experiment-2:start -->

**후속 연구:** [2차 실험 목차](final_experiment_2/README.md)에서 [전체265 군집화](final_experiment_2/cluster_improvement/README.md), [선형회귀](final_experiment_2/regression/README.md), [비선형 MLP](final_experiment_2/deep_learning/README.md), [Gemini A/B/C/D 비교와 실제 완료 범위](final_experiment_2/gemini_comparison/README.md)로 이동한다. 모델의 해설 토큰 예측과 Gemini의 수학 풀이 성능을 구분해 읽는다. 기존 1차 최종 실험·토큰 분석은 그대로 보존한다.

<!-- final-experiment-2:end -->

현재 연구의 최종 결과는 **[final_experiment/README.md](final_experiment/README.md)**에서 확인한다. 군집화·회귀·Gemini 세 조건의 표, 그림, 문항별 자료와 최종 보고서를 한곳에서 연결한다.

문제와 풀이부터 읽으려면 **[수식이 표시되는 문항별 화면](final_experiment/03_gemini/report.html)**을 연다. GitHub 파일 페이지에서는 실행되지 않으므로 저장소 ZIP을 압축 해제한 뒤 브라우저로 연다. 읽기 화면에는 로컬 `final_experiment/viewer_assets/`도 함께 필요하다. 인터넷 연결이나 Gemini 호출 없이 동작한다.

| 구분 | 내용 | 먼저 볼 자료 |
|---|---|---|
| **최종 연구 결과** | 과목·단원·세부단원·유형의 유클리드/구면 군집화, 실수 회귀 평가, Gemini A/B/C 각80문항 비교 | [전체 안내](final_experiment/README.md) · [군집별 문항](final_experiment/01_clustering/cluster_members.csv) · [Gemini80문항 비교](final_experiment/03_gemini/question_comparison.csv) · [최종 보고서](final_experiment/final_report.md) |
| **후속 연구1단계: 토큰 분석** | 문제·해설 통계, 학습 분류별 분산·중복성, OOV와 실제 B/C 전송 구성. 불용어 선정·군집화 재실험은 미실행 | [먼저 읽을 요약](token_analysis/README.md) · [종합 보고서](token_analysis/token_analysis_report.md) · [사용자 선택 파일](token_analysis/stopwords/) |
| 기존 실험의 불변 근거 | `model_comparison_2026-11-07/`의 원본 응답160개, 학습 모델·설정·검토·출처 및 기존 결과 | [보존 자료 안내](model_comparison_2026-11-07/README.md) |

기존 폴더는 재사용 결과의 근거를 확인하기 위한 보존 영역이다. 그 안의 두 조건 보고서·PDF는 당시 실험의 기록이며 현재 최종 세 조건 결과와 구분한다. 최종 해석과 수치는 `final_experiment/`를 기준으로 읽는다.

검사에 쓰는 가짜 데이터는 임시 폴더에만 둔다. 검토·보존할 연구 결과는 `results/`에서 관리한다. 데이터·설정이 다른 새 실험은 `Experiment.py`에서 별도 이름·결과 경로를 선택하고, 기존 결과를 덮어쓰지 않는다.
