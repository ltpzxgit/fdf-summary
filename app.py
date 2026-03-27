import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - FDF 3 Files", layout="wide")
st.title("ITOSE Tools - FDF (3 Files Version)")

# =========================
# REGEX
# =========================
DATETIME_ID_REGEX = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ([a-f0-9\-]{36})'
REQUEST_ID_REGEX = r'Request ID:\s*([a-f0-9\-]{36})'
KV_REGEX = r'(\w+)=([^,\s]+)'

# =========================
# FUNCTIONS
# =========================
def extract_uuid(text):
    m = re.search(DATETIME_ID_REGEX, text)
    return m.group(1) if m else None

def extract_request_id(text):
    m = re.search(REQUEST_ID_REGEX, text)
    return m.group(1) if m else None

def extract_kv(text):
    return dict(re.findall(KV_REGEX, text))

def extract_json_safe(text):
    """หา JSON block แบบไม่พัง nested"""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except:
            return None
    return None


# =========================
# MAIN PARSE
# =========================
def parse_fdfdatahub(df):

    log_map = {}
    rows = []

    for col in df.columns:
        for val in df[col]:
            if pd.isna(val):
                continue

            text = str(val)

            uuid = extract_uuid(text)
            if not uuid:
                continue

            log_map.setdefault(uuid, {
                "request_id": None,
                "json": None,
                "kv": None
            })

            # Request ID
            rid = extract_request_id(text)
            if rid:
                log_map[uuid]["request_id"] = rid

            # JSON
            j = extract_json_safe(text)
            if j:
                log_map[uuid]["json"] = j

            # KV
            kv = extract_kv(text)
            if kv:
                log_map[uuid]["kv"] = kv

            data = log_map[uuid]

            # ยิง row เมื่อมี JSON
            if data["json"]:
                rows.append({
                    "UUID": uuid,
                    "Request ID": data["request_id"],

                    # JSON
                    "VIN": data["json"].get("vin"),
                    "Message": data["json"].get("message"),
                    "Status": data["json"].get("status"),

                    # KV
                    "DeviceID": (data["kv"] or {}).get("deviceId"),
                    "ModelCode": (data["kv"] or {}).get("modelCode"),
                    "ModelSuffix": (data["kv"] or {}).get("modelSuffix"),
                    "Brand": (data["kv"] or {}).get("brand"),
                    "DCMFlag": (data["kv"] or {}).get("dcmFlag"),
                    "RewriteFlag": (data["kv"] or {}).get("rewriteFlag"),
                    "VehicleFlag": (data["kv"] or {}).get("vehicleFlag"),
                    "SendingTime": (data["kv"] or {}).get("sendingTime"),
                })

                # reset JSON กัน duplicate
                log_map[uuid]["json"] = None

    df_out = pd.DataFrame(rows).drop_duplicates()
    df_out = df_out.reset_index(drop=True)
    df_out.insert(0, "No.", df_out.index + 1)

    return df_out


# =========================
# UPLOAD
# =========================
col1, col2, col3 = st.columns(3)

with col1:
    file1 = st.file_uploader("FDFDataHub", type=["xlsx", "csv"])
with col2:
    file2 = st.file_uploader("FDFTCAP", type=["xlsx", "csv"])
with col3:
    file3 = st.file_uploader("VehicleSettingRequester", type=["xlsx", "csv"])


if file1 and file2 and file3:

    df_file1 = pd.read_csv(file1) if file1.name.endswith(".csv") else pd.read_excel(file1)
    df_file2 = pd.read_csv(file2) if file2.name.endswith(".csv") else pd.read_excel(file2)
    df_file3 = pd.read_csv(file3) if file3.name.endswith(".csv") else pd.read_excel(file3)

    # =========================
    # SHEET 1
    # =========================
    df1 = parse_fdfdatahub(df_file1)

    if df1.empty:
        st.warning("⚠️ Sheet1 ว่าง → ลองเช็ค format log หรือ regex")

    # =========================
    # SHEET 2
    # =========================
    df2 = df_file2.copy().reset_index(drop=True)
    df2.insert(0, "No.", df2.index + 1)

    # =========================
    # SHEET 3
    # =========================
    df3 = df_file3.copy().reset_index(drop=True)
    df3.insert(0, "No.", df3.index + 1)

    # =========================
    # DISPLAY
    # =========================
    st.subheader("FDFDataHubLinkage")
    st.dataframe(df1)

    st.subheader("FDFTCAPHubLinkage")
    st.dataframe(df2)

    st.subheader("VehicleSettingRequester")
    st.dataframe(df3)

    # =========================
    # EXPORT
    # =========================
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1.to_excel(writer, index=False, sheet_name='FDFDataHubLinkage')
        df2.to_excel(writer, index=False, sheet_name='FDFTCAPHubLinkage')
        df3.to_excel(writer, index=False, sheet_name='VehicleSettingRequester')

    output.seek(0)

    st.download_button(
        "Download Excel",
        data=output,
        file_name="fdf-3files.xlsx"
    )
