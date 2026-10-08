"""GridScout's local discovery experience."""
import json
import os
from pathlib import Path

import geopandas as gpd
import streamlit as st
from dotenv import load_dotenv
from streamlit_folium import st_folium

from gridscout.maps import build_map
from gridscout.scoring import FEATURES, LABELS, explain, score_breakdown, score_candidates
from gridscout.settings import ROOT, read_config

load_dotenv(ROOT / ".env")
st.set_page_config(page_title="GridScout | Discover storage opportunity",page_icon="◈",layout="wide")
st.markdown("""<style>
[data-testid="stAppViewContainer"]{background:#101820;color:#e7ecef}
[data-testid="stSidebar"]{background:#151f29;border-right:1px solid #293746}
.block-container{padding-top:3.5rem;max-width:1600px}
h1,h2,h3{font-family:Georgia,serif!important;letter-spacing:-.035em}
h1{font-size:3.4rem!important;line-height:1.06!important}
.eyebrow{font:12px monospace;letter-spacing:2px;color:#78d6b6;text-transform:uppercase}
.intro{color:#aabac8;max-width:690px;font-size:17px}
.brand{font:24px Georgia,serif;color:#f5d667;margin-bottom:2rem}
.signal-note{border-left:2px solid #78d6b6;padding:10px 16px;color:#acbdca;background:#17242d;margin:16px 0}
[data-testid="stMetricValue"]{font-family:monospace;color:#f5d667}
[data-testid="stMetricLabel"]{color:#aabac8}
button{border-radius:3px!important}
</style>""",unsafe_allow_html=True)


@st.cache_data(show_spinner="Loading infrastructure evidence…")
def load_data(directory, signature):
    path = Path(directory)
    frames = [gpd.read_parquet(path/f"{name}.parquet") for name in ["candidates","transmission","plants","counties"]]
    manifest = json.loads((path/"manifest.json").read_text(encoding="utf-8"))
    return *frames,manifest


with st.sidebar:
    st.markdown('<div class="brand">◈ GridScout</div>',unsafe_allow_html=True)
    st.caption("OPPORTUNITY ENGINE / TEXAS")
    public_ready = (ROOT/"data/processed/candidates.parquet").exists()
    modes = ["Public infrastructure","Synthetic demo"] if public_ready else ["Synthetic demo"]
    mode = st.selectbox("Evidence set",modes)
    st.markdown("### Shape the search")
    st.caption("Move the weights. Discover what rises.")
    defaults = read_config()["weights"]
    weights = {feature: st.slider(LABELS[feature],0.0,1.0,float(defaults[feature]),.05,key=f"weight_{feature}") for feature in FEATURES}
    st.caption("Weights are normalized to sum to one.")
    with st.expander("Map layers",expanded=True):
        show_lines = st.toggle("High-voltage transmission",value=True)
        show_plants = st.toggle("Power plants",value=True)
    st.divider()
    st.caption("SCREENING → EVIDENCE → DILIGENCE")
    st.caption("Geographic signals identify research leads. Grid access and economic value require separate diligence.")

data_dir = ROOT/("data/processed" if mode == "Public infrastructure" else "data/demo")
if not (data_dir/"candidates.parquet").exists():
    st.info("Prepare the demo once: python -m gridscout demo")
    st.stop()
signature = tuple((p.name,p.stat().st_mtime_ns) for p in data_dir.glob("*.parquet")) + (("manifest",(data_dir/"manifest.json").stat().st_mtime_ns),)
candidates,lines,plants,counties,manifest = load_data(str(data_dir),signature)
if sum(weights.values()) == 0:
    st.warning("Give at least one signal a positive weight to rank prospects.")
    st.stop()
ranked = score_candidates(candidates,weights)
top = ranked.head(50)

st.markdown('<p class="eyebrow">Texas / battery storage / opportunity discovery</p>',unsafe_allow_html=True)
st.title("Find the next storage opportunity.")
st.markdown('<p class="intro">Follow the infrastructure signals. Surface promising places. Turn a map pin into a research lead.</p>',unsafe_allow_html=True)
if manifest["mode"] == "synthetic":
    st.warning("SYNTHETIC DEMO · Fictional infrastructure and an illustrative boundary. These are not real development prospects.")
else:
    st.caption("PUBLIC EVIDENCE · EIA 2025 · TIGER/Line 2025 · HIFLD copy: underlying data edited 2022. Line-level dates vary.")
