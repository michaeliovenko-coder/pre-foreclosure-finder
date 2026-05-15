"""
Pre-Foreclosure Assumable Mortgage Finder
Streamlit UI — finds and ranks profitable assumable pre-foreclosure listings.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from fetcher import fetch_listings
from analyzer import analyze_property, CURRENT_RATE, monthly_payment

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PreFore Finder — Assumable Deals",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.metric-card {
    background: #1a1d2e;
    border-radius: 12px;
    padding: 14px 18px;
    margin: 6px 0;
    border-left: 4px solid #4CAF50;
}
.tag {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 10px;
    font-size: 0.76em;
    font-weight: 600;
    margin: 2px;
}
.tag-confirmed  { background: #1b5e20; color: #a5d6a7; }
.tag-inferred   { background: #1a3a1a; color: #81c784; border: 1px dashed #4CAF50; }
.tag-prefore    { background: #7f1d1d; color: #fca5a5; }
.tag-equity     { background: #1e3a5f; color: #93c5fd; }
.tag-fire       { color: #f97316; }
</style>
""", unsafe_allow_html=True)

GRADE_COLOR = {
    "A+": "#00e676", "A": "#69f0ae",
    "B+": "#ffeb3b", "B": "#ffc107",
    "C+": "#ff9800", "C": "#ff5722", "D": "#9e9e9e",
}


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🏠 PreFore Finder")
    st.caption("Assumable pre-foreclosure deals ranked by profitability")
    st.divider()

    st.subheader("Search")
    location = st.text_input(
        "Location",
        value="Phoenix, AZ",
        placeholder="City, State  or  Zip Code",
        help="US city/state or zip. Military markets (San Antonio TX, Jacksonville FL, Virginia Beach VA) have more VA assumables.",
    )
    use_live = st.toggle("Live data (Realtor.com)", value=True,
                         help="Scrape real listings. Disable to demo with sample data.")
    max_results = st.slider("Max listings to scan", 50, 500, 200, step=50)

    st.divider()
    st.subheader("Filters")

    assumable_filter = st.radio(
        "Assumable filter",
        ["Confirmed + Inferred", "Confirmed only", "All listings"],
        index=0,
        help="Confirmed = listing explicitly says assumable. Inferred = sold 2019-2022, FHA/VA-eligible price.",
    )
    show_only_preforeclosure = st.checkbox("Pre-foreclosure only", value=False)

    price_min, price_max = st.slider(
        "Price range ($)",
        min_value=50_000, max_value=2_000_000,
        value=(100_000, 800_000), step=10_000, format="$%d",
    )
    min_score = st.slider("Min profitability score", 0, 100, 25)

    st.divider()
    st.subheader("Rate Settings")
    current_rate = st.number_input(
        "Current market rate (%)",
        min_value=3.0, max_value=15.0, value=float(CURRENT_RATE),
        step=0.25, format="%.2f",
        help="30-yr fixed benchmark for monthly savings calculation",
    )

    search_btn = st.button("🔍 Search", use_container_width=True, type="primary")


# ── State ─────────────────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = []
    st.session_state.source = ""
    st.session_state.location = ""


def run_search():
    with st.spinner(f"Fetching listings for **{location}**…"):
        raw, source = fetch_listings(location, use_live=use_live, max_results=max_results)
    analyses = []
    progress = st.progress(0, text="Analyzing properties…")
    for i, r in enumerate(raw):
        try:
            analyses.append(analyze_property(r))
        except Exception:
            pass
        progress.progress((i + 1) / max(len(raw), 1))
    progress.empty()
    st.session_state.results = analyses
    st.session_state.source = source
    st.session_state.location = location


if search_btn:
    run_search()

if not st.session_state.results:
    run_search()

results = st.session_state.results


