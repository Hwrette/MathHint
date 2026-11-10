"""저장된 전체265 η² CSV를 읽어 문제·풀이 순위 Markdown만 만든다."""

import json
from pathlib import Path

from .eta_rankings import LEVELS, _csv, _eta


DOMAINS = {"problems": ("문제", "01_problem_tokens"), "solutions": ("풀이", "02_solution_tokens")}


def _write(path, lines):
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _scope(config):
    counts = config["counts"]
    return (f"기존 학습{counts['train']}문항과 테스트{counts['test']}문항을 합친 **전체{counts['total']}문항**의 탐색 통계다. "
            "기존 학습 전용 η²나 모델 평가 결과를 바꾸지 않았다.")


def _limits(config):
    group = config["groups"]["type"]
    return [
        "η²가 낮다고 불용어가 되거나 높다고 수학적으로 중요한 토큰이 되는 것은 아니다. 의미와 제거 시 잃는 정보는 사용자가 판단한다. 이 값은 K-means ARI·정답률이나 풀이의 정확도도 아니다.", "",
        f"전체 자료의 유형은 {group['group_count']}개이며 그중 {group['singleton_groups']}개는 문항1개뿐이다. "
        "집단 수가 많거나 토큰 DF가 작으면 높은 η²를 과대해석하기 쉽다. CSV의 조정η²·DF·집단 크기도 함께 확인한다.", "",
        "이 표는 **테스트 문항의 실제 분류도 포함**한다. 이 표를 참고해 토큰을 선택한 뒤 같은 테스트에서 평가한다면 완전히 독립적인 최종 평가라고 할 수 없다. 이번에는 불용어 선정·제거·모델 학습·Gemini 호출을 하지 않았다.",
    ]


def _choice_table(prefix=""):
    lines = ["|분류 수준|원시 BoW η² 내림차순|L2 정규화 η² 내림차순|", "|---|---|---|"]
    for level, name in LEVELS.items():
        lines.append(f"|{name}|[원시 순위]({prefix}{level}.md#raw-ranking)|[정규화 순위]({prefix}{level}.md#normalized-ranking)|")
    return lines


def _rank_document(domain, name, level, level_name, rows, config):
    from .eta_rankings import ranking_sections

    size = config["counts"][domain]
    group = config["groups"][level]
    lines = ['<a name="top"></a>', "", f"# {name} 토큰 · 전체265문항 · {level_name} η² 순위", "",
             _scope(config), "",
             f"고정 {name} 어휘 **{size}개 전체**를 보여 준다. DF는 학습·테스트를 합친265문항 중 이 토큰이 등장한 문항 수다.", "",
             "[A. 원시 η² 순위](#raw-ranking) · [B. 정규화 η² 순위](#normalized-ranking) · [다른 분류 선택](README.md)", "",
             "정렬은 반올림 전 저장 CSV 값의 내림차순, 완전 동점은 기존 어휘 인덱스 순서다. 표시는 소수점4자리이며 표시값이 같아도 실제 값은 다를 수 있다. 정의되지 않은 값은 —로 표시해 맨 아래에 둔다.", ""]
    lines += ranking_sections(rows, df_label="전체 DF", full_only=True)
    lines += ['<a name="interpretation"></a>', "", "## 해석과 출처", "",
              f"이 분류 수준의 전체 집단은 **{group['group_count']}개**, 문항1개인 집단은 **{group['singleton_groups']}개**다.", "",
              *_limits(config), "",
              "두 순위표는 같은 토큰의 원시·정규화 η²를 나란히 보여 준다. 정규화는 문항별 벡터를 각자의 L2 노름으로 나눈 표현이며, 기존 벡터 파일은 바꾸지 않았다.", "",
              "[전체 정밀도의 분산·η²·조정η²·TF·DF CSV](eta_statistics.csv) · [이 영역 안내](README.md) · [문제·풀이 전체 안내](../README.md) · [분류별 문항 수](../class_labels.csv)"]
    return lines


