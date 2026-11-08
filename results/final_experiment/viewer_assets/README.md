# 오프라인 표시 자산

`report.html`은 이 폴더를 상대 경로 `../viewer_assets/`로 읽는다. 읽기에는 인터넷·서버·로그인이 필요하지 않다. HTML만 단독으로 내려받으면 표시 라이브러리가 없으므로 `final_experiment/` 폴더 전체를 함께 보관한다. CSV·원본 TXT·감사 JSON 링크까지 사용할 때는 저장소 전체를 내려받는다.

- `vendor/markdown-it.min.js`: markdown-it 14.1.0, MIT. 원시 HTML 비활성화.
- `vendor/katex.min.js`, `katex.min.css`, `fonts/*.woff2`: KaTeX 0.16.22, MIT. 로컬 수식 표시, trust=false.
- 각 라이선스 원문은 vendor의 LICENSE 파일에 있다. 자산은 jsDelivr의 해당 고정 버전 npm 배포물에서 받았으며 실행 시 CDN에 접속하지 않는다. CSS는 함께 보관한 WOFF2 폰트만 참조하도록 사용하지 않는 WOFF/TTF 대체 경로를 제거했다.

수식은 코드 블록/인라인 코드를 제외하고 Markdown 해석 전 보호한 뒤 DOM 텍스트 위치에만 복원한다. 수식 오류는 원문과 실패 표시를 남기며 추측해 치환하지 않는다. 모델의 HTML·스크립트는 텍스트로 표시하고 외부 이미지를 자동으로 불러오지 않는다. 원본 기록은 HTML의 원문 접기와 기존 감사 파일에서 별도로 확인한다.
