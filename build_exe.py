import os
import sys
import subprocess
import shutil

def clean_old_builds():
    """Remove old build and dist folders if present"""
    print("[...] Cleaning old build and dist folders...")
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                print(f"  [✔] Removed old {folder}/ directory.")
            except Exception as e:
                print(f"  [!] Warning: Could not remove {folder}/: {e}")

def main():
    print("=" * 65)
    print("       TallyCC Standalone Desktop Software (.exe) Builder")
    print("=" * 65)
    print()

    # Step 1: Clean build and dist folders
    clean_old_builds()
    print()

    # Step 2: Ensure PyInstaller and required packages are installed
    required_pkgs = ["pyinstaller", "customtkinter", "darkdetect", "fastapi", "uvicorn", "requests", "pydantic", "pystray", "PIL"]
    for pkg in required_pkgs:
        try:
            __import__(pkg)
        except ImportError:
            print(f"[!] Installing missing dependency: {pkg}...")
            pip_pkg = "pillow" if pkg == "PIL" else pkg
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_pkg])

    print("[✔] All build dependencies satisfied.")

    # Step 3: Ensure template and icon files exist
    template_file = os.path.join("templates", "index.html")
    if not os.path.exists(template_file):
        print(f"[✘] ERROR: Template file {template_file} not found!")
        sys.exit(1)

    icon_file = "Logo.ico"
    if os.path.exists(icon_file):
        print(f"[✔] Found application icon ({icon_file}).")
    else:
        print(f"[!] Warning: Application icon {icon_file} not found!")

    print("[✔] Found web dashboard template (templates/index.html).")
    print()
    print("[...] Compiling single standalone executable (System Tray background support, no terminal)...")
    print()

    # Step 4: Run PyInstaller build using TallyCC.spec
    cmd = [sys.executable, "-m", "PyInstaller", "TallyCC.spec", "--noconfirm"]
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print()
        print("[✘] Build failed! Check PyInstaller error logs above.")
        sys.exit(1)

    dist_dir = os.path.abspath("dist")
    exe_name = "TallyCC.exe" if sys.platform == "win32" else "TallyCC"
    exe_path = os.path.join(dist_dir, exe_name)

    print()
    print("=" * 65)
    print("  SUCCESS! Standalone Desktop Executable Created Successfully!")
    print("=" * 65)
    print(f"  Executable Path: {exe_path}")
    print()
    print("  Features of TallyCC.exe:")
    print("    - Clean GUI Executable without Command Prompt Terminal window")
    print("    - System Tray Background Process support (closes to tray)")
    print("    - Custom Icon embedded (Logo.ico)")
    print("    - Auto-scaling scrollable GUI matching Web Dashboard layout")
    print("=" * 65)

if __name__ == "__main__":
    main()
