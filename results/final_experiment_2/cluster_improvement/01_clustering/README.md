# 전체265 문제 BoW 군집화: K0 원시 / K1 사용자 불용어

**전체265문항으로 중심과 대표 라벨을 정하고 같은265에서 구조를 관찰한 탐색 실험이다. 새로운 문항의 일반화 또는 테스트 성능이 아니다. 기존185/80 소속은 출처 열에만 남겼다.**

K0와 K1은 같은265 원문의 토큰화에서 출발한다. 공통 TorchKMeans 알고리즘·시드42~46의5회 초기화·최대100회·수렴1e-4를 유지했고 최저 학습 목적함수만으로 최종 시드를 골랐다. ARI/AMI/NMI를 보고 모델을 고르지 않았다.

## 먼저 볼 비교

|분류|거리|기존 전체265 ARI|K0 ARI|K1 ARI|K1−K0|K1 AMI|K1 NMI|K1 대표일치율|혼동행렬|
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
|과목|유클리드|0.0948|0.0948|0.4045|+0.3096|0.3320|0.3339|0.8189|[K0](experiments/K0_curriculum_euclidean/figures/confusion_matrix_all.png) · [K1](experiments/K1_curriculum_euclidean/figures/confusion_matrix_all.png)|
|과목|코사인(구면)|0.3396|0.3396|0.6206|+0.2810|0.5649|0.5661|0.8943|[K0](experiments/K0_curriculum_spherical/figures/confusion_matrix_all.png) · [K1](experiments/K1_curriculum_spherical/figures/confusion_matrix_all.png)|
|단원|유클리드|0.2139|0.2139|0.2247|+0.0108|0.4189|0.4500|0.6075|[K0](experiments/K0_unit_euclidean/figures/confusion_matrix_all.png) · [K1](experiments/K1_unit_euclidean/figures/confusion_matrix_all.png)|
|단원|코사인(구면)|0.2241|0.2241|0.2864|+0.0623|0.4831|0.5109|0.6453|[K0](experiments/K0_unit_spherical/figures/confusion_matrix_all.png) · [K1](experiments/K1_unit_spherical/figures/confusion_matrix_all.png)|
|세부단원|유클리드|0.2343|0.2504|0.3073|+0.0569|0.4344|0.5749|0.5849|[K0](experiments/K0_subunit_euclidean/figures/confusion_matrix_all.png) · [K1](experiments/K1_subunit_euclidean/figures/confusion_matrix_all.png)|
|세부단원|코사인(구면)|0.2302|0.2302|0.3604|+0.1303|0.4940|0.6270|0.6415|[K0](experiments/K0_subunit_spherical/figures/confusion_matrix_all.png) · [K1](experiments/K1_subunit_spherical/figures/confusion_matrix_all.png)|
|문제 유형|유클리드|0.1429|0.1528|0.4055|+0.2527|0.4802|0.7716|0.6528|[K0](experiments/K0_type_euclidean/figures/confusion_matrix_all.png) · [K1](experiments/K1_type_euclidean/figures/confusion_matrix_all.png)|
|문제 유형|코사인(구면)|0.2063|0.1993|0.3997|+0.2005|0.4569|0.7630|0.6377|[K0](experiments/K0_type_spherical/figures/confusion_matrix_all.png) · [K1](experiments/K1_type_spherical/figures/confusion_matrix_all.png)|

기존 수치는 학습185 어휘를 유지해 전체265를 군집화했던 보존 실험이다. 기존→K0는 어휘 범위 차이를, K0→K1은 같은 전체어휘 조건에서 승인 불용어 적용 차이를 살핀다. K1과 기존 결과의 차이를 불용어만의 효과로 해석하지 않는다.

[전체 지표16행](summary.csv) · [실제 문항 배정4240행](cluster_members.csv) · [시드별80회 결과](seed_metrics.csv) · [시드 평균·표준편차](seed_summary.csv) · [모인·혼합·분산 사례](case_studies.md)

## 지표와 그림

