# ==========================================================
# MATERIAL VIEWFINDER — DARK HEADER FINAL EDITION
# ==========================================================

import os
import pandas as pd
import numpy as np
import streamlit as st

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SK_OK = True
except:
    SK_OK = False

# ---------------- FILES ----------------
FILES = {
    "Spreader": "Spreader Material Master.xlsx",
    "Drawing": "Drawing Material Master.xlsx",
    "Carding": "Carding Material Master.xlsx",
    "Spinning": "Spinning Material Master.xlsx",
    "Spool Winding": "Spool Winding Material Master.xlsx",
}

KEY_MAT = "Material"
KEY_DESC = "Material Proposed Description"

# COLORS
BLUE = "#00B4D8"
DARK_BLUE = "#003566"
DARK_GREEN = "#064E3B"   # Header Background
LIGHT_GREEN = "#D1FAE5"  # Row Highlight Background
BORDER_GREEN = "#48BB78"

# ---------------- DATA EXTRACTION ----------------
def extract_tables(df):
    A = df.copy()
    vals = A.astype(str).values
    mat = set(np.where(vals == KEY_MAT)[0])
    desc = set(np.where(vals == KEY_DESC)[0])
    headers = sorted(mat.intersection(desc))

    out = []
    for i, r in enumerate(headers):
        header_vals = A.iloc[r].astype(str).tolist()
        cols = [c for c, v in enumerate(header_vals) 
                if v.strip() not in ("","nan","None","NaN")]
        if not cols:
            continue

        end = headers[i+1] if i+1 < len(headers) else len(A)
        block = A.iloc[r+1:end, cols].copy()
        block.columns = [header_vals[c].strip() for c in cols]
        block = block.dropna(how='all')
        for c in block.columns:
            if block[c].dtype == object:
                block[c] = block[c].astype(str).str.strip()
        
        if not block.empty:
            out.append(block)
    return out


@st.cache_data(show_spinner=True)
def load_all():
    rows = []
    base = os.path.dirname(os.path.abspath(__file__))

    for dept, fname in FILES.items():
        path = os.path.join(base, fname)
        if not os.path.exists(path):
            continue 

        sheets = pd.read_excel(path, sheet_name=None, header=None)

        for sheet, df in sheets.items():
            for tbl in extract_tables(df):
                T = tbl.copy()
                T["Department"] = dept

                m = sheet.strip()
                if m.lower() == "sheet1":
                    m = "Winding"

                T["Machine Type"] = m
                rows.extend(T.to_dict(orient="records"))

    if not rows:
        return pd.DataFrame()

    df_all = pd.DataFrame(rows)

    for c in df_all.columns:
        if df_all[c].dtype == object:
            df_all[c] = df_all[c].astype(str).str.replace(r"\s+"," ",regex=True).str.strip()

    df_all = df_all[df_all[KEY_DESC].str.len() > 0].reset_index(drop=True)
    return df_all


# ---------------- UI & CSS ----------------

st.set_page_config(page_title="Material Viewfinder", layout="wide")

st.markdown(f"""
<style>
/* 1. GLOBAL RESET */
* {{
    border-radius: 0px !important;
}}
body, .stApp {{
    background: white !important;
    font-family: 'Inter', sans-serif !important;
    color: #1e293b !important;
}}

/* 2. HEADINGS (H1, H2, H3) - DARK BLUE */
h1, h2, h3, h4, h5 {{
    color: {DARK_BLUE} !important;
    font-weight: 900 !important;
}}

/* 3. LABELS - FORCE BOLD (Plant, Search, Suggestions) */
.stSelectbox label p, .stTextInput label p, .stSelectbox label {{
    font-size: 17px !important;
    color: {DARK_BLUE} !important;
    font-weight: 900 !important; /* EXTRA BOLD */
}}

/* 4. INPUT & DROPDOWN BOXES */
.stTextInput input {{
    border: 2px solid {BLUE} !important;
    color: black !important;
    font-weight: 600 !important;
}}
.stSelectbox div[data-baseweb="select"] {{
    border: 2px solid #cccccc !important;
    background: #ffffff !important;
}}

/* 5. SUBMIT BUTTON */
.stButton>button {{
    background: {BLUE} !important;
    color: white !important;
    border: none !important;
    padding: 12px 40px !important;
    font-size: 16px !important;
    font-weight: 700 !important;
}}
.stButton>button:hover {{
    background: #0094B5 !important;
}}

/* 6. TABLE HEADERS - DARK GREEN BG, WHITE TEXT, BOLD */
[data-testid="dataframe"] th {{
    background-color: {DARK_GREEN} !important; /* Dark Green Background */
    color: white !important;                   /* White Text */
    font-size: 15px !important;
    font-weight: 900 !important;
    border-bottom: 2px solid {BORDER_GREEN} !important;
}}

/* 7. TABLE TOOLBAR ICONS (HUGE & DARK) */
[data-testid="stElementToolbar"] {{
    opacity: 1 !important;
    visibility: visible !important;
}}
[data-testid="stElementToolbar"] button {{
    transform: scale(1.3) !important;
    margin: 0 4px !important;
    opacity: 1 !important;
}}
[data-testid="stElementToolbar"] svg {{
    fill: #333333 !important;
    color: #333333 !important;
    stroke: #333333 !important;
    stroke-width: 0.5px !important;
    width: 24px !important;
    height: 24px !important;
}}

/* 8. SUGGESTION DROPDOWN STYLING (Green Theme) */
div[data-baseweb="select"] > div {{
    background-color: #ffffff;
    color: black;
}}
/* Dropdown Items Hover/Selected */
li[data-baseweb="option"]:hover, 
li[data-baseweb="option"][aria-selected="true"] {{
    background-color: {LIGHT_GREEN} !important;
    border-left: 5px solid {BORDER_GREEN} !important;
    color: {DARK_GREEN} !important;
    font-weight: 900 !important;
}}
</style>
""", unsafe_allow_html=True)


