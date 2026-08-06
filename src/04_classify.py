# -*- coding: utf-8 -*-
"""④ KAM 유형 분류 — 규칙기반 1차.

분류 기준은 '감사인이 무엇을 위험으로 보았는가'의 회계쟁점 축으로 둔다.
규칙은 순서가 있는 목록이며 위에서부터 먼저 걸리는 것을 채택한다(구체적인 것 우선).
미분류 건은 별도로 남겨 LLM 보조 분류 대상으로 넘기고, 최종 정확도는 사람 표본검증(κ)으로 잰다.
"""
import os, re, sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")

# (유형, 제목 우선 패턴, 본문 보조 패턴)
RULES = [
    ("영업권 손상",
     r"영업권|현금창출단위|CGU|사업결합.*손상",
     r"영업권"),
    # 콘텐츠 제작비는 회사마다 무형자산·선급금·재고자산으로 계상 위치가 갈린다
    # (2번 프로젝트에서 확인한 현상). 계정과목이 달라도 같은 회계쟁점이므로 한 유형으로 묶는다.
    ("콘텐츠·제작비 자산",
     r"(무형자산|판권|콘텐츠|컨텐츠|개발비|저작권|라이선스|게임\s*개발).*(손상|평가|상각|자산화)"
     r"|(손상).*(무형자산|판권|콘텐츠|컨텐츠|개발비)"
     r"|장기선급금|미니멈\s*개런티|선급금.*(손상|실재성)|선급비용.*(손상|계상)"
     r"|제작비.*(자산|손상)|애니메이션.*(자산|충당금)",
     r"무형자산.*손상|판권.*손상|콘텐츠.*손상|개발비.*자산화|장기선급금|미니멈\s*개런티"),
    ("종속·관계기업투자 평가",
     r"(종속기업|관계기업|공동기업|투자주식|지분법).*(손상|평가|회수가능)"
     r"|(손상|평가).*(종속기업|관계기업|투자주식)",
     r"종속기업투자|관계기업투자|지분법"),
    ("유형·비유동자산 손상",
     r"(유형자산|비유동자산|사용권자산|투자부동산).*(손상|평가)|비유동자산의?\s*손상",
     r"유형자산.*손상|비유동자산.*손상"),
    ("수익인식",
     r"수익.{0,2}인식|매출.*(인식|발생사실|기간귀속|실재성|과대)"
     r"|(발생사실|기간귀속|실재성).*매출|영업수익|변동대가|투입법|진행률|진행기준"
     r"|계약부채|이연수익|포인트|마일리지",
     r"수익인식|기간귀속|발생사실|변동대가|진행률"),
    ("금융상품 공정가치·평가",
     r"공정가치|파생상품|전환사채|신주인수권|금융자산.*(평가|손상)|수준\s*3|복합금융상품"
     r"|전환우선주|상환전환우선주|RCPS",
     r"공정가치\s*평가|파생상품|수준\s*3"),
    ("매출채권·대손",
     r"매출채권|대손|기대신용손실|채권.*(손상|평가|회수)",
     r"대손충당금|기대신용손실"),
    ("재고자산",
     r"재고자산|재고.*(평가|진부화)",
     r"재고자산\s*평가"),
    ("리스",
     r"리스",
     r"리스\s*(회계처리|계약|부채)"),
    ("특수관계자거래",
     r"특수관계자|이해관계자\s*거래|자금대여|가지급금",
     r"특수관계자"),
    ("계속기업·유동성",
     r"계속기업|유동성|자금조달|차입금.*상환|재무구조",
     r"계속기업\s*가정|유동성\s*위험"),
    ("이연법인세",
     r"이연법인세|법인세",
     r"이연법인세자산"),
    ("사업결합",
     r"사업결합|합병|취득자산.*배분|PPA|영업양수",
     r"사업결합"),
    ("충당부채·소송·우발",
     r"충당부채|우발부채|소송|손해배상|반품|환불",
     r"충당부채|우발"),
]
COMPILED = [(c, re.compile(t, re.I), re.compile(b, re.I)) for c, t, b in RULES]


def classify(title: str, body: str):
    """(유형, 근거단계) 반환. title 우선 → body 보조 → 미분류."""
    t = str(title or "")
    b = str(body or "")[:1200]
    for cat, rt, _ in COMPILED:
        if rt.search(t):
            return cat, "title"
    for cat, _, rb in COMPILED:
        if rb.search(b):
            return cat, "body"
    return "미분류", "none"


def main():
    k = pd.read_csv(os.path.join(OUT, "kam_items.csv"), dtype={"rcept_no": str},
                    encoding="utf-8-sig")
    res = k.apply(lambda r: classify(r["kam_title"], r["reason_text"]), axis=1)
    k["kam_type_rule"] = [x[0] for x in res]
    k["rule_basis"] = [x[1] for x in res]
    k.to_csv(os.path.join(OUT, "kam_classified.csv"), index=False, encoding="utf-8-sig")

    n = len(k)
    print(f"KAM 항목 {n}개")
    print(f"규칙 분류 성공 {(k.kam_type_rule!='미분류').sum()}개 "
          f"({(k.kam_type_rule!='미분류').mean()*100:.1f}%)  "
          f"[제목근거 {(k.rule_basis=='title').sum()} / 본문근거 {(k.rule_basis=='body').sum()}]")
    print("\n=== 유형 분포")
    vc = k.kam_type_rule.value_counts()
    for c, v in vc.items():
        print(f"  {c:<22} {v:>4}  ({v/n*100:>4.1f}%)")
    print("\n=== 군별 유형 분포 (상위 8유형, %)")
    top = [c for c in vc.index if c != "미분류"][:8]
    ct = pd.crosstab(k.kam_type_rule, k["군"], normalize="columns") * 100
    print(ct.loc[[c for c in top if c in ct.index]].round(1).to_string())
    print("\n=== 미분류 항목명 예시 20")
    for s in k[k.kam_type_rule == "미분류"].kam_title.head(20):
        print("   -", s)


if __name__ == "__main__":
    main()