ARI·AMI·NMI는 임의 군집번호와 실제 계층 분류의 일치도다. 대표 일치율/F1은 각 군집의 최빈 실제라벨로 바꾼 동일자료 설명용 수치다. 최빈 동률은 전체 계층 경로 문자열 순서로 결정한다. 서로 다른 군집이 같은 대표라벨이면 혼동행렬의 같은 열로 합산한다. 두 축은 같은 라벨 순서라 대각선이 일치 문항 수다.

|읽을 지표|그림|
|---|---|
|ARI|[열기](figures/ari_comparison.png)|
|AMI|[열기](figures/ami_comparison.png)|
|NMI|[열기](figures/nmi_comparison.png)|
|MAJORITY_ACCURACY|[열기](figures/majority_accuracy_comparison.png)|
|MACRO_F1|[열기](figures/macro_f1_comparison.png)|
|WEIGHTED_F1|[열기](figures/weighted_f1_comparison.png)|

## 16개 실험의 군집과 원문

각 실험에는 전체 문항·실제 계층 분류·원래 분할·군집·대표라벨, 교차표/혼동행렬의 CSV/PNG와 라벨 코드 대응표가 있다. 큰 교차표는20라벨씩, 구성비는25군집씩 분할했다. 유형70 혼동행렬은 고해상도이며 라벨 코드는 바로 옆 대응표로 확인한다.

