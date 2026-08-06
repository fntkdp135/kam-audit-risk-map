# -*- coding: utf-8 -*-
"""⑦ 사후 결과 레이블 생성 + 계속기업 불확실성(GC) 전수 검토표.

사후 결과는 외부 데이터 없이 같은 파이프라인 안에서 만든다:
  t+1 또는 t+2에 (a) 감사의견 비적정 (b) 사업보고서 제출 중단(상장폐지 근사)
  (c) GC 재기재 중 하나라도 발생하면 '부실 신호 발생'.
→ 실제 부도·상장폐지의 프록시이며, M&A로 인한 제출 중단도 섞일 수 있음(한계로 명시).

관측 창이 FY2024에서 끝나므로 t+1은 FY2023까지, t+2는 FY2022까지만 평가한다.
"""
import os, sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")
RES = os.path.join(ROOT, "data", "results")
FY_MIN, FY_MAX = 2019, 2024
ADVERSE = {"의견거절", "한정의견", "부적정의견"}


def build_panel() -> pd.DataFrame:
    m = pd.read_csv(os.path.join(OUT, "report_meta.csv"), dtype={"rcept_no": str},
                    encoding="utf-8-sig")
    # 연결 우선으로 firm-year 1행
    m["_p"] = (m.doc_type != "연결").astype(int)
    m = m.sort_values(["corp_code", "fy", "_p"]).drop_duplicates(["corp_code", "fy"], keep="first")
    m["has_report"] = (m.doc_name.fillna("") != "").astype(int)
    m["adverse"] = m.opinion.isin(ADVERSE).astype(int)
    return m[["corp_code", "기업명", "군", "fy", "has_report", "has_gc", "adverse",
              "opinion", "auditor", "n_kam", "kam_section_found"]]


