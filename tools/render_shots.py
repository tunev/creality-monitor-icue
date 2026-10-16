"""Renders the REAL widget (CrealityMonitor_Template/index.html + main.css + main.js)
in headless Edge with sample printer data, one screenshot per state.

The widget is vh-responsive; 1280x720 is roughly half of a Xeneon Edge (2560x720 is the
full screen), so the shots look like the widget does on the device.

Usage (from repo root):  python tools/render_shots.py   ->  tools/_shots/shot_<state>.png
Then:                    python tools/compose_media.py
"""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "CrealityMonitor_Template"
OUT = Path(__file__).resolve().parent / "_shots"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
VIEW_W, VIEW_H, SCALE = 1280, 720, 2

BASE = {
    "model": "K1C",
    "hostname": "K1C-7D5A",
    "printFileName": "/usr/data/printer_data/gcodes/benchy_0.2mm_PLA.gcode",
    "TotalLayer": 292,
    "maxNozzleTemp": 300,
    "maxBedTemp": 100,
    "boxTemp": 34,
    "usedMaterialLength": 8300,
    "curPosition": "X:110.00 Y:110.00 Z:24.60",
    "realTimeSpeed": 180,
    "realTimeFlow": 11.4,
    "modelFanPct": 100,
}

STATES = {
    "printing": dict(state=1, printProgress=63, layer=184, nozzleTemp=219.8, targetNozzleTemp=220,
                     bedTemp0=59.6, targetBedTemp0=60, printJobTime=3684, printLeftTime=2130),
    "heating": dict(state=1, printProgress=1, layer=2, nozzleTemp=148.3, targetNozzleTemp=220,
                    bedTemp0=47.9, targetBedTemp0=60, printJobTime=95, printLeftTime=5400,
                    realTimeSpeed=40, realTimeFlow=1.2, modelFanPct=0, curPosition="X:30.00 Y:20.00 Z:0.40"),
    "paused": dict(state=5, printProgress=41, layer=120, nozzleTemp=215.1, targetNozzleTemp=220,
                   bedTemp0=60.0, targetBedTemp0=60, printJobTime=2410, printLeftTime=3400,
                   realTimeSpeed=0, realTimeFlow=0, modelFanPct=0),
    "complete": dict(state=2, printProgress=100, layer=292, TotalLayer=292, nozzleTemp=32.1, targetNozzleTemp=0,
                     bedTemp0=28.4, targetBedTemp0=0, printJobTime=5840, printLeftTime=0, boxTemp=26,
                     realTimeSpeed=0, realTimeFlow=0, modelFanPct=0, curPosition="X:0.00 Y:0.00 Z:30.00"),
    "failed": dict(state=3, printProgress=37, layer=108, nozzleTemp=120.5, targetNozzleTemp=0,
                   bedTemp0=45.0, targetBedTemp0=0, printJobTime=1980, printLeftTime=0,
                   realTimeSpeed=0, realTimeFlow=0, modelFanPct=0),
}


def harness(index_html: str, state: dict, camera_frame: str | None = None) -> str:
    html = re.sub(r"<meta http-equiv=\"Content-Security-Policy\".*?/>", "", index_html, flags=re.S)
    stub = "<script>window.WebSocket=function(){this.readyState=0;this.send=function(){};this.close=function(){};};</script>\n"
    data = {**BASE, **state}
    cam = ""
    if camera_frame:
        cam = f'el["cam"].poster = {json.dumps(camera_frame)}; setCamBadge("LIVE", true);\n'
    inject = (
        "<script>\n"
        f"settings.showCamera = {json.dumps(bool(camera_frame))}; applyCameraVisibility();\n"
        f"data = {json.dumps(data)};\n"
        "setOnline(true); render();\n"
        + cam +
        "</script>\n"
    )
    html = html.replace('<script src="scripts/main.js"></script>', stub + '<script src="scripts/main.js"></script>\n' + inject)
    return html


def main() -> None:
    OUT.mkdir(exist_ok=True)
    index_html = (TEMPLATE / "index.html").read_text(encoding="utf-8")
    frame = next(iter(sorted(Path(__file__).resolve().parent.glob("camera-frame.*"))), None)
    # the camera card is on by default in the real widget, so every state is rendered with it
    jobs = [(name, state, frame.name if frame else None) for name, state in STATES.items()]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "widget"
        shutil.copytree(TEMPLATE, work)
        if frame:
            shutil.copy(frame, work / frame.name)
        for name, state, cam_frame in jobs:
            page = work / f"_{name}.html"
            page.write_text(harness(index_html, state, cam_frame), encoding="utf-8")
            out = OUT / f"shot_{name}.png"
            subprocess.run(
                [EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                 f"--screenshot={out}", f"--window-size={VIEW_W},{VIEW_H}",
                 f"--force-device-scale-factor={SCALE}", "--virtual-time-budget=4000",
                 page.as_uri()],
                check=True, capture_output=True,
            )
            print("rendered", out)


if __name__ == "__main__":
    main()
