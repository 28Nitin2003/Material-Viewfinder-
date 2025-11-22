# ==========================================================
# MATERIAL VIEWFINDER — FINAL AESTHETIC BUILD (BUTTON FIX + VISIBILITY)
# ==========================================================

import os
import re
import urllib.parse
import pandas as pd
import numpy as np
import streamlit as st

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

# --- ENHANCED COLORS ---
BLUE = "#1F7A8C"        # Richer Teal/Corporate Blue
DARK_BLUE = "#003566"   # Deep Blue for Title
DARK_GREEN = "#006D5B"  # Professional Dark Green for Headers
RED_DELETE = "#EF4444"
TEXT_DARK = "#1E293B"   # Very dark gray/almost black for all general text

# ==========================================================
# DATA EXTRACTION
# ==========================================================
def extract_tables(df: pd.DataFrame):
    """Detect blocks whose header row contains both KEY_MAT and KEY_DESC."""
    A = df.copy()
    vals = A.astype(str).values
    mat_rows = np.where(vals == KEY_MAT)[0]
    desc_rows = np.where(vals == KEY_DESC)[0]
    headers = sorted(set(mat_rows).intersection(set(desc_rows)))

    blocks = []
    for i, r in enumerate(headers):
        header_vals = A.iloc[r].astype(str).tolist()
        cols = [c for c, v in enumerate(header_vals) if v.strip() not in ("", "nan", "None", "NaN")]
        if not cols:
            continue

        end = headers[i + 1] if i + 1 < len(headers) else len(A)
        block = A.iloc[r + 1 : end, cols].copy()
        block.columns = [header_vals[c] for c in cols]
        block = block.dropna(how="all")

        for c in block.columns:
            block[c] = block[c].astype(str).str.strip()

        if not block.empty:
            blocks.append(block)

    return blocks


@st.cache_data(show_spinner=True)
def load_all():
    rows = []
    base = os.path.dirname(os.path.abspath(__file__))

    for dept, fname in FILES.items():
        path = os.path.join(base, fname)
        if not os.path.exists(path):
            continue

        xls = pd.ExcelFile(path)
        for sheet in xls.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet, header=None)
            for tbl in extract_tables(df):
                T = tbl.copy()
                T["Department"] = dept
                machine = "Winding" if sheet.lower() == "sheet1" else sheet
                T["Machine Type"] = machine
                rows.extend(T.to_dict(orient="records"))

    if not rows:
        return pd.DataFrame()

    df_all = pd.DataFrame(rows)

    for c in df_all.columns:
        df_all[c] = (
            df_all[c]
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

    df_all = df_all.replace({"nan": None, "NaN": None, "None": None, "": None})
    df_all = df_all[(df_all[KEY_MAT].notna()) | (df_all[KEY_DESC].notna())]

    return df_all.reset_index(drop=True)


def clean_display(df: pd.DataFrame) -> pd.DataFrame:
    """Replace nan/None with empty strings for nicer display."""
    return df.replace({"nan": "", "NaN": "", "None": "", None: ""}).fillna("")


# ==========================================================
# SEARCH HELPERS
# ==========================================================
def parse_keywords(q: str):
    q = q.lower().strip()
    if not q:
        return []
    parts = re.split(r"[,\s;|]+", q)
    seen = set()
    out = []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def hybrid_multi_search(df_sub: pd.DataFrame, q: str) -> pd.DataFrame:
    """Multi-keyword partial search on Material + Proposed Description."""
    keywords = parse_keywords(q)
    if not keywords:
        return df_sub.iloc[0:0].copy()

    df = df_sub.copy()
    combined = (
        df[[KEY_MAT, KEY_DESC]]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
    )

    masks_and = [combined.str.contains(k) for k in keywords]
    mask_and = np.logical_and.reduce(masks_and)
    masks_or = [combined.str.contains(k) for k in keywords]
    mask_or = np.logical_or.reduce(masks_or)

    if mask_and.any():
        cand = df[mask_and].copy()
    else:
        cand = df[mask_or].copy()

    if cand.empty:
        return cand

    first = keywords[0]
    desc = cand[KEY_DESC].fillna("").astype(str).str.lower()
    starts = desc.str.startswith(first)
    contains = desc.str.contains(first)

    cand = (
        cand.assign(_starts=starts.astype(int), _contains=contains.astype(int))
        .sort_values(by=["_starts", "_contains"], ascending=[False, False])
        .drop(columns=["_starts", "_contains"])
    )
    return cand.reset_index(drop=True)


# ==========================================================
# UI CSS (AESTHETIC STYLING)
# ==========================================================
st.set_page_config(page_title="Material Viewfinder", layout="wide")
st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

* {{ border-radius: 8px !important; }}

/* ============================================================ */
/* 0. DARK MODE FIX: Force Light Theme & Text Visibility        */
/* ============================================================ */
/* Force white background globally */
.stApp {{
    background: #FFFFFF !important;
    font-family: 'Inter', sans-serif !important;
}}

/* Force dark text color for specific elements only */
p, 
.stMarkdown,
.stCaption,
[data-testid^="stWidgetLabel"] p, /* Labels for selectboxes, textinputs */
.stText,
.stHeader,
.stSubheader,
[data-testid="stSidebar"] * /* Sidebar elements if present */
{{
    color: {TEXT_DARK} !important; 
}}

/* Ensure button text remains white */
button p {{
    color: white !important;
}}

/* Ensure all input/select box labels are visible against the main background */
.stSelectbox label p,
.stTextInput label p {{
    color: {TEXT_DARK} !important;
    font-weight: 600; /* Make labels stand out */
}}


/* ============================================================ */
/* 1. BLUE BUTTONS (Search, Submit, Clear, Add to Cart, Recent) */
/* ============================================================ */
button[kind="secondary"] {{
    background-color: {BLUE} !important;
    color: white !important; /* Ensure white text */
    border: none !important;
    font-weight: 700 !important;
    padding: 0.5rem 1rem !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.06);
    transition: all 0.2s ease;
}}
button[kind="secondary"]:hover {{
    background-color: {DARK_BLUE} !important;
    color: white !important;
    transform: translateY(-2px); 
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
}}
button[kind="secondary"]:focus, button[kind="secondary"]:active {{
    background-color: {DARK_BLUE} !important;
    color: white !important;
    outline: none !important;
    box-shadow: none !important;
    transform: translateY(0);
}}