def _domain_readme(domain, name, config):
    size = config["counts"][domain]
    excluded = config["ignored_test_tokens"][domain]
    lines = [f"# {name} 토큰 {size}개 · 전체265문항 η²", "", _scope(config), "",
             *(["여기서 풀이는 **원본 풀이·해설**의 `data/vectors/solutions/` 빈도 벡터를 뜻한다. Gemini가 생성한 응답을 분석한 것이 아니다.", ""] if domain == "solutions" else []),
             f"분류를 고르면 원시·정규화 순위 각각에서 **전체 {size}개 토큰이 처음부터 표시**된다. 좁은 화면에서는 표를 좌우로 밀어 DF·의미 열까지 읽는다.", "",
             *_choice_table(), "",
             f"기존 학습 어휘 {size}개와 그 인덱스를 그대로 사용했다. 테스트에만 처음 등장해 기존 벡터에 빠졌던 토큰의 등장 횟수 {excluded}회는 그대로 제외된 상태다. 어휘를 확장하거나 다시 토큰화하지 않았다.", "",
             "원시 η²와 정규화 η² 모두 전체265문항에서 직접 분산 분해한 결과다. 학습 η²와 테스트 η²를 따로 구해 평균한 값이 아니다.", "",
             "[분산·η²·조정η²·TF·DF 전체 CSV](eta_statistics.csv) · [분류별 학습/테스트/전체 문항 수](../class_labels.csv)", "",
             "DF는 등장 문항 수, TF는 총 등장 횟수다. 표의 DF는 전체265 기준이며 CSV에는 학습DF와 테스트DF도 따로 있다. 토큰 의미는 기존 분석의 설명을 그대로 사용했다.", "",
             *_limits(config), "",
             "[문제·풀이 전체 안내](../README.md) · [기존 학습185 문제 순위표](../../01_problem_tokens/eta_rankings/README.md)"]
    return lines


