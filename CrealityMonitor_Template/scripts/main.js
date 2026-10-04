/* Creality Monitor - Corsair Xeneon Edge / iCUE widget
 * Чете живи данни от собствения WebSocket API на Creality K-серия (порт 9999)
 * и показва камерата по WebRTC (порт 8000).
 * Принтерът праща пълен обект при свързване и после само променените полета,
 * затова състоянието се слива инкрементално в `data`.
 * ES5 синтаксис заради WebView2 контекста на iCUE.
 */

var settings = {
    host: "192.168.0.232",
    port: "9999",
    accent: "#00b3ff",
    showCamera: true,
    pcAddress: "192.168.0.100"
};

var CAM_PORT = 8000;        // порт на WebRTC услугата на принтера

var data = {};              // слят снимков образ на състоянието
var ws = null;
var heartbeatTimer = null;
var reconnectTimer = null;
var lastMessageAt = 0;

var RING_LEN = 326.7;       // 2 * PI * 52

var el = {};
[
    "conn-dot", "state-pill", "host-label", "model-name", "ring-fg", "progress-pct",
    "layer-info", "filename", "row-nozzle", "row-bed", "noz-cur", "noz-tgt", "noz-bar",
    "bed-cur", "bed-tgt", "bed-bar", "box-temp", "material", "elapsed", "remaining",
    "speed", "flow", "fan", "zpos", "status-text", "grid", "cam", "cam-badge"
].forEach(function (id) {
    el[id] = document.getElementById(id);
});

/* ------------------------------------------------------------------ utils */

