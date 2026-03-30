import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - FDF", layout="wide")
st.title("ITOSE Tools - FDF Summary")

# =========================
# 🎨 STYLE (แบบที่ตังค์อยากได้)
# =========================
st.markdown("""
<style>

/* ===== Upload Label ===== */
.upload-label {
    font-size: 14px;
    color: #9ca3af;
    margin-bottom: 8px;
}

/* ===== Upload Box ===== */
[data-testid="stFileUploader"] {
    background: linear-gradient(145deg, #2b2f3a, #1f2937);
    border-radius: 14px;
    padding: 18px;
    border: 1px solid #374151;
}

/* เอา border default ข้างในออก */
[data-testid="stFileUploader"] section {
    border: none !important;
}

/* ปุ่ม */
[data-testid="stFileUploader"] button {
    border-radius: 10px;
    background: #111827;
    border: 1px solid #374151;
    color: white;
}

/* hover */
[data-testid="stFileUploader"] button:hover {
    background: #1f2937;
}

/* ===== Summary Card ===== */
.card {
    padding: 20px;
    border-radius: 14px;
    background: linear-gradient(145deg, #0f172a, #111827);
    border: 1px solid #374151;
    text-align: center;
}
.card-title {
    font-size: 14px;
    color: #9ca3af;
}
.card-value {
    font-size: 42px;
    font-weight: bold;
    color: white;
}
.card-error {
    margin-top: 12px;
    padding: 12px;
    border-radius: 10px;
    color: #4ade80;
    background: rgba(34,197,94,0.1);
    border: 1px solid rgba(34,197,94,0.3);
}

</style>
""", unsafe_allow_html=True)

# =========================
# REGEX
# =========================
UUID_REGEX = r'([a-f0-9\-]{36})'
REQUEST_ID_REGEX = r'Request\s*ID[:\s]*([a-f0-9\-]{36})'

def extract_uuid(text):
    m = re.search(UUID_REGEX, text)
    return m.group(1) if m else None

def extract_request_id(text):
    m = re.search(REQUEST_ID_REGEX, text, re.IGNORECASE)
    return m.group(1) if m else None

# =========================
# FDFDataHub
# =========================
def extract_response_json(text):
    if "Response:" not in text:
        return None
    try:
        part = text.split("Response:", 1)[1].strip()
        part = part.replace('""', '"')
        return json.loads(part)
    except:
        return None

def parse_fdf_datahub(df):
    rows = []
    uuid_groups = {}

    for val in df:
        if pd.isna(val): continue
        text = str(val)
        uuid = extract_uuid(text)
        if not uuid: continue
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
        df_out = df_out.drop_duplicates(subset=["VIN"])
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
        clean = part[start:end].replace('""', '"')
        return json.loads(clean)
    except:
        return None

def parse_fdf_tcap(df):
    rows = []
    logs = [str(x) for x in df if not pd.isna(x)]

    for text in logs:
        data = extract_json_from_log(text)
        if not data:
            continue

        rows.append({
            "CountInsert": data.get("countInsert", 0)
        })

    return pd.DataFrame(rows)

# =========================
# VehicleSettingRequester
# =========================
def parse_vehicle_setting(df):
    logs = [str(x) for x in df if not pd.isna(x)]
    uuid_map = {}

    for text in logs:
        uuid = extract_uuid(text)
        if not uuid:
            continue

        uuid_map.setdefault(uuid, {})

        if "vin=" in text:
            uuid_map[uuid]["VIN"] = text.split("vin=")[1].split(",")[0]

    rows = []
    for i, (uuid, data) in enumerate(uuid_map.items(), 1):
        rows.append({
            "No.": i,
            "UUID": uuid,
            "VIN": data.get("VIN"),
        })

    return pd.DataFrame(rows)

# =========================
# UPLOAD (3 ช่อง)
# =========================
st.markdown("## Upload Files")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown('<div class="upload-label">FDFDataHub</div>', unsafe_allow_html=True)
    file1 = st.file_uploader("", key="f1")

with c2:
    st.markdown('<div class="upload-label">FDFTCAP</div>', unsafe_allow_html=True)
    file2 = st.file_uploader("", key="f2")

with c3:
    st.markdown('<div class="upload-label">VehicleSettingRequester</div>', unsafe_allow_html=True)
    file3 = st.file_uploader("", key="f3")

# =========================
# PROCESS
# =========================
def read_file(file):
    return pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)

df1 = df2 = df3 = pd.DataFrame()

if file1:
    df = read_file(file1)
    df1 = parse_fdf_datahub(df["@message"] if "@message" in df.columns else df)

if file2:
    df = read_file(file2)
    df2 = parse_fdf_tcap(df["@message"] if "@message" in df.columns else df)

if file3:
    df = read_file(file3)
    df3 = parse_vehicle_setting(df["@message"] if "@message" in df.columns else df)

# =========================
# SUMMARY
# =========================
st.markdown("## Summary")

s1, s2, s3 = st.columns(3)

def card(title, value):
    return f"""
    <div class="card">
        <div class="card-title">{title}</div>
        <div class="card-value">{value}</div>
        <div class="card-error">Error: 0</div>
    </div>
    """

with s1:
    st.markdown(card("TCAPLinkageDatahub", len(df1)), unsafe_allow_html=True)

with s2:
    st.markdown(card("TCAPLinkage", df2["CountInsert"].sum() if not df2.empty else 0), unsafe_allow_html=True)

with s3:
    st.markdown(card("VehicleSettingRequester", len(df3)), unsafe_allow_html=True)

# =========================
# TABLE
# =========================
st.divider()

if not df1.empty:
    st.dataframe(df1, use_container_width=True)

if not df2.empty:
    st.dataframe(df2, use_container_width=True)

if not df3.empty:
    st.dataframe(df3, use_container_width=True)
