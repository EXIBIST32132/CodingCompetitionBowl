let hostSocket;
let hostAuthenticated = false;
let hostToken = null;
const leaderboardTable = document.querySelector("#leaderboardTable tbody");
const submissionList = document.getElementById("submissionList");
const codeContent = document.getElementById("codeContent");
const hostStatus = document.getElementById("hostStatus");
const loginBtn = document.getElementById("loginBtn");
const hostPasswordInput = document.getElementById("hostPassword");
const timerInput = document.getElementById("timerInput");
const timerStartBtn = document.getElementById("timerStart");
const timerPauseBtn = document.getElementById("timerPause");
const timerStopBtn = document.getElementById("timerStop");
const timerDisplay = document.getElementById("timerDisplay");
const resetBtn = document.getElementById("resetBtn");
let hostTimerState = {status: "stopped", remaining: 0};
let hostTimerSync = Date.now();
let hostTimerTick = null;

function updateHostStatus(connectionState) {
    const base = hostAuthenticated ? "Unlocked" : "Locked";
    if (connectionState === "connecting") {
        hostStatus.textContent = `${base} (connecting)`;
    } else if (connectionState === "connected") {
        hostStatus.textContent = base;
    } else if (connectionState === "disconnected") {
        hostStatus.textContent = `${base} (disconnected)`;
    } else {
        hostStatus.textContent = base;
    }
}

function connectSocket() {
    updateHostStatus("connecting");
    hostSocket = io({withCredentials: true, auth: hostToken ? {token: hostToken} : undefined});
    hostSocket.on("connect", () => {
        updateHostStatus("connected");
        if (hostAuthenticated) {
            hostSocket.emit("register_host", {token: hostToken});
        }
    });
    hostSocket.on("disconnect", () => {
        updateHostStatus("disconnected");
    });
    hostSocket.on("connect_error", () => {
        updateHostStatus("disconnected");
    });
    hostSocket.on("scoreboard_update", (payload) => {
        if (payload && payload.leaderboard) {
            renderLeaderboard(payload.leaderboard);
        }
    });
    hostSocket.on("submission_logged", (payload) => {
        if (payload && payload.submission) {
            prependSubmission(payload.submission);
        }
    });
    hostSocket.on("timer_update", (payload) => {
        if (payload && payload.timer) {
            renderTimer(payload.timer);
        }
    });
}

async function loginHost() {
    const password = hostPasswordInput.value;
    if (!password) return;
    const res = await fetch("/api/host/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        credentials: "include",
        body: JSON.stringify({password})
    });
    const data = await res.json();
    if (!res.ok) {
        alert(data.error || "Login failed");
        return;
    }
    hostAuthenticated = true;
    hostToken = data.token;
    updateHostStatus(hostSocket && hostSocket.connected ? "connected" : undefined);
    try {
        hostSocket.disconnect();
    } catch (e) {
        /* ignore */
    }
    connectSocket();
    await Promise.all([fetchLeaderboard(), fetchSubmissions(), fetchTimer()]);
}

async function fetchLeaderboard() {
    const res = await fetch("/api/host/leaderboard", {
        credentials: "include",
        headers: hostToken ? {"X-Host-Token": hostToken} : {}
    });
    const data = await res.json();
    if (res.ok) {
        renderLeaderboard(data.leaderboard || []);
    }
}

async function fetchSubmissions() {
    const res = await fetch("/api/host/submissions", {
        credentials: "include",
        headers: hostToken ? {"X-Host-Token": hostToken} : {}
    });
    const data = await res.json();
    if (res.ok) {
        renderSubmissionList(data.submissions || []);
    }
}

