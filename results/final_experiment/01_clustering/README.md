# 군집화 결과

먼저 [전체 비교표](summary.csv)와 [해석·사례](analysis.md)를 보고, [문항별 군집 배정](cluster_members.csv)을 실험명·군집 번호로 필터링하세요.

- [ARI 비교](figures/ari_comparison.png), [NMI 비교](figures/nmi_comparison.png)
- [분류별 문항 수](label_counts.csv), [군집별 실제 라벨 빈도·비율](cluster_label_distribution.csv)
- [동일 분류의 군집 분산도](label_dispersion.csv)

| 분류 | 유클리드 | 코사인(구면) |
|---|---|---|
| 과목 | [군집 문항·교차표·그림](experiments/curriculum_euclidean/README.md) | [군집 문항·교차표·그림](experiments/curriculum_spherical/README.md) |
| 단원 | [군집 문항·교차표·그림](experiments/unit_euclidean/README.md) | [군집 문항·교차표·그림](experiments/unit_spherical/README.md) |
| 세부단원 | [군집 문항·교차표·그림](experiments/subunit_euclidean/README.md) | [군집 문항·교차표·그림](experiments/subunit_spherical/README.md) |
| 문제 유형 | [군집 문항·교차표·그림](experiments/type_euclidean/README.md) | [군집 문항·교차표·그림](experiments/type_spherical/README.md) |

`config.json`은 입력 해시와 공통 설정, 각 실험의 `experiment.json`은 모든 시드의 학습 목적함수·선택 결과, `model.pt`는 중심과 학습 ID를 보존한다. `manifest.json`은 산출물 무결성 검사 목록이다.
PCA는 학습 자료에서만 맞춘 표시용 2차원 투영이다. 군집화 자체는 원래 346차원에서 수행했다. 원시 빈도와 L2 정규화 공간은 별도로 투영했으며 서로 다른 PCA 좌표를 직접 비교하지 않는다.
