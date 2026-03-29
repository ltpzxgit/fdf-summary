import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="ITOSE - FDF", layout="wide")
st.title("ITOSE Tools - FDFTCAP Summary")

# =========================
# REGEX
# =========================
UUID_REGEX = r'([a-f0-9\-]{36})'
REQUEST_ID_REGEX = r'Request ID:\s*([a-f0-9\-]{36})'

# =========================
# FUNCTION
# =========================
def parse_fdf_tcap(df):
    rows = []
    req_groups = {}

    # 🔥 group ตาม RequestID
    for col in df.columns:
        for val in df[col]:
            if pd.isna(val):
                continue

            text = str(val)

            req_match = re.search(REQUEST_ID_REGEX, text)
            req_id = req_match.group(1) if req_match else None

            if not req_id:
                continue

            req_groups.setdefault(req_id, []).append(text)

    # 🔥 process ต่อ RequestID
    for req_id, logs in req_groups.items():

        uuid = None
        count_insert = 0

        for log in logs:

            # UUID
            if not uuid:
                u = re.search(UUID_REGEX, log)
                if u:
                    uuid = u.group(1)

            # 🔥 ดึง countInsert ตรง ๆ
            m = re.search(r'countInsert["=:\s]+(\d+)', log)
            if m:
                count_insert = int(m.group(1))

        rows.append({
            "RequestID": req_id,
            "UUID": uuid,
            "CountInsert": count_insert
        })

    df_out = pd.DataFrame(rows)

    if not df_out.empty:
        df_out = df_out.reset_index(drop=True)
        df_out.insert(0, "No.", df_out.index + 1)

    return df_out


# =========================
# UPLOAD
# =========================
file = st.file_uploader("Upload FDFTCAP", type=["xlsx", "csv"])

if file:
    df_file = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)

    df = parse_fdf_tcap(df_file)

    st.subheader("FDFTCAP Summary (CountInsert)")

    if df.empty:
        st.warning("⚠️ ไม่เจอข้อมูล")
    else:
        total_req = len(df)
        total_insert = df["CountInsert"].sum()

        c1, c2 = st.columns(2)
        c1.metric("Total Request", total_req)
        c2.metric("Total Insert", total_insert)

        st.divider()
        st.dataframe(df, use_container_width=True)

    # EXPORT
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='FDFTCAP')

    output.seek(0)

    st.download_button(
        "Download Excel",
        data=output,
        file_name="fdf-tcap-summary.xlsx"
    )