def main():
    p = build_panel()
    idx = p.set_index(["corp_code", "fy"])

    def get(cc, fy, col):
        try:
            return idx.loc[(cc, fy), col]
        except KeyError:
            return None

    rows = []
    for r in p.itertuples():
        rec = dict(corp_code=r.corp_code, 기업명=r.기업명, 군=r.군, fy=r.fy,
                   has_report=r.has_report, has_gc=r.has_gc, adverse=r.adverse,
                   opinion=r.opinion, auditor=r.auditor, n_kam=r.n_kam)
        for h in (1, 2):
            f = r.fy + h
            if f > FY_MAX:
                rec[f"sig_t{h}"] = None
                continue
            if get(r.corp_code, f, "has_report") is None:
                # 다음 해 보고서 자체가 없음 = 제출 중단(상장폐지 근사)
                rec[f"sig_t{h}"] = 1
                rec[f"why_t{h}"] = "보고서 제출 중단"
                continue
            adv = int(get(r.corp_code, f, "adverse") or 0)
            gc = int(get(r.corp_code, f, "has_gc") or 0)
            hr = int(get(r.corp_code, f, "has_report") or 0)
            why = []
            if adv:
                why.append("비적정의견")
            if gc:
                why.append("GC 재기재")
            if not hr:
                why.append("보고서 없음")
            rec[f"sig_t{h}"] = int(bool(why))
            rec[f"why_t{h}"] = ", ".join(why)
        s1, s2 = rec.get("sig_t1"), rec.get("sig_t2")
        rec["sig_2y"] = None if (s1 is None and s2 is None) else int(bool(s1) or bool(s2))
        rows.append(rec)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT, "panel_outcomes.csv"), index=False, encoding="utf-8-sig")

    print(f"firm-year {len(out)}건 (보고서 확보 {out.has_report.sum()}건)")
    ev = out[out.sig_t1.notna()]
    print(f"\n[t+1 평가가능 {len(ev)}건] 부실신호 발생 {int(ev.sig_t1.sum())}건 "
          f"({ev.sig_t1.mean()*100:.1f}%)")
    ev2 = out[out.sig_2y.notna()]
    print(f"[2년내 평가가능 {len(ev2)}건] 부실신호 발생 {int(ev2.sig_2y.sum())}건 "
          f"({ev2.sig_2y.mean()*100:.1f}%)")

    # ---------------- GC 전수 검토 -----------------
    gc = out[out.has_gc == 1].copy().sort_values(["군", "fy", "기업명"])
    print(f"\n=== GC 기재 {len(gc)}건 전수 검토")
    cols = ["기업명", "군", "fy", "opinion", "sig_t1", "why_t1", "sig_2y"]
    disp = gc[cols].copy()
    disp["sig_t1"] = disp.sig_t1.map({1: "발생", 0: "없음"}).fillna("관측불가")
    disp["sig_2y"] = disp.sig_2y.map({1: "발생", 0: "없음"}).fillna("관측불가")
    print(disp.to_string(index=False))
    gc[cols + ["why_t2"]].to_csv(os.path.join(RES, "gc_review.csv"),
                                 index=False, encoding="utf-8-sig")

    # ---- 경보 성능 --------------------------------------------------------
    # 레이블 A(포괄)는 'GC 재기재'를 포함하므로 자기충족적이다(GC 기재 기업은 이듬해도
    # GC일 가능성이 높음). GC를 제외한 레이블 B로 반드시 함께 봐야 한다.
    for h, col in ((1, "sig_t1"), (2, "sig_2y")):
        pass

    strict = out.copy()
    for h in (1, 2):
        f = strict.fy + h
        key = list(zip(strict.corp_code, f))
        adv, miss = [], []
        for cc, ff in key:
            if ff > FY_MAX:
                adv.append(None); miss.append(None); continue
            try:
                adv.append(int(idx.loc[(cc, ff), "adverse"])); miss.append(0)
            except KeyError:
                adv.append(0); miss.append(1)
        strict[f"sadv_t{h}"] = adv
        strict[f"smiss_t{h}"] = miss
    def _or(a, b):
        # 주의: 컬럼에 None을 넣으면 pandas가 NaN으로 바꾸고 bool(NaN)은 True다.
        # is None 검사만 하면 관측 불가 건이 전부 '발생'으로 집계된다(실제로 겪은 오류).
        na, nb = pd.isna(a), pd.isna(b)
        if na and nb:
            return None
        return int((not na and bool(a)) or (not nb and bool(b)))
    strict["sigB_t1"] = [_or(a, b) for a, b in zip(strict.sadv_t1, strict.smiss_t1)]
    strict["sigB_t2"] = [_or(a, b) for a, b in zip(strict.sadv_t2, strict.smiss_t2)]
    strict["sigB_2y"] = [_or(a, b) for a, b in zip(strict.sigB_t1, strict.sigB_t2)]
    strict.to_csv(os.path.join(OUT, "panel_outcomes.csv"), index=False, encoding="utf-8-sig")

    for label, col in (("A(포괄: 비적정·GC재기재·제출중단)", "sig_2y"),
                       ("B(엄격: 비적정·제출중단만)", "sigB_2y")):
        obs = strict[strict[col].notna()]
        tp = int(((obs.has_gc == 1) & (obs[col] == 1)).sum())
        fp = int(((obs.has_gc == 1) & (obs[col] == 0)).sum())
        fn = int(((obs.has_gc == 0) & (obs[col] == 1)).sum())
        tn = int(((obs.has_gc == 0) & (obs[col] == 0)).sum())
        prec = tp / (tp + fp) if tp + fp else float("nan")
        rc = tp / (tp + fn) if tp + fn else float("nan")
        print(f"\n=== GC 경보 vs 2년내 부실신호 — 레이블 {label}")
        print(f"  관측가능 {len(obs)} firm-year / 부실신호 {tp+fn}건 ({(tp+fn)/len(obs)*100:.1f}%)")
        print(f"             신호발생  신호없음")
        print(f"  GC 기재  {tp:>8} {fp:>9}")
        print(f"  GC 없음  {fn:>8} {tn:>9}")
        print(f"  Precision {prec:.3f} / Recall {rc:.3f}")
        print(f"  → 부실신호 {tp+fn}건 중 사전 경보 {tp}건, 경보 없이 발생 {fn}건(개별 검토 대상)")


if __name__ == "__main__":
    main()
