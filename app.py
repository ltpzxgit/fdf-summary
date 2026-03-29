import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - FDFTCAP Summary", layout="wide")
st.title("ITOSE Tools - FDFTCAP Summary")

# =========================
# FUNCTIONS
# =========================
def parse_fdf_tcap(df):
    rows = []
    uuid_groups = {}

    # 🔥 group ตาม UUID
    for col in df.columns:
        for val in df[col]:
            if pd.isna(val):
                continue

            text = str(val)

            uuid_match = re.search(r'([a-f0-9\-]{36})', text)
            uuid = uuid_match.group(1) if uuid_match else None

            if not uuid:
                continue

            uuid_groups.setdefault(uuid, []).append(text)

    # 🔥 process ต่อ UUID
    for uuid, logs in uuid_groups.items():

        request_id = None
        status_code = None
        message = None
        count_insert = 0

        for log in logs:

            # Request ID
            if not request_id:
                m = re.search(r'Request ID:\s*([a-f0-9\-]{36})', log)
                if m:
                    request_id = m.group(1)

            # CountInsert
            if "vehicleList=[" in log:
                count_insert = log.count("vin=")

            # Response
            if "Response:" in log and not status_code:
                try:
                    json_part = log.split("Response:", 1)[1].strip()
                    data = json.loads(json_part)

                    status_code = data.get("statusCode")
                    message = data.get("message")

                except:
                    pass

        rows.append({
            "UUID": uuid,
            "RequestID": request_id,
            "CountInsert": count_insert,
            "StatusCode": status_code,
            "Message": message
        })

    df_out = pd.DataFrame(rows)

    if not df_out.empty:
        df_out = df_out.reset_index(drop=True)
        df_out.insert(0, "No.", df_out.index + 1)

    return df_out


# =========================
# UPLOAD
# =========================
file = st.file_uploader("Upload FDFTCAP", type=["xlsx", "csv", "json"])

if file:

    if file.name.endswith(".json"):
        df_raw = pd.read_json(file)
        df_raw = df_raw["@message"]
    else:
        df_raw = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)

    df = parse_fdf_tcap(df_raw)

    # =========================
    # SUMMARY
    # =========================
    if not df.empty:

        total_txn = len(df)
        total_insert = df["CountInsert"].sum()

        success_count = df[df["StatusCode"] == 200].shape[0]
        fail_count = df[df["StatusCode"] != 200].shape[0]

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Total Transaction", total_txn)
        col2.metric("Total Insert", total_insert)
        col3.metric("Success (200)", success_count)
        col4.metric("Fail", fail_count)

        st.divider()

        # =========================
        # TABLE
        # =========================
        st.subheader("FDFTCAP Transaction Detail")

        st.dataframe(df, use_container_width=True)

    else:
        st.warning("⚠️ ไม่เจอข้อมูล")


    # =========================
    # EXPORT
    # =========================
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='FDFTCAP')

    output.seek(0)

    st.download_button(
        "Download Excel",
        data=output,
        file_name="fdf-tcap-summary.xlsx"
    )
