# 데이터 안내

현재 활성 자료는 `raw/`의 HML6개, 총265문항이다. 이전 HWPX와 이전 풀이 결과는 제거했다.

- `processed/annotated/`: 단원·유형·출처와 문제·정답을 함께 확인하는 파일.
- `processed/problems/`, `processed/solutions/`: 각각 문제 본문, 원본 정답·해설만 저장한 벡터 입력.
- `processed/metadata.json`: 문항 ID에 연결된 분류·출처·수식 변환 정보.
- `processed/splits/`: 학습185개·테스트80개의 고정 ID목록 및 단원·유형별 분할 보고서.
- `vectors/`: 문제·정답 영역별로 학습에서 만든 어휘와 학습/테스트 벡터.
- `provenance/`: 삭제 문항, 원래 번호 대조, 검증한 수식 전사표.

`diff_3_017`은 삭제 전 원래17번이며 현재 HML16번이다. 삭제한 `diff_3_016`은 결과에 없다. ID는 모든 파일과 JSON에서 동일하다.

생성 명령과 각 단계 설명은 루트 README를 참고한다.

## 정답표 정정 원칙 (2026-11-11)

원본 HML과 `processed/`는 변인 통제·출처 보존을 위해 변경하지 않는다. 검증된 답안 충돌 `trig_1_010` (원본 ④, 실제 ② = 9/5)은 [정정 레지스트리](curation/answer_key_corrections.json)에 기록되어 있다. [265문항 검토 기록](../docs/answer_key_audit_2026-11-11.md)과 `results/final_experiment_2/*/key_corrected/`의 정정 기준 결과를 읽는다.
