# -*- coding: utf-8 -*-
"""감사위험 지도 — 핵심감사사항(KAM)·계속기업 불확실성·의견변형 실증분석."""
import os, re
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="감사위험 지도", page_icon="◧", layout="wide")

BASE = os.path.dirname(os.path.abspath(__file__))
BG, SURF, LINE = "#0E1013", "#171A21", "#272D3A"
MINT, CORAL, AMBER = "#6FD3C2", "#E8705A", "#D9A25F"
TXT, MUTE = "#E8EAEE", "#868E9E"

st.markdown(f"""<style>
.stApp {{ background:{BG}; color:{TXT}; }}
section[data-testid="stSidebar"] {{ background:#0A0C0F; border-right:1px solid {LINE}; }}
h1,h2,h3,h4 {{ color:{TXT} !important; letter-spacing:-.025em; font-weight:650; }}
b, strong {{ color:{MINT}; font-weight:600; }}

.eyebrow {{ color:{MUTE}; font-size:.72rem; letter-spacing:.22em; text-transform:uppercase;
           margin-bottom:.5rem; }}
.secttl {{ font-size:1.85rem; font-weight:680; letter-spacing:-.03em; line-height:1.25;
          margin:0 0 1.1rem 0; }}
.lead {{ font-size:1.06rem; line-height:1.85; color:#CDD3DE; border-left:2px solid {MINT};
        padding-left:1.1rem; margin:0 0 2rem 0; }}
.lead.warn {{ border-left-color:{CORAL}; }}

.figrow {{ display:flex; gap:0; border-top:1px solid {LINE}; border-bottom:1px solid {LINE};
          margin:0 0 2rem 0; }}
.fig {{ flex:1; padding:1.1rem 1.3rem; border-right:1px solid {LINE}; }}
.fig:last-child {{ border-right:none; }}
.fig .lbl {{ color:#C3CAD8; font-size:.78rem; font-weight:600; margin-bottom:.42rem;
            letter-spacing:.01em; }}
.fig .n {{ font-size:1.62rem; font-weight:700; letter-spacing:-.035em; color:{MINT};
          line-height:1.3; font-variant-numeric:tabular-nums; }}
.fig .n.sm {{ font-size:1.18rem; line-height:1.45; }}
.fig .pct {{ color:#C3CAD8; font-weight:600; font-size:.92rem; margin-left:.3rem; }}
.fig.neg .n {{ color:{CORAL}; }}
.fig.amb .n {{ color:{AMBER}; }}
.fig .k {{ color:#A7AFBE; font-size:.76rem; margin-top:.35rem; line-height:1.55; }}

/* 다크 배경에서 회색 기본색이 거의 안 보이므로 위젯·내비 글자를 흰색 볼드로 올림 */
section[data-testid="stSidebar"] [role="radiogroup"] label p {{
  color:#FFFFFF !important; font-weight:700 !important; font-size:.92rem !important; }}
section[data-testid="stSidebar"] [role="radiogroup"] label {{ padding:.15rem 0; }}
div[data-testid="stWidgetLabel"] p, .stMultiSelect label p, .stSlider label p,
.stSelectbox label p {{ color:#FFFFFF !important; font-weight:700 !important; }}
div[data-testid="stSliderTickBarMin"], div[data-testid="stSliderTickBarMax"] {{
  color:#A7AFBE !important; }}

.body {{ color:#B8BFCC; font-size:.93rem; line-height:1.85; }}
.panel {{ background:{SURF}; border:1px solid {LINE}; border-radius:4px;
         padding:1rem 1.25rem; color:#AAB2C0; font-size:.88rem; line-height:1.8;
         margin:1.2rem 0; }}
.panel .h {{ color:{TXT}; font-weight:620; font-size:.9rem; display:block; margin-bottom:.45rem; }}
.src {{ color:#98A0AF; font-size:.87rem; line-height:1.85; white-space:pre-wrap; }}
.chip {{ display:inline-block; border:1px solid {LINE}; color:{MUTE}; border-radius:3px;
        padding:1px 7px; font-size:.72rem; margin-right:5px; }}
.rule {{ border-top:1px solid {LINE}; margin:2.4rem 0 1.6rem 0; }}
div[data-testid="stExpander"] {{ background:{SURF}; border:1px solid {LINE}; border-radius:4px; }}
div[data-testid="stExpander"] summary {{ font-size:.9rem; }}
.sbnum {{ color:{MINT}; font-variant-numeric:tabular-nums; font-weight:640; }}
.sbrow {{ color:{MUTE}; font-size:.78rem; padding:.28rem 0; border-bottom:1px solid #14171D; }}
</style>""", unsafe_allow_html=True)

