# η² 순위표 · 전체 346개 문제 토큰

**분류를 선택한 뒤 원시·정규화 순위를 비교하세요.** 각 문서에서 상위30개를 먼저 보고, 접힌 영역을 펼치면 전체346개를 확인할 수 있다. GitHub 파일 페이지에서 바로 읽으며, 별도 프로그램이나 CSV 다운로드가 필요 없다. 좁은 화면에서는 표를 좌우로 밀어 나머지 열을 읽는다.

|분류 수준|원시 BoW η² 내림차순|L2 정규화 η² 내림차순|
|---|---|---|
|과목|[원시 순위](curriculum.md#raw-ranking)|[정규화 순위](curriculum.md#normalized-ranking)|
|단원|[원시 순위](unit.md#raw-ranking)|[정규화 순위](unit.md#normalized-ranking)|
|세부단원|[원시 순위](subunit.md#raw-ranking)|[정규화 순위](subunit.md#normalized-ranking)|
|문제 유형|[원시 순위](type.md#raw-ranking)|[정규화 순위](type.md#normalized-ranking)|

두 표 모두 **원시 η²·정규화 η²·학습 DF·의미**를 나란히 표시한다. 소수점4자리는 표시용이며, 저장된 CSV와 내부 정렬 값의 정밀도는 바꾸지 않았다. 같은 표시값이라도 반올림 전 값이 다르면 순서가 다를 수 있고, 완전 동점은 기존 어휘 인덱스 순서다. 정의되지 않은 η²는 —로 표시해 맨 아래에 둔다.

분석 대상은 기존 학습185문항의 문제 어휘346개다. 과목은 curriculum이며, 단원·세부단원·유형은 기존 상위 분류를 포함한 계층 경로를 사용한 통계를 그대로 읽었다. subject 자료군과 혼동하지 않는다.

η²가 낮다는 이유로 불용어를 자동 선정하지 않는다. 높은 값도 수학적 중요성을 확정하지 않으며, 유형70개 중43개는 학습 문항1개뿐이므로 소집단·희귀 토큰의 높은 값에 주의한다. 원시·정규화 η²는 분류 연관성이며 K-means ARI나 정답률이 아니다. [조정η²·DF·정보 손실을 함께 보는 안내](../README.md)를 참고한다.

## 출처와 다시 만들기

[전체 토큰·인덱스·DF·의미](../all_tokens.csv) · [원시 η²](../variance_by_classification.csv) · [핵심 통계표](../key_token_statistics.csv) · [정규화 η²](../../04_distance_comparison/normalized_eta_comparison.csv)

저장소 루트에서 다음 명령은 기존 CSV를 읽어 이 Markdown5개만 재생성한다. 통계 재계산·모델 학습·API 호출·불용어 적용은 없다.

```bash
python -m mathhint_analysis.token_analysis.eta_rankings
```

[토큰 분석 처음으로](../../README.md) · [문제 토큰 안내](../README.md)
