from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime
import html
import re
from typing import Optional
import sys
import threading
import time
import webbrowser

def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller bundle"""
    if hasattr(sys, '_MEIPASS'):
        bundle_path = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(bundle_path):
            return bundle_path
    base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


app = FastAPI(title="Tally Ledger Closing Balance API")

# ** ALLOW CORS SO EXTERNAL APPLICATIONS (WEB APPS, MOBILE APPS, AUTOMATION SCRIPTS) CAN CALL THIS API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_FILE = "tally_config.json"
BALANCES_FILE = "balances.json"

DEFAULT_CONFIG = {"host": "localhost", "port": 9000, "company": ""}


class TallyConfig(BaseModel):
    host: str
    port: int
    company: str = ""


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_config():
    return load_json(CONFIG_FILE, DEFAULT_CONFIG)


def safe_parse_xml(xml_bytes: bytes) -> ET.Element:
    """Parses XML from Tally safely, fixing unescaped ampersands."""
    text = xml_bytes.decode("utf-8", errors="replace")
    clean_text = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+);)', '&amp;', text)
    return ET.fromstring(clean_text)


def build_xml_request_filtered(ledger_name: str, company: str) -> str:
    company_tag = f"<SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>" if company else ""
    escaped_name = html.escape(ledger_name)
    return f"""
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <TALLYREQUEST>Export</TALLYREQUEST>
  <TYPE>Collection</TYPE>
  <ID>LedgerCollection</ID>
 </HEADER>
 <BODY>
  <DESC>
   <STATICVARIABLES>
    {company_tag}
    <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
    <SVFROMDATE TYPE="Date">20000401</SVFROMDATE>
    <SVTODATE TYPE="Date">20991231</SVTODATE>
   </STATICVARIABLES>
   <TDL>
    <TDLMESSAGE>
     <COLLECTION NAME="LedgerCollection" ISMODIFY="No">
      <TYPE>Ledger</TYPE>
      <FILTER>NameFilter</FILTER>
      <FETCH>NAME, CLOSINGBALANCE, OPENINGBALANCE, PARENT</FETCH>
     </COLLECTION>
     <SYSTEM TYPE="Formulae" NAME="NameFilter">$Name = "{escaped_name}"</SYSTEM>
    </TDLMESSAGE>
   </TDL>
  </DESC>
 </BODY>
</ENVELOPE>
""".strip()


def build_xml_request_all(company: str) -> str:
    company_tag = f"<SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>" if company else ""
    return f"""
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <TALLYREQUEST>Export</TALLYREQUEST>
  <TYPE>Collection</TYPE>
  <ID>LedgerCollection</ID>
 </HEADER>
 <BODY>
  <DESC>
   <STATICVARIABLES>
    {company_tag}
    <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
    <SVFROMDATE TYPE="Date">20000401</SVFROMDATE>
    <SVTODATE TYPE="Date">20991231</SVTODATE>
   </STATICVARIABLES>
   <TDL>
    <TDLMESSAGE>
     <COLLECTION NAME="LedgerCollection" ISMODIFY="No">
      <TYPE>Ledger</TYPE>
      <FETCH>NAME, CLOSINGBALANCE, OPENINGBALANCE, PARENT</FETCH>
     </COLLECTION>
    </TDLMESSAGE>
   </TDL>
  </DESC>
 </BODY>