/* ============================================================ */
/* 2. DELETE BUTTON (Clean Red Icon)                            */
/* ============================================================ */
button[kind="primary"] {{
    background-color: transparent !important;
    border: 1px solid {RED_DELETE} !important;
    color: {RED_DELETE} !important;
    font-weight: 700 !important;
    transition: all 0.2s ease !important;
    height: 100% !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}
button[kind="primary"]:hover {{
    background-color: {RED_DELETE} !important;
    color: white !important;
    border: 1px solid {RED_DELETE} !important;
    transform: scale(1.05);
    box-shadow: 0 4px 6px rgba(239, 68, 68, 0.3);
}}
button[kind="primary"]:focus {{
    box-shadow: none !important;
    border-color: {RED_DELETE} !important;
}}

/* ============================================================ */
/* 3. INPUTS & DROPDOWNS (Light Background, Blue Borders)       */
/* ============================================================ */

/* Text Input Styling (Search Box) */
.stTextInput input {{
    background-color: white !important; /* Force light background */
    border: 2px solid {BLUE} !important;
    color: {TEXT_DARK} !important; /* Ensure text is dark */
    padding: 8px 12px !important;
    font-weight: 500;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}
.stTextInput input:focus {{
    border-color: {DARK_BLUE} !important;
    box-shadow: 0 0 0 1px {DARK_BLUE} !important;
}}

/* Selectbox (Dropdown) Styling */
.stSelectbox div[data-baseweb="select"] > div {{
    background-color: white !important; /* Force light background */
    border: 2px solid {BLUE} !important;
    color: {TEXT_DARK} !important; /* Ensure selected value is dark */
    font-weight: 500;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}}
/* Ensure all dropdown options (list items) are also dark text on light background */
[data-baseweb="menu"] li {{
    color: {TEXT_DARK} !important;
    background-color: white !important;
}}


/* ============================================================ */
/* 4. TABLE STYLING (SAP Record)                                */
/* ============================================================ */
[data-testid="stDataEditor"] {{
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.06);
}}
[data-testid="stDataEditor"] thead th {{
    font-weight: 800 !important; 
    background-color: {TEXT_DARK} !important; /* Darkest color for background */
    color: white !important;
    border: 1px solid #334155 !important;
    font-size: 15px !important;
}}
/* Apply border to the right side of cells for a grid look */
[data-testid="stDataEditor"] tbody td {{
    border-right: 1px solid #E5E7EB; 
    color: {TEXT_DARK} !important; /* Ensure data text is dark */
}}

/* Hides the default colored bar at top */
header {{visibility: hidden;}}

/* ============================================================ */
/* 5. CART ITEM STYLING - ULTRA TIGHT PADDING (Final Compression)*/
/* ============================================================ */

/* Reduce vertical padding on all blocks within the st.columns for the cart */
div[data-testid="stColumn"] > div > div > div {{
    padding-top: 1px !important; 
    padding-bottom: 1px !important; 
    margin-top: 0px !important;
    margin-bottom: 0px !important;
}}

/* Tighter spacing for description/caption text */
div[data-testid="stColumn"] .stMarkdown p, div[data-testid="stColumn"] .stCaption {{
    margin: 0px 0px !important;
    line-height: 1.1;
    font-size: 0.875rem;
}}

div[data-testid="stColumn"] .stText {{
    margin: 0px !important;
    padding: 0px !important;
    line-height: 1.1;
    font-size: 0.875rem;
}}

/* Tighter spacing and smaller height for Quantity Input */
.stNumberInput {{
    margin: 0 !important;
    padding: 0 !important;
}}
.stNumberInput div[data-baseweb="input"] input {{
    height: 28px !important;
    padding-top: 4px !important;
    padding-bottom: 4px !important;
    font-size: 0.875rem;
    color: white !important; /* FIX: Changed to white for visibility on dark backgrounds */
}}
/* Adjust buttons inside number input (plus/minus) */
.stNumberInput button {{
    min-height: 28px !important;
    line-height: 1;
    padding: 0 4px; 
    color: white !important; /* FIX: Also ensure the plus/minus buttons are white */
}}

/* Align delete button vertically */
.stColumns > div:nth-child(4) button {{
    margin-top: 4px; 
    height: 28px !important;
    min-width: 28px !important;
    padding: 0;
    display: flex;
    justify-content: center;
    align-items: center;
}}

/* Override the default margin on the Quantity label column to center content */
.stColumns > div:nth-child(1) .stMarkdown p {{
    margin-top: 8px !important;
}}

</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# SESSION STATE INIT
# ==========================================================
if "query" not in st.session_state:
    st.session_state["query"] = ""
if "clear_trigger" not in st.session_state:
    st.session_state["clear_trigger"] = False
if "trigger_search" not in st.session_state:
    st.session_state["trigger_search"] = False
if "recent_searches" not in st.session_state:
    st.session_state["recent_searches"] = []
if "cart" not in st.session_state:
    st.session_state["cart"] = {}

# --- CART DELETE LOGIC STATES ---
if "undo_item" not in st.session_state:
    st.session_state["undo_item"] = None 

# Base table logic
if "table_df_base" not in st.session_state:
    st.session_state["table_df_base"] = None
if "table_label" not in st.session_state:
    st.session_state["table_label"] = ""

# Current filter logic
if "current_dept" not in st.session_state:
    st.session_state["current_dept"] = None
if "current_machine" not in st.session_state:
    st.session_state["current_machine"] = None

# TABLE RESET KEY
if "editor_key" not in st.session_state:
    st.session_state["editor_key"] = 0

# Apply clear logic
if st.session_state["clear_trigger"]:
    st.session_state["query"] = ""
    st.session_state["table_df_base"] = None
    st.session_state["table_label"] = ""
    st.session_state["clear_trigger"] = False
    st.session_state["editor_key"] += 1

# ==========================================================
# LOAD DATA
# ==========================================================
df = load_all()
if df.empty:
    st.error("❌ Excel material files missing.")
    st.stop()

# ==========================================================
# AESTHETIC HEADER
# ==========================================================
st.markdown(
    f"""
    <div style="text-align: center; margin-top: -30px; margin-bottom: 40px;">
        <h1 style="color: {DARK_BLUE}; font-size: 3.5rem; font-weight: 800; margin-bottom: 0px; letter-spacing: -1px;">
            Material<span style="color: {BLUE};">Viewfinder</span>
        </h1>
        <p style="color: #64748B; font-size: 1.1rem; font-weight: 500; margin-top: 5px;">
            🔍 Smart Inventory & Procurement Assistant
        </p>
    </div>
    """, 
    unsafe_allow_html=True
)

# ==========================================================
# FILTERS
# ==========================================================
c1, c2, c3 = st.columns(3)
plant = c1.selectbox("Plant", ["SHJM", "MIJM", "SGJM", "SSKT"])
department = c2.selectbox("Department", sorted(df["Department"].unique()))
machine = c3.selectbox(
    "Machine Type",
    sorted(df[df["Department"] == department]["Machine Type"].unique()),
)

subset = df[(df["Department"] == department) & (df["Machine Type"] == machine)]

# Clear table if filters change
if (
    st.session_state["current_dept"] != department
    or st.session_state["current_machine"] != machine
):
    st.session_state["table_df_base"] = None
    st.session_state["table_label"] = ""
    st.session_state["current_dept"] = department
    st.session_state["current_machine"] = machine
    st.session_state["editor_key"] += 1

# ==========================================================
# SEARCH BAR
# ==========================================================
c_s, c_btn, c_clr = st.columns([5, 1, 1], vertical_alignment="bottom")

with c_s:
    q = st.text_input(
        "Search",
        key="query",
        placeholder="Search by description or material code (e.g. bearing, 13000...)",
        label_visibility="visible" 
    )

with c_btn:
    submit = st.button("Submit", use_container_width=True)

with c_clr:
    clear = st.button("Clear", key="clear_btn", use_container_width=True)

if clear:
    st.session_state["clear_trigger"] = True
    st.session_state["table_df_base"] = None
    st.session_state["table_label"] = ""
    st.session_state["editor_key"] += 1
    st.rerun()

# ==========================================================
# RECENT SEARCHES
# ==========================================================
def on_recent_click(search_text):
    st.session_state["query"] = search_text
    st.session_state["trigger_search"] = True

if st.session_state["recent_searches"]:
    st.markdown("### 🕘 Recent")
    cols = st.columns(len(st.session_state["recent_searches"]))
    for i, item in enumerate(st.session_state["recent_searches"]):
        with cols[i]:
            # These buttons are secondary, so they should now pick up the blue styling
            st.button(item, key=f"recent_{i}", on_click=on_recent_click, args=(item,), use_container_width=True)

# ==========================================================
# SEARCH LOGIC
# ==========================================================
should_search = submit or st.session_state.get("trigger_search", False)

if should_search:
    st.session_state["trigger_search"] = False
    st.session_state["editor_key"] += 1

    q_stripped = st.session_state["query"].strip()

    if not q_stripped:
        base = clean_display(subset).reset_index(drop=True)
        st.session_state["table_df_base"] = base
        st.session_state["table_label"] = f"📄 SAP Record — All materials in {machine}"
    else:
        filtered_local = hybrid_multi_search(subset, q_stripped)

        recent = st.session_state["recent_searches"]
        if q_stripped in recent:
            recent.remove(q_stripped)
        recent.insert(0, q_stripped)
        st.session_state["recent_searches"] = recent[:5]

        if not filtered_local.empty:
            base = clean_display(filtered_local).reset_index(drop=True)
            st.session_state["table_df_base"] = base
            st.session_state["table_label"] = (
                f"📄 SAP Record — {len(base)} result(s) in {machine}"
            )
        else:
            filtered_global = hybrid_multi_search(df, q_stripped)
            st.session_state["table_df_base"] = None
            st.session_state["table_label"] = ""

            if filtered_global.empty:
                st.error("❌ Material not found anywhere.")
            else:
                st.warning("⚠ Material not found in this machine, but found elsewhere:")
                st.dataframe(clean_display(filtered_global), use_container_width=True)

# ==========================================================
# SHOW SAP TABLE (AUTO RESET)
# ==========================================================
base = st.session_state["table_df_base"]
label = st.session_state["table_label"]

if base is not None and not base.empty:
    st.subheader(label)

    display_df = base.copy().reset_index(drop=True)
    if "Select" not in display_df.columns:
        display_df.insert(0, "Select", False)
    if "Quantity" not in display_df.columns:
        display_df.insert(1, "Quantity", 1)

    unique_key = f"sap_table_editor_{st.session_state['editor_key']}"

    edited = st.data_editor(
        display_df,
        key=unique_key,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "Select": st.column_config.CheckboxColumn("Select"),
            "Quantity": st.column_config.NumberColumn("Quantity", min_value=1, step=1),
        },
    )

    if st.button("Add Selected to Cart", use_container_width=True):
        selected_rows = edited[edited["Select"] == True]

        if selected_rows.empty:
            st.warning("No items selected.")
        else:
            cart = st.session_state["cart"]
            count = 0
            for _, row in selected_rows.iterrows():
                code = str(row.get(KEY_MAT, "")).strip()
                if not code:
                    continue

                try:
                    qty = int(row.get("Quantity", 1))
                    if qty < 1: qty = 1
                except:
                    qty = 1

                if code in cart:
                    cart[code]["Quantity"] += qty
                else:
                    cart[code] = {
                        "Material": code,
                        "Description": row.get(KEY_DESC, ""),
                        "Department": row.get("Department", ""),
                        "Machine Type": row.get("Machine Type", ""),
                        "Quantity": qty,
                    }
                count += 1

            if count > 0:
                st.session_state["cart"] = cart
                st.success(f"✔ Added {count} item(s) to cart.")
                st.session_state["editor_key"] += 1
                st.rerun()

