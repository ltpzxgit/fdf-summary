import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - FDF", layout="wide")
st.title("ITOSE Tools - FDF Summary")

# =========================
# 🎨 STYLE (เหมือน repo)
# =========================
st.markdown("""
<style>

/* Upload title */
.upload-title-box {
    background: #1e293b;
    padding: 20px;
    border-radius: 16px;
    text-align: center;
    color: #cbd5f5;
    font-size: 16px;
    margin-bottom: 10px;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: #1f2937;
    padding: 25px;
    border-radius: 16px;
    border: none;
}
[data-testid="stFileUploader"] section {
    border: none;
}

/* Summary */
.summary-card {
    background: linear-gradient(135deg, #1e293b, #0f172a);
    border-radius: 24px;
    padding: 40px;
    text-align: center;
    color: white;
}
.summary-title {
    color: #94a3b8;
}
.summary-value {
    font-size: 56px;
    font-weight: bold;
}
.summary-error {
    border: 1px solid #22c55e;
    border-radius: 14px;
    padding: 12px;
    margin-top: 15px;
    color: #22c55e;
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
        df_out = df_out.iloc[::-1].drop_duplicates(subset=["VIN"], keep="first").iloc[::-1]
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
        clean = part[start:end].replace('""', '"').replace('\n','').replace('\r','')
        return json.loads(clean)
    except:
        return None

def parse_fdf_tcap(df):
    rows = []
    logs = [str(x) for x in df if not pd.isna(x)]

    uuid_to_req = {}
    for text in logs:
        uuid = extract_uuid(text)
        req = extract_request_id(text)
        if uuid and req:
            uuid_to_req[uuid] = req

    for text in logs:
        data = extract_json_from_log(text)
        if not data:
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
        df_out.insert(0, "No.", range(1, len(df_out)+1))

    return df_out

# =========================
# VehicleSettingRequester (FULL)
# =========================
def extract_body_data(text):
    if "body={" not in text:
        return {}
    try:
        part = text.split("body={", 1)[1].split("}", 1)[0]
        data = {}
        for item in part.split(","):
            if "=" in item:
                k, v = item.split("=", 1)
                data[k.strip()] = v.strip()
        return data
    except:
        return {}

def extract_response_data(text):
    if "Response:" not in text:
        return {}
    try:
        part = text.split("Response:", 1)[1]
        start = part.find("{")
        end = part.rfind("}") + 1
        clean = part[start:end].replace('""', '"').replace('\n','').replace('\r','')
        data = json.loads(clean)
        return {
            "StatusCode": data.get("statusCode"),
            "ResponseMessage": data.get("message")
        }
    except:
        return {}

def parse_vehicle_setting(df):
    logs = [str(x) for x in df if not pd.isna(x)]
    uuid_map = {}

    for text in logs:
        uuid = extract_uuid(text)
        if not uuid:
            continue

        uuid_map.setdefault(uuid, {})

        if "Request:" in text:
            uuid_map[uuid].update(extract_body_data(text))

        if "Response:" in text:
            uuid_map[uuid].update(extract_response_data(text))

    rows = []
    for i, (uuid, data) in enumerate(uuid_map.items(), start=1):
        rows.append({
            "No.": i,
            "UUID": uuid,
            "VIN": data.get("vin"),
            "DeviceID": data.get("deviceId"),
            "IMEI": data.get("IMEI"),
            "SimStatus": data.get("simStatus"),
            "SimPackage": data.get("simPackage"),
            "CAL_Flag": data.get("CAL_Flag"),
            "B2CFlag": data.get("B2CFlag"),
            "B2BFlag": data.get("B2BFlag"),
            "Tconnectflag": data.get("Tconnectflag"),
            "StatusCode": data.get("StatusCode"),
            "ResponseMessage": data.get("ResponseMessage"),
        })

    return pd.DataFrame(rows)

# =========================
# 📂 UPLOAD (3 ช่อง)
# =========================
st.markdown("## Upload Files")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown('<div class="upload-title-box">FDFDataHub</div>', unsafe_allow_html=True)
    file1 = st.file_uploader("", key="f1")

with c2:
    st.markdown('<div class="upload-title-box">FDFTCAP</div>', unsafe_allow_html=True)
    file2 = st.file_uploader("", key="f2")

with c3:
    st.markdown('<div class="upload-title-box">VehicleSettingRequester</div>', unsafe_allow_html=True)
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
# SUMMARY (3 กล่อง)
# =========================
st.markdown("## Summary")

s1, s2, s3 = st.columns(3)

def card(title, value):
    st.markdown(f"""
    <div class="summary-card">
        <div class="summary-title">{title}</div>
        <div class="summary-value">{value}</div>
        <div class="summary-error">Error: 0</div>
    </div>
    """, unsafe_allow_html=True)

with s1:
    card("TCAPLinkageDatahub", len(df1))

with s2:
    card("TCAPLinkage", df2["CountInsert"].sum() if not df2.empty else 0)

with s3:
    card("VehicleSettingRequester", len(df3))

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

if not df3.empty:
    st.subheader("VehicleSettingRequester")
    st.dataframe(df3, use_container_width=True)

# =========================
# EXPORT
# =========================
if not df1.empty or not df2.empty or not df3.empty:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        if not df1.empty:
            df1.to_excel(writer, index=False, sheet_name='FDFDataHub')
        if not df2.empty:
            df2.to_excel(writer, index=False, sheet_name='FDFTCAP')
        if not df3.empty:
            df3.to_excel(writer, index=False, sheet_name='VehicleSettingRequester')

    output.seek(0)

    st.download_button("Download Excel", data=output, file_name="fdf-summary.xlsx")