</ENVELOPE>
""".strip()


def extract_ledger_info(ledger_elem) -> dict:
    name = ledger_elem.get("NAME") or ""
    name_elem = ledger_elem.find("NAME")
    if name_elem is not None and name_elem.text:
        name = name_elem.text.strip()

    closing_elem = ledger_elem.find("CLOSINGBALANCE")
    opening_elem = ledger_elem.find("OPENINGBALANCE")
    parent_elem = ledger_elem.find("PARENT")

    raw_closing = closing_elem.text.strip() if closing_elem is not None and closing_elem.text else ""
    raw_opening = opening_elem.text.strip() if opening_elem is not None and opening_elem.text else ""
    parent = parent_elem.text.strip() if parent_elem is not None and parent_elem.text else ""

    return {
        "name": name,
        "raw_closing": raw_closing,
        "raw_opening": raw_opening,
        "parent": parent,
    }


def parse_tally_amount(raw_val: str) -> tuple[str, str]:
    """Returns (formatted_balance_string, raw_number_string)"""
    if not raw_val or raw_val.strip() in ("", "0", "0.00"):
        return ("0.00", "0")
    val_str = raw_val.strip()
    if "Dr" in val_str or "Cr" in val_str:
        return (val_str, val_str)
    try:
        val = float(val_str)
        if val < 0:
            return (f"{abs(val):,.2f} Dr", val_str)
        elif val > 0:
            return (f"{val:,.2f} Cr", val_str)
        else:
            return ("0.00", "0")
    except ValueError:
        return (val_str, val_str)


@app.post("/config")
def save_config(config: TallyConfig):
    save_json(CONFIG_FILE, config.dict())
    return {"message": "Config saved", "config": config.dict()}


@app.get("/config")
def read_config():
    return get_config()


from fastapi import FastAPI, HTTPException, Query, Request


# ** CORE HELPER FUNCTION TO FETCH LEDGER CLOSING BALANCE FROM TALLY WITH AUTOMATIC CLIENT IP FALLBACK
def fetch_balance_from_tally(ledger_name: str, host: str, port: int, company: str, fallback_hosts: list = None):
    hosts_to_try = [host]
    if fallback_hosts:
        for fh in fallback_hosts:
            if fh and fh not in hosts_to_try:
                hosts_to_try.append(fh)

    matched_data = None
    last_error = None
    successful_host = host

    for current_host in hosts_to_try:
        url = f"http://{current_host}:{port}"
        target_name_clean = ledger_name.strip().lower()

        # ** STRATEGY 1: FILTERED QUERY
        try:
            xml_filtered = build_xml_request_filtered(ledger_name, company)
            resp = requests.post(url, data=xml_filtered.encode("utf-8"), timeout=8)
            resp.raise_for_status()
            root = safe_parse_xml(resp.content)
            ledgers = root.findall(".//LEDGER")

            for l_elem in ledgers:
                data = extract_ledger_info(l_elem)
                if data["name"].strip().lower() == target_name_clean:
                    matched_data = data
                    successful_host = current_host
                    break
        except Exception as e:
            last_error = e

        # ** STRATEGY 2: FETCH ALL LEDGERS AND MATCH IN PYTHON (FALLBACK IF TDL FILTER FORMULA RETURNED INCOMPLETE XML)
        if matched_data is None:
            try:
                xml_all = build_xml_request_all(company)
                resp = requests.post(url, data=xml_all.encode("utf-8"), timeout=12)
                resp.raise_for_status()
                root = safe_parse_xml(resp.content)
                ledgers = root.findall(".//LEDGER")

                for l_elem in ledgers:
                    data = extract_ledger_info(l_elem)
                    all_names = [data["name"].strip().lower()]
                    for name_node in l_elem.findall(".//NAME"):
                        if name_node.text:
                            all_names.append(name_node.text.strip().lower())

                    if target_name_clean in all_names:
                        matched_data = data
                        successful_host = current_host
                        break
            except Exception as e:
                last_error = e

        if matched_data is not None:
            break

    if matched_data is None:
        if last_error:
            raise HTTPException(status_code=500, detail=f"Error communicating with Tally at http://{host}:{port}: {last_error}")
        raise HTTPException(
            status_code=404,
            detail=f"Ledger '{ledger_name}' not found in Tally on port {port}. Please check company name or leave company blank to use active open company."
        )

    name = matched_data["name"] or ledger_name
    raw_closing = matched_data["raw_closing"]
    raw_opening = matched_data["raw_opening"]
    parent = matched_data["parent"]

    target_raw = raw_closing
    if (not target_raw or target_raw in ("0", "0.00")) and raw_opening not in ("0", "0.00", ""):
        target_raw = raw_opening

    formatted_balance, raw_num = parse_tally_amount(target_raw)

    # ** SAVE TO BALANCES.JSON
    saved_data = load_json(BALANCES_FILE, {})
    saved_data[name] = {
        "closing_balance": formatted_balance,
        "raw_balance": raw_num,
        "opening_balance": parse_tally_amount(raw_opening)[0],
        "parent": parent,
        "tally_port": port,
        "tally_host": successful_host,
        "last_updated": datetime.now().isoformat(timespec="seconds"),
    }
    save_json(BALANCES_FILE, saved_data)

    endpoint_url = f"/closing-balance/{name}"
    if port != 9000:
        endpoint_url += f"?port={port}"

    return {
        "status": "success",
        "ledger_name": name,
        "closing_balance": formatted_balance,
        "raw_balance": raw_num,
        "opening_balance": parse_tally_amount(raw_opening)[0],
        "parent": parent,
        "tally_port": port,
        "tally_host": successful_host,
        "last_updated": saved_data[name]["last_updated"],
        "api_endpoint": endpoint_url,
        "note": "Here I will write ledger name to get closing balance"
    }


# ** FALLBACK HANDLER WHEN NO LEDGER NAME IS PROVIDED IN URL PATH
@app.get("/closing-balance")
def closing_balance_help():
    return {
        "status": "info",
        "usage": "here I will write ledger name to get okay",
        "example": "/closing-balance/Om Pandey",
        "example_with_port": "/closing-balance/Om Pandey?port=9000"
    }


# ** GET CLOSING BALANCE ENDPOINT WITH OPTIONAL OVERRIDE QUERY PARAMETERS (PORT, HOST, COMPANY)
@app.get("/closing-balance/{ledger_name}")
def get_closing_balance(
    ledger_name: str,
    request: Request,
    port: Optional[int] = Query(None, description="Optional Tally Port override (e.g. 9000)"),
    host: Optional[str] = Query(None, description="Optional Tally Host override (default saved host or localhost)"),
    company: Optional[str] = Query(None, description="Optional Tally Company override (default active company)")
):
    # ** STRIP ACCIDENTAL CURLY BRACES {} FROM URL PLACEHOLDERS
    clean_ledger_name = ledger_name.strip("{} ").strip()

    config = get_config()
    target_host = host or config.get("host", "localhost")
    target_port = port if port is not None else config.get("port", 9000)
    target_company = company if company is not None else config.get("company", "")

    client_ip = request.client.host if request.client else None
    fallback_hosts = [client_ip] if client_ip and client_ip not in ("127.0.0.1", "localhost") else []

    return fetch_balance_from_tally(clean_ledger_name, target_host, target_port, target_company, fallback_hosts=fallback_hosts)


# ** DIRECT DYNAMIC QUERY API ENDPOINT
@app.get("/api/balance")
def query_balance_api(
    ledger_name: str,
    request: Request,
    port: Optional[int] = Query(None, description="Optional Tally Port (default 9000)"),
    host: Optional[str] = Query(None, description="Optional Tally Host (default saved host or localhost)"),
    company: Optional[str] = Query(None, description="Optional Tally Company Name")
):
    clean_ledger_name = ledger_name.strip("{} ").strip()

    config = get_config()
    target_host = host or config.get("host", "localhost")
    target_port = port if port is not None else config.get("port", 9000)
    target_company = company if company is not None else config.get("company", "")

    client_ip = request.client.host if request.client else None
    fallback_hosts = [client_ip] if client_ip and client_ip not in ("127.0.0.1", "localhost") else []

    return fetch_balance_from_tally(clean_ledger_name, target_host, target_port, target_company, fallback_hosts=fallback_hosts)


@app.get("/balances")
def get_all_saved_balances():
    return load_json(BALANCES_FILE, {})


@app.get("/", response_class=HTMLResponse)
def home():
    # ** SERVE HTML DASHBOARD FROM TEMPLATE FILE (TEMPLATES/INDEX.HTML OR EMBEDDED BUNDLE)
    template_path = get_resource_path(os.path.join("templates", "index.html"))
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Template file index.html not found!</h1>"


def open_browser_tab(url: str, delay: float = 1.2):
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from app_gui import main as gui_main
        gui_main()
    except Exception as e:
        print("Launching desktop GUI failed, starting CLI server fallback:", e)
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)