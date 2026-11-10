# 문제·풀이 토큰 η² · 학습+테스트 전체265문항

기존 학습185문항과 테스트80문항을 합친 **전체265문항**의 탐색 통계다. 기존 학습 전용 η²나 모델 평가 결과를 바꾸지 않았다.

여기서 풀이는 **원본 풀이·해설**의 `data/vectors/solutions/` 빈도 벡터다. Gemini 생성 응답의 토큰 통계가 아니다.

**문제와 풀이를 각각 선택하세요.** 각 분류에 원시·L2 정규화 순위를 모두 제공하며, 상위30개 아래에서 전체 목록을 펼칠 수 있다.

|영역|토큰 수|과목|단원|세부단원|문제 유형|
|---|---:|---|---|---|---|
|[문제 안내](01_problem_tokens/README.md)|346|[원시](01_problem_tokens/curriculum.md#raw-ranking) · [정규화](01_problem_tokens/curriculum.md#normalized-ranking)|[원시](01_problem_tokens/unit.md#raw-ranking) · [정규화](01_problem_tokens/unit.md#normalized-ranking)|[원시](01_problem_tokens/subunit.md#raw-ranking) · [정규화](01_problem_tokens/subunit.md#normalized-ranking)|[원시](01_problem_tokens/type.md#raw-ranking) · [정규화](01_problem_tokens/type.md#normalized-ranking)|
|[풀이 안내](02_solution_tokens/README.md)|431|[원시](02_solution_tokens/curriculum.md#raw-ranking) · [정규화](02_solution_tokens/curriculum.md#normalized-ranking)|[원시](02_solution_tokens/unit.md#raw-ranking) · [정규화](02_solution_tokens/unit.md#normalized-ranking)|[원시](02_solution_tokens/subunit.md#raw-ranking) · [정규화](02_solution_tokens/subunit.md#normalized-ranking)|[원시](02_solution_tokens/type.md#raw-ranking) · [정규화](02_solution_tokens/type.md#normalized-ranking)|

표의 **전체 DF**는265문항 중 등장 문항 수이며, TF(등장 횟수)와 다르다. 두 영역의 어휘와 의미·DF는 서로 독립적으로 관리한다. 문제 토큰346개와 풀이 토큰431개를 하나의 순위로 섞지 않았다.

## 계산 범위와 정의

원시 BoW는 기존 정수 빈도 그대로, 정규화 BoW는 문항별 L2 정규화 좌표다. 각 표현에서 전체265문항의 평균을 기준으로 다음을 계산했다.

- 전체 분산 T = Σᵢ(xᵢ−μ)² / 265.
- 집단 간 분산 B = Σɢ nɢ(μɢ−μ)² / 265, 집단 내 분산 W = ΣɢΣᵢ∈ɢ(xᵢ−μɢ)² / 265.
- T = B + W이고 η² = B/T다. T=0이면 η²는 정의되지 않음으로 남긴다.
- 조정η² = 1−(1−η²)(265−1)/(265−g). g는 해당 계층의 집단 수이며, 음수 보조 값도 그대로 보존한다.

학습185와 테스트80을 ID에 맞춰 연결한 뒤 전체 통계를 계산했다. 풀이 토큰에도 해당 문제의 실제 과목·단원·세부단원·유형을 사용했다. 기존 분할 파일이나 어휘를 변경하지 않았고, 순위는 표시 전 정밀도로 정렬했다. 과목은 curriculum, 하위 분류는 상위 경로를 포함하며 subject 자료군과 구분한다.

|분류|전체 집단 수|문항1개 집단 수|
|---|---:|---:|
|과목|2|0|
|단원|8|0|
|세부단원|25|6|
|문제 유형|70|28|

[분류별 학습·테스트·전체 문항 수](class_labels.csv) · [문제 통계 CSV](01_problem_tokens/eta_statistics.csv) · [풀이 통계 CSV](02_solution_tokens/eta_statistics.csv)

각 영역의 영벡터 수는 문제0·풀이0다. 기존 학습 어휘 밖 테스트 토큰은 문제29회·풀이48회 제외된 상태를 유지했다. 해당 토큰을 추가하거나 원문을 다시 토큰화하지 않았다.

## 이전 자료와의 구분

[기존 학습185문항의 문제 η² 순위표](../01_problem_tokens/eta_rankings/README.md)는 그대로 보존했다. 현재 폴더는 **전체265문항의 문제·풀이 η²**이며, 학습 전용 결과의 수치를 덮어쓰지 않았다.

η²가 낮다고 불용어가 되거나 높다고 수학적으로 중요한 토큰이 되는 것은 아니다. 의미와 제거 시 잃는 정보는 사용자가 판단한다. 이 값은 K-means ARI·정답률이나 풀이의 정확도도 아니다.

전체 자료의 유형은 70개이며 그중 28개는 문항1개뿐이다. 집단 수가 많거나 토큰 DF가 작으면 높은 η²를 과대해석하기 쉽다. CSV의 조정η²·DF·집단 크기도 함께 확인한다.

이 표는 **테스트 문항의 실제 분류도 포함**한다. 이 표를 참고해 토큰을 선택한 뒤 같은 테스트에서 평가한다면 완전히 독립적인 최종 평가라고 할 수 없다. 이번에는 불용어 선정·제거·모델 학습·Gemini 호출을 하지 않았다.

## 실행과 검증

```bash
python -m mathhint_analysis.token_analysis.full_dataset_eta analyze
python -m mathhint_analysis.token_analysis.full_dataset_eta report
python -m mathhint_analysis.token_analysis.full_dataset_eta verify
```

analyze는 고정 벡터로 이 폴더의 통계를 생성하고, report는 저장 CSV로 Markdown만 다시 만든다. verify는 저장값과 입력·산출물의 무결성을 확인한다. 세 명령 모두 모델 학습·Gemini 호출·불용어 적용을 하지 않는다.

[설정·입력 출처](config.json) · [검증 기록](validation.json) · [토큰 분석 처음으로](../README.md)
