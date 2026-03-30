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
REQUEST_ID_REGEX = r'Request\s*ID[:\s]*([a-f0-9\-]{36})'

# =========================
# COMMON
# =========================
def extract_uuid(text):
    match = re.search(UUID_REGEX, text)
    return match.group(1) if match else None

def extract_request_id(text):
    match = re.search(REQUEST_ID_REGEX, text, re.IGNORECASE)
    return match.group(1) if match else None


# =========================
# FDFDataHub
# =========================
def extract_response_json(text):
    if "Response:" not in text:
        return None
    try:
        json_part = text.split("Response:", 1)[1].strip()
        json_part = json_part.replace('""', '"')
        return json.loads(json_part)
    except:
        return None


def parse_fdf_datahub(df):
    rows = []
    uuid_groups = {}

    for val in df:
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
        df_out = df_out[df_out["Status"] != "0008"]

        df_out = df_out.iloc[::-1]
        df_out = df_out.drop_duplicates(subset=["VIN"], keep="first")
        df_out = df_out.iloc[::-1]

        df_out = df_out.reset_index(drop=True)
        df_out.insert(0, "No.", df_out.index + 1)

    return df_out


# =========================
# FDFTCAP
# =========================
def extract_json_from_log(log):
    if "Response" not in log:
        return None

    try:
        part = log.split("Response", 1)[1]

        start = part.find("{")
        end = part.rfind("}") + 1

        if start == -1 or end == -1:
            return None

        clean = part[start:end] \
                    .replace('""', '"') \
                    .replace('\n', '') \
                    .replace('\r', '') \
                    .strip()

        return json.loads(clean)

    except:
        return None


def parse_fdf_tcap(df):
    rows = []

    logs = [str(x) for x in df if not pd.isna(x)]

    # 👉 map UUID → RequestID
    uuid_to_req = {}
    for text in logs:
        uuid = extract_uuid(text)
        req = extract_request_id(text)

        if uuid and req:
            uuid_to_req[uuid] = req

    # 👉 extract response
    for text in logs:
        data = extract_json_from_log(text)

        if not data or "statusCode" not in data:
            continue

        uuid = extract_uuid(text)

        rows.append({
            "UUID": uuid,
            "RequestID": uuid_to_req.get(uuid),
            "CountInsert": data.get("countInsert", 0),
            "StatusCode": data.get("statusCode"),
            "Message": data.get("message")
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
# PROCESS
# =========================
if file1:
    df_file1 = pd.read_csv(file1) if file1.name.endswith(".csv") else pd.read_excel(file1)
    if "@message" in df_file1.columns:
        df_file1 = df_file1["@message"]
    df1 = parse_fdf_datahub(df_file1)

if file2:
    df_file2 = pd.read_csv(file2) if file2.name.endswith(".csv") else pd.read_excel(file2)
    if "@message" in df_file2.columns:
        df_file2 = df_file2["@message"]
    df2 = parse_fdf_tcap(df_file2)


# =========================
# 🔥 SUMMARY UI
# =========================
st.markdown("## Summary")

colA, colB = st.columns(2)

with colA:
    total_datahub = len(df1) if not df1.empty else 0

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b);
                padding: 30px;
                border-radius: 15px;
                text-align: center;
                border: 1px solid #334155;">
        <h4 style="color:#94a3b8;">TCAPLinkageDatahub</h4>
        <h1 style="color:white; font-size:48px;">{total_datahub}</h1>
        <div style="margin-top:15px; padding:10px;
                    border-radius:10px;
                    border:1px solid #22c55e;
                    color:#22c55e;">
            Error: 0
        </div>
    </div>
    """, unsafe_allow_html=True)


with colB:
    total_insert = df2["CountInsert"].sum() if not df2.empty else 0

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #0f172a, #1e293b);
                padding: 30px;
                border-radius: 15px;
                text-align: center;
                border: 1px solid #334155;">
        <h4 style="color:#94a3b8;">TCAPLinkage</h4>
        <h1 style="color:white; font-size:48px;">{total_insert}</h1>
        <div style="margin-top:15px; padding:10px;
                    border-radius:10px;
                    border:1px solid #22c55e;
                    color:#22c55e;">
            Error: 0
        </div>
    </div>
    """, unsafe_allow_html=True)


# =========================
# TABLE
# =========================
st.divider()

if not df1.empty:
    st.subheader("FDFDataHub")
    st.dataframe(df1, use_container_width=True)

if not df2.empty:
    st.subheader("FDFTCAP")
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
        "Download Excel",
        data=output,
        file_name="fdf-summary.xlsx"
    )
