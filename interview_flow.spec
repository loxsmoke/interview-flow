# PyInstaller spec — builds Interview Flow as a standalone desktop app.
#
# Prerequisites:
#   pip install pyinstaller
#   pip install -r requirements.txt
#
# Build (from the project root):
#   Windows:  pyinstaller interview_flow.spec
#   Mac:      pyinstaller interview_flow.spec
#
# Output:
#   dist/InterviewFlow/   (Windows — folder with .exe)
#   dist/InterviewFlow.app  (Mac — drag-and-drop .app)
#
# After building, place your .env file next to the executable / .app bundle.
# User data (interview sessions) is saved in a `data/` folder beside the executable.

block_cipher = None

a = Analysis(
    ["app/desktop.py"],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle the React frontend and agent modules alongside the frozen code
        ("app/static", "app/static"),
        ("app/agents", "app/agents"),
        ("app/prompts", "app/prompts"),
    ],
    hiddenimports=[
        # uvicorn sub-modules that aren't auto-discovered
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # app dependencies
        "fitz",
        "docx",
        "langfuse",
        "multipart",
        # pywebview platform backends (PyInstaller can't detect these at analysis time)
        "webview.platforms.winforms",   # Windows (Edge WebView2)
        "webview.platforms.cocoa",      # Mac (WKWebView)
        "webview.platforms.gtk",        # Linux (WebKitGTK) — included for completeness
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "playwright", "_pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="InterviewFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # console=True is useful during development to see server logs.
    # Set to False for a clean production build (no terminal window on Windows).
    console=False,
    icon=None,  # Supply "icon.ico" (Windows) or "icon.icns" (Mac) to add an icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="InterviewFlow",
)

# Mac: wrap the collected folder into a drag-and-drop .app bundle.
# On Windows this block is ignored — delete it if you prefer cleaner output.
app = BUNDLE(
    coll,
    name="InterviewFlow.app",
    icon=None,
    bundle_identifier="com.interview.flow",
    info_plist={
        "NSHighResolutionCapable": True,
        "CFBundleShortVersionString": "1.0.0",
    },
)