|조건|분류|거리|군집·원문·모델·설정|혼동행렬 CSV|라벨 코드|
|---|---|---|---|---|---|
|K0|과목|유클리드|[실험 안내](experiments/K0_curriculum_euclidean/README.md) · [군집 목록](experiments/K0_curriculum_euclidean/clusters.md)|[CSV](experiments/K0_curriculum_euclidean/confusion_matrix_all.csv)|[전체 경로](experiments/K0_curriculum_euclidean/label_key.csv)|
|K0|과목|코사인(구면)|[실험 안내](experiments/K0_curriculum_spherical/README.md) · [군집 목록](experiments/K0_curriculum_spherical/clusters.md)|[CSV](experiments/K0_curriculum_spherical/confusion_matrix_all.csv)|[전체 경로](experiments/K0_curriculum_spherical/label_key.csv)|
|K0|단원|유클리드|[실험 안내](experiments/K0_unit_euclidean/README.md) · [군집 목록](experiments/K0_unit_euclidean/clusters.md)|[CSV](experiments/K0_unit_euclidean/confusion_matrix_all.csv)|[전체 경로](experiments/K0_unit_euclidean/label_key.csv)|
|K0|단원|코사인(구면)|[실험 안내](experiments/K0_unit_spherical/README.md) · [군집 목록](experiments/K0_unit_spherical/clusters.md)|[CSV](experiments/K0_unit_spherical/confusion_matrix_all.csv)|[전체 경로](experiments/K0_unit_spherical/label_key.csv)|
|K0|세부단원|유클리드|[실험 안내](experiments/K0_subunit_euclidean/README.md) · [군집 목록](experiments/K0_subunit_euclidean/clusters.md)|[CSV](experiments/K0_subunit_euclidean/confusion_matrix_all.csv)|[전체 경로](experiments/K0_subunit_euclidean/label_key.csv)|
|K0|세부단원|코사인(구면)|[실험 안내](experiments/K0_subunit_spherical/README.md) · [군집 목록](experiments/K0_subunit_spherical/clusters.md)|[CSV](experiments/K0_subunit_spherical/confusion_matrix_all.csv)|[전체 경로](experiments/K0_subunit_spherical/label_key.csv)|
|K0|문제 유형|유클리드|[실험 안내](experiments/K0_type_euclidean/README.md) · [군집 목록](experiments/K0_type_euclidean/clusters.md)|[CSV](experiments/K0_type_euclidean/confusion_matrix_all.csv)|[전체 경로](experiments/K0_type_euclidean/label_key.csv)|
|K0|문제 유형|코사인(구면)|[실험 안내](experiments/K0_type_spherical/README.md) · [군집 목록](experiments/K0_type_spherical/clusters.md)|[CSV](experiments/K0_type_spherical/confusion_matrix_all.csv)|[전체 경로](experiments/K0_type_spherical/label_key.csv)|
|K1|과목|유클리드|[실험 안내](experiments/K1_curriculum_euclidean/README.md) · [군집 목록](experiments/K1_curriculum_euclidean/clusters.md)|[CSV](experiments/K1_curriculum_euclidean/confusion_matrix_all.csv)|[전체 경로](experiments/K1_curriculum_euclidean/label_key.csv)|
|K1|과목|코사인(구면)|[실험 안내](experiments/K1_curriculum_spherical/README.md) · [군집 목록](experiments/K1_curriculum_spherical/clusters.md)|[CSV](experiments/K1_curriculum_spherical/confusion_matrix_all.csv)|[전체 경로](experiments/K1_curriculum_spherical/label_key.csv)|
|K1|단원|유클리드|[실험 안내](experiments/K1_unit_euclidean/README.md) · [군집 목록](experiments/K1_unit_euclidean/clusters.md)|[CSV](experiments/K1_unit_euclidean/confusion_matrix_all.csv)|[전체 경로](experiments/K1_unit_euclidean/label_key.csv)|
|K1|단원|코사인(구면)|[실험 안내](experiments/K1_unit_spherical/README.md) · [군집 목록](experiments/K1_unit_spherical/clusters.md)|[CSV](experiments/K1_unit_spherical/confusion_matrix_all.csv)|[전체 경로](experiments/K1_unit_spherical/label_key.csv)|
|K1|세부단원|유클리드|[실험 안내](experiments/K1_subunit_euclidean/README.md) · [군집 목록](experiments/K1_subunit_euclidean/clusters.md)|[CSV](experiments/K1_subunit_euclidean/confusion_matrix_all.csv)|[전체 경로](experiments/K1_subunit_euclidean/label_key.csv)|
|K1|세부단원|코사인(구면)|[실험 안내](experiments/K1_subunit_spherical/README.md) · [군집 목록](experiments/K1_subunit_spherical/clusters.md)|[CSV](experiments/K1_subunit_spherical/confusion_matrix_all.csv)|[전체 경로](experiments/K1_subunit_spherical/label_key.csv)|
|K1|문제 유형|유클리드|[실험 안내](experiments/K1_type_euclidean/README.md) · [군집 목록](experiments/K1_type_euclidean/clusters.md)|[CSV](experiments/K1_type_euclidean/confusion_matrix_all.csv)|[전체 경로](experiments/K1_type_euclidean/label_key.csv)|
|K1|문제 유형|코사인(구면)|[실험 안내](experiments/K1_type_spherical/README.md) · [군집 목록](experiments/K1_type_spherical/clusters.md)|[CSV](experiments/K1_type_spherical/confusion_matrix_all.csv)|[전체 경로](experiments/K1_type_spherical/label_key.csv)|

## PCA는 표시용

원시 또는 L2 정규화된 전체265 입력에 각각 PCA를 맞췄다. 실제 군집화는 축소 전의 BoW 전체 활성차원에서 수행했다. 서로 다른 표현의 PCA 좌표 축을 직접 비교하지 않는다.

|조건|과목 유클리드|과목 코사인|단원 유클리드|단원 코사인|
|---|---|---|---|---|
|K0|[열기](projections/K0/figures/pca_curriculum_euclidean.png)|[열기](projections/K0/figures/pca_curriculum_spherical.png)|[열기](projections/K0/figures/pca_unit_euclidean.png)|[열기](projections/K0/figures/pca_unit_spherical.png)|
|K1|[열기](projections/K1/figures/pca_curriculum_euclidean.png)|[열기](projections/K1/figures/pca_curriculum_spherical.png)|[열기](projections/K1/figures/pca_unit_euclidean.png)|[열기](projections/K1/figures/pca_unit_spherical.png)|

[이번 연구 시작점](../README.md)
