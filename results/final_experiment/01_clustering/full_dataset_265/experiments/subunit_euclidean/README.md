# subunit_euclidean · 전체 265문항 · k=25

265문항 전체를 학습하고 같은 문항의 구조를 설명하는 탐색 실험이다. 새로운 문항에 대한 테스트 성능이 아니다.

[군집별 실제 문제](clusters.md) · [문항별 배정](members.csv) · [군집 요약](cluster_summary.csv)
[교차표](cross_tab_all.csv) · [전체 라벨 경로](label_key.csv) · [라벨 구성 빈도·비율](cluster_label_distribution.csv) · [라벨 분산](label_dispersion.csv)

- 실제 분류 × 군집 번호: [1쪽](figures/cross_tab_all_01.png) · [2쪽](figures/cross_tab_all_02.png)
- 군집 구성 비율: [1쪽](figures/label_composition_all_01.png)
- [동일 데이터 설명용 혼동행렬](figures/confusion_matrix_all.png) · [정확한 행렬 수치](confusion_matrix_all.csv)

교차표 가로축은 군집 번호다. 혼동행렬 가로축은 전체 데이터에서 정한 군집 최빈 실제 라벨이다. 이 대표 라벨 일치율은 같은 자료로 대표 라벨을 정하고 평가한 설명용 일치율이며 테스트 정확도가 아니다.
혼동행렬의 행과 열은 전체 계층 경로의 사전순 라벨 코드로 동일하게 정렬한다. 실제/예측 빈도가 0인 축도 남긴다. 전체 이름은 label_key.csv에서 확인한다.

[중심·원래 분할·어휘 체크포인트](model.pt) · [설정·시드별 목적함수·평가](experiment.json)

군집화는 원래 BoW 차원에서 수행했다. PCA는 상위 폴더의 그림/투영 JSON으로 확인하며 고차원 결과의 표시만을 위한 것이다.