function clean(v) {
    if (typeof v !== "string") return v;
    return v.trim().replace(/^['"]+|['"]+$/g, "");
}

function n(v, dflt) {
    var x = typeof v === "string" ? parseFloat(v) : v;
    return (typeof x === "number" && isFinite(x)) ? x : (dflt === undefined ? 0 : dflt);
}

function setText(node, text) { if (node) node.textContent = text; }

function pad(v) { return (v < 10 ? "0" : "") + v; }

function fmtTime(sec) {
    if (!isFinite(sec) || sec < 0) return "--:--";
    sec = Math.round(sec);
    var h = Math.floor(sec / 3600);
    var m = Math.floor((sec % 3600) / 60);
    var s = sec % 60;
    return h > 0 ? h + ":" + pad(m) + ":" + pad(s) : pad(m) + ":" + pad(s);
}

function fmtClock(d) { return pad(d.getHours()) + ":" + pad(d.getMinutes()); }

/* ----------------------------------------------------------- state labels */

// Стойности на полето `state` при Creality K-серия
var STATES = {
    0: { text: "IDLE",     cls: "" },
    1: { text: "PRINTING", cls: "" },
    2: { text: "COMPLETE", cls: "ok" },
    3: { text: "FAILED",   cls: "error" },
    4: { text: "PAUSED",   cls: "warn" },
    5: { text: "STOPPED",  cls: "warn" }
};

function describeState() {
    var err = data.err;
    if (err && n(err.errcode, 0) !== 0) {
        return { text: "ERROR " + err.errcode, cls: "error" };
    }
    var s = STATES[n(data.state, -1)];
    return s || { text: "STANDBY", cls: "" };
}

/* -------------------------------------------------------------- rendering */

function setOnline(online) {
    el["conn-dot"].className = "dot " + (online ? "online" : "offline");
}

function setTemp(row, curNode, tgtNode, barNode, cur, tgt, max) {
    setText(curNode, cur.toFixed(1));
    setText(tgtNode, String(Math.round(tgt)));
    barNode.style.width = Math.max(0, Math.min(100, (cur / max) * 100)) + "%";
    if (tgt > 0 && cur < tgt - 2) row.classList.add("heating");
    else row.classList.remove("heating");
}

function render() {
    var st = describeState();
    setText(el["state-pill"], st.text);
    el["state-pill"].className = "state-pill" + (st.cls ? " " + st.cls : "");

    setText(el["model-name"], data.model || "CREALITY");
    setText(el["host-label"], (data.hostname ? data.hostname + "  \u2022  " : "") + settings.host);

    // Прогрес
    var pct = Math.max(0, Math.min(100, n(data.printProgress, 0)));
    el["ring-fg"].style.strokeDashoffset = String(RING_LEN * (1 - pct / 100));
    setText(el["progress-pct"], String(Math.round(pct)));

    var layer = n(data.layer, 0), total = n(data.TotalLayer, 0);
    setText(el["layer-info"], total > 0 ? "LAYER " + layer + " / " + total : "LAYER \u2014 / \u2014");

    // Файл
    var f = data.printFileName || "";
    f = f.replace(/^.*[\\\/]/, "").replace(/\.(gcode|gco|g)$/i, "");
    setText(el["filename"], f || "No active job");

    // Температури
    setTemp(el["row-nozzle"], el["noz-cur"], el["noz-tgt"], el["noz-bar"],
            n(data.nozzleTemp), n(data.targetNozzleTemp), n(data.maxNozzleTemp, 300));
    setTemp(el["row-bed"], el["bed-cur"], el["bed-tgt"], el["bed-bar"],
            n(data.bedTemp0), n(data.targetBedTemp0), n(data.maxBedTemp, 100));

    setText(el["box-temp"], data.boxTemp !== undefined ? Math.round(n(data.boxTemp)) + "\u00B0" : "\u2014");
    el["material"].innerHTML = (n(data.usedMaterialLength) / 1000).toFixed(1) + "<i>m</i>";

    // Времена
    var printing = n(data.state, -1) === 1;
    setText(el["elapsed"], fmtTime(n(data.printJobTime, -1)));
    var left = n(data.printLeftTime, -1);
    setText(el["remaining"], printing ? fmtTime(left) : "--:--");

    // Малки показатели
    el["speed"].innerHTML = Math.round(n(data.realTimeSpeed)) + "<i>mm/s</i>";
    el["flow"].innerHTML  = n(data.realTimeFlow).toFixed(1) + "<i>mm\u00B3/s</i>";
    el["fan"].innerHTML   = Math.round(n(data.modelFanPct)) + "<i>%</i>";

    var z = 0;
    var m = /Z:\s*(-?[\d.]+)/.exec(data.curPosition || "");
    if (m) z = parseFloat(m[1]);
    el["zpos"].innerHTML = z.toFixed(2) + "<i>mm</i>";

    // Долен ред
    var parts = [];
    if (printing && left > 0) parts.push("Ends at " + fmtClock(new Date(Date.now() + left * 1000)));
    if (n(data.curFeedratePct, 100) !== 100) parts.push("Feedrate " + Math.round(n(data.curFeedratePct)) + "%");
    if (n(data.curFlowratePct, 100) !== 100) parts.push("Flowrate " + Math.round(n(data.curFlowratePct)) + "%");
    if (data.err && data.err.value) parts.push(String(data.err.value));
    parts.push("Live \u2022 " + new Date().toLocaleTimeString());
    setText(el["status-text"], parts.join("  \u2022  "));
}

function renderOffline(reason) {
    setOnline(false);
    setText(el["state-pill"], "OFFLINE");
    el["state-pill"].className = "state-pill error";
    setText(el["status-text"], "ws://" + settings.host + ":" + settings.port + " \u2014 " + reason);
}

/* ------------------------------------------------------------ camera (WebRTC)
 * K-серията раздава камерата по WebRTC. Сигнализацията е еднократен POST
 * към http://<ip>:8000/call/webrtc_local с тяло:
 *     base64( JSON {token, sdp, type:"offer"} )
 * и отговор base64( JSON {type:"answer", sdp} ).
 * Токенът се изисква по WebSocket с {"method":"get","params":{"getToken":1}}.
 */

var cam = { pc: null, retry: null, watchdog: null, startedAt: 0 };

function setCamBadge(text, live) {
    if (!el["cam-badge"]) return;
    el["cam-badge"].textContent = text;
    el["cam-badge"].className = "cam-badge" + (live ? " live" : "");
}

function stopCamera() {
    if (cam.watchdog) { clearInterval(cam.watchdog); cam.watchdog = null; }
    if (cam.retry) { clearTimeout(cam.retry); cam.retry = null; }
    if (cam.pc) {
        try {
            cam.pc.ontrack = null;
            cam.pc.oniceconnectionstatechange = null;
            cam.pc.close();
        } catch (e) { /* ignore */ }
        cam.pc = null;
    }
    if (el["cam"]) el["cam"].srcObject = null;
}

function scheduleCameraRetry(reason) {
    stopCamera();
    if (!settings.showCamera) return;
    setCamBadge(reason || "RECONNECTING", false);
    cam.retry = setTimeout(function () { cam.retry = null; startCamera(); }, 5000);
}

function requestVideoToken() {
    if (ws && ws.readyState === 1) ws.send('{"method":"get","params":{"getToken":1}}');
}

function postOffer(pc) {
    return new Promise(function (resolve, reject) {
        // Chromium скрива локалния IP зад mDNS име ("xxxx.local"), което
        // принтерът не може да разреши и DTLS никога не завършва.
        // Затова подменяме името с реалния IP на този компютър.
        var sdp = pc.localDescription.sdp;
        if (settings.pcAddress) {
            sdp = sdp.replace(/[0-9a-fA-F-]{36}\.local/g, settings.pcAddress);
        }
        var xhr = new XMLHttpRequest();
        xhr.open("POST", "http://" + settings.host + ":" + CAM_PORT + "/call/webrtc_local", true);
        xhr.setRequestHeader("Content-Type", "plain/text");
        xhr.timeout = 8000;
        xhr.onreadystatechange = function () {
            if (xhr.readyState !== 4) return;
            if (xhr.status === 200 && xhr.responseText) resolve(xhr.responseText);
            else reject(new Error("HTTP " + xhr.status));
        };
        xhr.onerror = function () { reject(new Error("network")); };
        xhr.ontimeout = function () { reject(new Error("timeout")); };
        xhr.send(window.btoa(JSON.stringify({
            token: String(data.videoToken).trim(),
            sdp: sdp,
            type: "offer"
        })));
    });
}

function waitForIce(pc) {
    return new Promise(function (resolve) {
        if (pc.iceGatheringState === "complete") { resolve(); return; }
        var t = setTimeout(resolve, 2500);
        pc.onicegatheringstatechange = function () {
            if (pc.iceGatheringState === "complete") { clearTimeout(t); resolve(); }
        };
    });
}

function startCamera() {
    if (!settings.showCamera || cam.pc) return;
    if (!window.RTCPeerConnection) { setCamBadge("NO WEBRTC", false); return; }
    if (!data.videoToken) { setCamBadge("WAITING TOKEN", false); requestVideoToken(); return; }

    setCamBadge("CONNECTING", false);
    var pc = new RTCPeerConnection({ iceServers: [] });
    cam.pc = pc;
    pc.addTransceiver("video", { direction: "recvonly" });

    pc.ontrack = function (evt) {
        var v = el["cam"];
        if (!v) return;
        v.srcObject = evt.streams[0];
        var p = v.play();
        if (p && p["catch"]) p["catch"](function () { /* autoplay guard */ });
    };

    pc.oniceconnectionstatechange = function () {
        var s = pc.iceConnectionState;
        if (s === "failed" || s === "closed") scheduleCameraRetry("RECONNECTING");
    };

    // Ако до 12 сек. няма реални кадри - нов опит.
    cam.watchdog = setInterval(function () {
        var v = el["cam"];
        if (v && v.videoWidth > 0) {
            clearInterval(cam.watchdog); cam.watchdog = null;
            setCamBadge("LIVE", true);
            return;
        }
        if (Date.now() - cam.startedAt > 12000) {
            scheduleCameraRetry(settings.pcAddress
                ? "NO VIDEO " + settings.pcAddress
                : "SET PC IP");
        }
    }, 1000);
    cam.startedAt = Date.now();

    pc.createOffer()
        .then(function (offer) { return pc.setLocalDescription(offer); })
        .then(function () { return waitForIce(pc); })
        .then(function () { return postOffer(pc); })
        .then(function (body) {
            var answer = JSON.parse(window.atob(body));
            if (!answer || !answer.sdp) throw new Error("bad answer");
            return pc.setRemoteDescription(new RTCSessionDescription(answer));
        })
        ["catch"](function (err) {
            // токенът може да е изтекъл - взимаме нов преди следващия опит
            data.videoToken = null;
            requestVideoToken();
            scheduleCameraRetry("SIGNAL: " + (err && err.message ? err.message : "error"));
        });
}

function applyCameraVisibility() {
    if (settings.showCamera) {
        el["grid"].classList.add("has-cam");
        startCamera();
    } else {
        el["grid"].classList.remove("has-cam");
        stopCamera();
    }
}

/* ------------------------------------------------------------- connection */

function stopTimers() {
    if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null; }
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
}

function scheduleReconnect(reason) {
    renderOffline(reason);
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(function () {
        reconnectTimer = null;
        connect();
    }, 4000);
}

function connect() {
    stopTimers();
    if (ws) {
        try { ws.onclose = null; ws.onerror = null; ws.close(); } catch (e) { /* ignore */ }
        ws = null;
    }

    var url = "ws://" + settings.host + ":" + settings.port + "/";
    try {
        ws = new WebSocket(url);
    } catch (ex) {
        scheduleReconnect("Cannot open socket: " + ex.message);
        return;
    }

    ws.onopen = function () {
        setOnline(true);
        setText(el["status-text"], "Connected \u2014 waiting for data\u2026");
        requestVideoToken();
        // Принтерът затваря връзката без периодичен heart_beat.
        heartbeatTimer = setInterval(function () {
            if (!ws || ws.readyState !== 1) return;
            ws.send('{"ModeCode":"heart_beat","msg":"' + Math.floor(Date.now() / 1000) + '"}');
            if (lastMessageAt && Date.now() - lastMessageAt > 30000) {
                try { ws.close(); } catch (e) { /* ignore */ }
            }
        }, 5000);
    };

    ws.onmessage = function (evt) {
        if (typeof evt.data !== "string") return;
        var text = evt.data;
        if (text.charAt(0) !== "{") return;     // напр. обикновен "ok"
        var msg;
        try { msg = JSON.parse(text); } catch (ex) { return; }
        if (!msg || typeof msg !== "object") return;

        lastMessageAt = Date.now();
        for (var k in msg) {
            if (Object.prototype.hasOwnProperty.call(msg, k)) data[k] = msg[k];
        }
        if (msg.videoToken && !cam.pc) startCamera();
        setOnline(true);
        render();
    };

    ws.onerror = function () { scheduleReconnect("Connection error"); };
    ws.onclose = function () { scheduleReconnect("Disconnected"); };
}

/* --------------------------------------------------------------- settings */

function applySettings(s) {
    var changed = false;
    if (s) {
        if (s.printerHost && clean(s.printerHost) !== settings.host) {
            settings.host = clean(s.printerHost); changed = true;
        }
        if (s.printerPort && clean(s.printerPort) !== settings.port) {
            settings.port = clean(s.printerPort); changed = true;
        }
        if (s.accentColor) settings.accent = clean(s.accentColor);
        if (s.pcAddress !== undefined && s.pcAddress !== null) {
            var ip = clean(s.pcAddress);
            if (ip !== settings.pcAddress) { settings.pcAddress = ip; stopCamera(); }
        }
        if (s.showCamera !== undefined && s.showCamera !== null) {
            var v = clean(s.showCamera);
            settings.showCamera = !(v === false || v === "false" || v === "0" || v === 0);
        }
    }
    document.documentElement.style.setProperty("--accent", settings.accent);
    if (changed) { stopCamera(); data = {}; }
    if (changed || !ws) connect();
    applyCameraVisibility();
}

window.icueEvents = {
    onICUEInitialized: function (p) { applySettings(p && p.settings); },
    onDataUpdated:     function (p) { applySettings(p && p.settings); }
};

// Часовникът в долния ред остава жив и когато принтерът мълчи
setInterval(function () { if (ws && ws.readyState === 1) render(); }, 1000);

applySettings(null);
