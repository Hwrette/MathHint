# MathHint — 문항 분리·학습/테스트·빈도벡터

현재 데이터는 **미분 140문항 + 삼각함수 125문항, 총 265문항**이다. HML 원본6개에서 본문 그래프가 있는 미분 문제3의 원래16번을 제외했다. 이전 HWPX2개와 이전 풀이 결과는 활성 데이터에서 제거했다.

## 지금 저장된 결과

```text
data/
├── raw/                         # 그림 문항 제외 후 HML6개
├── provenance/                  # 삭제 내역·원래번호 대조·검증한 수식 전사표
├── processed/
│   ├── annotated/               # ID·단원·유형·출처 + 문제·원본 정답해설 (265개)
│   ├── problems/                # 문제 본문만, 같은 ID의 TXT265개
│   ├── solutions/               # 원본 정답·해설만, 같은 ID의 TXT265개
│   ├── metadata.json            # ID별 분류·출처·현재/원래번호·수식 추적 정보
│   ├── splits/
│   │   ├── train.json           # 학습 문항 ID목록
│   │   ├── test.json            # 테스트 문항 ID목록
│   │   └── report.json          # 단원·유형별 실제 분할 수와 제약
│   ├── manifest.json            # 파일별 SHA-256과 전체 문항ID
│   └── report.json              # 전체 집계와 검사 결과
└── vectors/
    ├── problems/
    │   ├── vocabulary.json      # 학습 문제에서만 만든 공통 어휘
    │   ├── train_vectors.json
    │   └── test_vectors.json
    ├── solutions/
    │   ├── vocabulary.json      # 학습 정답·해설에서만 만든 공통 어휘
    │   ├── train_vectors.json
    │   └── test_vectors.json
    └── report.json
```

**확인용은 `annotated/`, 실제 벡터 입력은 `problems/`와 `solutions/`다.** 단원·유형·출처·문항ID 문자열을 빈도에 넣지 않는다. 문제 벡터에 정답을 섞지 않고, 정답·해설 벡터를 별도로 만든다.

## 문항 ID가 연결 기준

`diff_3_017`은 **미분 문제3의 삭제 전 원래17번**이다. 현재 HML에서는16번이지만 ID는 그대로 유지한다. `trig_1_001`은 삼각함수 문제1의 원래1번이다.

한 ID가 다음 모든 위치에서 동일하게 연결된다.

```text
annotated/diff_3_017.txt
problems/diff_3_017.txt
solutions/diff_3_017.txt
metadata.json 의 id
splits/train.json 또는 test.json 의 ID
문제·정답 벡터 JSON documents[].id 및 file
```

삭제한 `diff_3_016`은 결과와 분할 목록에 없다. 문제와 정답 벡터의 행 순서도 같은 분할 ID목록과 일치한다. `metadata.json`은 벡터화 입력이 아니므로 원래 유형을 나중에 군집 결과와 대조할 수 있다.

## 현재 실행 결과

- 학습 **185문항**, 테스트 **80문항** (약7:3).
- 원본 세부 유형 **70개**.
- 문제 어휘 **346개**, 정답·해설 어휘 **431개**.
- 난수 시드 **42**. 동일 입력·설정에서 같은 문항이 같은 집합에 배치된다.
- 모든 문항 ID 유일, 학습·테스트 겹침 없음, 문제·정답 ID 및 행 순서 일치.

단원별로 테스트30%에 가까워지도록 나누고, 세부 유형에 독립 문항이2개 이상 있으면 양쪽에 최소1개를 둔다. 1문항 유형과 분리할 수 없는 중복 그룹은 학습에 둔다. 동일 출처/동일 본문은 같은 집합으로 묶고, 서로 다른 유형으로 표기된 동일 문항이 있으면 중단한다. 목표 비율과 실제 수의 차이는 분할 보고서에 남긴다.

공통 어휘는 **학습에서만 생성**한다. 테스트는 같은 어휘·같은 순서·같은 길이로 변환하며, 새로운 토큰은 어휘를 늘리지 않고 `ignored_token_count`로 기록한다. 문제와 정답·해설의 어휘 공간은 서로 다를 수 있다.

