# 군집화 결과

<!-- clustering-additions:start -->
## 실험 선택

| 실험 | 목적과 평가 대상 | 먼저 볼 자료 |
|---|---|---|
| **A — 학습·테스트 분리 (기존)** | 학습185문항으로 중심·대표 라벨을 정하고 테스트80문항에 적용 | [기존 ARI·NMI 표](summary.csv) · [ARI 그림](figures/ari_comparison.png) · [NMI 그림](figures/nmi_comparison.png) · [군집 사례](analysis.md) |
| **B — 전체 데이터 탐색 (추가)** | 전체265문항으로 중심·대표 라벨을 정하고 같은265문항의 구조를 설명 | [전체265 안내](full_dataset_265/README.md) · [전체 ARI·NMI 표](full_dataset_265/summary.csv) · [기존 테스트와 비교](full_dataset_265/comparison_with_holdout.csv) · [혼합·분산 사례](full_dataset_265/analysis.md) |

권장 순서는 실험 선택 → ARI·NMI 비교 → 군집별 실제 문항 → 혼합 사례 → 혼동행렬이다. **B의 점수는 새로운 문항에 대한 일반화 성능이 아니다.** 기존 A의 수치를 B의 결과로 바꾸지 않았다.

실험별 실행 코드는 `mathhint_learning/holdout/`와 `mathhint_learning/full_dataset_265/`로 분리했다. 공통 K-means는 `TorchKMeans.py` 한곳에서 관리한다. 기존 `python -m mathhint_learning.FinalClustering` 명령과 import는 호환 진입점으로 유지하며, 새 분리 실험 명령은 `python -m mathhint_learning.holdout`, 전체 탐색 명령은 `python -m mathhint_learning.full_dataset_265`다. 완료 결과는 입력·설정·산출물 해시가 같으면 재학습 없이 읽는다.

### A의 테스트 혼동행렬 8개

각 실험 README에서 기존 교차표·문항 목록과 함께 확인할 수 있다. 아래는 테스트80문항의 혼동행렬 이미지 직접 링크다.

| 분류 | 유클리드 | 코사인(구면) |
|---|---|---|
| 과목 | [혼동행렬](experiments/curriculum_euclidean/figures/confusion_matrix_test.png) | [혼동행렬](experiments/curriculum_spherical/figures/confusion_matrix_test.png) |
| 단원 | [혼동행렬](experiments/unit_euclidean/figures/confusion_matrix_test.png) | [혼동행렬](experiments/unit_spherical/figures/confusion_matrix_test.png) |
| 세부단원 | [혼동행렬](experiments/subunit_euclidean/figures/confusion_matrix_test.png) | [혼동행렬](experiments/subunit_spherical/figures/confusion_matrix_test.png) |
| 문제 유형 | [혼동행렬](experiments/type_euclidean/figures/confusion_matrix_test.png) | [혼동행렬](experiments/type_spherical/figures/confusion_matrix_test.png) |

기존 교차표는 **실제 분류 × 군집 번호**, 새 혼동행렬은 **실제 분류 × 군집 대표 라벨로 대응한 분류**다. A의 대표 라벨은 학습185문항으로만 정한다. 전체 계층 라벨2/8/25/70을 같은 행·열 순서로 남겨 테스트에 없는 분류도 0행·0열로 표시한다. 전체 경로는 각 실험의 `label_key.csv`, 합계·대각·미등장 분류 검증은 [혼동행렬 검증](confusion_matrix_validation.json)에 있다. B의 혼동행렬은 전체265에서 정한 대표 라벨을 쓰는 설명용 자료로 별도 구분한다.

## A — 기존 분리 실험의 문항·교차표
<!-- clustering-additions:end -->

먼저 [전체 비교표](summary.csv)와 [해석·사례](analysis.md)를 보고, [문항별 군집 배정](cluster_members.csv)을 실험명·군집 번호로 필터링하세요.

문항 목록의 ID는 수식·Markdown 읽기 화면으로 연결됩니다. 학습 문항은 생성 실험 대상 아님으로 표시하고, 저장된 원문은 별도 링크에서 확인할 수 있습니다.

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
