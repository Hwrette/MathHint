# 전체 265문항 K-means · 탐색 실험 B

**실험 A(기존 분리)**는 185문항으로 중심과 대표 라벨을 정하고 별도 테스트 80문항을 평가했다. **실험 B(이 폴더)**는 전체 265문항으로 중심과 대표 라벨을 정하고 같은 265문항을 관찰한다. 따라서 B의 점수가 높더라도 새로운 문제에 대한 일반화 성능이 개선됐다는 뜻이 아니다.

## 확인 순서

1. [ARI·NMI 요약](summary.csv)와 [기존 테스트 비교표](comparison_with_holdout.csv)를 본다.
2. 아래 표에서 분류 수준·거리 방식의 군집별 실제 문제를 연다.
3. [혼합·동일 유형 분산 사례](analysis.md#문항을-직접-읽는-관찰-사례)를 원문과 비교한다.
4. 각 실험 안내에서 교차표·혼동행렬·구성비·PCA를 확인한다.

문항 ID 링크는 기존 [수식 읽기 화면](../../03_gemini/report.html)의 해당 문제로 이동한다. 화면에 표시되는 학습/테스트와 A/B/C는 기존 연구의 출처 정보이며, 이 군집화의 학습 구분이 아니다. 추가 Gemini 호출은 없다.

## 핵심 수치 · 평가 범위를 구분해서 읽기

|분류 수준|거리 방식|기존 테스트 80 ARI|전체 265 ARI|기존 테스트 80 NMI|전체 265 NMI|
|---|---|---:|---:|---:|---:|
|과목|유클리드|0.096741|0.094820|0.103918|0.091713|
|과목|코사인(구면)|0.240409|0.339623|0.189496|0.272621|
|단원|유클리드|0.147941|0.213871|0.401007|0.385410|
|단원|코사인(구면)|0.146974|0.224111|0.423195|0.419235|
|세부단원|유클리드|0.193247|0.234335|0.593365|0.537225|
|세부단원|코사인(구면)|0.197151|0.230153|0.636467|0.558116|
|문제 유형|유클리드|0.167027|0.142868|0.780388|0.698617|
|문제 유형|코사인(구면)|0.150731|0.206329|0.789955|0.724463|

ARI는 우연 일치를 보정한 군집/실제 분류의 일치도, NMI는 두 분류의 정보 공유 정도다. 군집 번호는 임의 번호이며 실제 유형 번호처럼 비교하지 않는다. 전체 자료의 군집 최빈 라벨 일치율은 `summary.csv`의 `full_majority_match_rate`이며 동일 자료에서 계산한 설명용 보조 지표다.

[전체265 ARI 그림](figures/ari_comparison_full.png) · [전체265 NMI 그림](figures/nmi_comparison_full.png) · [기존 테스트/전체자료 범위 비교 그림](figures/comparison_with_holdout.png)

## 8개 실험 · 문제 목록과 그림

|분류 수준 · k|유클리드|코사인(구면)|
|---|---|---|
|과목 · 2|[안내·그림](experiments/curriculum_euclidean/README.md) · [군집별 문제](experiments/curriculum_euclidean/clusters.md) · [혼동행렬](experiments/curriculum_euclidean/figures/confusion_matrix_all.png)|[안내·그림](experiments/curriculum_spherical/README.md) · [군집별 문제](experiments/curriculum_spherical/clusters.md) · [혼동행렬](experiments/curriculum_spherical/figures/confusion_matrix_all.png)|
|단원 · 8|[안내·그림](experiments/unit_euclidean/README.md) · [군집별 문제](experiments/unit_euclidean/clusters.md) · [혼동행렬](experiments/unit_euclidean/figures/confusion_matrix_all.png)|[안내·그림](experiments/unit_spherical/README.md) · [군집별 문제](experiments/unit_spherical/clusters.md) · [혼동행렬](experiments/unit_spherical/figures/confusion_matrix_all.png)|
|세부단원 · 25|[안내·그림](experiments/subunit_euclidean/README.md) · [군집별 문제](experiments/subunit_euclidean/clusters.md) · [혼동행렬](experiments/subunit_euclidean/figures/confusion_matrix_all.png)|[안내·그림](experiments/subunit_spherical/README.md) · [군집별 문제](experiments/subunit_spherical/clusters.md) · [혼동행렬](experiments/subunit_spherical/figures/confusion_matrix_all.png)|
|문제 유형 · 70|[안내·그림](experiments/type_euclidean/README.md) · [군집별 문제](experiments/type_euclidean/clusters.md) · [혼동행렬](experiments/type_euclidean/figures/confusion_matrix_all.png)|[안내·그림](experiments/type_spherical/README.md) · [군집별 문제](experiments/type_spherical/clusters.md) · [혼동행렬](experiments/type_spherical/figures/confusion_matrix_all.png)|

## 원자료와 계산 기준

- [전체 문항 배정](cluster_members.csv): 기존 출처 분할은 `original_split`로 보존한다.
- [군집별 실제 라벨 빈도·비율](cluster_label_distribution.csv) · [실제 분류의 군집 분산](label_dispersion.csv)
- [실험 설정·입력 해시](config.json): 고정 346차원 어휘, 42~46 시드, 재시작 5회, 최대 100회, 기존 수렴 기준.
- 각 실험의 `model.pt`, `experiment.json`에 최적 학습 목적함수·중심·배정·선택 시드와 재현 근거를 남긴다.

교차표 히트맵은 **실제 분류 × 군집 번호**를 보여 준다. 혼동행렬은 전체 265문항의 군집별 최빈 라벨을 예측 분류로 대응한 **실제 분류 × 대응 분류**다. 후자는 같은 자료로 대표 라벨을 만들고 평가한 설명용이며 테스트 정확도가 아니다.

## PCA · 표시용 2차원 투영

|표시 분류|유클리드 원시 빈도 공간|코사인 L2 정규화 공간|
|---|---|---|
|과목|[실제 분류·군집 PCA](figures/pca_curriculum_euclidean.png)|[실제 분류·군집 PCA](figures/pca_curriculum_spherical.png)|
|단원|[실제 분류·군집 PCA](figures/pca_unit_euclidean.png)|[실제 분류·군집 PCA](figures/pca_unit_spherical.png)|

PCA는 전체 265문항에서 맞춘 2차원 표시용 투영이다. K-means 자체는 고정된 346차원 입력에서 학습했다. 원시 빈도와 L2 정규화 표현의 PCA는 각각의 표시 공간이며 좌표를 직접 비교하지 않는다.

기존 모델·배정·지표·원본 데이터·어휘·회귀·Gemini 결과는 이 탐색 실험에서 변경하지 않는다.

## 실행과 재사용

프로젝트 루트에서 `python -m mathhint_learning.full_dataset_265`를 실행한다. 이 탐색 폴더에만 결과를 저장하며, 같은 입력·설정의 완료 산출물이 있으면 파일 해시를 검증하고 재학습 없이 반환한다. 알고리즘은 기존 `TorchKMeans.py`를 공통으로 사용하고 이 실험의 데이터 결합·평가·저장 절차만 별도 패키지에 둔다. Gemini 호출과 회귀 학습은 포함하지 않는다.
