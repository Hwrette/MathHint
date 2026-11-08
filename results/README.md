# 실험 결과 안내

현재 연구의 최종 결과는 **[final_experiment/README.md](final_experiment/README.md)**에서 확인한다. 군집화·회귀·Gemini 세 조건의 표, 그림, 문항별 자료와 최종 보고서를 한곳에서 연결한다.

| 구분 | 내용 | 먼저 볼 자료 |
|---|---|---|
| **최종 연구 결과** | 과목·단원·세부단원·유형의 유클리드/구면 군집화, 실수 회귀 평가, Gemini A/B/C 각80문항 비교 | [전체 안내](final_experiment/README.md) · [군집별 문항](final_experiment/01_clustering/cluster_members.csv) · [Gemini80문항 비교](final_experiment/03_gemini/question_comparison.csv) · [최종 보고서](final_experiment/final_report.md) |
| 기존 실험의 불변 근거 | `model_comparison_2026-11-07/`의 원본 응답160개, 학습 모델·설정·검토·출처 및 기존 결과 | [보존 자료 안내](model_comparison_2026-11-07/README.md) |

기존 폴더는 재사용 결과의 근거를 확인하기 위한 보존 영역이다. 그 안의 두 조건 보고서·PDF는 당시 실험의 기록이며 현재 최종 세 조건 결과와 구분한다. 최종 해석과 수치는 `final_experiment/`를 기준으로 읽는다.

실행 중 임시 결과는 Git에서 제외되는 `outputs/`에 두며, 검토·보존할 결과만 `results/`에서 관리한다. 데이터·설정이 다른 새 실험은 기존 결과를 덮어쓰지 않고 별도 폴더를 사용한다.