function renderLeaderboard(rows) {
    leaderboardTable.innerHTML = "";
    rows.forEach((row, idx) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${idx + 1}</td><td>${row.name}</td><td>${row.total_score}</td>`;
        leaderboardTable.appendChild(tr);
    });
}

function renderSubmissionList(subs) {
    submissionList.innerHTML = "";
    subs.forEach((sub) => submissionList.appendChild(buildSubmissionNode(sub)));
}

function buildSubmissionNode(sub) {
    const li = document.createElement("li");
    const score = `${sub.passed_tests}/${sub.total_tests}`;
    li.innerHTML = `<strong>${sub.name}</strong> - P${sub.problem_id} - ${sub.language} - ${score} - ${sub.timestamp}`;
    li.dataset.id = sub.id;
    li.addEventListener("click", () => loadSubmission(sub.id));
    return li;
}

function prependSubmission(sub) {
    submissionList.prepend(buildSubmissionNode(sub));
}

async function loadSubmission(id) {
    const res = await fetch(`/api/host/submission/${id}`, {
        credentials: "include",
        headers: hostToken ? {"X-Host-Token": hostToken} : {}
    });
    const data = await res.json();
    if (!res.ok) {
        alert(data.error || "Unable to load submission");
        return;
    }
    const sub = data.submission;
    codeContent.textContent = `// ${sub.name} — Problem ${sub.problem_id}\n// Language: ${sub.language}\n// Score: ${sub.passed_tests}/${sub.total_tests}\n\n${sub.code}`;
}

async function controlTimer(action) {
    const durationVal = parseInt(timerInput.value, 10);
    const headers = {"Content-Type": "application/json"};
    if (hostToken) headers["X-Host-Token"] = hostToken;
    const res = await fetch("/api/host/timer", {
        method: "POST",
        headers,
        credentials: "include",
        body: JSON.stringify({action, duration_seconds: durationVal, token: hostToken})
    });
    const data = await res.json();
    if (!res.ok) {
        alert(data.error || "Timer action failed");
        return;
    }
    if (data.timer) renderTimer(data.timer);
}

async function fetchTimer() {
    const res = await fetch("/api/timer", {credentials: "include"});
    const data = await res.json();
    if (data.timer) renderTimer(data.timer);
}

function stopHostTimerTick() {
    if (hostTimerTick) {
        clearInterval(hostTimerTick);
        hostTimerTick = null;
    }
}

function startHostTimerTick() {
    stopHostTimerTick();
    if (hostTimerState.status === "running") {
        hostTimerTick = setInterval(renderTimerState, 1000);
    }
}

function hostRemainingSeconds() {
    if (!hostTimerState) return 0;
    if (hostTimerState.status !== "running") return hostTimerState.remaining || 0;
    const elapsed = Math.floor((Date.now() - hostTimerSync) / 1000);
    return Math.max(0, (hostTimerState.remaining || 0) - elapsed);
}

function renderTimerState() {
    let status = hostTimerState.status || "stopped";
    let remaining = hostRemainingSeconds();
    if (status === "running" && remaining <= 0) {
        status = "stopped";
        hostTimerState = {status, remaining: 0};
        stopHostTimerTick();
        remaining = 0;
    }
    timerDisplay.textContent = `${status} (${remaining}s)`;
}

function renderTimer(timer) {
    if (!timer) return;
    hostTimerState = timer;
    hostTimerSync = Date.now();
    renderTimerState();
    startHostTimerTick();
}

async function resetScores() {
    if (!confirm("Reset all submissions and scores?")) return;
    const res = await fetch("/api/host/reset", {
        method: "POST",
        credentials: "include",
        headers: hostToken ? {"X-Host-Token": hostToken} : {}
    });
    const data = await res.json();
    if (!res.ok) {
        alert(data.error || "Reset failed");
    } else {
        await fetchLeaderboard();
        submissionList.innerHTML = "";
    }
}

function init() {
    connectSocket();
    loginBtn.addEventListener("click", loginHost);
    timerStartBtn.addEventListener("click", () => controlTimer("start"));
    timerPauseBtn.addEventListener("click", () => controlTimer("pause"));
    timerStopBtn.addEventListener("click", () => controlTimer("stop"));
    resetBtn.addEventListener("click", resetScores);
    setInterval(fetchTimer, 5000);
}

init();
