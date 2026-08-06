# -*- coding: utf-8 -*-
"""⑤-1 규칙기반으로 분류되지 않은 KAM에 대한 LLM 보조 분류.

규칙(04)이 놓친 잔여 항목을 LLM이 항목명·사유 원문을 읽고 유형을 배정한 결과를 표로 고정한 것.
- 자동 실행이 아니라 '판정 결과를 기록해 재현 가능하게 만든' 파일이다.
- 항목명이 파싱 과정에서 잘려 의미를 알 수 없는 건은 배정하지 않고 '미분류'로 남긴다.
  (억지로 채우면 뒤의 사람 검증(κ)이 무의미해짐)
- 최종 정확도는 규칙·LLM을 합친 결과에 대해 사람이 무작위 표본을 blind 분류해 잰다(06).
"""
import os, re, sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")

# 항목명(정규화 전 원문) → 유형
LLM_MAP = {
    "Inc.) 손상평가": "영업권 손상",
    "수익의 발생사실": "수익인식",
    "형자산의 실재성과 평가": "유형·비유동자산 손상",
    "계약체결증분원가 및 계약이행원가의 인식": "수익인식",
    "손실충당금의 적정성 감사": "매출채권·대손",
    "기대가입기간": "수익인식",
    "영화상품매출의 정확성": "수익인식",
    "음원매출의 측정": "수익인식",
    "확성": "수익인식",
    "유형자산 전송망설비": "유형·비유동자산 손상",
    "스카이라이프TV상품": "매출채권·대손",
    ". 또한": "수익인식",
    "계약서상 공사기간을 초과한 현장 또는 공사기간이 완료기한에 임박한 현장에 대하여 지연배상금 발생가능성에 대한":
        "충당부채·소송·우발",
    "미르의전설 부문 물적분할 회계처리 및 공시의 적정성": "사업결합",
    "관계기업 투자주식에 대한 검토": "종속·관계기업투자 평가",
    "단영업": "사업결합",
    "단기금융상품의 실재성, 분류 및 사용제한 내역에 대한 공시사항": "금융상품 공정가치·평가",
    "내부거래 검토": "특수관계자거래",
    "종속기업투자주식에 대한 검토": "종속·관계기업투자 평가",
    "종속기업투자주식 처분으로 인한 지배력 상실에 따른 회계처리": "종속·관계기업투자 평가",
    "이연게임매출의": "수익인식",
    "음반 및 음원 매출": "수익인식",
    "주)사일로랩 인수에 따른 거래가격배분": "사업결합",
    "주요 현장에 대하여 공사변경에 따른 추가계약원가 추정액이 총계약원가 산정에 반영되었는지 확인": "수익인식",
    # --- FY2025 반영 후 재추출에서 항목명이 달라져 새로 판정한 건 ---
    "이연게임매출의 정확성": "수익인식",
    "중단영업": "사업결합",
    "전환금융상품 평가 및 회계처리의 적정성 (주석19, 21 참조": "금융상품 공정가치·평가",
    # 오타('현금창충단위')로 규칙에 걸리지 않은 건 — 내용은 현금창출단위 사용가치 평가
    "동 현금창충단위의 사용가치 평가에 포함된 미래현금흐름 추정에는 재무예산의 예측": "영업권 손상",
}

# 항목명이 잘려 의미 판별 불가 → 배정하지 않음(정직하게 미분류로 남김)
UNRESOLVABLE = {".", "주석9, 18 참조", "주석19, 21 참조", "위험",
                "801,778백만원, 1,218,906백만원 및 576,100백만원",
                "주)케이티에이치씨엔(구, (주)에이치씨엔", "케이티에이치씨엔(구, (주)에이치씨엔"}

# 선급비용 관련 항목명은 회사·연도별로 금액 표기가 달라 키가 매번 바뀐다.
# 정확 일치 대신 패턴으로 잡는다(웹툰·웹소설 제작 선급비용 = 콘텐츠 제작비 자산).
PATTERN_MAP = [
    (r"당기말\s*계상된\s*선급비용", "콘텐츠·제작비 자산"),
]


def main():
    k = pd.read_csv(os.path.join(OUT, "kam_classified.csv"), dtype={"rcept_no": str},
                    encoding="utf-8-sig")
    k["kam_type"] = k["kam_type_rule"]
    k["type_source"] = k["rule_basis"].map(lambda x: "rule" if x != "none" else "none")

    m = k["kam_type_rule"] == "미분류"
    key = k["kam_title"].astype(str).str.strip()
    hit = m & key.isin(LLM_MAP)
    k.loc[hit, "kam_type"] = key[hit].map(LLM_MAP)
    k.loc[hit, "type_source"] = "llm"

    # 정확 일치로 안 잡히는 잔여 건을 패턴으로 한 번 더
    still = k["kam_type"] == "미분류"
    for pat, cat in PATTERN_MAP:
        sel = still & key.str.contains(pat, regex=True, na=False)
        k.loc[sel, "kam_type"] = cat
        k.loc[sel, "type_source"] = "llm"
        still = k["kam_type"] == "미분류"

    k.to_csv(os.path.join(OUT, "kam_typed.csv"), index=False, encoding="utf-8-sig")

    n = len(k)
    unres = (k.kam_type == "미분류").sum()
    print(f"KAM {n}개")
    print(f"  규칙 분류    {(k.type_source=='rule').sum():>4} ({(k.type_source=='rule').mean()*100:.1f}%)")
    print(f"  LLM 보조     {(k.type_source=='llm').sum():>4} ({(k.type_source=='llm').mean()*100:.1f}%)")
    print(f"  최종 미분류  {unres:>4} ({unres/n*100:.1f}%)  ← 항목명 파싱 손실로 판별 불가")
    print("\n=== 최종 유형 분포")
    vc = k[k.kam_type != "미분류"].kam_type.value_counts()
    for c, v in vc.items():
        print(f"  {c:<20} {v:>4}  ({v/n*100:>4.1f}%)")


if __name__ == "__main__":
    main()
