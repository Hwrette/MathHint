# 유클리드·코사인 군집화 비교

학습 185문항에서 중심과 군집의 대표 라벨을 만들고 고정 테스트 80문항에 적용했다. 과목은 curriculum을 사용하며 subject는 자료군이다.

[문항별 군집 배정](cluster_members.csv) · [군집별 라벨 비율](cluster_label_distribution.csv) · [실제 라벨의 분산도](label_dispersion.csv) · [분류 수](label_counts.csv)

ARI는 우연 일치를 보정한 군집 일치도, NMI는 분류와 군집이 공유하는 정보다. 다수 라벨 정확도는 학습 군집의 대표 라벨로 테스트 분류를 맞힌 비율이다.

| 분류 | 거리 | k | ARI | NMI | 학습 다수 라벨 정확도 | 점유 군집 |
|---|---|---:|---:|---:|---:|---:|
| 과목 | 유클리드 | 2 | 0.0967 | 0.1039 | 66.2% | 2 |
| 과목 | 코사인(구면) | 2 | 0.2404 | 0.1895 | 75.0% | 2 |
| 단원 | 유클리드 | 8 | 0.1479 | 0.4010 | 52.5% | 8 |
| 단원 | 코사인(구면) | 8 | 0.1470 | 0.4232 | 50.0% | 8 |
| 세부단원 | 유클리드 | 25 | 0.1932 | 0.5934 | 50.0% | 17 |
| 세부단원 | 코사인(구면) | 25 | 0.1972 | 0.6365 | 51.2% | 20 |
| 문제 유형 | 유클리드 | 70 | 0.1670 | 0.7804 | 31.2% | 34 |
| 문제 유형 | 코사인(구면) | 70 | 0.1507 | 0.7900 | 38.8% | 37 |

## 수치에서 확인한 사실

- 과목 테스트 ARI는 유클리드 0.0967, 구면 0.2404; NMI는 0.1039, 0.1895다.
- 단원 테스트 ARI는 유클리드 0.1479, 구면 0.1470; NMI는 0.4010, 0.4232다.
- 세부단원 테스트 ARI는 유클리드 0.1932, 구면 0.1972; NMI는 0.5934, 0.6365다.
- 문제 유형 테스트 ARI는 유클리드 0.1670, 구면 0.1507; NMI는 0.7804, 0.7900다.

## 해석과 한계

원시 빈도와 유클리드 거리는 문서 길이·전체 등장 횟수의 영향을 받을 수 있다. 구면 방식은 방향을 비교하므로 길이 영향을 줄이지만, 이번 비교 하나로 모든 차이의 원인을 길이로 확정할 수 없다.
유형 70개에 학습 185문항이므로 작은 군집이 많다. k가 커질 때 NMI가 높아지는 경향과 테스트에 나타나지 않은 라벨을 함께 고려해야 한다. 학습·테스트 점수 차이도 확인해야 한다.
5개 시드 중 각 방법의 학습 목적함수로만 결과를 선택했다. 두 방법의 목적함수 값은 단위와 의미가 다르므로 서로 비교하지 않는다. 테스트 지표로 시드나 k를 선택하지 않았다.
기존 테스트 성능을 관찰한 뒤 설계한 후속 비교이며, 전혀 보지 않은 독립 최종 평가로 주장하지 않는다.

## 직접 확인할 성공·혼합·분산 사례

사례는 결과를 읽기 위한 기술적 예시이며 통계적 일반화를 위한 별도 표본이 아니다.

### 유클리드 · 세부단원

[이 실험의 군집 문항·그림](experiments/subunit_euclidean/README.md)