# ==========================================================
# CART LOGIC (INSTANT DELETE + UNDO)
# ==========================================================
st.write("---")

# 1. UNDO Notification
if st.session_state["undo_item"]:
    c_undo, _ = st.columns([2, 5])
    with c_undo:
        # Standard Blue Button
        if st.button("↩ Undo Delete", use_container_width=True):
            restored = st.session_state["undo_item"]
            st.session_state["cart"][restored["Material"]] = restored
            st.session_state["undo_item"] = None
            st.rerun()

st.subheader("🛒 Cart")

if not st.session_state["cart"]:
    st.info("Your cart is empty.")
else:
    # 2. HEADER ROW
    # Adjusted column widths for tighter Qty
    h1, h2, h3, h4 = st.columns([0.6, 4, 1.5, 0.5]) 
    h1.markdown("**Qty**")
    h2.markdown("**Material / Description**")
    h3.markdown("**Machine**")
    h4.markdown("") # Empty for delete button

    st.markdown("<hr style='margin: 5px 0'>", unsafe_allow_html=True)

    # 3. ITERATE ITEMS
    current_cart = st.session_state["cart"]
    
    # List conversion for safe iteration
    for code, item in list(current_cart.items()):
        
        # Adjusted column widths for tighter Qty
        c1, c2, c3, c4 = st.columns([0.6, 4, 1.5, 0.5])
        
        # COLUMN 1: EDITABLE QUANTITY
        with c1:
            new_qty = st.number_input(
                "Qty", 
                value=int(item["Quantity"]), 
                min_value=1, 
                step=1, 
                key=f"qty_{code}",
                label_visibility="collapsed"
            )
            if new_qty != item["Quantity"]:
                st.session_state["cart"][code]["Quantity"] = new_qty
                
        # COLUMN 2: DESCRIPTION & CODE
        with c2:
            st.markdown(f"**{item['Description']}**")
            st.caption(f"Code: {item['Material']} | Dept: {item['Department']}")
            
        # COLUMN 3: MACHINE
        with c3:
            st.text(item['Machine Type'])
            
        # COLUMN 4: INSTANT DELETE BUTTON
        with c4:
            # type="primary" makes it Red (via CSS)
            if st.button("🗑️", key=f"del_{code}", type="primary"):
                # 1. Save to Undo
                st.session_state["undo_item"] = st.session_state["cart"][code]
                # 2. Delete immediately
                del st.session_state["cart"][code]
                st.rerun()
        
        # NOTE: The custom CSS handles the separator line now, making the cart cleaner
        st.markdown("<hr>", unsafe_allow_html=True) 

    # CLEAR ALL BUTTON
    if st.button("Clear Entire Cart"):
        st.session_state["cart"] = {}
        st.session_state["undo_item"] = None
        st.rerun()