# ── Apply filters ─────────────────────────────────────────────────────────────
def keep(r):
    if r.list_price < 10_000:  # skip auction placeholders
        return False
    if r.list_price < price_min or r.list_price > price_max:
        return False
    if r.profitability_score < min_score:
        return False
    if show_only_preforeclosure and not r.is_preforeclosure:
        return False
    if assumable_filter == "Confirmed only" and (not r.is_assumable or r.assumable_inferred):
        return False
    if assumable_filter == "Confirmed + Inferred" and not r.is_assumable:
        return False
    return True


filtered = sorted([r for r in results if keep(r)], key=lambda x: x.profitability_score, reverse=True)


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("Pre-Foreclosure Assumable Mortgage Finder")
st.caption(
    f"📍 {st.session_state.location}  |  Source: {st.session_state.source}  |  "
    f"Benchmark: **{current_rate:.2f}%** 30-yr fixed"
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Scanned", len(results))
c2.metric("Confirmed Assumable", sum(1 for r in results if r.is_assumable and not r.assumable_inferred))
c3.metric("Potentially Assumable", sum(1 for r in results if r.assumable_inferred))
c4.metric("Pre-Foreclosure", sum(1 for r in results if r.is_preforeclosure))
c5.metric("Showing", len(filtered))
st.divider()

if not filtered:
    st.warning("No properties match your filters. Try loosening price range, score threshold, or assumable filter.")
    st.stop()


# ── Top picks ──────────────────────────────────────────────────────────────────
top = filtered[:3]
st.subheader("🏆 Top Deals")
cols = st.columns(len(top))

for col, p in zip(cols, top):
    tags = ""
    if p.is_assumable and not p.assumable_inferred:
        tags += '<span class="tag tag-confirmed">✓ Confirmed Assumable</span>'
    elif p.assumable_inferred:
        tags += '<span class="tag tag-inferred">~ Possibly Assumable</span>'
    if p.is_preforeclosure:
        tags += '<span class="tag tag-prefore">⚠ Pre-Foreclosure</span>'
    if p.equity_discount_pct >= 10:
        tags += f'<span class="tag tag-equity">↓ {p.equity_discount_pct:.0f}% Below Est.</span>'

    grade_color = GRADE_COLOR.get(p.profitability_grade, "#fff")
    savings_str = f"${p.monthly_payment_savings:,.0f}/mo saved" if p.monthly_payment_savings else "—"
    rate_line = (
        f'<div style="font-size:0.8em;color:#aaa;margin-top:4px">'
        f'Assumed rate: <b style="color:#fff">{p.assumed_rate:.2f}%</b> vs market {current_rate:.2f}%'
        f'{"  <i>(inferred)</i>" if p.assumable_inferred else ""}</div>'
        if p.is_assumable else ""
    )

    col.markdown(f"""
<div class="metric-card">
  <div style="font-size:0.82em;color:#9ca3af">{p.city}, {p.state}</div>
  <div style="font-weight:700;font-size:1.05em;margin:3px 0">{p.street}</div>
  <div style="font-size:1.55em;font-weight:800">${p.list_price:,.0f}</div>
  <div style="margin:4px 0">{tags}</div>
  <hr style="border-color:#2d3748;margin:8px 0">
  <div style="display:flex;justify-content:space-between;align-items:flex-end">
    <div>
      <div style="font-size:0.7em;color:#9ca3af;text-transform:uppercase">Profit Score</div>
      <div style="color:{grade_color};font-weight:800;font-size:1.35em">
        {p.profitability_grade}&nbsp;<span style="font-size:0.7em">({p.profitability_score:.0f}/100)</span>
      </div>
    </div>
    <div style="text-align:right">
      <div style="font-size:0.7em;color:#9ca3af;text-transform:uppercase">Mo. Savings</div>
      <div style="color:#4ade80;font-weight:700;font-size:1.1em">{savings_str}</div>
    </div>
  </div>
  {rate_line}
</div>
""", unsafe_allow_html=True)
    if p.url:
        col.link_button("View listing →", p.url, use_container_width=True)

st.divider()


# ── Scatter chart ──────────────────────────────────────────────────────────────
st.subheader("📊 Profitability Map")

chart_rows = []
for p in filtered:
    typ = (
        "Confirmed Assumable + Pre-Fore" if (p.is_assumable and not p.assumable_inferred and p.is_preforeclosure) else
        "Confirmed Assumable" if (p.is_assumable and not p.assumable_inferred) else
        "Possibly Assumable + Pre-Fore" if (p.assumable_inferred and p.is_preforeclosure) else
        "Possibly Assumable" if p.assumable_inferred else
        "Pre-Foreclosure Only" if p.is_preforeclosure else
        "Standard"
    )
    chart_rows.append({
        "Address": f"{p.street[:28]}, {p.city}",
        "List Price": p.list_price,
        "Monthly Savings": p.monthly_payment_savings,
        "Score": p.profitability_score,
        "Grade": p.profitability_grade,
        "Type": typ,
        "Equity Discount": f"{p.equity_discount_pct:.1f}%",
        "Assumed Rate": f"{p.assumed_rate:.2f}%" if p.assumed_rate else "—",
    })

df_c = pd.DataFrame(chart_rows)
cmap = {
    "Confirmed Assumable + Pre-Fore": "#00e676",
    "Confirmed Assumable": "#4ade80",
    "Possibly Assumable + Pre-Fore": "#fbbf24",
    "Possibly Assumable": "#fcd34d",
    "Pre-Foreclosure Only": "#f87171",
    "Standard": "#6b7280",
}
if not df_c.empty:
    fig = px.scatter(
        df_c, x="List Price", y="Monthly Savings",
        size="Score", color="Type",
        hover_name="Address",
        hover_data={"Grade": True, "Equity Discount": True, "Assumed Rate": True, "Score": True},
        color_discrete_map=cmap,
        template="plotly_dark",
        title="Monthly Savings vs. List Price  (bubble = profitability score)",
        labels={"List Price": "List Price ($)", "Monthly Savings": "Est. Monthly Savings ($)"},
    )
    fig.update_layout(height=400, margin=dict(t=40, b=20))
    st.plotly_chart(fig, use_container_width=True)


# ── Full table ─────────────────────────────────────────────────────────────────
st.subheader(f"📋 All Results ({len(filtered)} properties)")

rows = []
for p in filtered:
    assumable_label = (
        "✓ Confirmed" if (p.is_assumable and not p.assumable_inferred) else
        "~ Possible" if p.assumable_inferred else ""
    )
    rows.append({
        "Grade": p.profitability_grade,
        "Score": p.profitability_score,
        "Address": f"{p.street}, {p.city}, {p.state}",
        "List Price": f"${p.list_price:,.0f}",
        "Est. Value": f"${p.zestimate:,.0f}" if p.zestimate else "—",
        "Discount": f"{p.equity_discount_pct:.1f}%" if p.equity_discount_pct > 0 else "—",
        "Assumable": assumable_label,
        "Pre-Fore.": "⚠" if p.is_preforeclosure else "",
        "Assumed Rate": f"{p.assumed_rate:.2f}%" if p.assumed_rate else "—",
        "Mo. Savings": f"${p.monthly_payment_savings:,.0f}" if p.monthly_payment_savings else "—",
        "Annual": f"${p.annual_savings:,.0f}" if p.annual_savings else "—",
        "Bd/Ba": f"{p.beds or '?'}/{p.baths or '?'}",
        "Sqft": f"{p.sqft:,}" if p.sqft else "—",
    })

df_t = pd.DataFrame(rows)
st.dataframe(
    df_t,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f"),
    },
)