- 학습 다수 라벨과 일치: [diff_1_011](../../../data/processed/problems/diff_1_011.txt) · 군집 7 · 실제 `10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성`. 학습 내 같은 라벨은 10/10문항이다. 이 사례가 전체 유형의 완전 분리를 뜻하지는 않는다.
- 서로 다른 라벨이 같은 군집: [diff_1_018](../../../data/processed/problems/diff_1_018.txt) · 실제 `10 미적분1 / 03 미분계수와 도함수 / 01 미분계수` · 군집 5의 학습 다수 `10 미적분1 / 05 함수의 증가와 감소 / 02 함수의 극대와 극소`.
  같은 군집의 학습 문항 [diff_1_031](../../../data/processed/problems/diff_1_031.txt)의 실제 라벨은 `10 미적분1 / 05 함수의 증가와 감소 / 02 함수의 극대와 극소`이다. 대표 라벨은 테스트 문항을 보지 않고 학습에서 정했다.
- 같은 라벨이 여러 군집으로 분산: `09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식` 학습 37문항이 11군집으로 나뉨. 예: [trig_1_038](../../../data/processed/problems/trig_1_038.txt)→13, [trig_1_040](../../../data/processed/problems/trig_1_040.txt)→18, [trig_1_041](../../../data/processed/problems/trig_1_041.txt)→23, [trig_1_044](../../../data/processed/problems/trig_1_044.txt)→5, [trig_1_045](../../../data/processed/problems/trig_1_045.txt)→18, [trig_1_047](../../../data/processed/problems/trig_1_047.txt)→4, [trig_1_048](../../../data/processed/problems/trig_1_048.txt)→0, [trig_2_021](../../../data/processed/problems/trig_2_021.txt)→18 외 29문항. 전체 ID와 군집은 [문항별 배정](cluster_members.csv), 분산 수치는 [분산도 표](label_dispersion.csv)에서 이 라벨로 확인한다.

### 코사인(구면) · 세부단원

[이 실험의 군집 문항·그림](experiments/subunit_spherical/README.md)

- 학습 다수 라벨과 일치: [diff_2_040](../../../data/processed/problems/diff_2_040.txt) · 군집 15 · 실제 `10 미적분1 / 06 방부등식과 직선운동 / 03 속도, 가속도와 미분`. 학습 내 같은 라벨은 8/8문항이다. 이 사례가 전체 유형의 완전 분리를 뜻하지는 않는다.
- 서로 다른 라벨이 같은 군집: [diff_1_018](../../../data/processed/problems/diff_1_018.txt) · 실제 `10 미적분1 / 03 미분계수와 도함수 / 01 미분계수` · 군집 23의 학습 다수 `09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식`.
  같은 군집의 학습 문항 [trig_1_044](../../../data/processed/problems/trig_1_044.txt)의 실제 라벨은 `09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식`이다. 대표 라벨은 테스트 문항을 보지 않고 학습에서 정했다.
- 같은 라벨이 여러 군집으로 분산: `09 대수 / 06 삼각함수의 그래프 / 03 삼각방정식과 부등식` 학습 37문항이 12군집으로 나뉨. 예: [trig_1_038](../../../data/processed/problems/trig_1_038.txt)→13, [trig_1_040](../../../data/processed/problems/trig_1_040.txt)→16, [trig_1_041](../../../data/processed/problems/trig_1_041.txt)→9, [trig_1_044](../../../data/processed/problems/trig_1_044.txt)→23, [trig_1_045](../../../data/processed/problems/trig_1_045.txt)→16, [trig_1_047](../../../data/processed/problems/trig_1_047.txt)→0, [trig_1_048](../../../data/processed/problems/trig_1_048.txt)→21, [trig_2_021](../../../data/processed/problems/trig_2_021.txt)→16 외 29문항. 전체 ID와 군집은 [문항별 배정](cluster_members.csv), 분산 수치는 [분산도 표](label_dispersion.csv)에서 이 라벨로 확인한다.

### 유클리드 · 문제 유형

[이 실험의 군집 문항·그림](experiments/type_euclidean/README.md)