metrics = st.columns(4)
metrics[0].metric("Cells scanned",f"{len(candidates):,}")
metrics[1].metric("Prospects surfaced",len(top))
metrics[2].metric("Leading signal score",f"{top.iloc[0].score:.3f}")
metrics[3].metric("Renewable search radius","25 km")
st.divider()

ids = top.site_id.tolist()
mode_key = manifest["mode"]
widget_key = f"selected_{mode_key}"
pending = st.session_state.pop("map_selection",None)
if pending in ids:
    st.session_state[widget_key] = pending
if st.session_state.get(widget_key) not in ids:
    st.session_state[widget_key] = ids[0]
map_column,detail_column = st.columns([1.65,1],gap="large")
with detail_column:
    st.markdown("### Follow a prospect")
    site_id = st.selectbox("Select a top site",ids,key=widget_key,format_func=lambda value: f"#{int(top.loc[top.site_id==value,'rank'].iloc[0]):02} · {value}")
    site = top.loc[top.site_id==site_id].iloc[0]
    st.caption(f"{site['county']} · {site.latitude:.4f}, {site.longitude:.4f}")
    st.metric("Opportunity signal",f"{site.score:.3f} / 1.000")
    st.markdown("#### Why it surfaced")
    st.write(explain(site))
    breakdown = score_breakdown(site)
    st.dataframe(breakdown[["Signal","+ score"]],hide_index=True,width="stretch",column_config={"Signal":st.column_config.TextColumn(width="medium"),"+ score":st.column_config.NumberColumn(format="+%.3f",width="small")})
    st.markdown('<div class="signal-note">A nearby line is a research lead. Its voltage and proximity do not establish available interconnection capacity.</div>',unsafe_allow_html=True)
    with st.expander("Nearby renewable evidence"):
        nearby = json.loads(site.nearby_plants_json)
        if nearby:
            st.dataframe(nearby,hide_index=True,width="stretch")
        else:
            st.caption("No operating solar or wind plants were found inside the search radius.")
    st.markdown("#### Research memo")
    memo_mode = st.radio("Writer",["Evidence brief (no API)","LLM research memo"],horizontal=True)
    if "memo_agent" not in st.session_state:
        from gridscout.memos import MemoAgent
        st.session_state.memo_agent = MemoAgent(ROOT/"data/memos",max_calls=int(os.getenv("GRIDSCOUT_MAX_MEMOS","3")))
    agent = st.session_state.memo_agent
    st.caption(f"LLM calls this session: {agent.calls}/{agent.max_calls}. Cached memos do not use the API.")
    if st.button("Write this prospect’s memo",type="primary",width="stretch"):
        from gridscout.memos import evidence_packet
        try:
            with st.spinner("Assembling evidence and writing memo…"):
                packet = evidence_packet(site,lines,manifest,weights)
                memo = agent.generate(packet,use_llm=memo_mode.startswith("LLM"))
                st.session_state[f"memo_{mode_key}_{site_id}"] = memo
        except Exception as error:
            st.error(str(error))
    memo = st.session_state.get(f"memo_{mode_key}_{site_id}")
    if memo:
        from gridscout.memos import memo_markdown
        markdown = memo_markdown(memo)
        st.markdown(markdown)
        st.download_button("Export memo",markdown,f"{site_id}-memo.md",mime="text/markdown")

with map_column:
    st.caption("DISCOVERY FIELD · TOP 50 · CLICK A PROSPECT TO FOLLOW IT")
    view = build_map(top,lines,plants,counties,selected=site_id,show_lines=show_lines,show_plants=show_plants)
    interaction = st_folium(view,height=480,width="100%",key=f"discovery_{mode_key}_{site_id}",returned_objects=["last_object_clicked_tooltip"])
    clicked = interaction.get("last_object_clicked_tooltip") if interaction else None
    if clicked in ids and clicked != site_id:
        st.session_state.map_selection = clicked
        st.rerun()
    st.caption("● Low score: blue · High score: yellow     /     ─ Transmission     /     ● Solar: amber · Wind: cyan")

with st.expander("The opportunity field · ranked prospects"):
    st.dataframe(top[["rank","site_id","county","score","distance_to_hv_m","voltage_kv","solar_count","wind_count","renewable_capacity_mw"]],hide_index=True,width="stretch")
    st.download_button("Export ranked features",ranked.drop(columns=["geometry"]).to_csv(index=False),"gridscout-ranked-sites.csv","text/csv")
with st.expander("Source provenance & cleaning audit"):
    st.json(manifest)