GNAME = {"콘텐츠": "E&M", "게임": "Game"}
G1, G2 = "E&M", "Game"
MODIFIED = ["의견거절", "한정의견", "부적정의견"]


@st.cache_data
def load():
    k = pd.read_csv(f"{BASE}/data/processed/kam_typed.csv", dtype={"corp_code": str},
                    encoding="utf-8-sig")
    k["corp_code"] = k.corp_code.str.zfill(8)
    k = k.drop_duplicates(["corp_code", "fy", "kam_title"])
    k = k[k.kam_type != "미분류"]
    k["군"] = k["군"].map(GNAME).fillna(k["군"])
    p = pd.read_csv(f"{BASE}/data/processed/panel_outcomes.csv", dtype={"corp_code": str},
                    encoding="utf-8-sig")
    p["corp_code"] = p.corp_code.str.zfill(8)
    p["군"] = p["군"].map(GNAME).fillna(p["군"])
    b = pd.read_csv(f"{BASE}/data/results/opinion_basis_typed.csv", dtype={"corp_code": str},
                    encoding="utf-8-sig")
    b["corp_code"] = b.corp_code.str.zfill(8)
    b["군"] = b["군"].map(GNAME).fillna(b["군"])
    return k, p, b


kam, pan, bas = load()

BAD = re.compile(r"^[\d,\.\s]+$|백만원|^\D{0,3}\d[\d,\.]*\s*(원|건)?$"
                 r"|(하였고|이며|하므로|고려하여|점을|바|이)$|참조\)")


def disp(t):
    t = str(t or "").strip()
    return "(항목명 추출 실패 — 원문 확인)" if (not t or len(t) < 4 or BAD.search(t)) else t


# 한계 서술에 쓰는 값도 화면과 같은 판정으로 계산한다(하드코딩하면 데이터가 바뀔 때 어긋남)
n_bad = int(kam.kam_title.apply(lambda t: disp(t).startswith("(항목명")).sum())


def figs(items):
    """(라벨, 값, 보조설명, 클래스) — 라벨·값·보조설명이 한눈에 보이도록."""
    html = '<div class="figrow">'
    for lbl, val, sub, cls in items:
        small = " sm" if len(re.sub(r"<[^>]+>", "", str(val))) > 9 else ""
        html += (f'<div class="fig {cls}"><div class="lbl">{lbl}</div>'
                 f'<div class="n{small}">{val}</div>'
                 + (f'<div class="k">{sub}</div>' if sub else "") + "</div>")
    st.markdown(html + "</div>", unsafe_allow_html=True)


def head(eyebrow, title, lead, warn=False):
    st.markdown(f'<div class="eyebrow">{eyebrow}</div>'
                f'<div class="secttl">{title}</div>'
                f'<div class="lead {"warn" if warn else ""}">{lead}</div>', unsafe_allow_html=True)


def chart(fig, h=380):
    """제목과 범례가 겹치지 않도록 범례를 차트 아래로 내리고, 글자색을 밝게 유지."""
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", height=h + 46,
                      font=dict(color="#E2E6EE", size=12),
                      title=dict(font=dict(color=TXT, size=14), x=0, xanchor="left",
                                 y=0.98, yanchor="top"),
                      margin=dict(l=6, r=6, t=50, b=58),
                      legend=dict(orientation="h", yanchor="top", y=-0.10, x=0,
                                  font=dict(color="#E2E6EE", size=12),
                                  bgcolor="rgba(0,0,0,0)"),
                      xaxis=dict(gridcolor="#1D222C", zerolinecolor="#1D222C",
                                 tickfont=dict(color="#C7CEDA")),
                      yaxis=dict(gridcolor="#1D222C", zerolinecolor="#1D222C",
                                 tickfont=dict(color="#E2E6EE")))
    st.plotly_chart(fig, use_container_width=True)


def b(s):
    """플로틀리 축·범례 라벨을 볼드로."""
    return f"<b>{s}</b>"


