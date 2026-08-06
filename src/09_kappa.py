# -*- coding: utf-8 -*-
"""⑨ 사람 분류 vs 자동 분류 일치도(Cohen's κ) 측정.

자동 분류(규칙+LLM)를 사람의 blind 분류와 대조한다.
불일치는 '기계가 틀린 것'으로 단정하지 않고 유형을 나눠 본다:
  (a) 기계 오류  (b) 사람 오류  (c) 분류 기준 자체의 모호성
(c)가 많으면 기준을 고쳐 재측정하는 것이 맞다(정확도가 아니라 기준을 고치는 것).
"""
import os, sys
import pandas as pd
from sklearn.metrics import cohen_kappa_score

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")
RES = os.path.join(ROOT, "data", "results")
XLSX = os.path.join(RES, "KAM분류_사람검증_60건.xlsx")


def load():
    h = pd.read_excel(XLSX, sheet_name="분류")
    h = h.rename(columns={h.columns[0]: "번호", h.columns[3]: "kam_title",
                          h.columns[-1]: "human"})
    h = h[["번호", "kam_title", "human"]]
    k = pd.read_csv(os.path.join(OUT, "kappa_machine_key.csv"),
                    dtype={"corp_code": str}, encoding="utf-8-sig")
    d = k.merge(h[["번호", "human"]], on="번호", how="left")
    d["human"] = d.human.fillna("").astype(str).str.strip()
    d["machine"] = d.kam_type.astype(str).str.strip()
    return d


def main():
    d = load()
    blank = (d.human == "").sum()
    print(f"표본 {len(d)}건 / 미입력 {blank}건")
    if blank:
        print(d[d.human == ""][["번호", "기업명", "kam_title"]].to_string(index=False))
    ev = d[d.human != ""].copy()

    # 기계가 '미분류'인 건과 사람이 '판단 불가'인 건은 κ 본계산에서 분리
    core = ev[(ev.machine != "미분류") & (ev.human != "판단 불가")]
    agree = (core.machine == core.human).mean()
    kappa = cohen_kappa_score(core.human, core.machine)

    print(f"\n=== 일치도 (핵심 {len(core)}건 기준)")
    print(f"  단순 일치율   {agree*100:.1f}%  ({int((core.machine==core.human).sum())}/{len(core)})")
    print(f"  Cohen's κ    {kappa:.3f}")
    print("  해석 기준: 0.81~1.00 almost perfect / 0.61~0.80 substantial / 0.41~0.60 moderate")

    excl = ev[(ev.machine == "미분류") | (ev.human == "판단 불가")]
    if len(excl):
        print(f"\n  ※ κ 계산에서 제외 {len(excl)}건 "
              f"(기계 미분류 {(ev.machine=='미분류').sum()} / 사람 판단불가 {(ev.human=='판단 불가').sum()})")

    dis = ev[ev.machine != ev.human]
    print(f"\n=== 불일치 {len(dis)}건")
    if len(dis):
        for r in dis.itertuples():
            print(f"  [{r.번호:>2}] {str(r.기업명)[:14]:<14} FY{r.fy}  {str(r.kam_title)[:44]}")
            print(f"       기계={r.machine}  /  사람={r.human}   (출처 {r.type_source})")

    print("\n=== 유형별 일치")
    g = core.assign(ok=(core.machine == core.human).astype(int)) \
            .groupby("machine").agg(n=("ok", "size"), 일치=("ok", "sum"))
    g["일치율"] = (g.일치 / g.n * 100).round(1)
    print(g.sort_values("n", ascending=False).to_string())

    d.to_csv(os.path.join(RES, "kappa_result.csv"), index=False, encoding="utf-8-sig")
    print(f"\n저장: {os.path.join(RES,'kappa_result.csv')}")


if __name__ == "__main__":
    main()
