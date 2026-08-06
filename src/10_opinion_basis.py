# -*- coding: utf-8 -*-
"""⑩ 의견변형 근거 단락의 사유 유형화.

'이 산업에서 의견변형은 왜 나오는가'에 답하는 축.
한 건에 여러 사유가 병기되는 것이 일반적이므로 다중 레이블로 둔다.
"""
import os, re, sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")
RES = os.path.join(ROOT, "data", "results")

MODIFIED = ["의견거절", "한정의견", "부적정의견"]

# 사유 유형 — 감사범위 제한의 '무엇을 확인하지 못했는가' 기준
REASONS = [
    ("재무제표·자료 자체 미제시",
     r"제시\s*받지\s*못|제공\s*받지\s*못|제출\s*받지\s*못|자료를\s*제공\s*받지"
     r"|재무제표를\s*제시받지|미제출"),
    ("전기 의견변형 이월(기초잔액)",
     r"기초\s*(연결)?재무제표|기초잔액|타감사인이\s*감사"),
    ("계속기업 불확실성의 결과 추정 불가", r"계속기업"),
    ("특수관계자 범위·거래 확인 불가", r"특수관계자|최상위지배자"),
    ("자금·투자거래의 정당성", r"자금\s*거래|자금거래|투자.{0,8}거래|대여금|자금\s*대여|취득금액"),
    ("종속기업 재무정보 미입수", r"종속기업.{0,25}(재무정보|자료|감사|제공)"),
    ("매출·수익의 실재성", r"매출|영업수익|수익인식"),
    ("자산의 실재성·평가", r"실재성|손상|평가의?\s*적정성|재고자산|공정가치"),
    ("핵심인력 이탈", r"퇴사|인력\s*이탈"),
]
COMP = [(k, re.compile(p)) for k, p in REASONS]


def main():
    m = pd.read_csv(os.path.join(OUT, "report_meta.csv"),
                    dtype={"rcept_no": str, "corp_code": str}, encoding="utf-8-sig")
    m["corp_code"] = m.corp_code.str.zfill(8)
    m["_p"] = (m.doc_type != "연결").astype(int)
    m = m.sort_values(["corp_code", "fy", "_p"]).drop_duplicates(["corp_code", "fy"])

    mod = m[m.opinion.isin(MODIFIED)].copy()
    mod["opinion_basis"] = mod.opinion_basis.fillna("")
    rows = []
    for r in mod.itertuples():
        hits = [k for k, c in COMP if c.search(r.opinion_basis)]
        rows.append(dict(corp_code=r.corp_code, 기업명=r.기업명, 군=r.군, fy=r.fy,
                         의견=r.opinion, 감사인=r.auditor, 사유수=len(hits),
                         사유="|".join(hits), 근거단락=r.opinion_basis))
    d = pd.DataFrame(rows).sort_values(["기업명", "fy"])
    d.to_csv(os.path.join(RES, "opinion_basis_typed.csv"), index=False, encoding="utf-8-sig")

    n = len(d)
    print(f"의견변형 {n}건 / {d.기업명.nunique()}개사")
    print(f"  의견거절 {(d.의견=='의견거절').sum()} · 한정의견 {(d.의견=='한정의견').sum()} · "
          f"부적정의견 {(d.의견=='부적정의견').sum()}")
    print(f"  사유 미분류 {int((d.사유수==0).sum())}건")

    print("\n=== 사유 유형별 출현 (다중 레이블)")
    cnt = {}
    for s in d.사유:
        for x in [y for y in s.split("|") if y]:
            cnt[x] = cnt.get(x, 0) + 1
    tab = pd.DataFrame({"건수": pd.Series(cnt)}).sort_values("건수", ascending=False)
    tab["비율"] = (tab.건수 / n * 100).round(1).astype(str) + "%"
    print(tab.to_string())
    tab.to_csv(os.path.join(RES, "opinion_reason_freq.csv"), encoding="utf-8-sig")

    print("\n=== 기업별 의견변형 연속 연도")
    seq = d.groupby(["기업명", "군"]).agg(연도수=("fy", "size"),
                                       기간=("fy", lambda s: f"{s.min()}~{s.max()}"),
                                       의견=("의견", lambda s: "/".join(sorted(set(s)))))
    print(seq.sort_values("연도수", ascending=False).to_string())

    # 이월 구조: 전기에도 의견변형이었던 비율
    key = set(zip(d.corp_code, d.fy))
    carry = sum(1 for c, f in key if (c, f - 1) in key)
    print(f"\n=== 이월 구조")
    print(f"  직전 사업연도에도 의견변형이었던 건: {carry}/{n} ({carry/n*100:.1f}%)")
    print(f"  근거 단락에 '기초잔액 검증 불가'가 명시된 건: "
          f"{int(d.사유.str.contains('기초잔액').sum())}건")


if __name__ == "__main__":
    main()
