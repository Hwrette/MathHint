# 문제 → 원본 풀이 예측의 공통 데이터

[2차 연구 목차](../README.md)

|구분|결과|
|---|---:|
|기존 불용어 제거 문제 입력|270차원, 그대로 재사용|
|전체265 원본 풀이 어휘|462개|
|사용자 풀이 불용어|103개|
|실제 제거 후 풀이 타깃|359차원|
|원래 학습 / 테스트|185 / 80|
|학습 내부 fit / validation|148 / 37|
|풀이 TF 제거 전 / 후|59,408 / 27,949|
|풀이 영벡터|0개|

문제 벡터는 군집화에서 완성한 원시 정수 빈도를 읽기만 했다. 원본 풀이265개만 원래 Kiwi·LaTeX 함수로 새로 토큰화했다. 사용자103개 외 토큰은 제거하지 않았다. 문제와 풀이 어휘·인덱스는 독립이다.

검증은 기존 학습185 안에서 과목/단원으로 층화한148/37(시드42)이다. 모델 선택의 주 지표는 **검증 Precision@20**, 동률이면 음수 보정 MSE, 단순한 모델/사전 후보 순서다. 양의 빈도만 내림차순, 동률 어휘 인덱스 순으로20개를 선택한다. P@20의 분모는20, Recall의 분모는 실제 선택된 최대20개 수다. 테스트 타깃은 모델 확정 후에만 읽는 로더 옵션으로 분리했다.

전체265의 어휘와 테스트 원본 풀이의 단어 존재를 미리 알고 있는 전이적 실험이다. 가중치·검증 최적화에 테스트를 넣지 않았다는 사실과 완전히 독립적인 미관측 평가라는 주장을 구분한다. 학습에서 한 번도 나타나지 않은 타깃 토큰은 어휘에 있어도 해당 빈도를 배울 직접 사례가 없다. 기존 문제필터에서 동일벡터가 된 diff_1_007/train·diff_1_011/test도 원래 분할 그대로 보존한다.

- [요약](summary.json) · [설정·입력/불용어 SHA와 선택 정책](config.json)
- [전체 풀이 어휘·제거/유지·원시↔활성 인덱스·TF/DF](solution_token_mapping.csv)
- [승인 목록 실제 적용](stopword_audit.csv) · [기존 좌표 재계수265행](recount_validation.csv)
- [문항별 빈도 감소](question_token_counts.csv) · [원래·내부 분할](generated_data/splits.json)
- [불변 문제 입력 참조](generated_data/input_reference.json) · [준비 파일 SHA](manifest.json)

```bash
python -m mathhint_learning.final_experiment_2.solution_data prepare
python -m mathhint_learning.final_experiment_2.solution_data verify
```

prepare는 완료된 동일 입력을 검증해 재사용한다. verify는 저장 자료만 읽으며 모델 학습·토큰화·API 호출이 없다.
