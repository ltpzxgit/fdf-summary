import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - FDF", layout="wide")
st.title("ITOSE Tools - FDF Summary")

# =========================
# 🎨 STYLE
# =========================
st.markdown("""
<style>
.card {
    background: linear-gradient(135deg, #1e293b, #0f172a);
    border-radius: 20px;
    padding: 30px;
    text-align: center;
    color: white;
    box-shadow: 0 10px 25px rgba(0,0,0,0.4);
}
.card-title {
    font-size: 18px;
    color: #94a3b8;
}
.card-value {
    font-size: 48px;
    font-weight: bold;
    margin: 10px 0;
}
.card-error {
    border: 1px solid #22c55e;
    border-radius: 12px;
    padding: 10px;
    color: #22c55e;
    margin-top: 10px;
}
.upload-box {
    background: #0f172a;
    padding: 20px;
    border-radius: 16px;
    border: 1px dashed #334155;
    text-align: center;
    color: #cbd5f5;
    margin-bottom: 10px;
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
        if start == -1 or end == -1:
            return None
        clean = part[start:end].replace('""', '"').replace('\n', '').replace('\r', '').strip()
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
# VehicleSettingRequester
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
        clean = part[start:end].replace('""', '"')
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
            "StatusCode": data.get("StatusCode"),
            "ResponseMessage": data.get("ResponseMessage"),
        })

    return pd.DataFrame(rows)

# =========================
# 📂 UPLOAD (3 ช่องสมดุล)
# =========================
st.markdown("## Upload Files")

u1, u2, u3 = st.columns(3)

with u1:
    st.markdown('<div class="upload-box">FDFDataHub</div>', unsafe_allow_html=True)
    file1 = st.file_uploader("", key="f1")

with u2:
    st.markdown('<div class="upload-box">FDFTCAP</div>', unsafe_allow_html=True)
    file2 = st.file_uploader("", key="f2")

with u3:
    st.markdown('<div class="upload-box">VehicleSettingRequester</div>', unsafe_allow_html=True)
    file3 = st.file_uploader("", key="f3")

df1, df2, df3 = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# =========================
# PROCESS
# =========================
if file1:
    df = pd.read_csv(file1) if file1.name.endswith(".csv") else pd.read_excel(file1)
    df1 = parse_fdf_datahub(df["@message"] if "@message" in df.columns else df)

if file2:
    df = pd.read_csv(file2) if file2.name.endswith(".csv") else pd.read_excel(file2)
    df2 = parse_fdf_tcap(df["@message"] if "@message" in df.columns else df)

if file3:
    df = pd.read_csv(file3) if file3.name.endswith(".csv") else pd.read_excel(file3)
    df3 = parse_vehicle_setting(df["@message"] if "@message" in df.columns else df)

# =========================
# SUMMARY
# =========================
st.markdown("## Summary")

total1 = len(df1)
error1 = len(df1[df1["Status"] != "0000"]) if not df1.empty else 0

total2 = df2["CountInsert"].sum() if not df2.empty else 0
error2 = len(df2[df2["StatusCode"] != "000"]) if not df2.empty else 0

total3 = len(df3)
error3 = len(df3[df3["StatusCode"] != "000"]) if not df3.empty else 0

c1, c2, c3 = st.columns(3)

def card(title, value, error):
    st.markdown(f"""
    <div class="card">
        <div class="card-title">{title}</div>
        <div class="card-value">{value}</div>
        <div class="card-error">Error: {error}</div>
    </div>
    """, unsafe_allow_html=True)

with c1: card("TCAPLinkageDatahub", total1, error1)
with c2: card("TCAPLinkage", total2, error2)
with c3: card("VehicleSettingRequester", total3, error3)

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