# ---------------- LOAD DATA ----------------
df = load_all()

if df.empty:
    st.error("No data files found.")
    st.stop()

# HEADER
st.markdown(f"""<h1 style='color:{DARK_BLUE}; font-weight:900;'>🔍 Material Viewfinder</h1>""", unsafe_allow_html=True)


# ---------------- FILTERS ----------------
c1, c2, c3 = st.columns([1,1,1])

plant = c1.selectbox("Plant", ["SHJM","MIJM","SGJM","SSKT"])
department = c2.selectbox("Department", sorted(df["Department"].unique()))
machine = c3.selectbox(
    "Machine Type", 
    sorted(df[df["Department"] == department]["Machine Type"].unique())
)

subset = df[(df["Department"] == department) & (df["Machine Type"] == machine)]


# ---------------- SEARCH ----------------
st.write("---") 
c_search, c_btn = st.columns([4,1])
with c_search:
    q = st.text_input("Search by description or material code", placeholder="e.g., disc, stud, bearing, 13000...")
with c_btn:
    st.write("") 
    st.write("") 
    submit = st.button("Submit")


# ---------------- SUGGESTIONS ----------------
def get_suggestions(d, q):
    if not q.strip():
        return []
    
    d = d.copy()
    
    if SK_OK:
        vec = TfidfVectorizer(stop_words='english')
        X = vec.fit_transform(d[KEY_DESC])
        score = cosine_similarity(vec.transform([q]), X).ravel()
        d["score"] = score
    else:
        d["score"] = 0
    
    mask = (
        d[KEY_MAT].str.contains(q, case=False) | 
        d[KEY_DESC].str.contains(q, case=False)
    )
    d.loc[mask,"score"] += 2
    
    d = d.sort_values("score", ascending=False)
    
    return [f"【{r[KEY_MAT]}】 {r[KEY_DESC]}" for _, r in d.iterrows()]


suggestions = get_suggestions(subset, q)

chosen = None
if q.strip():
    # INJECT CSS TO MAKE SELECTED DROPDOWN GREEN
    st.markdown(f"""
    <style>
    div[data-baseweb="select"] > div:first-child {{
        background-color: {LIGHT_GREEN} !important;
        border-left: 5px solid {BORDER_GREEN} !important;
    }}
    div[data-baseweb="select"] span {{
        color: {DARK_GREEN} !important;
        font-weight: 900 !important;
    }}
    </style>
    """, unsafe_allow_html=True)
    
    chosen = st.selectbox("Suggestions", suggestions if suggestions else ["No results"])


# ---------------- LOGIC ----------------

# CASE A — Submit with empty search
if submit and not q.strip():
    st.subheader(f"📄 All Materials in {machine}")
    st.dataframe(subset, use_container_width=True)

# CASE B — Show filtered results (GREEN HIGHLIGHT, NO PINK)
elif q.strip() and not (chosen and chosen != "No results"):
    filtered = subset[
        subset[KEY_DESC].str.contains(q, case=False) | 
        subset[KEY_MAT].str.contains(q, case=False)
    ]
    
    if not filtered.empty:
        st.subheader(f"🟩 {len(filtered)} Matching Results")
        
        # Styling function: Sets Green Background AND Green Text
        def highlight_green(s):
            return [f'background-color: {LIGHT_GREEN}; color: {DARK_GREEN}; font-weight: bold;'] * len(s)
            
        st.dataframe(filtered.style.apply(highlight_green, axis=1), use_container_width=True)

# CASE C — user selected specific material
if chosen and chosen != "No results":
    code = chosen.split("】")[0].replace("【","")
    row = subset[subset[KEY_MAT] == code].iloc[0]
    
    st.markdown(f"<h2 style='color:{BLUE};'>{row[KEY_MAT]}</h2>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='color:{BLUE};font-weight:600;'>{row[KEY_DESC]}</h4>", unsafe_allow_html=True)
    
    st.subheader("📄 Full Raw Record")
    st.dataframe(pd.DataFrame(row).T, use_container_width=True)