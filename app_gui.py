import sys
import os
import json
import threading
import time
import webbrowser
from datetime import datetime

# Handle headless/noconsole mode stdout/stderr redirection
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import customtkinter as ctk
import uvicorn
from PIL import Image
import pystray
from pystray import MenuItem as item

from main import (
    app as fastapi_app,
    fetch_balance_from_tally,
    get_config,
    save_json,
    CONFIG_FILE,
    BALANCES_FILE,
    get_resource_path
)

# Configure CustomTkinter appearance
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("green")


class ServerManager:
    """Manages the background FastAPI Uvicorn server thread"""
    def __init__(self, host="0.0.0.0", port=8000):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
        self.is_running = False

    def start(self):
        if self.is_running:
            return
        config = uvicorn.Config(
            fastapi_app,
            host=self.host,
            port=self.port,
            log_level="warning"
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        self.is_running = True

    def _run_server(self):
        try:
            self.server.run()
        except Exception as e:
            print(f"Uvicorn Server Error: {e}")
        finally:
            self.is_running = False

    def stop(self):
        if self.server and self.is_running:
            self.server.should_exit = True
            self.is_running = False


class TallyDesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Tally Ledger Closing Balance Desktop App & API")
        self.geometry("1180x820")
        self.minsize(900, 600)

        # Set Window Icon if Logo.ico exists
        self.icon_path = get_resource_path("Logo.ico")
        if os.path.exists(self.icon_path):
            try:
                self.iconbitmap(self.icon_path)
            except Exception:
                pass

        # Configure root grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.server_mgr = ServerManager(host="0.0.0.0", port=8000)
        self.last_api_response_str = ""
        self.tray_icon = None

        self._build_header()
        self._build_main_dashboard()
        self._load_config_into_fields()
        self._setup_system_tray()

        # Handle window close [X] button -> Minimize to System Tray
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_system_tray(self):
        """Set up system tray icon and context menu"""
        try:
            if os.path.exists(self.icon_path):
                tray_image = Image.open(self.icon_path)
            else:
                tray_image = Image.new("RGB", (64, 64), color=(5, 150, 105))

            menu = pystray.Menu(
                item("Open TallyCC Dashboard", self._tray_show_window, default=True),
                item("Start / Stop API Server", self._tray_toggle_server),
                item("Open Web Dashboard (Browser)", self._tray_open_web),
                pystray.Menu.SEPARATOR,
                item("Exit TallyCC Completely", self._tray_exit_app)
            )

            self.tray_icon = pystray.Icon(
                "TallyCC",
                tray_image,
                "TallyCC - Tally API & Dashboard",
                menu
            )

            # Start system tray loop in a background daemon thread
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            print("System tray setup failed:", e)

    def _tray_show_window(self, icon=None, item=None):
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tray_toggle_server(self, icon=None, item=None):
        self.after(0, self.toggle_api_server)

    def _tray_open_web(self, icon=None, item=None):
        self.after(0, self.open_web_dashboard)

    def _tray_exit_app(self, icon=None, item=None):
        self.after(0, self._force_quit)

    def _build_header(self):
        """Header Frame containing Title, Server Control Toggle, LED Status, and Web Launch Button"""
        header_frame = ctk.CTkFrame(self, fg_color="#ffffff", corner_radius=0, border_width=1, border_color="#e2e8f0")
        header_frame.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 8))
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)

        # App Title & Subtitle (Left Aligned)
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.grid(row=0, column=0, padx=12, pady=10, sticky="w")

        title_lbl = ctk.CTkLabel(
            title_box,
            text="TallyCC Desktop & API",
            font=ctk.CTkFont(family="Plus Jakarta Sans", size=17, weight="bold"),
            text_color="#0f172a"
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            title_box,
            text="Query Tally Prime / ERP 9 Closing Balances",
            font=ctk.CTkFont(family="Plus Jakarta Sans", size=11),
            text_color="#64748b"
        )
        subtitle_lbl.pack(anchor="w")

        # Server Controls Box (Right Aligned - Grid Layout for Zero Clipping)
        ctrl_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        ctrl_box.grid(row=0, column=1, padx=12, pady=10, sticky="e")

        # Live Status LED Badge
        self.status_badge = ctk.CTkLabel(
            ctrl_box,
            text="🔴 API Server Stopped",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#dc2626",
            fg_color="#fef2f2",
            corner_radius=0,
            padx=8,
            pady=4
        )
        self.status_badge.grid(row=0, column=0, padx=(0, 8), sticky="e")

        # Start / Stop Server Toggle Button
        self.server_btn = ctk.CTkButton(
            ctrl_box,
            text="▶ Start API Server",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            corner_radius=0,
            height=30,
            command=self.toggle_api_server
        )
        self.server_btn.grid(row=0, column=1, padx=(0, 8), sticky="e")

        # Open Web Dashboard Button
        self.web_btn = ctk.CTkButton(
            ctrl_box,
            text="🌐 Open Web Dashboard",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            corner_radius=0,
            height=30,
            command=self.open_web_dashboard
        )
        self.web_btn.grid(row=0, column=2, padx=(0, 8), sticky="e")

        # Exit App Button
        self.exit_btn = ctk.CTkButton(
            ctrl_box,
            text="✖ Quit App",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#f1f5f9",
            hover_color="#e2e8f0",
            text_color="#475569",
            corner_radius=0,
            height=30,
            width=75,
            command=self._force_quit
        )
        self.exit_btn.grid(row=0, column=3, sticky="e")

    def _build_main_dashboard(self):
        """Scrollable 2-Column Dashboard Grid Layout ensuring no elements cut off"""
        scroll_container = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        scroll_container.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 12))
        scroll_container.grid_columnconfigure(0, weight=1)
        scroll_container.grid_columnconfigure(1, weight=1)

        # ==========================================
        # LEFT COLUMN: Connection Settings & API Reference
        # ==========================================
        left_col = ctk.CTkFrame(scroll_container, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        left_col.grid_columnconfigure(0, weight=1)

        # STEP 1: CONNECTION SETTINGS CARD
        card_step1 = ctk.CTkFrame(left_col, fg_color="#ffffff", corner_radius=0, border_width=1, border_color="#e2e8f0")
        card_step1.pack(fill="x", pady=(0, 12))

        step1_hdr = ctk.CTkFrame(card_step1, fg_color="transparent")
        step1_hdr.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(
            step1_hdr,
            text="Tally Connection Settings",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#0f172a"
        ).pack(side="left")

        ctk.CTkLabel(
            step1_hdr,
            text="STEP 1",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#475569",
            fg_color="#f1f5f9",
            padx=6,
            pady=2,
            corner_radius=0
        ).pack(side="right")

        form1_inner = ctk.CTkFrame(card_step1, fg_color="transparent")
        form1_inner.pack(fill="x", padx=14, pady=(4, 14))

        # Host Input
        ctk.CTkLabel(form1_inner, text="TALLY HOST (IP OR 'LOCALHOST')", font=ctk.CTkFont(size=10, weight="bold"), text_color="#475569").pack(anchor="w", pady=(4, 2))
        self.entry_host = ctk.CTkEntry(form1_inner, placeholder_text="localhost", corner_radius=0, border_color="#cbd5e1", height=32)
        self.entry_host.pack(fill="x", pady=(0, 8))

        # Port Input
        ctk.CTkLabel(form1_inner, text="TALLY PORT", font=ctk.CTkFont(size=10, weight="bold"), text_color="#475569").pack(anchor="w", pady=(4, 2))
        self.entry_port = ctk.CTkEntry(form1_inner, placeholder_text="9000", corner_radius=0, border_color="#cbd5e1", height=32)
        self.entry_port.pack(fill="x", pady=(0, 8))

        # Company Input
        ctk.CTkLabel(form1_inner, text="COMPANY NAME (AS SHOWN IN TALLY)", font=ctk.CTkFont(size=10, weight="bold"), text_color="#475569").pack(anchor="w", pady=(4, 2))
        self.entry_company = ctk.CTkEntry(form1_inner, placeholder_text="e.g. Demo Company (or blank for active)", corner_radius=0, border_color="#cbd5e1", height=32)
        self.entry_company.pack(fill="x", pady=(0, 10))

        # Save Button
        self.btn_save_config = ctk.CTkButton(
            form1_inner,
            text="Save Connection Settings",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            corner_radius=0,
            height=34,
            command=self.save_settings
        )
        self.btn_save_config.pack(fill="x")

        # API INTEGRATION REFERENCE CARD
        card_api_ref = ctk.CTkFrame(left_col, fg_color="#ffffff", corner_radius=0, border_width=1, border_color="#e2e8f0")
        card_api_ref.pack(fill="x")

        ref_hdr = ctk.CTkFrame(card_api_ref, fg_color="transparent")
        ref_hdr.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(
            ref_hdr,
            text="API Integration Reference",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#0f172a"
        ).pack(side="left")

        ctk.CTkLabel(
            ref_hdr,
            text="REFERENCE",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#475569",
            fg_color="#f1f5f9",
            padx=6,
            pady=2,
            corner_radius=0
        ).pack(side="right")

        ref_inner = ctk.CTkFrame(card_api_ref, fg_color="transparent")
        ref_inner.pack(fill="x", padx=14, pady=(4, 14))

        # Format 1 Box
        box1 = ctk.CTkFrame(ref_inner, fg_color="#f8fafc", border_width=1, border_color="#e2e8f0", corner_radius=0)
        box1.pack(fill="x", pady=(0, 8), ipadx=8, ipady=6)

        ctk.CTkLabel(box1, text="Format 1: Standard URL", font=ctk.CTkFont(size=10, weight="bold"), text_color="#0284c7").pack(anchor="w", padx=6)
        ctk.CTkLabel(box1, text="GET /closing-balance/{ledger_name}", font=ctk.CTkFont(family="Courier", size=11, weight="bold"), text_color="#059669").pack(anchor="w", padx=6, pady=(2, 0))

        # Format 2 Box
        box2 = ctk.CTkFrame(ref_inner, fg_color="#ecfdf5", border_width=1, border_color="#a7f3d0", corner_radius=0)
        box2.pack(fill="x", ipadx=8, ipady=6)

        ctk.CTkLabel(box2, text="Format 2: Port Parameter Override", font=ctk.CTkFont(size=10, weight="bold"), text_color="#059669").pack(anchor="w", padx=6)
        ctk.CTkLabel(box2, text="GET /closing-balance/{ledger_name}?port=9001", font=ctk.CTkFont(family="Courier", size=11, weight="bold"), text_color="#047857").pack(anchor="w", padx=6, pady=(2, 0))

        # ==========================================
        # RIGHT COLUMN: Check Ledger Balance & Live Result
        # ==========================================
        right_col = ctk.CTkFrame(scroll_container, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)
        right_col.grid_columnconfigure(0, weight=1)

        # STEP 2: CHECK LEDGER FORM CARD
        card_step2 = ctk.CTkFrame(right_col, fg_color="#ffffff", corner_radius=0, border_width=1, border_color="#e2e8f0")
        card_step2.pack(fill="x", pady=(0, 12))

        step2_hdr = ctk.CTkFrame(card_step2, fg_color="transparent")
        step2_hdr.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(
            step2_hdr,
            text="Check Ledger Balance",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#0f172a"
        ).pack(side="left")

        ctk.CTkLabel(
            step2_hdr,
            text="STEP 2",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#475569",
            fg_color="#f1f5f9",
            padx=6,
            pady=2,
            corner_radius=0
        ).pack(side="right")

        form2_inner = ctk.CTkFrame(card_step2, fg_color="transparent")
        form2_inner.pack(fill="x", padx=14, pady=(4, 14))

        # Ledger Name Input
        ctk.CTkLabel(form2_inner, text="LEDGER NAME", font=ctk.CTkFont(size=10, weight="bold"), text_color="#475569").pack(anchor="w", pady=(4, 2))
        self.entry_ledger_name = ctk.CTkEntry(form2_inner, placeholder_text="e.g. Om Pandey, Sunita Pagal, ABC Traders", corner_radius=0, border_color="#cbd5e1", height=32)
        self.entry_ledger_name.pack(fill="x", pady=(0, 8))

        # Override Port Input
        ctk.CTkLabel(form2_inner, text="OPTIONAL TALLY PORT OVERRIDE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#475569").pack(anchor="w", pady=(4, 2))
        self.entry_override_port = ctk.CTkEntry(form2_inner, placeholder_text="e.g. 9000 or 9001 (leave empty for default)", corner_radius=0, border_color="#cbd5e1", height=32)
        self.entry_override_port.pack(fill="x", pady=(0, 10))

        # Check Balance Button
        self.btn_check_balance = ctk.CTkButton(
            form2_inner,
            text="Check Ledger Balance",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            corner_radius=0,
            height=34,
            command=self.check_balance
        )
        self.btn_check_balance.pack(fill="x")

        # LIVE RESULT CARD
        self.card_result = ctk.CTkFrame(right_col, fg_color="#ffffff", corner_radius=0, border_width=1, border_color="#e2e8f0")
        self.card_result.pack(fill="x")

        res_hdr = ctk.CTkFrame(self.card_result, fg_color="transparent")
        res_hdr.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(
            res_hdr,
            text="Balance Result",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#0f172a"
        ).pack(side="left")

        # Compact Copy Button prevents text truncation
        self.btn_copy_json = ctk.CTkButton(
            res_hdr,
            text="📋 Copy JSON",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#f1f5f9",
            hover_color="#e2e8f0",
            text_color="#0f172a",
            corner_radius=0,
            height=26,
            width=95,
            command=self.copy_json_response
        )
        self.btn_copy_json.pack(side="right")

        res_inner = ctk.CTkFrame(self.card_result, fg_color="transparent")
        res_inner.pack(fill="x", padx=14, pady=(4, 14))

        # Hero Balance Card
        self.hero_box = ctk.CTkFrame(res_inner, fg_color="#ecfdf5", border_width=1, border_color="#a7f3d0", corner_radius=0)
        self.hero_box.pack(fill="x", pady=(0, 10), ipadx=8, ipady=8)

        self.lbl_r_ledger = ctk.CTkLabel(
            self.hero_box,
            text="Enter a ledger name to check balance",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#475569",
            wraplength=480
        )
        self.lbl_r_ledger.pack(anchor="w", padx=6)

        self.lbl_r_balance = ctk.CTkLabel(
            self.hero_box,
            text="0.00",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#059669"
        )
        self.lbl_r_balance.pack(anchor="w", padx=6, pady=(2, 0))

        # Meta Pills (2-Column Grid)
        meta_grid = ctk.CTkFrame(res_inner, fg_color="transparent")
        meta_grid.pack(fill="x", pady=(0, 10))
        meta_grid.grid_columnconfigure(0, weight=1)
        meta_grid.grid_columnconfigure(1, weight=1)

        # Parent Group Pill
        pill1 = ctk.CTkFrame(meta_grid, fg_color="#f8fafc", border_width=1, border_color="#e2e8f0", corner_radius=0)
        pill1.grid(row=0, column=0, sticky="ew", padx=(0, 4), ipadx=6, ipady=4)
        ctk.CTkLabel(pill1, text="PARENT GROUP", font=ctk.CTkFont(size=9, weight="bold"), text_color="#94a3b8").pack(anchor="w", padx=4)
        self.lbl_r_parent = ctk.CTkLabel(pill1, text="N/A", font=ctk.CTkFont(size=11, weight="bold"), text_color="#0f172a")
        self.lbl_r_parent.pack(anchor="w", padx=4)

        # Tally Port & Host Pill
        pill2 = ctk.CTkFrame(meta_grid, fg_color="#f8fafc", border_width=1, border_color="#e2e8f0", corner_radius=0)
        pill2.grid(row=0, column=1, sticky="ew", padx=(4, 0), ipadx=6, ipady=4)
        ctk.CTkLabel(pill2, text="TALLY PORT & HOST", font=ctk.CTkFont(size=9, weight="bold"), text_color="#94a3b8").pack(anchor="w", padx=4)
        self.lbl_r_porthost = ctk.CTkLabel(pill2, text="9000 (localhost)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#0f172a")
        self.lbl_r_porthost.pack(anchor="w", padx=4)

        # Raw JSON Output Text Area
        ctk.CTkLabel(res_inner, text="RAW JSON API RESPONSE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#475569").pack(anchor="w", pady=(4, 2))
        self.textbox_json = ctk.CTkTextbox(
            res_inner,
            font=ctk.CTkFont(family="Courier", size=10),
            fg_color="#0f172a",
            text_color="#38bdf8",
            corner_radius=0,
            border_width=1,
            border_color="#1e293b",
            height=140
        )
        self.textbox_json.pack(fill="x")

    def _load_config_into_fields(self):
        """Loads saved settings from tally_config.json into entry widgets"""
        cfg = get_config()
        self.entry_host.insert(0, cfg.get("host", "localhost"))
        self.entry_port.insert(0, str(cfg.get("port", 9000)))
        self.entry_company.insert(0, cfg.get("company", ""))

    def toggle_api_server(self):
        """Toggle Start / Stop API Server"""
        if not self.server_mgr.is_running:
            self.server_mgr.start()
            self.status_badge.configure(
                text="🟢 API Server Live: http://localhost:8000",
                text_color="#059669",
                fg_color="#ecfdf5"
            )
            self.server_btn.configure(
                text="⏹ Stop API Server",
                fg_color="#dc2626",
                hover_color="#b91c1c"
            )
        else:
            self.server_mgr.stop()
            self.status_badge.configure(
                text="🔴 API Server Stopped",
                text_color="#dc2626",
                fg_color="#fef2f2"
            )
            self.server_btn.configure(
                text="▶ Start API Server",
                fg_color="#059669",
                hover_color="#047857"
            )

    def open_web_dashboard(self):
        """Opens web browser to http://localhost:8000"""
        if not self.server_mgr.is_running:
            self.toggle_api_server()
            time.sleep(0.5)
        webbrowser.open("http://localhost:8000")

    def save_settings(self):
        """Save Tally connection configuration"""
        host = self.entry_host.get().strip() or "localhost"
        try:
            port = int(self.entry_port.get().strip() or "9000")
        except ValueError:
            port = 9000
        company = self.entry_company.get().strip()

        config_data = {"host": host, "port": port, "company": company}
        save_json(CONFIG_FILE, config_data)

        self.btn_save_config.configure(text="✅ Settings Saved!")
        self.after(2000, lambda: self.btn_save_config.configure(text="Save Connection Settings"))

    def check_balance(self):
        """Check Ledger Closing Balance via direct Python helper"""
        ledger_name = self.entry_ledger_name.get().strip()
        if not ledger_name:
            self.lbl_r_ledger.configure(text="⚠️ Please enter a ledger name!")
            self.lbl_r_balance.configure(text="Error")
            return

        cfg = get_config()
        host = cfg.get("host", "localhost")
        try:
            saved_port = int(cfg.get("port", 9000))
        except (ValueError, TypeError):
            saved_port = 9000
        company = cfg.get("company", "")

        override_port_str = self.entry_override_port.get().strip()
        if override_port_str:
            try:
                active_port = int(override_port_str)
            except ValueError:
                active_port = saved_port
        else:
            active_port = saved_port

        self.lbl_r_ledger.configure(text=f"Fetching '{ledger_name}'...")
        self.lbl_r_balance.configure(text="...")
        self.update_idletasks()

        def _fetch_task():
            try:
                res = fetch_balance_from_tally(
                    ledger_name=ledger_name,
                    host=host,
                    port=active_port,
                    company=company
                )
                self.after(0, lambda: self._update_result_ui(res))
            except Exception as err:
                err_msg = str(err)
                if hasattr(err, "detail"):
                    err_msg = err.detail
                self.after(0, lambda: self._update_result_error(ledger_name, err_msg))

        threading.Thread(target=_fetch_task, daemon=True).start()

    def _update_result_ui(self, res_data: dict):
        """Update result UI components with fetched ledger balance"""
        self.lbl_r_ledger.configure(text=res_data.get("ledger_name", ""))
        self.lbl_r_balance.configure(text=res_data.get("closing_balance", "0.00"))
        self.lbl_r_parent.configure(text=res_data.get("parent") or "N/A")

        t_port = res_data.get("tally_port", 9000)
        t_host = res_data.get("tally_host", "localhost")
        self.lbl_r_porthost.configure(text=f"{t_port} ({t_host})")

        self.last_api_response_str = json.dumps(res_data, indent=2)
        self.textbox_json.delete("1.0", "end")
        self.textbox_json.insert("1.0", self.last_api_response_str)

    def _update_result_error(self, ledger_name: str, error_msg: str):
        """Update result UI when fetch fails"""
        self.lbl_r_ledger.configure(text=f"Failed to fetch '{ledger_name}'")
        self.lbl_r_balance.configure(text="Error")
        self.lbl_r_parent.configure(text="N/A")
        self.lbl_r_porthost.configure(text="Error")

        err_json = {"status": "error", "ledger_name": ledger_name, "detail": error_msg}
        self.last_api_response_str = json.dumps(err_json, indent=2)
        self.textbox_json.delete("1.0", "end")
        self.textbox_json.insert("1.0", self.last_api_response_str)

    def copy_json_response(self):
        """Copy raw JSON string to clipboard"""
        if not self.last_api_response_str:
            return
        self.clipboard_clear()
        self.clipboard_append(self.last_api_response_str)
        self.btn_copy_json.configure(text="✅ Copied!")
        self.after(2000, lambda: self.btn_copy_json.configure(text="📋 Copy JSON"))

    def _on_close(self):
        """When user clicks [X] button, minimize to System Tray instead of exiting"""
        self.withdraw()
        if self.server_mgr.is_running and hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.notify(
                    "TallyCC API Server is active in the background system tray.",
                    "TallyCC Background Service"
                )
            except Exception:
                pass

    def _force_quit(self):
        """Completely stop server, remove tray icon, and exit process"""
        if self.server_mgr.is_running:
            self.server_mgr.stop()
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.destroy()
        sys.exit(0)


def main():
    app = TallyDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