# ==========================================================
# EMAIL SECTION
# ==========================================================
st.write("---")
st.subheader("✉ Send Materials via Gmail")

to_email = st.text_input("Receiver Email")
subject = "Material Requirement – Material Viewfinder"

body_lines = [
    "Dear Sir/Madam,",
    "",
    "Please arrange the following materials:",
    "",
]

for item in st.session_state["cart"].values():
    body_lines.append(
        f"- {item['Material']} — {item['Description']} "
        f"(Dept: {item['Department']}, Machine: {item['Machine Type']}, Qty: {item['Quantity']})"
    )

body_lines += ["", "Regards,", "Material Viewfinder Bot"]
body = "\n".join(body_lines)

st.text_area("Email Preview", body, height=200)

if st.button("Send Email"):
    if not to_email.strip():
        st.warning("Please enter receiver email.")
    else:
        subject_encoded = urllib.parse.quote(subject)
        body_encoded = urllib.parse.quote(body)
        to_encoded = urllib.parse.quote(to_email)

        gmail_url = (
            "https://mail.google.com/mail/?view=cm&fs=1"
            f"&to={to_encoded}&su={subject_encoded}&body={body_encoded}"
        )

        st.markdown(
            f"""
            <script>
                window.open("{gmail_url}", "_blank");
            </script>
            """,
            unsafe_allow_html=True,
        )
