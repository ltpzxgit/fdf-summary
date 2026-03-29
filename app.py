import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - FDF", layout="wide")
st.title("ITOSE Tools - FDF Summary")

# =========================
# REGEX
# =========================
UUID_REGEX = r'([a-f0-9\-]{36})'
REQUEST_ID_REGEX = r'Request ID:\s*([a-f0-9\-]{36})'

# =========================
# FDFDataHub (เหมือนเดิม)
# =========================
def extract_uuid(text):
    match = re.search(UUID_REGEX, text)
    return match.group(1) if match else None

def extract_request_id(text):
    match = re.search(REQUEST_ID_REGEX, text)
    return match.group(1) if match else None

def extract_response_json(text):
    if "Response:" not in text:
        return None
    try:
        json_part = text.split("Response:", 1)[1].strip()
        return json.loads(json_part)
    except:
        return None


def parse_fdf_datahub(df):
    rows = []
    uuid_groups = {}

    for col in df.columns:
        for val in df[col]:
            if pd.isna(val):
                continue

            text = str(val)
            uuid = extract_uuid(text)

            if not uuid:
                continue

            uuid_groups.setdefault(uuid, []).append(text)

    for uuid, logs in uuid_groups.items():

        request_id = None
        response_data = None

        for log in logs:
            if not request_id:
                request_id = extract_request_id(log)

            if not response_data:
                response_data = extract_response_json(log)

        if response_data and "data" in response_data:
            vehicle_list = response_data["data"].get("vehicleList", [])

            for item in vehicle_list:
                rows.append({
                    "RequestID": request_id,
                    "VIN": item.get("vin"),
                    "Message": item.get("message"),
                    "Status": str(item.get("status"))
                })

    df_out = pd.DataFrame(rows)

    if not df_out.empty:
        df_out = df_out[df_out["VIN"].notna()]

        # ❌ ตัด 0008
        df_out = df_out[df_out["Status"] != "0008"]

        # 🔥 Latest ต่อ VIN
        df_out = df_out.iloc[::-1]
        df_out = df_out.drop_duplicates(subset=["VIN"], keep="first")
        df_out = df_out.iloc[::-1]

        df_out = df_out.reset_index(drop=True)
        df_out.insert(0, "No.", df_out.index + 1)

    return df_out


# =========================
# FDFTCAP (NEW - RequestID Driven)
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
        status_code = None
        message = None
        count_insert = 0

        for log in logs:

            # UUID
            if not uuid:
                u = re.search(UUID_REGEX, log)
                if u:
                    uuid = u.group(1)

            # 🔥 TCAP Response (ตัวจริง)
            if "Response from TCAP Cloud IF:" in log:
                try:
                    json_part = log.split("Response from TCAP Cloud IF:", 1)[1].strip()
                    data = json.loads(json_part)

                    status_code = data.get("statusCode")
                    message = data.get("message")
                    count_insert = data.get("countInsert", 0)

                except:
                    pass

        rows.append({
            "RequestID": req_id,
            "UUID": uuid,
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
col1, col2 = st.columns(2)

with col1:
    file1 = st.file_uploader("Upload FDFDataHub", type=["xlsx", "csv", "json"])

with col2:
    file2 = st.file_uploader("Upload FDFTCAP", type=["xlsx", "csv", "json"])

df1 = pd.DataFrame()
df2 = pd.DataFrame()

# =========================
# PROCESS DataHub
# =========================
if file1:
    if file1.name.endswith(".json"):
        df_file1 = pd.read_json(file1)
        df_file1 = df_file1["@message"]
    else:
        df_file1 = pd.read_csv(file1) if file1.name.endswith(".csv") else pd.read_excel(file1)

    df1 = parse_fdf_datahub(df_file1)

    st.subheader("FDFDataHub (Latest per VIN | No 0008)")

    if df1.empty:
        st.warning("⚠️ ไม่เจอข้อมูล")
    else:
        st.dataframe(df1, use_container_width=True)
        st.markdown(f"### 🔢 Total Rows: {len(df1)}")
        st.markdown(f"### 🧠 Unique VIN: {df1['VIN'].nunique()}")

# =========================
# PROCESS TCAP
# =========================
if file2:
    if file2.name.endswith(".json"):
        df_file2 = pd.read_json(file2)
        df_file2 = df_file2["@message"]
    else:
        df_file2 = pd.read_csv(file2) if file2.name.endswith(".csv") else pd.read_excel(file2)

    df2 = parse_fdf_tcap(df_file2)

    st.subheader("FDFTCAP Summary (By RequestID)")

    if df2.empty:
        st.warning("⚠️ ไม่เจอข้อมูล")
    else:
        total_txn = len(df2)
        total_insert = df2["CountInsert"].sum()
        success = df2[df2["StatusCode"] == "000"].shape[0]
        fail = df2[df2["StatusCode"] != "000"].shape[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Request", total_txn)
        c2.metric("Total Insert", total_insert)
        c3.metric("Success (000)", success)
        c4.metric("Fail", fail)

        st.divider()

        st.dataframe(df2, use_container_width=True)

# =========================
# EXPORT
# =========================
if not df1.empty or not df2.empty:
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df1.empty:
            df1.to_excel(writer, index=False, sheet_name='FDFDataHub')
        if not df2.empty:
            df2.to_excel(writer, index=False, sheet_name='FDFTCAP')

    output.seek(0)

    st.download_button(
        "Download Excel (All)",
        data=output,
        file_name="fdf-summary.xlsx"
    )
