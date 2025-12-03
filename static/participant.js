/*
MIT License

Copyright (c) 2025 Jonathan St-Georges

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

let editor;
let problems = [];
let currentProblemId = null;
let currentProblemData = null;
let socket;
const statusIndicator = document.getElementById("statusIndicator");
const timerIndicator = document.getElementById("timerIndicator");
const problemListEl = document.getElementById("problemList");
const problemTitleEl = document.getElementById("problemTitle");
const problemIdEl = document.getElementById("problemId");
const problemDescEl = document.getElementById("problemDescription");
const problemInputEl = document.getElementById("problemInput");
const problemOutputEl = document.getElementById("problemOutput");
const problemConstraintsEl = document.getElementById("problemConstraints");
const problemMethodEl = document.getElementById("problemMethod");
const problemSampleEl = document.getElementById("problemSample");
const submitBtn = document.getElementById("submitBtn");
const nameInput = document.getElementById("nameInput");
const languageSelect = document.getElementById("languageSelect");
const saveProfileBtn = document.getElementById("saveProfile");
const resultSummary = document.getElementById("resultSummary");
const resultDetails = document.getElementById("resultDetails");
let currentTimer = {status: "stopped", remaining: 0};
let timerLastSync = Date.now();
let timerTickInterval = null;

const FALLBACK_TEMPLATES = {
    python: "def solution():\n    pass\n",
    java: "import java.util.*;\n\npublic class Main {\n    // Implement the required method below\n}\n",
    cpp: "// Implement the required function below\n",
};

function initSocket(userId) {
    if (socket) {
        socket.disconnect();
    }
    socket = io();
    socket.on("connect", () => {
        statusIndicator.textContent = "Connected";
        statusIndicator.classList.add("badge", "success");
        if (userId) {
            socket.emit("register_user", {user_id: userId});
        }
    });
    socket.on("disconnect", () => {
        statusIndicator.textContent = "Disconnected";
        statusIndicator.classList.remove("success");
    });

    socket.on("submission_scored", (payload) => {
        if (payload && payload.user_id === getUserId()) {
            resultSummary.innerHTML = `Latest: ${payload.passed_tests}/${payload.total_tests} tests`;
        }
    });
    socket.on("timer_update", (payload) => {
        if (payload && payload.timer) {
            applyTimerState(payload.timer);
        }
    });
}

function getUserId() {
    return localStorage.getItem("cc_user_id");
}

function loadPersistentState() {
    const savedName = localStorage.getItem("cc_name");
    const savedLang = localStorage.getItem("cc_language");
    const savedProblem = localStorage.getItem("cc_problem");

    if (savedName) nameInput.value = savedName;
    if (savedLang) languageSelect.value = savedLang;
    if (savedProblem) currentProblemId = parseInt(savedProblem, 10);
}

async function fetchProblems() {
    const res = await fetch("/api/problems");
    const data = await res.json();
    problems = data.problems || [];
    if (!currentProblemId && problems.length) {
        currentProblemId = problems[0].id;
    }
    renderProblemList();
    if (currentProblemId) {
        selectProblem(currentProblemId);
    }
}

function renderProblemList() {
    problemListEl.innerHTML = "";
    problems.forEach((p) => {
        const li = document.createElement("li");
        li.textContent = `${p.id}. ${p.title}`;
        if (p.id === currentProblemId) li.classList.add("active");
        li.addEventListener("click", () => selectProblem(p.id));
        problemListEl.appendChild(li);
    });
}

function buildExampleLines(sampleTests) {
    if (!Array.isArray(sampleTests) || sampleTests.length === 0) return "";
    const arrow = "\u2192";
    return sampleTests.slice(0, 3).map((sample) => {
        const inputInline = (sample.input || "").trim().replace(/\s+/g, " ");
        const outputInline = (sample.output || "").trim().replace(/\s+/g, " ");
        return `${inputInline} ${arrow} ${outputInline}`;
    }).join("\n");
}

function formatProblemDescription(problem) {
    const desc = problem.description || "";
    const examples = buildExampleLines(problem.sample_tests);
    if (!examples) return desc;
    return `${desc}\n\nExamples:\n${examples}`;
}

async function selectProblem(problemId) {
    currentProblemId = problemId;
    localStorage.setItem("cc_problem", problemId);
    renderProblemList();
    const res = await fetch(`/api/problem/${problemId}`);
    if (!res.ok) return;
    const data = await res.json();
    const problem = data.problem;
    currentProblemData = problem;
    problemIdEl.textContent = `Problem ${problem.id}`;
    problemTitleEl.textContent = problem.title;
    problemDescEl.textContent = formatProblemDescription(problem);
    problemInputEl.textContent = problem.input_format;
    problemOutputEl.textContent = problem.output_format;
    problemConstraintsEl.textContent = problem.constraints;
    renderMethodSignatures(problem);
    if (problem.sample_tests && problem.sample_tests.length > 0) {
        const sample = problem.sample_tests[0];
        problemSampleEl.textContent = `Input:\n${sample.input}\n\nOutput:\n${sample.output}`;
    } else {
        problemSampleEl.textContent = "";
    }
    await hydrateEditor();
}

function stopTimerTick() {
    if (timerTickInterval) {
        clearInterval(timerTickInterval);
        timerTickInterval = null;
    }
}

function startTimerTick() {
    stopTimerTick();
    if (currentTimer.status === "running") {
        timerTickInterval = setInterval(renderTimerState, 1000);
    }
}

function computeRemainingSeconds() {
    if (!currentTimer) return 0;
    if (currentTimer.status !== "running") return currentTimer.remaining || 0;
    const elapsed = Math.floor((Date.now() - timerLastSync) / 1000);
    return Math.max(0, (currentTimer.remaining || 0) - elapsed);
}

function applyTimerState(timer) {
    currentTimer = timer || {status: "stopped", remaining: 0};
    timerLastSync = Date.now();
    renderTimerState();
    startTimerTick();
}

async function fetchTimer() {
    try {
        const res = await fetch("/api/timer");
        const data = await res.json();
        if (data.timer) applyTimerState(data.timer);
    } catch (e) {
        // ignore
    }
}

function renderTimerState() {
    let status = currentTimer.status || "stopped";
    let remaining = computeRemainingSeconds();
    if (status === "running" && remaining <= 0) {
        status = "stopped";
        currentTimer = {status, remaining: 0};
        stopTimerTick();
        remaining = 0;
    }
    timerIndicator.textContent = `Timer: ${status} (${remaining}s)`;
    const allow = status === "running" && remaining > 0;
    if (editor) {
        editor.updateOptions({readOnly: !allow});
    }
    submitBtn.disabled = !allow;
}

function renderMethodSignatures(problem) {
    const sigs = problem.method_signatures;
    if (sigs && typeof sigs === "object") {
        const parts = [];
        if (sigs.java) parts.push(`Java: ${sigs.java}`);
        if (sigs.python) parts.push(`Python: ${sigs.python}`);
        if (sigs.cpp) parts.push(`C++: ${sigs.cpp}`);
        problemMethodEl.textContent = parts.join("\n") || "N/A";
        return;
    }
    if (problem.method_signature) {
        problemMethodEl.textContent = `Java: ${problem.method_signature}`;
    } else {
        problemMethodEl.textContent = "N/A";
    }
}

async function hydrateEditor() {
    const lang = languageSelect.value;
    const key = codeKey(currentProblemId, lang);
    const saved = localStorage.getItem(key);
    if (saved) {
        setEditorValue(saved);
        return;
    }
    const userId = getUserId();
    if (userId && currentProblemId) {
        try {
            const res = await fetch(`/api/user/${userId}/last_submission?problem_id=${currentProblemId}`);
            const data = await res.json();
            if (data.submission && data.submission.code) {
                setEditorValue(data.submission.code);
                return;
            }
        } catch (e) {
            // ignore and fall back
        }
    }
    setEditorValue(buildTemplate(lang));
}

function codeKey(problemId, lang) {
    return `code_${problemId}_${lang}`;
}

function setEditorValue(val) {
    if (editor) {
        editor.setValue(val);
    }
}

function buildTemplate(lang) {
    if (currentProblemData && currentProblemData.method_signatures) {
        const sig = currentProblemData.method_signatures[lang] || null;
        if (sig) {
            if (lang === "python") {
                return `${sig}:\n    pass\n`;
            }
            if (lang === "java") {
                return `import java.util.*;\n\npublic class Main {\n    ${sig} {\n        // TODO\n    }\n}\n`;
            }
            if (lang === "cpp") {
                return `${sig} {\n    // TODO\n}\n`;
            }
        }
    }
    return FALLBACK_TEMPLATES[lang] || "";
}

async function registerUser() {
    const name = nameInput.value.trim();
    const language = languageSelect.value;
    if (!name) {
        alert("Enter your name first.");
        return;
    }
    const res = await fetch("/api/register", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name, language})
    });
    const data = await res.json();
    if (res.ok) {
        const user = data.user;
        localStorage.setItem("cc_user_id", user.id);
        localStorage.setItem("cc_name", user.name);
        localStorage.setItem("cc_language", language);
        initSocket(user.id);
        resultSummary.textContent = "Profile saved.";
    } else {
        alert(data.error || "Unable to register");
    }
}

async function submitSolution() {
    const userId = getUserId();
    if (!userId) {
        alert("Save your profile first.");
        return;
    }
    if (!currentProblemId) {
        alert("Pick a problem.");
        return;
    }
    const code = editor ? editor.getValue() : "";
    if (!code.trim()) {
        alert("Write some code before submitting.");
        return;
    }

    submitBtn.disabled = true;
    resultSummary.innerHTML = `<span class="badge pending">Running...</span>`;

    try {
        const res = await fetch("/api/submit", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                user_id: userId,
                problem_id: currentProblemId,
                language: languageSelect.value,
                code
            })
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || "Submission failed");
        }
        localStorage.setItem(codeKey(currentProblemId, languageSelect.value), code);
        renderResults(data.result);
    } catch (err) {
        resultSummary.innerHTML = `<span class="badge danger">Error</span> ${err.message}`;
    } finally {
        submitBtn.disabled = currentTimer.status !== "running";
    }
}

function renderResults(result) {
    if (!result) return;
    const passed = result.passed || 0;
    const total = result.total || 0;
    const badgeClass = passed === total ? "success" : "danger";
    resultSummary.innerHTML = `<span class="badge ${badgeClass}">${passed}/${total} tests</span>`;
    resultDetails.innerHTML = "";

    (result.details || []).forEach((t, idx) => {
        const card = document.createElement("div");
        card.className = `result-card ${t.passed ? "good" : "bad"}`;
        const status = t.passed ? "Passed" : "Failed";
        const extra =
            t.error || t.timeout || t.compile_error
                ? `<div><small>Detail</small><pre>${t.error || (t.timeout ? "Timed out" : t.compile_error ? "Compile error" : "")}</pre></div>`
                : "";
        card.innerHTML = `<div><strong>Test ${idx + 1}</strong> — ${status}</div>${extra}`;
        resultDetails.appendChild(card);
    });
}

function initEditor() {
    require.config({paths: {vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs"}});
    require(["vs/editor/editor.main"], () => {
        editor = monaco.editor.create(document.getElementById("editor"), {
            value: "",
            language: "python",
            theme: "vs-dark",
            automaticLayout: true,
            minimap: {enabled: false},
        });
        editor.onDidChangeModelContent(() => {
            if (currentProblemId) {
                const key = codeKey(currentProblemId, languageSelect.value);
                localStorage.setItem(key, editor.getValue());
            }
        });
        applyLanguage();
        applyTimerState(currentTimer);
        if (currentProblemId) {
            hydrateEditor();
        }
    });
}

function applyLanguage() {
    const lang = languageSelect.value;
    const monacoLang = lang === "cpp" ? "cpp" : lang;
    if (editor) {
        monaco.editor.setModelLanguage(editor.getModel(), monacoLang);
    }
}

function registerEventHandlers() {
    saveProfileBtn.addEventListener("click", registerUser);
    submitBtn.addEventListener("click", submitSolution);
    languageSelect.addEventListener("change", () => {
        localStorage.setItem("cc_language", languageSelect.value);
        applyLanguage();
        hydrateEditor();
    });
}

(function bootstrap() {
    loadPersistentState();
    registerEventHandlers();
    applyTimerState(currentTimer);
    fetchTimer();
    setInterval(fetchTimer, 5000);
    fetchProblems();
    initEditor();
    initSocket(getUserId());
})();