# ── Property detail ────────────────────────────────────────────────────────────
st.subheader("🔍 Property Detail")

sel = st.selectbox(
    "Select a property",
    range(len(filtered)),
    format_func=lambda i: (
        f"#{i+1} — {filtered[i].profitability_grade} ({filtered[i].profitability_score:.0f}) | "
        f"{filtered[i].street}, {filtered[i].city}"
    ),
)

p = filtered[sel]
left, right = st.columns([1, 1])

with left:
    st.markdown(f"### {p.street}")
    st.markdown(f"**{p.city}, {p.state} {p.zip_code}**")
    if p.url:
        st.link_button("Open on Realtor.com", p.url)
    ca, cb, cc = st.columns(3)
    ca.metric("List Price", f"${p.list_price:,.0f}")
    cb.metric("Est. Value", f"${p.zestimate:,.0f}" if p.zestimate else "N/A")
    discount_delta = f"${(p.zestimate - p.list_price):,.0f} below est." if p.zestimate and p.zestimate > p.list_price else None
    cc.metric("Discount", f"{p.equity_discount_pct:.1f}%" if p.equity_discount_pct > 0 else "N/A", delta=discount_delta)
    cd, ce, cf = st.columns(3)
    cd.metric("Beds", p.beds or "?")
    ce.metric("Baths", p.baths or "?")
    cf.metric("Sqft", f"{p.sqft:,}" if p.sqft else "?")
    if p.year_built:
        st.caption(f"Built {p.year_built}  |  {p.price_per_sqft or '?'} $/sqft")