- 학습 다수 라벨과 일치: [diff_1_011](../../../data/processed/problems/diff_1_011.txt) · 군집 7 · 실제 `10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)`. 학습 내 같은 라벨은 6/6문항이다. 이 사례가 전체 유형의 완전 분리를 뜻하지는 않는다.
- 서로 다른 라벨이 같은 군집: [diff_1_005](../../../data/processed/problems/diff_1_005.txt) · 실제 `10 미적분1 / 01 함수의 극한 / 03 극한식의 해석 / 04 해석4 (함수 구하기. 인수정리)` · 군집 65의 학습 다수 `10 미적분1 / 01 함수의 극한 / 03 극한식의 해석 / 03 해석3 (함수 구하기. 차수 결정)`.
  같은 군집의 학습 문항 [diff_2_002](../../../data/processed/problems/diff_2_002.txt)의 실제 라벨은 `10 미적분1 / 01 함수의 극한 / 03 극한식의 해석 / 03 해석3 (함수 구하기. 차수 결정)`이다. 대표 라벨은 테스트 문항을 보지 않고 학습에서 정했다.
- 같은 라벨이 여러 군집으로 분산: `09 대수 / 06 삼각함수의 그래프 / 01 삼각함수의 그래프 / 04 그래프4 (표준형 그래프에서 Mm)` 학습 12문항이 10군집으로 나뉨. 예: [trig_1_014](../../../data/processed/problems/trig_1_014.txt)→34, [trig_1_015](../../../data/processed/problems/trig_1_015.txt)→3, [trig_1_016](../../../data/processed/problems/trig_1_016.txt)→56, [trig_1_017](../../../data/processed/problems/trig_1_017.txt)→55, [trig_1_019](../../../data/processed/problems/trig_1_019.txt)→56, [trig_1_022](../../../data/processed/problems/trig_1_022.txt)→18, [trig_2_013](../../../data/processed/problems/trig_2_013.txt)→16, [trig_2_015](../../../data/processed/problems/trig_2_015.txt)→60 외 4문항. 전체 ID와 군집은 [문항별 배정](cluster_members.csv), 분산 수치는 [분산도 표](label_dispersion.csv)에서 이 라벨로 확인한다.

### 코사인(구면) · 문제 유형

[이 실험의 군집 문항·그림](experiments/type_spherical/README.md)

- 학습 다수 라벨과 일치: [diff_1_011](../../../data/processed/problems/diff_1_011.txt) · 군집 7 · 실제 `10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)`. 학습 내 같은 라벨은 8/8문항이다. 이 사례가 전체 유형의 완전 분리를 뜻하지는 않는다.
- 서로 다른 라벨이 같은 군집: [diff_1_005](../../../data/processed/problems/diff_1_005.txt) · 실제 `10 미적분1 / 01 함수의 극한 / 03 극한식의 해석 / 04 해석4 (함수 구하기. 인수정리)` · 군집 29의 학습 다수 `10 미적분1 / 01 함수의 극한 / 03 극한식의 해석 / 03 해석3 (함수 구하기. 차수 결정)`.
  같은 군집의 학습 문항 [diff_1_003](../../../data/processed/problems/diff_1_003.txt)의 실제 라벨은 `10 미적분1 / 01 함수의 극한 / 03 극한식의 해석 / 03 해석3 (함수 구하기. 차수 결정)`이다. 대표 라벨은 테스트 문항을 보지 않고 학습에서 정했다.
- 같은 라벨이 여러 군집으로 분산: `09 대수 / 06 삼각함수의 그래프 / 01 삼각함수의 그래프 / 04 그래프4 (표준형 그래프에서 Mm)` 학습 12문항이 10군집으로 나뉨. 예: [trig_1_014](../../../data/processed/problems/trig_1_014.txt)→34, [trig_1_015](../../../data/processed/problems/trig_1_015.txt)→3, [trig_1_016](../../../data/processed/problems/trig_1_016.txt)→56, [trig_1_017](../../../data/processed/problems/trig_1_017.txt)→55, [trig_1_019](../../../data/processed/problems/trig_1_019.txt)→56, [trig_1_022](../../../data/processed/problems/trig_1_022.txt)→56, [trig_2_013](../../../data/processed/problems/trig_2_013.txt)→16, [trig_2_015](../../../data/processed/problems/trig_2_015.txt)→60 외 4문항. 전체 ID와 군집은 [문항별 배정](cluster_members.csv), 분산 수치는 [분산도 표](label_dispersion.csv)에서 이 라벨로 확인한다.

