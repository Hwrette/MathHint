# 취소된 작업 체크포인트

`cancelled_before_final.zip`은 새 최종 명세를 받기 전에 사용자가 취소한 작업의 기록이다. 현재 구현이나 승인된 후속 요구사항으로 취급하지 않는다.

ZIP의 `state.json`에 기준 Git 커밋과 저장한 파일 목록이 있다. `tracked_changes.patch`, `untracked/`, `cancelled_results/`는 복구·검토용이다. 새 최종 명세가 필요한 부분을 명시적으로 채택한 경우에만 재사용한다.

API 키와 `.env`는 포함하지 않는다.