# ─────────────────────────────────────────────── 사이드바
with st.sidebar:
    st.markdown(f'<div class="eyebrow">Samil Audit Portfolio</div>'
                f'<div style="font-size:1.22rem;font-weight:800;letter-spacing:-.03em;'
                f'color:#FFFFFF;margin-bottom:1.3rem">감사위험 지도</div>',
                unsafe_allow_html=True)
    sec = st.radio("섹션", [
        "01  감사인이 지목한 위험",
        "02  세 축은 이어지는가 (KAM·GC·의견변형)",
        "03  의견변형은 왜 나오는가",
        "04  만드는 과정",
    ], label_visibility="collapsed")
    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    n_mod = len(bas)
    for lab, val in [("분석 단위", "541 firm-year"), ("사업연도", "FY2019–2024"),
                     ("기업", "109개사"), ("핵심감사사항", f"{len(kam)}개"),
                     ("의견변형", f"{n_mod}건"), ("분류 검증 κ", "0.911")]:
        st.markdown(f'<div class="sbrow">{lab}<span style="float:right" class="sbnum">{val}</span></div>',
                    unsafe_allow_html=True)
    st.markdown(f'<div style="color:{MUTE};font-size:.72rem;line-height:1.7;margin-top:1.2rem">'
                f'DART 사업보고서에 첨부된 감사보고서 원문 기반. 감사의견의 적정성을 평가하지 않으며 '
                f'공시된 기재를 집계·대조한 것임.</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────── 01
if sec.startswith("01"):
    # 표시하는 비율은 전부 여기서 계산한다(하드코딩 금지).
    # 또한 **분모가 무엇인지**를 라벨에 반드시 적는다 — 전체 합산 비율을 각 부문의 비율인 것처럼
    # 쓰면 안 됨(전체 69.5% / E&M 67.6% / Game 75.2%로 서로 다른 값임).
    top = kam.kam_type.value_counts()
    T1, T2 = top.index[0], top.index[1]
    p1 = top.iloc[0] / len(kam) * 100
    p2 = (top.iloc[0] + top.iloc[1]) / len(kam) * 100

    def share(seg, types):
        s = kam[kam["군"] == seg]
        return s.kam_type.isin(types).sum() / len(s) * 100 if len(s) else float("nan")

    e2, g2 = share(G1, [T1, T2]), share(G2, [T1, T2])
    e1, g1 = share(G1, [T1]), share(G2, [T1])

    head("Section 01 · 무엇을 위험으로 보았나",
         "콘텐츠 산업 기업의 핵심감사사항",
         f"<b>E&amp;M 부문</b>(음악·방송·영화·드라마·웹툰, 78개사)과 "
         f"<b>Game 부문</b>(31개사, 대조군)의 핵심감사사항 {len(kam)}개를 13개 유형으로 분류함. "
         f"전체의 <b>{p2:.1f}%</b>가 <b>{T1}·{T2}</b> 두 유형에 몰려 있고, 부문별로 나눠 봐도 "
         f"E&amp;M {e2:.1f}% · Game {g2:.1f}%로 비슷함. "
         f"<b>부문 간 유형 분포 차이는 유의하지 않음</b>(카이제곱 p=0.155).")
    figs([(f"최다 유형 · 전체 {len(kam)}건 기준",
           f"{T1}<span class='pct'>{p1:.1f}%</span>",
           f"{int(top.iloc[0])}건 · 부문별 E&M {e1:.1f}% / Game {g1:.1f}%", ""),
          (f"상위 2유형 · 전체 {len(kam)}건 기준",
           f"{T1} · {T2}<span class='pct'>{p2:.1f}%</span>",
           f"{int(top.iloc[0]+top.iloc[1])}건 · 부문별 E&M {e2:.1f}% / Game {g2:.1f}%", ""),
          ("분류 유형 수", "13", "감사인이 지목한 회계쟁점 기준", ""),
          ("부문 간 분포 차이", "없음", "카이제곱 p=0.155 · 유의하지 않음", "amb")])

    c1, c2, c3 = st.columns([1, 1, 2])
    grp = c1.multiselect("부문", [G1, G2], default=[G1, G2])
    yrs = c2.slider("사업연도", 2019, 2024, (2019, 2024))
    tsel = c3.multiselect("유형", sorted(kam.kam_type.unique()), default=[])
    v = kam[kam["군"].isin(grp) & kam.fy.between(*yrs)]
    if tsel:
        v = v[v.kam_type.isin(tsel)]

    if v.empty:
        st.warning("조건에 맞는 항목이 없음")
    else:
        L, R = st.columns([1.15, 1])
        with L:
            ct = pd.crosstab(v.kam_type, v["군"], normalize="columns") * 100
            ct = ct.reindex(v.kam_type.value_counts().index).fillna(0).round(1)
            fig = go.Figure()
            for g, col in [(G1, MINT), (G2, AMBER)]:
                if g in ct.columns:
                    fig.add_bar(y=[b(x) for x in ct.index[::-1]], x=ct[g][::-1], name=b(g),
                                orientation="h", marker_color=col,
                                hovertemplate="%{y} %{x}%<extra></extra>")
            fig.update_layout(title="부문별 유형 구성비 (%)", barmode="group")
            chart(fig, h=max(360, 27 * len(ct) + 90))
        with R:
            tr = v.groupby(["fy", "kam_type"]).size().unstack(fill_value=0)
            keep = [c for c in v.kam_type.value_counts().head(5).index if c in tr.columns]
            fig = go.Figure()
            for i, c in enumerate(keep):
                fig.add_scatter(x=tr.index, y=tr[c], name=b(c), mode="lines+markers",
                                line=dict(color=[MINT, AMBER, "#7C9CE0", CORAL, "#9B8ACB"][i],
                                          width=2.2))
            fig.update_layout(title="연도별 추이 (상위 5유형, 건수)",
                              xaxis=dict(dtick=1, gridcolor="#1D222C"))
            chart(fig, h=max(360, 27 * len(ct) + 90))
        st.markdown(f'<div class="panel"><span class="h">한 firm-year에서 한 문서만 채택했음</span>'
                    f'연결·별도 감사보고서를 둘 다 세면 같은 사건이 두 번 계상됨. 예를 들어 한 게임사는 '
                    f'연결에서 「현금창출단위(영업권)의 회수가능액 측정」, 별도에서 「종속기업투자주식 '
                    f'손상검사」로 기재되는데 같은 사건을 두 재무제표에서 다르게 부른 것임. '
                    f'실제로 종속·관계기업투자 유형의 <b>85%가 별도보고서</b>에서 나와, 둘 다 세면 '
                    f'부문별 분포가 문서 구성에 따라 왜곡됨. <b>연결 우선, 연결 미작성 기간만 별도</b>를 '
                    f'적용함(연결 373 · 별도 27).</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="panel"><span class="h">FY2019는 다른 연도와 같은 선상에 놓을 수 없음</span>'
                    f'핵심감사사항 기재가 자산규모별로 단계 도입되던 시기라 소형사가 빠져 있음'
                    f'(검출률 44.4% vs 다른 해 66~77%).</div>', unsafe_allow_html=True)

        st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
        st.markdown("#### 감사보고서 원문")
        st.markdown('<div class="body">항목을 펼치면 감사인이 쓴 <b>선정 이유</b>와 '
                    '<b>실제 수행한 감사절차</b>가 나옴. 수치만이 아니라 그 산업에서 위험이 '
                    '어떤 언어로 서술되는지 확인하는 용도임.</div>', unsafe_allow_html=True)
        f = st.selectbox("기업", ["(전체)"] + sorted(v.기업명.unique()))
        vv = (v if f == "(전체)" else v[v.기업명 == f]).sort_values(["fy", "기업명"],
                                                              ascending=[False, True])
        st.caption(f"{len(vv)}건 · 상위 60건 표시")
        for r in vv.head(60).itertuples():
            with st.expander(f"{r.fy} · {r.기업명} · {r.kam_type} — {disp(r.kam_title)[:56]}"):
                st.markdown(f'<span class="chip">{r.군}</span>'
                            f'<span class="chip">{r.doc_type}감사보고서</span>'
                            f'<span class="chip">분류 {"규칙" if r.type_source=="rule" else "LLM 보조"}</span>',
                            unsafe_allow_html=True)
                st.markdown("**핵심감사사항으로 결정한 이유**")
                st.markdown(f'<div class="src">{str(r.reason_text)[:2400]}</div>', unsafe_allow_html=True)
                if isinstance(r.procedure_text, str) and len(r.procedure_text) > 30:
                    st.markdown("**감사에서 다루어진 방법**")
                    st.markdown(f'<div class="src">{r.procedure_text[:2400]}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────── 02
elif sec.startswith("02"):
    obs = pan[pan.sig_2y.notna()]
    gco = pan[(pan.has_gc == 1) & (pan.sig_2y.notna())]

    def worst(r):
        s = " ".join([x for x in [r.why_t1, r.why_t2] if isinstance(x, str)])
        if "비적정의견" in s:
            return "의견변형"
        if "제출 중단" in s or "보고서 없음" in s:
            return "보고서 제출 중단"
        if "GC 재기재" in s:
            return "계속기업 불확실성 재기재"
        return "변화 없음"

    g = gco.copy()
    g["후속"] = g.apply(worst, axis=1)
    vc = g.후속.value_counts()
    n_gc = len(g)
    head("Section 02 · 세 축은 이어지는가",
         "핵심감사사항 → 계속기업 → 의견변형으로<br>이어지는 선은 생각보다 약하다",
         "세 축은 서로 다른 것을 말함. <b>핵심감사사항</b>은 감사인이 공개적으로 밝힌 위험이라 "
         "수위가 조절되고, <b>계속기업 불확실성</b>은 기업의 재무적 존속 문제이며, "
         "<b>의견변형</b>은 감사 수행 자체가 막힌 결과임. "
         "따라서 이 절은 인과가 아니라 <b>세 기재가 실제로 어떻게 겹치는지</b>를 본 것임.", warn=True)
    n_gc_all = int(pan.has_gc.sum())
    figs([("이후 의견변형", f"{int(vc.get('의견변형',0))}건",
           f"후속 관측이 가능한 {n_gc}건 기준 "
           f"(전체 {n_gc_all}건 중 {n_gc_all-n_gc}건은 FY2024라 관측 불가)", "neg"),
          ("계속기업 재기재", f"{int(vc.get('계속기업 불확실성 재기재',0))}건",
           "감사의견은 적정일 수 있음", "amb"),
          ("보고서 제출 중단", f"{int(vc.get('보고서 제출 중단',0))}건", "상장폐지 근사", "amb"),
          ("이후 특이사항 없음", f"{int(vc.get('변화 없음',0))}건", "", "")])

    st.markdown(f'<div class="panel"><span class="h">"부실"이라는 한 덩어리로 묶지 않은 이유</span>'
                f'계속기업 불확실성이 이듬해 다시 기재되는 것은 의견변형과 성격이 전혀 다름 '
                f'(감사의견은 적정일 수 있음). 셋을 합쳐 하나의 비율로 제시하면 '
                f'<b>계속기업 기재 후 {(n_gc-int(vc.get("변화 없음",0)))/n_gc*100:.0f}%가 부실</b>처럼 읽히지만, '
                f'실제로 의견변형까지 간 것은 <b>{int(vc.get("의견변형",0))}건'
                f'({int(vc.get("의견변형",0))/n_gc*100:.0f}%)</b>임. '
                f'그래서 후속 결과를 합치지 않고 세 갈래로 나눠 제시함.</div>', unsafe_allow_html=True)

    L, R = st.columns([1, 1.1])
    with L:
        order = ["의견변형", "계속기업 불확실성 재기재", "보고서 제출 중단", "변화 없음"]
        vals = [int(vc.get(o, 0)) for o in order]
        fig = go.Figure(go.Bar(y=[b(x) for x in order[::-1]], x=vals[::-1], orientation="h",
                               marker_color=[MUTE, AMBER, AMBER, CORAL][::-1],
                               hovertemplate="%{y} %{x}건<extra></extra>"))
        fig.update_layout(title=f"계속기업 불확실성 기재 {n_gc}건의 2년 내 후속 감사결과")
        chart(fig, h=330)
    with R:
        st.markdown('<div class="body"><b>핵심감사사항이 계속기업의 조기경보가 되는가</b><br>'
                    f'검정할 수 없었음. 계속기업 불확실성이 기재된 {n_gc_all}건 중 <b>직전 사업연도에 '
                    '핵심감사사항이 관측되는 건은 5건</b>뿐이었음. '
                    '의견거절·한정의견 보고서에는 핵심감사사항을 기재하지 않기 때문에, '
                    '계속기업 문제가 붙는 기업은 직전 연도에 이미 의견변형인 경우가 많음. '
                    '표본이 부족한 것이 아니라 <b>제도의 구조상 조기경보로 기능할 여지가 없음</b>.</div>',
                    unsafe_allow_html=True)

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.markdown("#### 핵심감사사항 유형과 이후 후속 감사결과")
    t = kam.groupby(["corp_code", "fy"]).kam_type.apply(set).rename("types").reset_index()
    d = pan.merge(t, on=["corp_code", "fy"], how="inner")
    d = d[d.sig_2y.notna()]
    rows = []
    for ty in sorted(kam.kam_type.unique()):
        has = d.types.apply(lambda s: ty in s)
        if int(has.sum()) < 5:
            continue
        rows.append(dict(유형=ty, 보유=int(has.sum()),
                         보유군=round((d[has].sig_2y == 1).mean() * 100, 1),
                         미보유군=round((d[~has].sig_2y == 1).mean() * 100, 1)))
    r = pd.DataFrame(rows).sort_values("보유군", ascending=False)
    fig = go.Figure()
    yl = [b(x) for x in r.유형[::-1]]
    fig.add_bar(y=yl, x=r.보유군[::-1], name=b("해당 유형 보유"), orientation="h",
                marker_color=CORAL)
    fig.add_bar(y=yl, x=r.미보유군[::-1], name=b("미보유"), orientation="h", marker_color=MUTE)
    fig.update_layout(title="유형별 2년 내 후속 감사결과 발생률 (%)", barmode="group")
    chart(fig, h=max(340, 30 * len(r) + 90))
    st.markdown('<div class="panel"><span class="h">수익인식은 오히려 안전 신호</span>'
                '수익인식이 핵심감사사항인 firm-year의 후속 발생률은 <b>0.8%</b>로, 미보유군(11.0%)보다 '
                '뚜렷하게 낮음(p=0.0004). 기업 단위로 다시 재도 3.8% vs 25.8%(p=0.005)로 유지됨. 정상 영업 중인 기업만 수익인식이 '
                '핵심위험이 되고, 존속이 흔들리는 기업은 쟁점이 계속기업·자산손상으로 옮겨가기 때문임. '
                '<b>핵심감사사항 유형은 위험의 예측이라기보다 기업의 현재 상태를 반영함.</b><br><br>'
                '특수관계자거래는 방향이 반대(23.1% vs 5.8%, p=0.046)이나 해당 기업이 6개사뿐이라 '
                '기업 단위 검정에서는 유의하지 않음(p=0.151) — 확정할 수 없는 신호로 둠.</div>',
                unsafe_allow_html=True)

# ─────────────────────────────────────────────── 03
elif sec.startswith("03"):
    n = len(bas)
    n_firm = bas.기업명.nunique()
    key = set(zip(bas.corp_code, bas.fy))
    carry = sum(1 for c, f in key if (c, f - 1) in key)
    head("Section 03 · 의견변형은 왜 나오는가",
         "‘재무제표가 틀렸다’가 아니라<br>‘확인할 수 없었다’는 판정이었다",
         f"FY2019~2024 동안 의견변형은 <b>{n}건</b>이었고 전부 감사범위 제한에서 왔음. "
         f"<b>부적정의견은 0건</b> — 왜곡표시를 단정한 사례가 없었다는 뜻임. "
         f"근거 단락을 전수 추출해 사유를 유형화한 결과, 절반 이상이 "
         f"<b>전기 의견변형이 기초잔액 검증을 막아 이월된 것</b>이었음.", warn=True)
    figs([("의견변형", f"{n}건",
           f"의견거절 {int((bas.의견=='의견거절').sum())} · "
           f"한정 {int((bas.의견=='한정의견').sum())}", "neg"),
          ("해당 기업 수", f"{n_firm}개사", f"평균 {n/n_firm:.1f}년씩 연속됨", "amb"),
          ("부적정의견", "0건", "왜곡표시를 단정한 사례 없음", ""),
          ("직전 연도에도 의견변형", f"{carry/n*100:.0f}%", f"{carry}/{n}건", "neg")])

    cnt = {}
    for s in bas.사유.fillna(""):
        for x in [y for y in s.split("|") if y]:
            cnt[x] = cnt.get(x, 0) + 1
    freq = pd.Series(cnt).sort_values()
    fig = go.Figure(go.Bar(y=[b(x) for x in freq.index], x=(freq / n * 100).round(1),
                           orientation="h", marker_color=CORAL,
                           hovertemplate="%{y} %{x}%<extra></extra>"))
    fig.update_layout(title=f"의견변형 근거 단락의 사유 유형 (n={n}, 다중 집계, %)")
    chart(fig, h=max(360, 32 * len(freq) + 80))

    st.markdown(f'<div class="panel"><span class="h">의견변형은 스스로를 재생산한다</span>'
                f'근거 단락 {int(bas.사유.str.contains("기초잔액").sum())}건에 '
                f'"전기 재무제표를 타감사인이 감사했고 의견을 표명하지 않았으므로 기초잔액에 대한 '
                f'충분하고 적합한 증거를 확보하지 못했다"는 취지가 명시돼 있음. '
                f'전기에 한 번 의견변형이 나면 당기 감사인은 기초잔액을 검증할 방법이 없어 '
                f'당기도 의견변형이 됨. 실제로 {n}건이 {n_firm}개사에서 나왔고 '
                f'평균 {n/n_firm:.1f}년씩 연속됨.</div>', unsafe_allow_html=True)

    L, R = st.columns([1.1, 1])
    with L:
        seq = bas.groupby(["기업명", "군"]).agg(
            연도수=("fy", "size"), 기간=("fy", lambda s: f"{s.min()}–{s.max()}"),
            의견=("의견", lambda s: "·".join(sorted(set(s))))).reset_index()
        st.markdown("**기업별 의견변형 지속 기간**")
        st.dataframe(seq.sort_values("연도수", ascending=False), use_container_width=True,
                     hide_index=True, height=330)
    with R:
        by = bas.groupby("군").size()
        st.markdown("**부문별**")
        st.dataframe(pd.DataFrame({"의견변형 건수": by,
                                   "기업 수": bas.groupby("군").기업명.nunique()}),
                     use_container_width=True)
        st.markdown(f'<div class="body">한정의견은 <b>2건</b>뿐이며 모두 한 기업'
                    f'(로아앤코홀딩스 FY2023–2024)임. 의견변형의 실질은 의견거절이므로 '
                    f'분석의 초점을 의견거절에 둠.</div>', unsafe_allow_html=True)

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.markdown("#### 의견변형 근거 단락 원문")
    st.markdown('<div class="body">감사인이 <b>무엇을 확인하지 못했는지</b>를 직접 기술한 문단임. '
                '유형 분류는 이 원문에서 나옴.</div>', unsafe_allow_html=True)
    pick = st.selectbox("건 선택", [f"{r.기업명} · FY{r.fy} · {r.의견}" for r in bas.itertuples()])
    row = bas.iloc[[f"{r.기업명} · FY{r.fy} · {r.의견}" for r in bas.itertuples()].index(pick)]
    st.markdown("".join(f'<span class="chip">{x}</span>'
                        for x in str(row.사유).split("|") if x), unsafe_allow_html=True)
    st.markdown(f'<div class="src">{row.근거단락}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────── 04
else:
    head("Section 04 · 만드는 과정",
         "공개 API가 주지 않는 데이터를<br>원문에서 꺼내 검증했다",
         "감사보고서 전문은 공시유형 검색으로 받을 수 없음(거래소 「감사보고서제출」 공시는 "
         "표지 3천여 자뿐). <b>사업보고서 원문 ZIP에 첨부된 별도·연결 감사보고서</b>를 통해서만 "
         "확보됨. 여기서 핵심감사사항·계속기업 불확실성·감사의견·의견근거를 추출함.")
    figs([("감사보고서 확보율", "98.3%", "532 / 541 firm-year", ""),
          ("규칙기반 분류", "93.6%", "코드가 처리", ""),
          ("LLM 보조 분류", "4.4%", "규칙이 놓친 잔여분만", "amb"),
          ("사람 표본검증", "κ 0.911", "무작위 60건 blind 재분류", "")])

    steps = pd.DataFrame([
        ("① 모집단", "E&M 78개사(59x·60x·90x + 웹툰·웹소설) + Game 대조군 31개사(5821)", "541 firm-year"),
        ("② 원문 수집", "사업보고서 ZIP 692건 — 정정본→원본 순 폴백", "캐시 후 재사용"),
        ("③ 추출", "핵심감사사항 · 계속기업 · 감사의견 · 의견근거", "확보 98.3%"),
        ("④ 규칙 분류", "13개 유형, 키워드 규칙", "93.6%"),
        ("⑤ LLM 보조", "규칙 미분류분만. 판정을 코드에 고정해 재현 가능화", "4.4%"),
        ("⑥ 사람 표본검증", "무작위 60건 blind 재분류", "κ=0.935 → 존속분 0.911"),
        ("⑦ 후속 결과", "t+1·t+2 의견변형 / 계속기업 재기재 / 제출 중단", "관측가능 446"),
    ], columns=["단계", "내용", "결과"])
    st.dataframe(steps, use_container_width=True, hide_index=True)

    st.markdown(f'<div class="panel"><span class="h">사람 검증은 정확도 확인이면서 결함 발견이었다</span>'
                f'무작위 60건을 자동 분류 결과를 감춘 채 사람이 다시 분류해 대조함. '
                f'κ=0.935로 분류 품질을 확인했고, 동시에 <b>자동화가 조용히 만든 오류</b>를 찾아냄. '
                f'불일치 6건 중 분류 기준 차이는 1건뿐이었고 나머지는 추출 결함이었음. '
                f'원인은 감사보고서 XML이 서식 때문에 <b>단어 중간에서 태그를 끊는 것</b>으로, '
                f'「유형자산의 실재성과 평가」가 「형자산의 실재성과 평가」로, 「정확성」이 「확성」으로 '
                f'잘리고 있었음. 섹션 표제도 같은 이유로 「연결재무제표감사에…」가 「결재무제표감사에…」가 '
                f'되어 핵심감사사항 구간이 뒤 섹션을 삼키고 있었음. 인접한 같은 서식 조각만 병합하도록 '
                f'고쳐 섹션 검출 426→434건, 깨진 항목명 23→11건으로 개선함.</div>',
                unsafe_allow_html=True)

    st.markdown(f'<div class="panel"><span class="h">규칙과 LLM의 역할을 나눈 이유</span>'
                f'분류 기준을 먼저 규칙으로 세워 코드가 처리하게 하면 실행할 때마다 같은 결과가 나오고 '
                f'왜 그렇게 분류됐는지 규칙을 보면 설명됨. 규칙으로 잡히지 않는 잔여 건만 LLM이 '
                f'원문을 읽어 분류했고, <b>그 판정을 코드에 표로 고정</b>해 재현 가능하게 만듦. '
                f'LLM이 분류한 것 중 패턴이 반복되는 것(장기선급금·미니멈개런티 같은 콘텐츠 제작비 계정)은 '
                f'다시 규칙으로 옮겨 처리율을 올렸음(최종 93.6%).</div>', unsafe_allow_html=True)

    st.markdown("#### 한계")
    st.markdown(f'<div class="panel">'
                f'· <b>후속 결과는 프록시임.</b> 실제 부도·상장폐지 자료 대신 의견변형·사업보고서 제출 '
                f'중단·계속기업 재기재로 대체했으므로 M&amp;A로 인한 제출 중단이 섞일 수 있음<br>'
                f'· <b>부적정의견 0건은 이 표본에서의 관측</b>이며 일반 명제가 아님<br>'
                f'· <b>Game 부문은 업종코드 5821 접두로만 정의함.</b> 3자리 582는 게임과 시스템·응용 '
                f'소프트웨어를 구분할 수 없어 제외했고 그 안에 엔씨소프트·컴투스홀딩스·넥슨게임즈가 포함됨<br>'
                f'· <b>핵심감사사항은 기업 안에 중첩됨.</b> 항목 단위 검정은 독립성 가정을 어기므로 '
                f'기업 단위 재검정을 병기했고 결과가 갈리면 확정하지 않음<br>'
                f'· <b>κ 표본 60건.</b> 신뢰구간이 넓으며, 파이프라인 수정 후 재측정은 사람 분류를 '
                f'다시 받아야 해 수행하지 않음(표본 60건 중 <b>42건 존속·분류 변경 0건</b>·'
                f'존속분 κ=0.911)<br>'
                f'· <b>항목명 추출 실패 {n_bad}건</b>({n_bad/len(kam)*100:.1f}%)이 남아 있어 '
                f'화면에서는 대체 문구로 표시함<br>'
                f'· <b>FY2019는 다른 연도와 비교 불가</b> — 핵심감사사항 단계 도입기<br>'
                f'· <b>감사인별 성과 비교는 수행하지 않음.</b> 감사인마다 클라이언트 구성이 달라 '
                f'통제 없는 비교는 감사 품질이 아니라 클라이언트 구성을 재게 됨</div>',
                unsafe_allow_html=True)