with right:
    st.markdown("### Financial Analysis")
    if p.is_assumable:
        confidence = "Confirmed (explicitly listed)" if not p.assumable_inferred else "Possible (sold in low-rate era)"
        st.info(f"**Assumable confidence:** {confidence}")

        cg, ch = st.columns(2)
        delta_rate = f"{p.assumed_rate - current_rate:.2f}% vs market"
        cg.metric("Assumed Rate", f"{p.assumed_rate:.2f}%", delta=delta_rate, delta_color="inverse")
        ch.metric("Market Rate", f"{current_rate:.2f}%")

        ci, cj = st.columns(2)
        ci.metric("Monthly Savings", f"${p.monthly_payment_savings:,.0f}", help="80% LTV assumed")
        cj.metric("Annual Savings", f"${p.annual_savings:,.0f}")

        loan = p.list_price * 0.8
        pmt_a = monthly_payment(loan, p.assumed_rate)
        pmt_m = monthly_payment(loan, current_rate)
        fig2 = go.Figure(go.Bar(
            x=["Assumed Mortgage", "New Mortgage at Market"],
            y=[pmt_a, pmt_m],
            marker_color=["#4ade80", "#ef4444"],
            text=[f"${pmt_a:,.0f}/mo", f"${pmt_m:,.0f}/mo"],
            textposition="auto",
        ))
        fig2.update_layout(
            title="Monthly Payment (80% LTV)",
            template="plotly_dark", height=240,
            showlegend=False, yaxis_title="$/month",
            margin=dict(t=35, b=10),
        )
        st.plotly_chart(fig2, use_container_width=True)

        # 10-year savings projection
        yrs = list(range(1, 11))
        cumulative = [p.monthly_payment_savings * 12 * y for y in yrs]
        fig3 = go.Figure(go.Scatter(
            x=yrs, y=cumulative,
            fill="tozeroy", line=dict(color="#4ade80"),
            text=[f"${v:,.0f}" for v in cumulative],
        ))
        fig3.update_layout(
            title="Cumulative Savings Over 10 Years",
            template="plotly_dark", height=220,
            xaxis_title="Year", yaxis_title="Savings ($)",
            margin=dict(t=35, b=10),
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No assumable financing signals detected for this property.")

# Signals
sig1, sig2 = st.columns(2)
with sig1:
    st.markdown("**Pre-Foreclosure Signals**")
    for s in (p.preforeclosure_signals or ["None"]):
        st.markdown(f"- `{s}`")
with sig2:
    st.markdown("**Assumable Signals**")
    for s in (p.assumable_signals or ["None"]):
        st.markdown(f"- `{s}`")

if p.description:
    with st.expander("Listing Description"):
        st.write(p.description)

# ── Disclaimer ────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "⚠️ For informational purposes only. Verify assumability with the lender — not all loans on "
    "'possibly assumable' properties are actually assumable. Consult a licensed real estate "
    "attorney before acting. Profitability scores are estimates based on available listing data."
)
