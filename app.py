import streamlit as st
import os
import re
import sqlite3
import pandas as pd
from rapidfuzz import fuzz

#config
DB_FOLDER      = "constituency_dbs"
NAME_THRESHOLD = 80
RELATIVE_THRESHOLD = 80
AC_MAPPING_URL = "https://ceodelhi.gov.in/PDFFolders/2025/AC_Mapping_from_2002_to_2025.pdf"
CHUNK_SIZE     = 5000

st.set_page_config(page_title="Electoral Fuzzy Search", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Noto+Sans:wght@300;400;500&display=swap');

    html, body, [class*="css"] { font-family: 'Noto Sans', sans-serif; }
    .stApp { background: #0f1117; color: #e8e8e8; }
    h1, h2, h3 { font-family: 'Rajdhani', sans-serif !important; letter-spacing: 0.05em; }

    .topbar {
        display: flex; align-items: center; justify-content: space-between;
        border-bottom: 2px solid #f0a500; padding-bottom: 0.5rem; margin-bottom: 1.5rem;
    }
    .main-title {
        font-family: 'Rajdhani', sans-serif;
        font-size: 2.4rem; font-weight: 700; color: #f0a500;
        letter-spacing: 0.1em; text-transform: uppercase; margin: 0;
    }
    .ac-link {
        font-family: 'Rajdhani', sans-serif; font-size: 0.85rem;
        color: #f0a500; text-decoration: none; font-weight: 600;
        letter-spacing: 0.06em; text-transform: uppercase;
        border: 1px solid #f0a500; border-radius: 4px;
        padding: 4px 12px; white-space: nowrap;
    }
    .ac-link:hover { background: #f0a500; color: #0f1117; }
    .result-card {
        background: #1a1d27; border: 1px solid #2e3245;
        border-left: 4px solid #f0a500; border-radius: 6px;
        padding: 1rem 1.4rem; margin-bottom: 1rem;
    }
    .result-header {
        font-family: 'Rajdhani', sans-serif; font-size: 1.1rem;
        font-weight: 600; color: #f0a500; margin-bottom: 0.5rem;
    }
    .badge {
        display: inline-block; padding: 2px 10px; border-radius: 20px;
        font-size: 0.75rem; font-weight: 600; margin-right: 6px;
    }
    .badge-name   { background: #1e3a5f; color: #5ab4ff; }
    .badge-rel    { background: #1e4a30; color: #5ddf8a; }
    .badge-male   { background: #1a2f4a; color: #7ab8f5; }
    .badge-female { background: #3a1a3a; color: #f5a7f5; }
    .badge-age    { background: #2a2a1a; color: #e0d080; }
    .badge-ac     { background: #2a1a2a; color: #d07af5; }
    .row-text {
        font-family: 'Noto Sans', sans-serif; font-size: 0.95rem; color: #ccc;
        background: #12151e; border-radius: 4px; padding: 0.5rem 0.8rem;
        margin-top: 0.5rem; font-style: italic;
    }
    div[data-testid="stButton"] > button {
        background: #f0a500; color: #0f1117;
        font-family: 'Rajdhani', sans-serif; font-size: 1rem;
        font-weight: 700; letter-spacing: 0.08em; border: none;
        border-radius: 4px; padding: 0.5rem 2rem; text-transform: uppercase;
    }
    div[data-testid="stButton"] > button:hover { background: #ffc233; }
    div[data-testid="stSelectbox"] label,
    div[data-testid="stTextInput"] label,
    div[data-testid="stNumberInput"] label {
        color: #aaa; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em;
    }
    .filter-section {
        background: #1a1d27; border: 1px solid #2e3245;
        border-radius: 8px; padding: 1.2rem 1.4rem; margin-bottom: 1.5rem;
    }
    .section-label {
        font-family: 'Rajdhani', sans-serif; font-size: 0.85rem; color: #666;
        text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 0.8rem;
    }
    .age-hint { font-size: 0.8rem; color: #f0a500; margin-top: 0.3rem; font-style: italic; }
    .warn-all-ac {
        background: #2a1f00; border: 1px solid #f0a500; border-radius: 6px;
        padding: 0.6rem 1rem; font-size: 0.85rem; color: #f0c040; margin-bottom: 1rem;
    }
    .no-index-warn {
        background: #2a0000; border: 1px solid #f05050; border-radius: 6px;
        padding: 0.6rem 1rem; font-size: 0.85rem; color: #f08080; margin-bottom: 1rem;
    }
    .pdf-btn {
        display: inline-block; margin-top: 0.6rem;
        background: transparent; color: #f0a500;
        border: 1px solid #f0a500; border-radius: 4px;
        padding: 3px 14px; font-size: 0.78rem; font-family: 'Rajdhani', sans-serif;
        font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase;
        text-decoration: none; cursor: pointer;
    }
    .pdf-btn:hover { background: #f0a500; color: #0f1117; }
</style>
""", unsafe_allow_html=True)



def normalize(text):
    text = text.lower()
    text = re.sub(r'[^a-z\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def db_path(constituency):
    return os.path.join(DB_FOLDER, f"{constituency}.db")


def index_exists(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='voter_index'"
    )
    return cur.fetchone() is not None


@st.cache_data(show_spinner=False)
def get_constituencies():
    if not os.path.exists(DB_FOLDER):
        return []
    names = []
    for f in os.listdir(DB_FOLDER):
        if f.endswith(".db"):
            names.append(f.replace(".db", ""))
    # sort numerically
    names.sort(key=lambda x: int(x) if x.isdigit() else 0)
    return names


@st.cache_data(show_spinner=False)
def has_prebuilt_index():
    """Check if at least one DB has a voter_index table."""
    if not os.path.exists(DB_FOLDER):
        return False
    for f in os.listdir(DB_FOLDER):
        if f.endswith(".db"):
            conn = sqlite3.connect(os.path.join(DB_FOLDER, f))
            result = index_exists(conn)
            conn.close()
            if result:
                return True
    return False


def query_db(constituency, gender, age_min, age_max):
    """
    Multi-DB version: scans individual constituency DB files.
    Keeps output format EXACTLY same as before.
    """
    rows = []

    if constituency:
        ac_list = [constituency] if isinstance(constituency, str) else list(constituency)
    else:
        ac_list = []
        for f in os.listdir(DB_FOLDER):
            if f.endswith(".db"):
                ac_list.append(f.replace(".db", ""))

    for ac in ac_list:
        path = db_path(ac)

        if not os.path.exists(path):
            continue

        conn = sqlite3.connect(path)

        try:
            use_index = index_exists(conn)
            table     = "voter_index" if use_index else "voter"

            query  = f"SELECT constituency, part, sNo, gender, age, {'raw, norm' if use_index else 'row'} FROM {table} WHERE 1=1"
            params = []

            if gender:
                query += " AND gender = ?"
                params.append(gender)

            if age_min is not None and age_max is not None:
                query += " AND age BETWEEN ? AND ?"
                params.extend([age_min, age_max])

            df = pd.read_sql_query(query, conn, params=params)

            for _, rec in df.iterrows():
                if use_index:
                    raw  = str(rec.get("raw", ""))
                    norm = str(rec.get("norm", ""))
                else:
                    raw  = str(rec.get("row", ""))
                    norm = normalize(raw)

                if len(raw) > 5:
                    rows.append({
                        "constituency": rec.get("constituency", ac),
                        "part":         rec.get("part", ""),
                        "sNo":          rec.get("sNo", ""),
                        "gender":       rec.get("gender", ""),
                        "age":          int(rec.get("age") or 0),
                        "raw":          raw,
                        "norm":         norm,
                    })

        except Exception:
            continue

        finally:
            conn.close()

    return rows


def do_fuzzy_search(rows, name, relative):
    n_name = normalize(name)
    n_rel  = normalize(relative)
    results = []
    for row in rows:
        name_score = fuzz.partial_ratio(n_name, row["norm"])
        rel_score  = fuzz.partial_ratio(n_rel,  row["norm"])
        if name_score >= NAME_THRESHOLD and rel_score >= RELATIVE_THRESHOLD:
            results.append({
                "constituency":   row["constituency"],
                "part":           row["part"],
                "sNo":            row["sNo"],
                "gender":         row["gender"],
                "age":            row["age"],
                "name_score":     name_score,
                "relative_score": rel_score,
                "text":           row["raw"],
            })
    results.sort(key=lambda x: x["name_score"] + x["relative_score"], reverse=True)
    return results


def do_fuzzy_search_chunked(rows, name, relative, status_el, progress_el):
    n_name  = normalize(name)
    n_rel   = normalize(relative)
    results = []
    total   = len(rows)

    for start in range(0, total, CHUNK_SIZE):
        chunk = rows[start : start + CHUNK_SIZE]
        for row in chunk:
            name_score = fuzz.partial_ratio(n_name, row["norm"])
            rel_score  = fuzz.partial_ratio(n_rel,  row["norm"])
            if name_score >= NAME_THRESHOLD and rel_score >= RELATIVE_THRESHOLD:
                results.append({
                    "constituency":   row["constituency"],
                    "part":           row["part"],
                    "sNo":            row["sNo"],
                    "gender":         row["gender"],
                    "age":            row["age"],
                    "name_score":     name_score,
                    "relative_score": rel_score,
                    "text":           row["raw"],
                })
        pct = min(start + CHUNK_SIZE, total)
        status_el.markdown(
            f'<div class="age-hint">Scanned {pct:,} / {total:,} rows — {len(results)} match(es) so far…</div>',
            unsafe_allow_html=True
        )
        progress_el.progress(pct / total)

    results.sort(key=lambda x: x["name_score"] + x["relative_score"], reverse=True)
    return results


def result_card_html(i, r):
    gender_badge_cls = "badge-male" if r["gender"] == "M" else "badge-female"
    gender_label     = "Male"       if r["gender"] == "M" else "Female"
    constituency     = str(r['constituency']).zfill(3)
    part             = str(r['part']).zfill(3)
    pdf_url = (
        f"https://sakshamo5.github.io/Delhi-SIR-Helper/eci_pdfs/U05/"
        f"{constituency}/U05_{constituency}_{part}.pdf"
    )
    return f"""
    <div class="result-card">
        <div class="result-header">#{i} — S.No {r['sNo']} &nbsp;|&nbsp; Part {r['part']} &nbsp;|&nbsp; AC {r['constituency']}</div>
        <span class="badge badge-name">Name {r['name_score']}%</span>
        <span class="badge badge-rel">Relative {r['relative_score']}%</span>
        <span class="badge {gender_badge_cls}">{gender_label}</span>
        <span class="badge badge-age">Age {r['age']} (in 2002)</span>
        <span class="badge badge-ac">AC {r['constituency']}</span>
        <div class="row-text">{r['text']}</div>
        <a class="pdf-btn" href="{pdf_url}" target="_blank">&#128196; View PDF</a>
    </div>"""


def render_results(results):
    if results:
        st.success(f"✅ {len(results)} match(es) found")
        for i, r in enumerate(results[:20], 1):
            st.markdown(result_card_html(i, r), unsafe_allow_html=True)
    else:
        st.info("No matches found. Try adjusting filters or check spelling.")


def age_filter_ui(key_suffix):
    gender_option = st.selectbox("Gender (optional)", options=["Any", "Male", "Female"], index=0, key=f"g_{key_suffix}")
    current_age   = st.number_input("Current Age (optional)", min_value=0, max_value=120, value=0, step=1,
        key=f"a_{key_suffix}",
        help="Searches 2002 records where age was (current−30) to (current−20).")
    gender = {"Any": None, "Male": "M", "Female": "F"}[gender_option]
    if current_age > 0:
        age_min = max(0, current_age - 30)
        age_max = max(0, current_age - 20)
        st.markdown(f'<div class="age-hint">↳ Filtering 2002 records with age {age_min}–{age_max}</div>', unsafe_allow_html=True)
    else:
        age_min = age_max = None
    return gender, age_min, age_max


if not os.path.exists(DB_FOLDER):
    st.error(f"Folder `{DB_FOLDER}` not found. Create it and place constituency DBs inside.")
    st.stop()

constituencies = get_constituencies()
if not constituencies:
    st.error("Could not load constituencies. Check DB schema.")
    st.stop()

st.markdown(f"""
<div class="topbar">
    <div class="main-title">🗳️ Electoral Roll — Fuzzy Search</div>
    <a class="ac-link" href="{AC_MAPPING_URL}" target="_blank">📄 2002 → 2025 AC Mapping</a>
</div>
""", unsafe_allow_html=True)

# Show index status
if not has_prebuilt_index():
    st.markdown("""
    <div class="no-index-warn">
        ⚠️ Pre-built index not found. Run <code>python preprocess.py</code> once locally for faster searches.
        App will still work but normalize on the fly.
    </div>
    """, unsafe_allow_html=True)

# ========== PAGE TOGGLE ==========
page = st.radio(
    "Mode", ["Search by Constituency", "Search All Constituencies"],
    horizontal=True, label_visibility="collapsed"
)
st.markdown("---")

# ============================================================
# PAGE 1 — Single Constituency
# ============================================================
if page == "Search by Constituency":

    if "results_single" not in st.session_state:
        st.session_state.results_single = []

    st.markdown('<div class="filter-section"><div class="section-label">Filters</div>', unsafe_allow_html=True)

    selected_constituencies = st.multiselect(
        "Constituency Numbers (select 1–4)",
        options=constituencies,
        default=[constituencies[0]] if constituencies else [],
        max_selections=4,
        key="c_single",
        help="Select up to 4 ACs — useful when old→new AC mapping isn't 1-to-1."
    )
    if not selected_constituencies:
        st.warning("Please select at least one constituency.")

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        selected_gender, age_min, age_max = age_filter_ui("single")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="filter-section"><div class="section-label">Name Search</div>', unsafe_allow_html=True)
    scol1, scol2 = st.columns(2)
    with scol1:
        name = st.text_input("Name", placeholder="e.g. Virender Kumar", key="n_single")
    with scol2:
        relative = st.text_input("Relative Name", placeholder="e.g. Dharam Singh", key="r_single")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("Search", key="btn_single"):
        if not selected_constituencies:
            st.warning("Please select at least one constituency.")
        elif not name or not relative:
            st.warning("Please enter both Name and Relative Name.")
        else:
            with st.spinner("Searching…"):
                rows = query_db(selected_constituencies, selected_gender, age_min, age_max)
                st.session_state.results_single = do_fuzzy_search(rows, name, relative)

    if st.session_state.results_single or (selected_constituencies and name and relative):
        render_results(st.session_state.results_single)


# ============================================================
# PAGE 2 — All Constituencies
# ============================================================
else:

    if "results_all" not in st.session_state:
        st.session_state.results_all = []

    st.markdown("""
    <div class="warn-all-ac">
        ⚠️ Scanning all constituencies. Use gender + age filters to narrow results and speed things up.
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="filter-section"><div class="section-label">Filters</div>', unsafe_allow_html=True)
    fcol1, fcol2 = st.columns(2)
    with fcol1:
        selected_gender_all, age_min_all, age_max_all = age_filter_ui("all")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="filter-section"><div class="section-label">Name Search</div>', unsafe_allow_html=True)
    scol1, scol2 = st.columns(2)
    with scol1:
        name_all = st.text_input("Name", placeholder="e.g. Virender Kumar", key="n_all")
    with scol2:
        relative_all = st.text_input("Relative Name", placeholder="e.g. Dharam Singh", key="r_all")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("Search All ACs", key="btn_all"):
        if not name_all or not relative_all:
            st.warning("Please enter both Name and Relative Name.")
        else:
            rows        = query_db(None, selected_gender_all, age_min_all, age_max_all)
            status_el   = st.empty()
            progress_el = st.empty()
            results     = do_fuzzy_search_chunked(rows, name_all, relative_all, status_el, progress_el)
            status_el.empty()
            progress_el.empty()
            st.session_state.results_all = results

    if st.session_state.results_all or (name_all and relative_all):
        render_results(st.session_state.results_all)
