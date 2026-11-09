# type_euclidean · k=70

[군집별 문항 목록](clusters.md) · [문항별 CSV](members.csv) · [군집 요약/문항 ID](cluster_summary.csv)

[문제·풀이 수식 읽기 화면](../../../03_gemini/report.html)에서 문항 ID로 찾을 수 있다. 군집 문항 목록의 ID를 누르면 해당 문제를 바로 연다. 학습 문항은 생성 실험 대상 아님으로 표시하며 추가 API를 호출하지 않는다.

[학습 교차표](cross_tab_train.csv) · [테스트 교차표](cross_tab_test.csv) · [라벨 코드 전체 경로](label_key.csv)

아래 링크에서 저장된 그림을 바로 연다. 라벨이 많으면 최대 20행으로 히트맵을 나누었다. 라벨 코드는 전체 경로의 사전순 번호이며 라벨 번호와 군집 번호는 다르다.
구성비 그림은 학습 빈도 상위 8개 라벨과 기타를 사용한다. 모든 실제 라벨의 정확한 비율은 상위 폴더의 `cluster_label_distribution.csv`에 보존했다.
테스트 그림에 실제 라벨을 표시하는 것은 평가·관찰을 위한 것이며 중심 계산이나 대표 라벨 선정에 사용하지 않았다.

| 구분 | 실제 분류 × 군집 히트맵 | 군집별 실제 라벨 구성 비율 |
|---|---|---|
| 학습 | [1쪽](figures/cross_tab_train_01.png) · [2쪽](figures/cross_tab_train_02.png) · [3쪽](figures/cross_tab_train_03.png) · [4쪽](figures/cross_tab_train_04.png) | [1쪽](figures/label_composition_train_01.png) · [2쪽](figures/label_composition_train_02.png) · [3쪽](figures/label_composition_train_03.png) |
| 테스트 | [1쪽](figures/cross_tab_test_01.png) · [2쪽](figures/cross_tab_test_02.png) · [3쪽](figures/cross_tab_test_03.png) | [1쪽](figures/label_composition_test_01.png) · [2쪽](figures/label_composition_test_02.png) · [3쪽](figures/label_composition_test_03.png) |

## 테스트 혼동행렬

[실제 분류 × 예측 분류 혼동행렬](figures/confusion_matrix_test.png) · [전체 라벨 경로](label_key.csv)

테스트 80문항을 행=실제 분류, 열=학습 문항의 군집별 최빈 라벨로 대응한 예측 분류로 셌다. 전체 70분류를 같은 순서의 두 축에 포함한다. 실제 미등장 28분류·예측 미등장 47분류도 0행·0열로 남긴다. 같은 분류 수준의 두 거리 방식은 축 순서와 색상 범위가 같다. 큰 행렬은 코드를 사용한 고해상도 그림이며 숫자를 생략한 칸은 0이다.

기존 교차표 히트맵의 가로축은 군집 번호다. 이 혼동행렬은 가로축을 학습 대표 분류로 대응하여, 분류 간 혼동을 보여준다. 대표 라벨을 정할 때 테스트 실제 라벨을 사용하지 않았다.
