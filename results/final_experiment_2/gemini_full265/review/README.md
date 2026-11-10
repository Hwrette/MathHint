# 풀이 과정 검토 상태

[전체 응답별 상태](status.csv) · [상태별 개수](summary.json) · [문항 화면](../report.html)

최종 답은 기존 보수적 자동채점기로 비교한다. **최종 답이 맞아도 풀이가 타당하다고 판정하지 않는다.**
새 응답의 수학적 단계를 충분히 검증하지 못한 경우 `deferred`(검토 보류)다. 미실행 풀이에는 `not_generated`를 쓴다.
과거 A 응답과 문제·입력·출력이 완전히 같은 경우에만 과거 AI 보조 검토를 연결한다. 사람의 확정 판정으로 승격하지 않는다.
새 B/C/D에 과거 검토를 옮기지 않는다. 문장이 원본과 다르다는 사실만으로 오류라고 판단하지 않는다.

추가 검토 API는 호출하지 않았다. 후속 직접 검토는 선택적으로 `curated_reviews.json`의 records 배열에
id/condition/response_sha256/review_status/math_status/reason/error_step/evidence_quotes/reviewer_type/human_confirmed를 기록할 수 있다.
`confirmed_error`에는 응답에 실제 존재하는 인용, 잘못된 단계, 수학적 근거가 모두 필요하다. 응답 SHA나 인용이 맞지 않으면 보고서 생성을 중단한다.

전체265 실험의 기존 테스트80 A/B/C/D 검토는 동일 응답 SHA와 실제 인용이 일치한320개만 출처를 보존해 재사용한다. 이 검토를 새 학습185 응답에 자동 복사하지 않는다.
