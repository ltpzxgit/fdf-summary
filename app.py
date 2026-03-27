import streamlit as st
import pandas as pd
import re
import json
from io import BytesIO

st.set_page_config(page_title="ITOSE - FDF", layout="wide")
st.title("ITOSE Tools - FDF Summary")

# =========================
# CSS (SMOOTH CARD)
# =========================
st.markdown("""
<style>
.card {
    padding: 20px;
    border-radius: 14px;
    background: linear-gradient(145deg, #0f172a, #111827);
    border: 1px solid #374151;
    text-align: center;
    transition: all 0.2s ease-in-out;
}
.card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 20px rgba(0,0,0,0.3);
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
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)

# =========================
# REGEX
# =========================
DATETIME_ID_REGEX = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ([a-f0-9\-]{36})'
REQUEST_ID_REGEX = r'Request ID:\s*([a-f0-9\-]{36})'

PAIR_REGEX = r'"LDCMID":"([A-Za-z0-9\-]+)".*?"StatusReg":"([^"]+)".*?"ResDate":"([^"]+)"'

TCAP_REGEX = r'"deviceId":"([^"]+)".*?"IMEI":"([^"]+)".*?"ICCID":"([^"]+)".*?"IMSI":"([^"]+)".*?"prodStatus":"([^"]+)".*?"prodDate":"([^"]+)".*?"sendDate":"([^"]+)".*?"typeStatus":"([^"]+)"'

AIS_REGEX = r'resourceOrderId":\s*"([^"]+)".*?resourceGroupId":\s*"([^"]+)".*?resourceOrderTimeOut":\s*"([^"]+)".*?resultCode":\s*"([^"]+)".*?resultDesc":\s*"([^"]+)".*?developerMessage":\s*"([^"]*)"'


# =========================
# FUNCTIONS
# =========================
def extract_corr_id(text):
    m = re.search(DATETIME_ID_REGEX, text)
    return m.group(1) if m else None

def extract_request_id(text):
    m = re.search(REQUEST_ID_REGEX, text)
    return m.group(1) if m else None

def extract_pairs(text):
    return re.findall(PAIR_REGEX, text)

def extract_tcap(text):
    return re.findall(TCAP_REGEX, text)

def extract_ais(text):
    return re.findall(AIS_REGEX, text, re.DOTALL)

def get_carrier(deviceid):
    if isinstance(deviceid, str) and deviceid.startswith(("A", "Z")):
        return "AIS"
    return "TRUE"


# =========================
# HIGHLIGHT FUNCTIONS
# =========================
def highlight_error_dten(row):
    return ['background-color: #ffcccc' if row["Result"] != "Process completed successfully" else '' for _ in row]

def highlight_error_tcap(row):
    return ['background-color: #ffcccc' if row["TypeStatus"] != "OK" else '' for _ in row]

def highlight_error_req(row):
    return ['background-color: #ffcccc' if row["ResultCode"] != "20000" else '' for _ in row]

def highlight_error_res(row):
    return ['background-color: #ffcccc' if row["ResultCode"] != "20000" else '' for _ in row]


# =========================
# UPLOAD
# =========================
col1, col2, col3, col4 = st.columns(4)

with col1:
    dten_file = st.file_uploader("DTEN", type=["xlsx", "csv"])
with col2:
    tcap_file = st.file_uploader("DTENTCAP", type=["xlsx", "csv"])
with col3:
    req_file = st.file_uploader("ProvisioningRequester", type=["xlsx", "csv"])
with col4:
    res_file = st.file_uploader("ProvisioningResponder", type=["xlsx", "csv"])


if dten_file and tcap_file and req_file and res_file:

    df_dten = pd.read_csv(dten_file) if dten_file.name.endswith(".csv") else pd.read_excel(dten_file)
    df_tcap = pd.read_csv(tcap_file) if tcap_file.name.endswith(".csv") else pd.read_excel(tcap_file)
    df_req = pd.read_csv(req_file) if req_file.name.endswith(".csv") else pd.read_excel(req_file)
    df_res = pd.read_csv(res_file) if res_file.name.endswith(".csv") else pd.read_excel(res_file)

    # =========================
    # DTEN
    # =========================
    log_map = {}
    rows = []

    for col in df_dten.columns:
        for val in df_dten[col]:
            if pd.isna(val): continue

            text = str(val)
            cid = extract_corr_id(text)
            if not cid: continue

            log_map.setdefault(cid, {"req": None, "pairs": []})

            rid = extract_request_id(text)
            if rid:
                log_map[cid]["req"] = rid

            pairs = extract_pairs(text)
            if pairs:
                log_map[cid]["pairs"].extend(pairs)

            data = log_map[cid]
            if data["pairs"] and data["req"]:
                for d, s, dt in data["pairs"]:
                    rows.append({
                        "DeviceID": d,
                        "Request ID": data["req"],
                        "Result": s,
                        "Date Time": dt
                    })
                log_map[cid]["pairs"] = []

    df1 = pd.DataFrame(rows).drop_duplicates(subset=["DeviceID","Request ID","Date Time"])
    df1["Result"] = df1["Result"].astype(str).str.strip()

    df1["Carrier"] = df1["DeviceID"].apply(get_carrier)
    df1 = df1.reset_index(drop=True)
    df1.insert(0, "No.", df1.index + 1)

    # =========================
    # TCAP
    # =========================
    trows = []

    for col in df_tcap.columns:
        for val in df_tcap[col]:
            if pd.isna(val): continue

            for d, imei, iccid, imsi, prod, pd1, sd, ts in extract_tcap(str(val)):
                trows.append({
                    "DeviceID": d,
                    "IMEI": imei,
                    "ICCID": iccid,
                    "IMSI": imsi,
                    "ProdStatus": prod,
                    "ProdDate": pd1,
                    "SendDate": sd,
                    "TypeStatus": ts
                })

    df2 = pd.DataFrame(trows).drop_duplicates(subset=["DeviceID","IMEI"])
    df2["TypeStatus"] = df2["TypeStatus"].astype(str).str.strip()

    df2 = df2.reset_index(drop=True)
    df2.insert(0, "No.", df2.index + 1)

    # =========================
    # Requester
    # =========================
    rrows = []

    for col in df_req.columns:
        for val in df_req[col]:
            if pd.isna(val): continue

            text = str(val)
            cid = extract_corr_id(text)
            if not cid: continue

            for ro, d, to, code, desc, msg in extract_ais(text):
                rrows.append({
                    "DeviceID": d,
                    "UUID": cid,
                    "ResourceOrderId": ro,
                    "ResultCode": code,
                    "ResultDesc": desc
                })

    df3 = pd.DataFrame(rrows).drop_duplicates(subset=["DeviceID","UUID"])
    df3["ResultCode"] = df3["ResultCode"].astype(str).str.strip()

    df3 = df3.reset_index(drop=True)
    df3.insert(0, "No.", df3.index + 1)

    # =========================
    # Responder
    # =========================
    srows = []

    for col in df_res.columns:
        for val in df_res[col]:
            if pd.isna(val): continue

            text = str(val)
            cid = extract_corr_id(text)
            if not cid: continue

            try:
                json_part = text.split("Response:")[-1].strip()
                data = json.loads(json_part)

                srows.append({
                    "DeviceID": data.get("resourceGroupId"),
                    "UUID": cid,
                    "ResourceOrderId": data.get("resourceOrderId"),
                    "ResultCode": data.get("resultCode"),
                    "ResultDesc": data.get("resultDesc"),
                    "DeveloperMessage": data.get("developerMessage") or "-"
                })
            except:
                continue

    df4 = pd.DataFrame(srows).drop_duplicates(subset=["DeviceID","UUID"])
    df4["ResultCode"] = df4["ResultCode"].astype(str).str.strip()

    df4 = df4.reset_index(drop=True)
    df4.insert(0, "No.", df4.index + 1)

    # =========================
    # COUNT
    # =========================
    dten_total = len(df1)
    dten_error = len(df1[df1["Result"] != "Process completed successfully"])

    tcap_total = len(df2)
    tcap_error = len(df2[df2["TypeStatus"] != "OK"])

    req_total = len(df3)
    req_error = len(df3[df3["ResultCode"] != "20000"])

    res_total = len(df4)
    res_error = len(df4[df4["ResultCode"] != "20000"])

    # =========================
    # CARD FUNCTION
    # =========================
    def card(title, total, error):
        if error > 0:
            bg = "linear-gradient(135deg, rgba(239,68,68,0.15), rgba(239,68,68,0.05))"
            border = "rgba(239,68,68,0.4)"
            color = "#f87171"
        else:
            bg = "linear-gradient(135deg, rgba(34,197,94,0.15), rgba(34,197,94,0.05))"
            border = "rgba(34,197,94,0.4)"
            color = "#4ade80"

        return f"""
        <div class="card">
            <div class="card-title">{title}</div>
            <div class="card-value">{total}</div>
            <div class="card-error" style="
                background:{bg};
                border:1px solid {border};
                color:{color};
            ">
                Error: {error}
            </div>
        </div>
        """

    # =========================
    # SUMMARY
    # =========================
    st.markdown("### Summary")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(card("DTEN", dten_total, dten_error), unsafe_allow_html=True)

    with col2:
        st.markdown(card("DTENTCAP", tcap_total, tcap_error), unsafe_allow_html=True)

    with col3:
        st.markdown(card("ProvisioningRequester", req_total, req_error), unsafe_allow_html=True)

    with col4:
        st.markdown(card("ProvisioningResponder", res_total, res_error), unsafe_allow_html=True)

    # =========================
    # TABLE
    # =========================
    st.subheader("DTENLinkage")
    st.dataframe(df1.style.apply(highlight_error_dten, axis=1))

    st.subheader("DTENTCAPLinkage")
    st.dataframe(df2.style.apply(highlight_error_tcap, axis=1))

    st.subheader("ProvisioningRequester")
    st.dataframe(df3.style.apply(highlight_error_req, axis=1))

    st.subheader("ProvisioningResponder")
    st.dataframe(df4.style.apply(highlight_error_res, axis=1))

    # =========================
    # EXPORT
    # =========================
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df1.to_excel(writer, index=False, sheet_name='DTENLinkage')
        df2.to_excel(writer, index=False, sheet_name='DTENTCAPLinkage')
        df3.to_excel(writer, index=False, sheet_name='ProvisioningRequester')
        df4.to_excel(writer, index=False, sheet_name='ProvisioningResponder')

    output.seek(0)

    st.download_button(
        "Download Summary",
        data=output,
        file_name="fdf-summary.xlsx"
    )