def build_report(root, output):
    """CSV·설정을 읽어 Markdown11개만 작성한다. 통계는 계산하지 않는다."""
    output = Path(output)
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    for domain, (name, folder_name) in DOMAINS.items():
        folder = output / folder_name
        saved = _csv(folder / "eta_statistics.csv")
        size = config["counts"][domain]
        if len(saved) != size * len(LEVELS):
            raise ValueError(f"전체265 {name} 통계 CSV의 행 수가 다릅니다.")
        for level, level_name in LEVELS.items():
            selected = [row for row in saved if row["level"] == level]
            if ([int(row["index"]) for row in selected] != list(range(size))
                    or any(row["region"] != domain or int(row["n"]) != 265 for row in selected)):
                raise ValueError(f"전체265 {name}/{level}의 인덱스·문항 수가 다릅니다.")
            rows = [{"index": int(row["index"]), "token": row["token"],
                     "raw": _eta(row["original_eta_squared"]), "normalized": _eta(row["normalized_eta_squared"]),
                     "df": int(row["total_df"]), "meaning": row["meaning"]} for row in selected]
            _write(folder / f"{level}.md", _rank_document(domain, name, level, level_name, rows, config))
        _write(folder / "README.md", _domain_readme(domain, name, config))

    lines = ["# 문제·풀이 토큰 η² · 학습+테스트 전체265문항", "", _scope(config), "",
             "여기서 풀이는 **원본 풀이·해설**의 `data/vectors/solutions/` 빈도 벡터다. Gemini 생성 응답의 토큰 통계가 아니다.", "",
             "**문제와 풀이를 각각 선택하세요.** 각 분류의 원시·L2 정규화 순위에서 **문제346개·풀이431개 전체가 처음부터 표시**된다. 전체 목록을 바로 읽을 수 있다.", "",
             "|영역|토큰 수|과목|단원|세부단원|문제 유형|", "|---|---:|---|---|---|---|"]
    for domain, (name, folder_name) in DOMAINS.items():
        links = [f"[원시]({folder_name}/{level}.md#raw-ranking) · [정규화]({folder_name}/{level}.md#normalized-ranking)" for level in LEVELS]
        lines.append(f"|[{name} 안내]({folder_name}/README.md)|{config['counts'][domain]}|" + "|".join(links) + "|")
    lines += ["", "표의 **전체 DF**는265문항 중 등장 문항 수이며, TF(등장 횟수)와 다르다. 두 영역의 어휘와 의미·DF는 서로 독립적으로 관리한다. 문제 토큰346개와 풀이 토큰431개를 하나의 순위로 섞지 않았다.", "",
              "## 계산 범위와 정의", "",
              "원시 BoW는 기존 정수 빈도 그대로, 정규화 BoW는 문항별 L2 정규화 좌표다. 각 표현에서 전체265문항의 평균을 기준으로 다음을 계산했다.", "",
              "- 전체 분산 T = Σᵢ(xᵢ−μ)² / 265.",
              "- 집단 간 분산 B = Σɢ nɢ(μɢ−μ)² / 265, 집단 내 분산 W = ΣɢΣᵢ∈ɢ(xᵢ−μɢ)² / 265.",
              "- T = B + W이고 η² = B/T다. T=0이면 η²는 정의되지 않음으로 남긴다.",
              "- 조정η² = 1−(1−η²)(265−1)/(265−g). g는 해당 계층의 집단 수이며, 음수 보조 값도 그대로 보존한다.", "",
              "학습185와 테스트80을 ID에 맞춰 연결한 뒤 전체 통계를 계산했다. 풀이 토큰에도 해당 문제의 실제 과목·단원·세부단원·유형을 사용했다. 기존 분할 파일이나 어휘를 변경하지 않았고, 순위는 표시 전 정밀도로 정렬했다. 과목은 curriculum, 하위 분류는 상위 경로를 포함하며 subject 자료군과 구분한다.", "",
              "|분류|전체 집단 수|문항1개 집단 수|", "|---|---:|---:|"]
    for level, name in LEVELS.items():
        group = config["groups"][level]
        lines.append(f"|{name}|{group['group_count']}|{group['singleton_groups']}|")
    lines += ["", "[분류별 학습·테스트·전체 문항 수](class_labels.csv) · [문제 통계 CSV](01_problem_tokens/eta_statistics.csv) · [풀이 통계 CSV](02_solution_tokens/eta_statistics.csv)", "",
              f"각 영역의 영벡터 수는 문제{config['zero_vectors']['problems']}·풀이{config['zero_vectors']['solutions']}다. 기존 학습 어휘 밖 테스트 토큰은 문제{config['ignored_test_tokens']['problems']}회·풀이{config['ignored_test_tokens']['solutions']}회 제외된 상태를 유지했다. 해당 토큰을 추가하거나 원문을 다시 토큰화하지 않았다.", "",
              "## 이전 자료와의 구분", "",
              "[기존 학습185문항의 문제 η² 순위표](../01_problem_tokens/eta_rankings/README.md)는 그대로 보존했다. 현재 폴더는 **전체265문항의 문제·풀이 η²**이며, 학습 전용 결과의 수치를 덮어쓰지 않았다.", "",
              *_limits(config), "",
              "## 실행과 검증", "",
              "```bash", "python -m mathhint_analysis.token_analysis.full_dataset_eta analyze", "python -m mathhint_analysis.token_analysis.full_dataset_eta report", "python -m mathhint_analysis.token_analysis.full_dataset_eta verify", "```", "",
              "analyze는 고정 벡터로 이 폴더의 통계를 생성하고, report는 저장 CSV로 Markdown만 다시 만든다. verify는 저장값과 입력·산출물의 무결성을 확인한다. 세 명령 모두 모델 학습·Gemini 호출·불용어 적용을 하지 않는다.", "",
              "[설정·입력 출처](config.json) · [검증 기록](validation.json) · [토큰 분석 처음으로](../README.md)"]
    _write(output / "README.md", lines)
