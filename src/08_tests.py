# -*- coding: utf-8 -*-
"""⑧ 가설검정.

H1 업종군(콘텐츠 vs 게임)별 KAM 유형 분포에 차이가 있는가            → 카이제곱
H2 엔터·미디어 KAM은 콘텐츠·제작비 자산/수익인식에 편중되는가         → 유형별 비율차(Fisher)
H4 GC 기재에 앞서(t-1) 특정 KAM 유형이 선행하는가                    → Fisher
H5 KAM 개수는 이후 부실신호와 관련되는가                             → Mann-Whitney U

주의: KAM 항목은 기업 안에 중첩되어 있어 항목 단위 검정은 독립성 가정을 어긴다.
     → 기업 단위(해당 유형을 한 번이라도 받은 기업 수) 로버스트니스 검정을 함께 제시한다.
"""
import os, sys, itertools
import pandas as pd
from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")
RES = os.path.join(ROOT, "data", "results")


def stars(p):
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""


def main():
    k = pd.read_csv(os.path.join(OUT, "kam_typed.csv"),
                    dtype={"rcept_no": str, "corp_code": str}, encoding="utf-8-sig")
    k["corp_code"] = k.corp_code.str.zfill(8)
    k = k.drop_duplicates(subset=["corp_code", "fy", "kam_title"], keep="first")
    k = k[k.kam_type != "미분류"]
    pan = pd.read_csv(os.path.join(OUT, "panel_outcomes.csv"), dtype={"corp_code": str},
                      encoding="utf-8-sig")
    pan["corp_code"] = pan.corp_code.str.zfill(8)

    print(f"분석 대상 KAM {len(k)}개 / {k.corp_code.nunique()}개사 / "
          f"{k.groupby(['corp_code','fy']).ngroups} firm-year\n")

    # ---------------- H1 ----------------
    ct = pd.crosstab(k.kam_type, k["군"])
    chi2, p, dof, exp = stats.chi2_contingency(ct)
    print("=" * 72)
    print("[H1] 업종군별 KAM 유형 분포 차이 — 카이제곱")
    pct = (ct / ct.sum() * 100).round(1)
    tbl = ct.copy()
    tbl.columns = [f"{c}(건)" for c in ct.columns]
    for c in pct.columns:
        tbl[f"{c}(%)"] = pct[c]
    print(tbl.sort_values(tbl.columns[0], ascending=False).to_string())
    print(f"\nchi2={chi2:.2f}, dof={dof}, p={p:.4g} {stars(p)}  "
          f"(기대빈도 5 미만 셀 {int((exp<5).sum())}개)")
    n = ct.values.sum()
    v = (chi2 / (n * (min(ct.shape) - 1))) ** 0.5
    print(f"Cramer's V = {v:.3f}")

    # ---------------- H2 ----------------
    print("\n" + "=" * 72)
    print("[H2] 유형별 콘텐츠 vs 게임 비율차 — Fisher 정확검정 (항목 단위 / 기업 단위)")
    firm = k.groupby(["corp_code", "군", "kam_type"]).size().reset_index(name="n")
    nfirm = k.groupby("군").corp_code.nunique()
    rows = []
    for t in ct.index:
        a = int(ct.loc[t, "콘텐츠"]); b = int(ct["콘텐츠"].sum() - a)
        c = int(ct.loc[t, "게임"]); d = int(ct["게임"].sum() - c)
        _, p_i = stats.fisher_exact([[a, b], [c, d]])
        fc = firm[(firm.kam_type == t) & (firm["군"] == "콘텐츠")].corp_code.nunique()
        fg = firm[(firm.kam_type == t) & (firm["군"] == "게임")].corp_code.nunique()
        _, p_f = stats.fisher_exact([[fc, nfirm["콘텐츠"] - fc], [fg, nfirm["게임"] - fg]])
        rows.append(dict(유형=t, 콘텐츠_항목=f"{a/(a+b)*100:.1f}%", 게임_항목=f"{c/(c+d)*100:.1f}%",
                         p_항목=round(p_i, 4), sig_항목=stars(p_i),
                         콘텐츠_기업=f"{fc}/{nfirm['콘텐츠']}", 게임_기업=f"{fg}/{nfirm['게임']}",
                         p_기업=round(p_f, 4), sig_기업=stars(p_f)))
    h2 = pd.DataFrame(rows).sort_values("p_항목")
    print(h2.to_string(index=False))
    h2.to_csv(os.path.join(RES, "h2_type_by_group.csv"), index=False, encoding="utf-8-sig")

    # ---------------- H4 ----------------
    print("\n" + "=" * 72)
    print("[H4] GC 기재에 앞서(t-1) 특정 KAM 유형이 선행하는가 — Fisher")
    pan["key"] = pan.corp_code + "_" + pan.fy.astype(str)
    kam_prev = k.copy()
    kam_prev["key"] = kam_prev.corp_code + "_" + (kam_prev.fy + 1).astype(str)  # t-1 KAM → t년에 매칭
    types_prev = kam_prev.groupby("key").kam_type.apply(set)

    ev = pan[pan.has_gc.notna()].copy()
    ev["prev_types"] = ev.key.map(types_prev)
    # 왜 GC군에서 직전연도 KAM 관측이 적은지 진단 (해석에 필수)
    meta = pd.read_csv(os.path.join(OUT, "report_meta.csv"),
                       dtype={"rcept_no": str, "corp_code": str}, encoding="utf-8-sig")
    meta["corp_code"] = meta.corp_code.str.zfill(8)
    meta["_p"] = (meta.doc_type != "연결").astype(int)
    meta = meta.sort_values(["corp_code", "fy", "_p"]).drop_duplicates(["corp_code", "fy"])
    mi = meta.set_index(["corp_code", "fy"])
    gcev = pan[pan.has_gc == 1]
    diag = dict(총GC=len(gcev), 직전보고서있음=0, 직전KAM섹션있음=0, 직전의견거절=0)
    for r in gcev.itertuples():
        try:
            pr = mi.loc[(r.corp_code, r.fy - 1)]
        except KeyError:
            continue
        diag["직전보고서있음"] += 1
        diag["직전KAM섹션있음"] += int(pr.kam_section_found == 1)
        diag["직전의견거절"] += int(pr.opinion in ("의견거절", "한정의견", "부적정의견"))
    print("진단:", diag)
    print("  → 의견거절·한정의견 보고서에는 핵심감사사항을 기재하지 않는 것이 일반적이므로,"
          "\n    GC가 붙은 기업은 직전연도에도 이미 비적정의견인 경우가 많아 t-1 KAM이 존재하지 않음")

    ev = ev[ev.prev_types.notna()]                    # 직전연도 KAM이 관측되는 건만
    g1 = ev[ev.has_gc == 1]; g0 = ev[ev.has_gc == 0]
    print(f"직전연도 KAM 관측 가능: GC 기재 {len(g1)}건 / GC 없음 {len(g0)}건")
    if len(g1) < 10:
        print(f"  ※ GC군 {len(g1)}건으로는 검정력이 없음. 아래 표는 참고용이며 H4는 '검정 불가'로 결론.")
    rows = []
    for t in sorted(k.kam_type.unique()):
        a = int(g1.prev_types.apply(lambda s: t in s).sum())
        c = int(g0.prev_types.apply(lambda s: t in s).sum())
        _, p = stats.fisher_exact([[a, len(g1) - a], [c, len(g0) - c]])
        rows.append(dict(직전연도_KAM유형=t, GC기재군=f"{a}/{len(g1)}",
                         대조군=f"{c}/{len(g0)}",
                         GC군_비율=f"{a/len(g1)*100:.1f}%" if len(g1) else "-",
                         대조군_비율=f"{c/len(g0)*100:.1f}%" if len(g0) else "-",
                         p=round(p, 4), sig=stars(p)))
    h4 = pd.DataFrame(rows).sort_values("p")
    print(h4.to_string(index=False))
    h4.to_csv(os.path.join(RES, "h4_kam_before_gc.csv"), index=False, encoding="utf-8-sig")

    # ---------------- H5 ----------------
    print("\n" + "=" * 72)
    print("[H5] KAM 개수와 이후 부실신호 — Mann-Whitney U")
    for col, lab in (("sig_2y", "레이블A(포괄)"), ("sigB_2y", "레이블B(엄격)")):
        d = pan[pan[col].notna() & (pan.n_kam > 0)]
        x = d[d[col] == 1].n_kam.dropna(); y = d[d[col] == 0].n_kam.dropna()
        if len(x) > 3 and len(y) > 3:
            u, p = stats.mannwhitneyu(x, y, alternative="two-sided")
            print(f"  {lab}: 신호발생 중앙값 {x.median():.1f}(n={len(x)}) vs "
                  f"미발생 {y.median():.1f}(n={len(y)})  U={u:.0f}, p={p:.4g} {stars(p)}")


if __name__ == "__main__":
    main()
