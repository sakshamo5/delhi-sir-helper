import streamlit as st
import os
import re
import sqlite3
from rapidfuzz import fuzz

#config
DB_FOLDER      = "constituency_dbs"
NAME_THRESHOLD = 80
RELATIVE_THRESHOLD = 80
AC_MAPPING_URL = "https://ceodelhi.gov.in/PDFFolders/2025/AC_Mapping_from_2002_to_2025.pdf"
CHUNK_SIZE     = 2000

st.set_page_config(page_title="Electoral Fuzzy Search", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Noto+Sans:wght@300;400;500&display=swap');

    /* ── CSS variables: dark mode (default) ── */
    :root {
        --bg:           #0f1117;
        --bg-card:      #1a1d27;
        --bg-input:     #1a1d27;
        --bg-deep:      #12151e;
        --border:       #2e3245;
        --border-hover: #f0a500;
        --text:         #e8e8e8;
        --text-sub:     #cccccc;
        --accent:       #f0a500;
        --accent-hover: #ffc233;
        --accent-fg:    #0f1117;
        --placeholder:  #7a6020;
        --warn-bg:      #2a1f00;
        --warn-text:    #f0c040;
        --err-bg:       #2a0000;
        --err-border:   #f05050;
        --err-text:     #f08080;
        --drop-bg:      #1a1d27;
        --drop-hover:   #2a2200;
    }

    /* ── CSS variables: light mode ── */
    @media (prefers-color-scheme: light) {
        :root {
            --bg:           #f5f6fa;
            --bg-card:      #ffffff;
            --bg-input:     #ffffff;
            --bg-deep:      #eef0f6;
            --border:       #c8cde0;
            --border-hover: #1a3a6b;
            --text:         #0f1117;
            --text-sub:     #2e3245;
            --accent:       #1a3a6b;
            --accent-hover: #0f2548;
            --accent-fg:    #ffffff;
            --placeholder:  #6b82aa;
            --warn-bg:      #fff8e1;
            --warn-text:    #7a4f00;
            --err-bg:       #fff0f0;
            --err-border:   #e05050;
            --err-text:     #900000;
            --drop-bg:      #ffffff;
            --drop-hover:   #e8edf8;
        }
    }

    /* ── Base ── */
    html, body, [class*="css"] { font-family: 'Noto Sans', sans-serif; }
    .stApp { background: var(--bg) !important; color: var(--text) !important; }
    h1, h2, h3 { font-family: 'Rajdhani', sans-serif !important; letter-spacing: 0.05em; }

    /* ── Topbar ── */
    .topbar {
        display: flex; align-items: center; justify-content: space-between;
        border-bottom: 2px solid var(--accent); padding-bottom: 0.5rem; margin-bottom: 1.5rem;
    }
    .main-title {
        font-family: 'Rajdhani', sans-serif;
        font-size: 2.4rem; font-weight: 700; color: var(--accent);
        letter-spacing: 0.1em; text-transform: uppercase; margin: 0;
    }
    .ac-link {
        font-family: 'Rajdhani', sans-serif; font-size: 0.85rem;
        color: var(--accent); text-decoration: none; font-weight: 600;
        letter-spacing: 0.06em; text-transform: uppercase;
        border: 1px solid var(--accent); border-radius: 4px;
        padding: 4px 12px; white-space: nowrap;
    }
    .ac-link:hover { background: var(--accent); color: var(--accent-fg); }

    /* ── Result cards ── */
    .result-card {
        background: var(--bg-card); border: 1px solid var(--border);
        border-left: 4px solid var(--accent); border-radius: 6px;
        padding: 1rem 1.4rem; margin-bottom: 1rem;
    }
    .result-header {
        font-family: 'Rajdhani', sans-serif; font-size: 1.1rem;
        font-weight: 600; color: var(--accent); margin-bottom: 0.5rem;
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
    @media (prefers-color-scheme: light) {
        .badge-name   { background: #ddeeff; color: #1a3a6b; }
        .badge-rel    { background: #ddf5e8; color: #1a5a3a; }
        .badge-male   { background: #ddeeff; color: #1a3a6b; }
        .badge-female { background: #f0ddff; color: #6a1a9a; }
        .badge-age    { background: #e8edf8; color: #1a3a6b; }
        .badge-ac     { background: #e0e8ff; color: #2a3a8a; }
    }
    .row-text {
        font-family: 'Noto Sans', sans-serif; font-size: 0.95rem; color: var(--text-sub);
        background: var(--bg-deep); border-radius: 4px; padding: 0.5rem 0.8rem;
        margin-top: 0.5rem; font-style: italic;
    }

    /* ── Search button ── */
    div[data-testid="stButton"] > button {
        background: var(--accent); color: var(--accent-fg);
        font-family: 'Rajdhani', sans-serif; font-size: 1rem;
        font-weight: 700; letter-spacing: 0.08em; border: none;
        border-radius: 4px; padding: 0.5rem 2rem; text-transform: uppercase;
    }
    div[data-testid="stButton"] > button:hover { background: var(--accent-hover); }

    /* ── Widget labels ── */
    div[data-testid="stSelectbox"] label,
    div[data-testid="stTextInput"] label,
    div[data-testid="stNumberInput"] label,
    div[data-testid="stMultiSelect"] label {
        color: var(--accent) !important; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em;
    }

    /* ── Input / selectbox boxes ── */
    div[data-testid="stSelectbox"] > div > div,
    div[data-testid="stTextInput"] > div > div > input,
    div[data-testid="stNumberInput"] > div > div > input {
        background: var(--bg-input) !important;
        border: 1px solid var(--accent) !important;
        color: var(--text) !important;
        border-radius: 4px !important;
    }

    /* ── Selectbox arrow & selected text ── */
    div[data-testid="stSelectbox"] svg { fill: var(--accent) !important; }
    div[data-testid="stSelectbox"] span { color: var(--text) !important; }

    /* ── Dropdown menu ── */
    div[data-baseweb="select"] ul {
        background: var(--drop-bg) !important;
        border: 1px solid var(--accent) !important;
    }
    div[data-baseweb="select"] li {
        background: var(--drop-bg) !important;
        color: var(--text) !important;
    }
    div[data-baseweb="select"] li:hover { background: var(--drop-hover) !important; }

    /* ── Multiselect ── */
    div[data-testid="stMultiSelect"] > div > div {
        background: var(--bg-input) !important;
        border: 1px solid var(--accent) !important;
        border-radius: 4px !important;
    }
    div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
        background: var(--accent) !important;
        color: var(--accent-fg) !important;
    }
    div[data-testid="stMultiSelect"] input { color: var(--text) !important; }
    div[data-testid="stMultiSelect"] svg { fill: var(--accent) !important; }

    /* ── Number input +/- ── */
    div[data-testid="stNumberInput"] button {
        background: var(--bg-input) !important;
        border: 1px solid var(--accent) !important;
        color: var(--accent) !important;
        border-radius: 4px !important;
    }
    div[data-testid="stNumberInput"] button:hover {
        background: var(--accent) !important; color: var(--accent-fg) !important;
    }
    div[data-testid="stNumberInput"] button svg { fill: var(--accent) !important; }
    div[data-testid="stNumberInput"] button:hover svg { fill: var(--accent-fg) !important; }

    /* ── Radio buttons ── */
    div[data-testid="stRadio"] label { color: var(--accent) !important; }
    div[data-testid="stRadio"] div[role="radio"] div { border-color: var(--accent) !important; }
    div[data-testid="stRadio"] div[aria-checked="true"] div { background: var(--accent) !important; }

    /* ── Help icon ── */
    button[data-testid="stBaseButton-elementToolbar"] svg { fill: var(--accent) !important; }

    /* ── Misc ── */
    input::placeholder { color: var(--placeholder) !important; }
    hr { border-color: var(--accent) !important; opacity: 0.3; }

    /* ── Filter section ── */
    .filter-section {
        background: var(--bg-card); border: 1px solid var(--border);
        border-radius: 8px; padding: 1.2rem 1.4rem; margin-bottom: 1.5rem;
    }
    .section-label {
        font-family: 'Rajdhani', sans-serif; font-size: 0.85rem; color: var(--accent);
        text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 0.8rem;
    }
    .age-hint { font-size: 0.8rem; color: var(--accent); margin-top: 0.3rem; font-style: italic; }

    /* ── Warnings ── */
    .warn-all-ac {
        background: var(--warn-bg); border: 1px solid var(--accent); border-radius: 6px;
        padding: 0.6rem 1rem; font-size: 0.85rem; color: var(--warn-text); margin-bottom: 1rem;
    }
    .no-index-warn {
        background: var(--err-bg); border: 1px solid var(--err-border); border-radius: 6px;
        padding: 0.6rem 1rem; font-size: 0.85rem; color: var(--err-text); margin-bottom: 1rem;
    }

    /* ── PDF button ── */
    .pdf-btn {
        display: inline-block; margin-top: 0.6rem;
        background: transparent; color: var(--accent);
        border: 1px solid var(--accent); border-radius: 4px;
        padding: 3px 14px; font-size: 0.78rem; font-family: 'Rajdhani', sans-serif;
        font-weight: 600; letter-spacing: 0.07em; text-transform: uppercase;
        text-decoration: none; cursor: pointer;
    }
    .pdf-btn:hover { background: var(--accent); color: var(--accent-fg); }
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
    names.sort(key=lambda x: int(x) if x.isdigit() else 0)
    return names


@st.cache_data(show_spinner=False)
def has_prebuilt_index():
    """Check if at least one DB has a voter_index table."""
    if not os.path.exists(DB_FOLDER):
        return False
    for f in os.listdir(DB_FOLDER):
        if f.endswith(".db"):
            path = os.path.join(DB_FOLDER, f)
            try:
                conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                result = index_exists(conn)
                conn.close()
                if result:
                    return True
            except Exception:
                pass
    return False


def search_db_streaming(ac, gender, age_min, age_max, n_name, n_rel):
    """
    Stream rows from one constituency DB in small batches.
    Fuzzy-match on the fly — never builds a full in-memory row list.
    Returns only matches (no intermediate storage of all rows).
    """
    path = db_path(ac)
    if not os.path.exists(path):
        return []

    results = []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        use_index = index_exists(conn)
        table     = "voter_index" if use_index else "voter"

        cols   = "constituency, part, sNo, gender, age, raw, norm" if use_index else "constituency, part, sNo, gender, age, row"
        query  = f"SELECT {cols} FROM {table} WHERE 1=1"
        params = []

        if gender:
            query += " AND gender = ?"
            params.append(gender)
        if age_min is not None and age_max is not None:
            query += " AND age BETWEEN ? AND ?"
            params.extend([age_min, age_max])

        cur = conn.execute(query, params)

        while True:
            batch = cur.fetchmany(CHUNK_SIZE)
            if not batch:
                break
            for rec in batch:
                raw  = str(rec["raw"]  if use_index else rec["row"])
                norm = str(rec["norm"] if use_index else normalize(raw))
                if len(raw) <= 5:
                    continue
                # Early-exit: check name score first (cheaper gate)
                name_score = fuzz.partial_ratio(n_name, norm)
                if name_score < NAME_THRESHOLD:
                    continue
                rel_score = fuzz.partial_ratio(n_rel, norm)
                if rel_score < RELATIVE_THRESHOLD:
                    continue
                results.append({
                    "constituency":   rec["constituency"] or ac,
                    "part":           rec["part"],
                    "sNo":            rec["sNo"],
                    "gender":         rec["gender"],
                    "age":            int(rec["age"] or 0),
                    "name_score":     name_score,
                    "relative_score": rel_score,
                    "text":           raw,
                })

        conn.close()
    except Exception:
        pass

    return results


def do_fuzzy_search(ac_list, gender, age_min, age_max, name, relative):
    """Single / small-list constituency search — no progress UI."""
    n_name = normalize(name)
    n_rel  = normalize(relative)
    results = []
    for ac in ac_list:
        results.extend(search_db_streaming(ac, gender, age_min, age_max, n_name, n_rel))
    results.sort(key=lambda x: x["name_score"] + x["relative_score"], reverse=True)
    return results


def do_fuzzy_search_all(gender, age_min, age_max, name, relative, status_el, progress_el):
    """All-constituencies search — one DB at a time with live progress."""
    n_name    = normalize(name)
    n_rel     = normalize(relative)
    results   = []
    ac_list   = get_constituencies()
    total_acs = len(ac_list)

    for idx, ac in enumerate(ac_list, 1):
        status_el.markdown(
            f'<div class="age-hint">Scanning AC {ac} ({idx}/{total_acs}) — {len(results)} match(es) so far…</div>',
            unsafe_allow_html=True
        )
        progress_el.progress(idx / total_acs)
        results.extend(search_db_streaming(ac, gender, age_min, age_max, n_name, n_rel))

    results.sort(key=lambda x: x["name_score"] + x["relative_score"], reverse=True)
    return results


def result_card_html(i, r):
    gender_badge_cls = "badge-male" if r["gender"] == "M" else "badge-female"
    gender_label     = "Male"       if r["gender"] == "M" else "Female"
    constituency     = str(r['constituency'])
    part             = str(r['part'])
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
                st.session_state.results_single = do_fuzzy_search(
                    selected_constituencies, selected_gender, age_min, age_max, name, relative
                )

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
            status_el   = st.empty()
            progress_el = st.empty()
            results     = do_fuzzy_search_all(
                selected_gender_all, age_min_all, age_max_all,
                name_all, relative_all, status_el, progress_el
            )
            status_el.empty()
            progress_el.empty()
            st.session_state.results_all = results

    if st.session_state.results_all or (name_all and relative_all):
        render_results(st.session_state.results_all)