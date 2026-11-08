# 직접 비교할 사례

선정은 이미 나온 결과를 설명하기 위한 관찰이다. 이 문항을 보고 모델을 다시 선택하거나 학습하지 않았다.

## 실제 문제 유형과 군집의 성공·혼합·분산

아래는 세부단원이 아닌 과목/단원/세부단원/유형 전체 경로를 비교한다. 학습에서 정한 대표 라벨을 그대로 쓰며 테스트 결과로 모델을 선택하지 않는다.

### type_euclidean

[이 실험의 모든 군집·문항](../01_clustering/experiments/type_euclidean/clusters.md)
- **일치 사례:** [diff_1_011](questions.md#diff_1_011)는 군집7에 배정되었고 실제 유형 `10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)`이 학습 대표 유형과 같다. 해당 학습 군집에서 이 유형은 6/6문항이다.
- **서로 다른 유형의 혼합:** 학습 군집21에는 5개 실제 유형이 섞였다. [trig_1_001](../../../data/processed/problems/trig_1_001.txt)의 `09 대수 / 05 삼각함수의 정의 / 01 일반각과 호도법 / 03 일반각과 호도법3 (두 동경의 위치관계)`과 [trig_1_002](../../../data/processed/problems/trig_1_002.txt)의 `09 대수 / 05 삼각함수의 정의 / 02 삼각함수의 정의 및 활용 / 01 정의1 (삼각함수의 뜻)`을 비교한다.
- **동일 유형의 분산:** `09 대수 / 06 삼각함수의 그래프 / 01 삼각함수의 그래프 / 04 그래프4 (표준형 그래프에서 Mm)`의 학습 12문항이 10개 군집으로 나뉘었다. [trig_1_015](../../../data/processed/problems/trig_1_015.txt)→군집3 · [trig_3_007](../../../data/processed/problems/trig_3_007.txt)→군집11 · [trig_2_013](../../../data/processed/problems/trig_2_013.txt)→군집16 · [trig_1_022](../../../data/processed/problems/trig_1_022.txt)→군집18 · [trig_3_005](../../../data/processed/problems/trig_3_005.txt)→군집24 · [trig_1_014](../../../data/processed/problems/trig_1_014.txt)→군집34 · [trig_1_017](../../../data/processed/problems/trig_1_017.txt)→군집55 · [trig_1_016](../../../data/processed/problems/trig_1_016.txt)→군집56 · [trig_2_015](../../../data/processed/problems/trig_2_015.txt)→군집60 · [trig_3_008](../../../data/processed/problems/trig_3_008.txt)→군집66.

### type_spherical

[이 실험의 모든 군집·문항](../01_clustering/experiments/type_spherical/clusters.md)
- **일치 사례:** [diff_1_011](questions.md#diff_1_011)는 군집7에 배정되었고 실제 유형 `10 미적분1 / 02 함수의 연속성 / 01 함수의 연속성 / 05 연속성5 (구간정의함수)`이 학습 대표 유형과 같다. 해당 학습 군집에서 이 유형은 8/8문항이다.
- **서로 다른 유형의 혼합:** 학습 군집29에는 6개 실제 유형이 섞였다. [diff_1_001](../../../data/processed/problems/diff_1_001.txt)의 `10 미적분1 / 01 함수의 극한 / 01 좌극한과 우극한 / 07 좌극한과 우극한7 (추론)`과 [diff_1_002](../../../data/processed/problems/diff_1_002.txt)의 `10 미적분1 / 01 함수의 극한 / 02 극한의 성질과 계산 / 01 극한의 성질을 이용한 연산`을 비교한다.
- **동일 유형의 분산:** `09 대수 / 06 삼각함수의 그래프 / 01 삼각함수의 그래프 / 04 그래프4 (표준형 그래프에서 Mm)`의 학습 12문항이 10개 군집으로 나뉘었다. [trig_1_015](../../../data/processed/problems/trig_1_015.txt)→군집3 · [trig_3_007](../../../data/processed/problems/trig_3_007.txt)→군집11 · [trig_2_013](../../../data/processed/problems/trig_2_013.txt)→군집16 · [trig_3_006](../../../data/processed/problems/trig_3_006.txt)→군집18 · [trig_3_005](../../../data/processed/problems/trig_3_005.txt)→군집24 · [trig_1_014](../../../data/processed/problems/trig_1_014.txt)→군집34 · [trig_1_017](../../../data/processed/problems/trig_1_017.txt)→군집55 · [trig_1_016](../../../data/processed/problems/trig_1_016.txt)→군집56 · [trig_2_015](../../../data/processed/problems/trig_2_015.txt)→군집60 · [trig_3_008](../../../data/processed/problems/trig_3_008.txt)→군집66.

세부단원 사례와 모든 라벨의 분산도는 [군집 분석](../01_clustering/analysis.md), [라벨 분산 CSV](../01_clustering/label_dispersion.csv)에 있다.

## 조건별 정오답이 바뀐 문항

- [diff_3_004](questions.md#diff_3_004): A=16 (정답) / B=32 (오답) / C=32 (오답)
- [diff_3_044](questions.md#diff_3_044): A=7 (정답) / B=7 (정답) / C=1 (오답)
- [trig_1_046](questions.md#trig_1_046): A=20 (정답) / B=20 (정답) / C=9 (오답)
- [trig_2_022](questions.md#trig_2_022): A=① (오답) / B=③ (정답) / C=③ (정답)
- [trig_3_034](questions.md#trig_3_034): A=⑤ (정답) / B=② (오답) / C=④ (오답)

## 벡터 정보와 정오답 변화 관찰

### 기본 조건 대비 예측 조건에서 개선된 것으로 보이는 사례

[trig_2_022](questions.md#trig_2_022)

위 사례 중 `trig_2_022`는 B와 C가 모두 정답이다. 예측 조건에서만 개선되었다는 뜻은 아니다.

### 예측 조건에서 악화된 것으로 보이는 사례

[diff_3_004](questions.md#diff_3_004) · [trig_3_034](questions.md#trig_3_034)

### 실제 해설 벡터에도 오답이 남은 사례

[diff_3_004](questions.md#diff_3_004) · [diff_3_044](questions.md#diff_3_044) · [trig_1_046](questions.md#trig_1_046) · [trig_3_034](questions.md#trig_3_034)

### 신규 C 풀이의 오류·불확실 사례

- [diff_1_038](questions.md#diff_1_038): inappropriate / derivative_notation_error / 원본 최종정오=True · 극값의 필요조건을 f(3)=0이라고 명시한 것은 틀리다. 실제 조건은 f′(3)=0이며 이후 계산은 올바르게 a=9,b=2,합11을 얻는다. 실제 f(3)=b=2이므로 오기를 포함한 거짓 중간 명제가 남아 있다. 최종답은 맞지만 풀이의 이 문장은 부정확하다.
- [diff_2_004](questions.md#diff_2_004): inappropriate / unjustified_special_case / 원본 최종정오=True · 첫 극한은 g와 f의 최고차항 계수 차가1임을 뜻하며 g의 계수가 반드시2이고 f가1이라는 결론은 나오지 않는다. 반례 f(x)=2x²,g(x)=3x²+2x−15는 첫 비율극한1과 h=g−f=(x−3)(x+5), h′(3)=8을 모두 만족한다. 이 근거 없는 특수화는 오류다. 다만 h의 계수1은 일반적으로 성립해 h(5)=20은 올바르다.
- [diff_2_024](questions.md#diff_2_024): inappropriate / intermediate_sign_error_later_recomputed / 원본 최종정오=True · 인수형으로 시작한 첫 계산에서 2(−4)(−2−k)를 8(−2−k)로 바꾸어 부호를 잘못 처리했다. 올바른 도함수값은32+8k이다. 뒤에서 일반 다항식으로 다시 계산해 정답35를 회복했지만, 잘못된 중간 계산 f(0)=6.2가 설명에 남아 있다. 최종 정답과 풀이 오류를 구분한다.
- [diff_3_004](questions.md#diff_3_004): inappropriate / extra_factor_wrong_answer / 원본 최종정오=False · 목표식은 [f/(x−1)]×[(x²−1)/g]와 이미 같다. 첫 변형의 (x+1)/(x+1)=1을 다음 줄에서 x+1로 바꿔 추가 인자2를 만들었다. 따라서32는 틀리고 올바른 극한은8×2=16이다.
- [diff_3_044](questions.md#diff_3_044): inappropriate / distinct_positive_root_count / 원본 최종정오=False · 서로 다른 양의 근이2개이려면 수평선 높이가 극솟값−8과0 사이여야 한다. −k=−8에서 x=3도 교점이라고 한 것은 f(3)=0과 모순이다. k=8일 때 다항식은2(x−2)²(x+1)로 양의 근은2 하나뿐이다. 올바른 조건0<k<8의 정수1~7이7개인데 답1을 냈다.
- [trig_1_013](questions.md#trig_1_013): inappropriate / incorrect_extremum_location / 원본 최종정오=True · 최종⑤7/3 및 최댓값1/2를 이용한 a=2는 맞지만, 각4π/3에서 cos가 최솟값−1이라는 문장은 거짓이다. cos(4π/3)=−1/2이며 구간 내 최솟값−1은 각π에서 달성한다. 답과 무관한 중간 수학 진술 오류를 분리 판정했다.
- [trig_1_043](questions.md#trig_1_043): inappropriate / incorrect_last_root_unjustified_conclusion / 원본 최종정오=True · 최종4는 맞지만 마지막 근을 ax=8aπ−α로 잘못 설정한다. 이 각의 사인은−sinα이므로 원래 방정식을 만족하지 않는다. 실제 마지막 근은 ax=(8a−1)π−α이며 두 극단 근의 합8π−π/a로4를 도출해야 한다. 응답은 모순 뒤 잘못된 식을 반복하고4를 근거 없이 선택한다.
- [trig_1_046](questions.md#trig_1_046): inappropriate / inequality_division_without_sign_cases / 원본 최종정오=False · cosθ<sinθ는 전체 구간에서 tanθ>1과 동치가 아니다. cosθ<0인 구간의 부등호 반전을 처리하지 않아 실제 해x=2,3,4,5,6 대신2,7을 선택하고 합9로 틀렸다. 올바른 각 구간은 π/4<θ<5π/4, 합은20이다.
- [trig_3_034](questions.md#trig_3_034): inappropriate / unsupported_maximum_after_incomplete_case_count / 원본 최종정오=False · n=6에서도 세 교점이 존재하는데 최대를5라 단정했다. F(x)=tan(πx)+(10/3)x는 세 구간에서 각각 엄격히 증가하며 치역이 [0,∞), 전체 실수, (−∞,20/3]이다. 따라서 자연수 n≤20/3이면 각 구간에 하나씩 있어 최대는6(⑤)이다. 응답은 n=6에서 x=2의 직선값−2/3까지 계산한 뒤 근거 없이5(④)로 결론내렸다. 최종 답과 풀이 모두 부적절하다.

근거는 [검토 JSON](../03_gemini/solution_review.json)의 실제 출력 인용과 해시를 확인한다. 최종 정오답과 별도인 AI 보조 판단이다.

`diff_3_004`의 실제 C 입력에는 정답16에 직접 연결되는 `latex:16` 빈도 2.0도 들어 있지만 최종 출력은 32다. 숫자 토큰의 존재와 올바른 수식 관계·풀이 순서의 생성은 같지 않다는 관찰 사례다. 토큰 때문에 오류가 생겼다는 인과 주장은 아니다.

이 변화만으로 빈도 토큰이 변화의 원인이었다고 확정할 수 없다. 풀이의 실제 인용과 수학적 검토를 함께 확인해야 한다.

## 이미 확인된 풀이 문제

- `diff_3_004`: 기본 풀이에는 잘못된 중간 등식이 있으나 최종16에 도달한 사례다. 예측 조건의 답32와 구분해 볼 수 있다.
- `diff_2_004`: 기본 풀이가 불가능한 중간 등식을 썼다가 뒤에서 다시 계산해 최종20에 도달한다. 최종 답 일치와 논리적 타당성은 다르다.
- `trig_2_022`: 기본 조건은 주기 안 해의 누락으로 π를 출력했고 기존 예측 조건은 2π를 출력했다. [문항](questions.md#trig_2_022)에서 원문과 각 요청·출력을 비교한다.
- `diff_3_005`: 기본 풀이의 로피탈 사용은 교과 범위 검토 대상으로 남긴다. 다른 풀이의 공식 교육과정 적합성은 단원명만 보고 확정하지 않았다.
- `trig_1_010`: 원본 정답표 충돌 때문에 두 채점 기준이 다른 문항이다. [충돌 근거](../../model_comparison_2026-11-07/03_Gemini비교/원본정답표_오류근거.json)를 먼저 읽는다.

기존 상세 AI 검토: [원래 검토·인용](../../model_comparison_2026-11-07/03_Gemini비교/AI보조_풀이검토.html). 사람의 검증된 확정 판정이 아니다.