빈도는 Kiwi의 한국어 형태소와 LaTeX 명령·숫자·기호의 **원시 등장 횟수**다. 불용어 제거·TF-IDF·정규화는 적용하지 않았다. 임베딩이나 군집화는 이 준비 명령이 실행하지 않는다.

## 다시 만드는 방법

Python3.10 이상에서 필요한 패키지를 설치하고 실행한다.

```bash
python -m pip install -e '.[analysis]'
python -m mathhint_analysis.PrepareDataset --overwrite
```

기본 입력은 `data/raw/`, 결과는 `data/processed/`와 `data/vectors/`다. `--overwrite` 없이 기존 결과가 있으면 중단한다. 두 결과 폴더는 임시 폴더에서 완성한 후 함께 교체하며, 실패하면 이전 결과를 복구한다. 원본 HML은 수정하지 않는다.

```bash
python -m mathhint_analysis.PrepareDataset --test-fraction 0.3 --seed 42 --overwrite
```

분할 비율이나 시드를 바꾸면 비교 실험의 데이터도 달라진다. 빈도벡터·임베딩 비교에는 저장된 동일한 ID목록을 사용해야 한다.

## 수식 추적과 검토

HML의 수식 SCRIPT만 LaTeX로 바꾸며, 수식 caption의 인코딩 문자열·출처·분류표를 문제 본문에 섞지 않는다. 원문과 변환 결과는 `metadata.json`의 `equations`에서 추적한다.

원본에 잘못된 구분자나 문장 사이에 나뉜 수식이 있어, 46개 고유 전사를 `data/provenance/latex_transcriptions.json`에 별도로 기록했다. 각 항목에는 문항ID·문제/해설 구분·원문 전체·원문 해시·전사한 LaTeX·근거가 있다. 원본 파일을 고치거나 정답을 다시 생성한 것이 아니다. 전사표와 현재 수식이 대응하지 않으면 중단한다. 빈 서식 객체1개는 수학 내용이 없음을 명시해 토큰을 새로 추가하지 않는다.

해설에만 있는 그림은 문항 제외 이유로 삼지 않았다. 해설 그림의 존재는 메타데이터에 기록하며 이미지 자체는 텍스트 빈도에 포함하지 않는다. 변환 규칙 지원과 원문과의 수학적 동치는 별도 개념이다.

## 코드 위치

| 기능 | 파일 |
|---|---|
| 새 HML 문항·분류·정답 추출 | `mathhint_preprocess/hml.py` |
| 전체 준비·분할·벡터 생성 | `mathhint_analysis/PrepareDataset.py` |
| 한국어·LaTeX 토큰 분석 | `mathhint_analysis/BagOfWord.py` |
| 일반 TXT폴더의 빈도벡터 생성 | `mathhint_analysis/BuildFrequencyVectors.py` |
| 기존 HWPX 전처리 지원 | `python -m mathhint_preprocess` |
| Gemini 풀이 생성 | `mathhint_solver/GoogleAPI.py` |
| 기존 PyTorch 회귀·K-means | `mathhint_learning/` |

일반 TXT폴더만 분석할 때는 아래 명령도 계속 사용할 수 있다. 이 명령은 단원별 분할이나 ID 대조를 자동으로 수행하지 않는다.

```bash
python -m mathhint_analysis.BuildFrequencyVectors 문제폴더 -o outputs/frequency_vectors
```

## API 키

`.env.example`을 프로젝트 루트의 `.env`로 복사하고 `GEMINI_API_KEY`를 설정한다. `GoogleAPI.py`는 루트 `.env`를 읽으며 기존 환경변수가 우선한다. `.env`는 Git에서 제외한다.

```bash
python -m pip install -e '.[solver]'
python -m mathhint_solver.GoogleAPI
```

데이터 준비 과정은 Gemini API를 호출하지 않는다.

## 검사

```bash
python -m unittest discover -s tests -v
```
