<p align="center">
  <img src="Logo.ico" alt="TallyCC Logo" width="128" height="128">
</p>

# Tally Ledger Closing Balance Desktop App & API

A lightweight FastAPI service, native Desktop GUI application, and clean 2-column web dashboard to query ledger closing balances directly from **Tally Prime** / **Tally.ERP 9** via Tally's built-in HTTP/XML interface across your local network. No DSN or ODBC driver installation required.

---

## 🚀 Standalone Executable (`TallyCC.exe`)

You can run TallyCC as a **single standalone Windows executable (`TallyCC.exe`)**.

### 🌟 Executable Features:
- **Clean Native Desktop GUI**: Recreates the exact 2-column layout & card interface of the web dashboard with zero cut-off text/buttons.
- **No Command Prompt Window**: Launches directly without opening a CMD console window.
- **System Tray Background Service**: Closing the window (`[X]`) minimizes the application to the **System Tray** (notification area next to the clock), keeping your background API server active until explicitly exited.
- **Start / Stop API Server Toggle**: Control the FastAPI server on/off directly from the desktop window or system tray menu.

### 📦 1-Click Building `TallyCC.exe` on Windows:

1. Double-click **`build_exe.bat`**
2. The compiled single executable will be saved in **`dist\TallyCC.exe`**
3. Double-click **`dist\TallyCC.exe`** anytime to launch!

---

## ⚡ Standard Script Run Options

1. Double-click **`install.bat`**  
   *(Creates a local `.\venv` virtual environment and installs required dependencies).*

2. Double-click **`RunServer.bat`**  
   *(Starts the FastAPI server bound to `0.0.0.0:8000`, making it accessible across your local network).*

3. Open your browser:
   - On the same machine: `http://localhost:8000`
   - From another PC on the network: `http://<YOUR-SERVER-IP>:8000`

---

## 🌟 Key Features

- **Single Executable (`TallyCC.exe`)**: Embeds API server & HTML web interface template inside one portable `.exe` file.
- **System Tray Background Process**: Keeps the API service live when window is closed.
- **Decoupled Web Dashboard**: Built with a clean white minimalist theme (`border-radius: 0px`), animated inputs, toast notifications, and zero vertical scroll.
- **2-Column Layout**:
  - **Left Side**: Step 1 Tally Connection Settings & API Integration Reference Guide.
  - **Right Side**: Step 2 Check Ledger Closing Balance Form & Live Results Hero Card with Raw JSON Viewer.
- **Dual API Querying Modes**:
  1. **Standard Mode**: `GET /closing-balance/{ledger_name}` (uses saved host/port/company or client IP fallback).
  2. **Direct Parameter Mode**: `GET /closing-balance/{ledger_name}?port=9001` or `GET /api/balance?ledger_name=Sunita%20Pagal&port=9001`.
- **Automatic Client IP Detection**: When called from another PC on the network, the backend automatically detects the remote client IP to query Tally on that PC.

---

## 📋 Prerequisites & Tally Configuration

1. Make sure **Tally Prime** (or Tally.ERP 9) is running.
2. Verify Tally HTTP API port (Default is `9000` or `9001`):
   - In Tally: Go to **F1: Help** -> **TDL & Add-On** -> **F4: Manage Local TDLs** / **Configure Tally.NET Services**.
   - Ensure HTTP/XML interface is enabled.

---

## 🔌 API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Web Dashboard UI |
| `POST` | `/config` | Save Tally connection parameters |
| `GET` | `/config` | Get saved configuration |
| `GET` | `/closing-balance/{ledger_name}` | Fetch balance (accepts optional `?port=9001&host=192.168.101.6`) |
| `GET` | `/api/balance` | Query balance with parameters `?ledger_name=Sunita%20Pagal&port=9001` |
| `GET` | `/balances` | Retrieve all previously checked/saved balances |

### Example API Response (`GET /closing-balance/Sunita%20Pagal?port=9001`):
```json
{
  "status": "success",
  "ledger_name": "Sunita Pagal",
  "closing_balance": "5,000.00 Dr",
  "raw_balance": "-5000.00",
  "opening_balance": "5,000.00 Dr",
  "parent": "Sundry Debtors",
  "tally_port": 9001,
  "tally_host": "192.168.101.6",
  "last_updated": "2026-09-03T12:30:15",
  "api_endpoint": "/closing-balance/Sunita Pagal?port=9001",
  "note": "Here I will write ledger name to get closing balance"
}
```
