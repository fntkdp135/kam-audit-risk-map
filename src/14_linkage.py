# -*- coding: utf-8 -*-
"""⑭ 연도를 건너뛴 연계 분석 — "그 핵심감사사항은 실제로 핵심이었나".

**왜 같은 해로 보면 안 되는가**
회계감사기준서 1701(ISA 701) 문단 15는, 의견변형을 초래하는 사항과 계속기업 관련 중요한
불확실성은 그 특성상 핵심감사사항이지만 **핵심감사사항 단락에 기술해서는 안 된다**고 정한다
(각각 의견근거 단락·계속기업 단락에 기술하고, 핵심감사사항 단락에서는 그 사항을 언급만 함).
따라서 **같은 보고서에서 세 기재가 겹치는 일은 제도상 발생하지 않으며**, 겹침을 세는 것은
발견이 아니라 기준서를 다시 읽는 것에 불과하다.

그래서 검증은 **연도를 건너뛰어** 해야 한다:
  ① t년 핵심감사사항 → 이후 연도 계속기업 불확실성
  ② t년 핵심감사사항 → 이후 연도 의견변형
  ③ t년 계속기업 불확실성 → 이후 연도 의견변형
그리고 단순히 "이어졌는가"가 아니라 **"같은 사유로 이어졌는가"**를 봐야 한다.
"""
import os, sys, json
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")
RES = os.path.join(ROOT, "data", "results")

# 핵심감사사항 유형 → 의견변형 근거 사유 유형 대응.
# 감사인이 '핵심위험'으로 지목한 회계쟁점이, 뒤에 '증거를 얻지 못한 대상'으로 다시 나타났는지를
# 보기 위한 대응표. 자산 관련 유형은 근거 단락에서 대부분 '자산의 실재성·평가'로 서술된다.
KAM2REASON = {
    "수익인식": "매출·수익의 실재성",
    "영업권 손상": "자산의 실재성·평가",
    "콘텐츠·제작비 자산": "자산의 실재성·평가",
    "유형·비유동자산 손상": "자산의 실재성·평가",
    "종속·관계기업투자 평가": "자산의 실재성·평가",
    "금융상품 공정가치·평가": "자산의 실재성·평가",
    "재고자산": "자산의 실재성·평가",
    "매출채권·대손": "자산의 실재성·평가",
    "특수관계자거래": "특수관계자 범위·거래 확인 불가",
    "계속기업·유동성": "계속기업 불확실성의 결과 추정 불가",
}


def load():
    k = pd.read_csv(os.path.join(OUT, "kam_typed.csv"), dtype={"corp_code": str},
                    encoding="utf-8-sig")
    k["corp_code"] = k.corp_code.str.zfill(8)
    k = k.drop_duplicates(["corp_code", "fy", "kam_title"])
    k = k[k.kam_type != "미분류"]
    p = pd.read_csv(os.path.join(OUT, "panel_outcomes.csv"), dtype={"corp_code": str},
                    encoding="utf-8-sig")
    p["corp_code"] = p.corp_code.str.zfill(8)
    b = pd.read_csv(os.path.join(RES, "opinion_basis_typed.csv"), dtype={"corp_code": str},
                    encoding="utf-8-sig")
    b["corp_code"] = b.corp_code.str.zfill(8)
    return k, p, b


def main():
    k, p, b = load()
    gc = p[p.has_gc == 1][["corp_code", "기업명", "군", "fy"]]
    gcset = set(zip(gc.corp_code, gc.fy))
    kam_by = {}
    for r in k.itertuples():
        kam_by.setdefault(r.corp_code, {}).setdefault(r.fy, set()).add(r.kam_type)

    def prior_kam(cc, fy):
        """해당 기업의 fy 이전 연도 중 가장 최근의 핵심감사사항(연도, 유형집합)."""
        ys = [y for y in kam_by.get(cc, {}) if y < fy]
        return (max(ys), kam_by[cc][max(ys)]) if ys else (None, set())

    rows = []
    # ① 핵심감사사항 → 이후 계속기업 불확실성
    for r in gc.itertuples():
        py, pk = prior_kam(r.corp_code, r.fy)
        if py is None:
            continue
        rows.append(dict(경로="KAM → 계속기업 불확실성", 기업명=r.기업명, 군=r.군,
                         선행연도=py, 선행기재="·".join(sorted(pk)),
                         후행연도=r.fy, 후행기재="계속기업 불확실성", 간격=r.fy - py,
                         사유일치="", 일치=None))
    # ② 핵심감사사항 → 이후 의견변형 (사유 일치 판정)
    for r in b.itertuples():
        py, pk = prior_kam(r.corp_code, r.fy)
        if py is None:
            continue
        reasons = {x for x in str(r.사유).split("|") if x}
        mapped = {KAM2REASON.get(t) for t in pk} - {None}
        hit = mapped & reasons
        rows.append(dict(경로="KAM → 의견변형", 기업명=r.기업명, 군=r.군,
                         선행연도=py, 선행기재="·".join(sorted(pk)),
                         후행연도=r.fy, 후행기재=f"의견변형({r.의견})", 간격=r.fy - py,
                         사유일치="·".join(sorted(hit)), 일치=int(bool(hit))))
    # ③ 계속기업 불확실성 → 이후 의견변형 (근거 사유에 계속기업이 있는지)
    for r in b.itertuples():
        ys = [y for (c, y) in gcset if c == r.corp_code and y < r.fy]
        if not ys:
            continue
        reasons = {x for x in str(r.사유).split("|") if x}
        hit = {x for x in reasons if "계속기업" in x}
        rows.append(dict(경로="계속기업 불확실성 → 의견변형", 기업명=r.기업명, 군=r.군,
                         선행연도=max(ys), 선행기재="계속기업 불확실성",
                         후행연도=r.fy, 후행기재=f"의견변형({r.의견})", 간격=r.fy - max(ys),
                         사유일치="·".join(sorted(hit)), 일치=int(bool(hit))))

    d = pd.DataFrame(rows).sort_values(["경로", "기업명", "후행연도"])
    d.to_csv(os.path.join(RES, "linkage.csv"), index=False, encoding="utf-8-sig")

    n_gc, n_mod = len(gc), len(b)
    print(f"모집단: 계속기업 불확실성 {n_gc}건 · 의견변형 {n_mod}건 · "
          f"핵심감사사항 {len(k)}개 / {k.corp_code.nunique()}개사\n")
    for path, denom in [("KAM → 계속기업 불확실성", n_gc),
                        ("KAM → 의견변형", n_mod),
                        ("계속기업 불확실성 → 의견변형", n_mod)]:
        s = d[d.경로 == path]
        line = (f"■ {path}\n   연결 {len(s)}/{denom}건 ({len(s)/denom*100:.0f}%) · "
                f"{s.기업명.nunique()}개사 · 간격 중앙값 {s.간격.median():.0f}년")
        if s.일치.notna().any():
            m = int(s.일치.sum())
            line += (f"\n   그중 **사유까지 일치** {m}건 ({m/len(s)*100:.0f}%) · "
                     f"{s[s.일치 == 1].기업명.nunique()}개사")
        print(line + "\n")

    print("=== 사유가 일치한 사례")
    for r in d[d.일치 == 1].itertuples():
        print(f"  [{r.경로}] {r.기업명} FY{r.선행연도} {r.선행기재} "
              f"→ FY{r.후행연도} {r.후행기재} (간격 {r.간격}년)")
        print(f"      일치 사유: {r.사유일치}")
    print(f"\n저장: {os.path.join(RES,'linkage.csv')} ({len(d)}건)")


if __name__ == "__main__":
    main()
