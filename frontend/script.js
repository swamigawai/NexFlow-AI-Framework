// --- Auth Logic ---
function handleLogin(e) {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    const spinner = document.getElementById('login-spinner');

    // UI Loading state
    btn.querySelector('span').textContent = 'Authenticating...';
    spinner.classList.remove('hidden');

    setTimeout(() => {
        document.getElementById('auth-screen').classList.add('hidden');
        document.getElementById('app-screen').classList.remove('hidden');

        // Sync name over
        const email = document.getElementById('email').value;
        const namePart = email.split('@')[0].replace('.', ' ');
        const finalName = namePart.charAt(0).toUpperCase() + namePart.slice(1);

        document.getElementById('nav-user-name').textContent = finalName;
        document.getElementById('prof-name').value = finalName;
        document.getElementById('prof-email').value = email;

        const avatarUrl = `https://ui-avatars.com/api/?name=${encodeURIComponent(finalName)}&background=6558F5&color=fff`;
        document.getElementById('nav-avatar').src = avatarUrl;
        document.getElementById('main-avatar').src = avatarUrl;

    }, 1500);
}

function handleLogout() {
    document.getElementById('app-screen').classList.add('hidden');
    document.getElementById('auth-screen').classList.remove('hidden');

    // Reset login button UI
    const btn = document.getElementById('login-btn');
    btn.querySelector('span').textContent = 'Sign In';
    document.getElementById('login-spinner').classList.add('hidden');
}

// --- Navigation Logic ---
const titles = {
    'chat': 'AI Support Agent',
    'csv': 'Data Pipeline',
    'profile': 'Profile Settings'
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach(sec => sec.classList.remove('active-pane'));
    document.querySelectorAll('.menu-btn').forEach(btn => btn.classList.remove('active'));

    document.getElementById(tabId).classList.add('active-pane');

    // Change active UI state in sidebar
    document.querySelectorAll(`[onclick="switchTab('${tabId}')"]`).forEach(el => el.classList.add('active'));

    // Update Header title
    document.getElementById('current-page-title').textContent = titles[tabId];
}

// --- Terminal Log Streamer ---
function streamLogs(logsArray) {
    if (!logsArray || logsArray.length === 0) return;
    const term = document.getElementById('term-logs');

    // Clear out default boot text if present
    if (term.textContent.includes('SYSTEM BOOT')) {
        term.innerHTML = '';
    }

    let i = 0;
    function printNext() {
        if (i < logsArray.length) {
            const span = document.createElement('span');
            span.className = 'log-fade';
            span.textContent = `> ${logsArray[i]}`;
            term.appendChild(span);
            term.scrollTop = term.scrollHeight;
            i++;
            setTimeout(printNext, 300); // 300ms delay between prints to look like processing
        }
    }
    printNext();
}

// --- Chat / Briefing Logic ---
const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const briefStatus = document.getElementById('brief-status');
const briefEmpty = document.getElementById('brief-empty');
const briefLoader = document.getElementById('brief-loader');
const briefData = document.getElementById('brief-data');

let messages = [
    { role: "assistant", content: "Welcome back! I'm your Level 1 AI assistant. Type a message, or simulate frustration to trigger a human handoff." }
];

function handleKey(e) { if (e.key === "Enter") sendMessage(); }

function appendMessage(role, text) {
    const div = document.createElement('div');
    div.className = `chat-bubble ${role === 'user' ? 'user' : 'ai'}`;

    // Parse markdown if it's the AI responding
    if (role === 'ai') {
        div.innerHTML = marked.parse(text);

        // Remove bottom margin from last paragraph so bubble padding looks right
        const lastP = div.querySelector('p:last-child');
        if (lastP) lastP.style.marginBottom = '0';
    } else {
        div.textContent = text;
    }

    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    appendMessage('user', text);
    messages.push({ role: 'user', content: text });
    chatInput.value = '';

    const frustration = ["human", "agent", "useless", "stuck", "frustrated", "can't find", "support", "angry"];

    if (frustration.some(kw => text.toLowerCase().includes(kw))) {
        appendMessage('ai', "I understand. I am escalating this to our human workforce right now.");
        messages.push({ role: 'assistant', content: "Transferring..." });

        briefEmpty.classList.add('hidden');
        briefLoader.classList.remove('hidden');
        briefData.classList.add('hidden');

        briefStatus.classList.remove('hidden');
        briefStatus.textContent = "Processing...";

        try {
            const res = await fetch('/api/brief', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages })
            });
            const brief = await res.json();

            document.getElementById('out-intent').textContent = brief.intent || "Unknown";
            document.getElementById('out-blocker').textContent = brief.blocker || "Unknown";

            if (brief.logs) streamLogs(brief.logs);

            briefLoader.classList.add('hidden');
            briefData.classList.remove('hidden');
            briefStatus.textContent = "Action Required";
            briefStatus.style.background = "#FEF2F2";
            briefStatus.style.color = "#DC2626";

        } catch (err) {
            console.error(err);
            briefLoader.innerHTML = `<p style="color:#DC2626">Error: Backend Connection Failed.</p>`;
        }
    } else {
        // Add a temporary typing indicator
        const typingId = "typing-" + Date.now();
        const typingDiv = document.createElement('div');
        typingDiv.className = 'chat-bubble ai';
        typingDiv.id = typingId;
        typingDiv.innerHTML = '<i class="fas fa-ellipsis-h fa-fade"></i>';
        chatHistory.appendChild(typingDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages })
            });
            const data = await res.json();

            // Remove typing indicator
            document.getElementById(typingId).remove();

            appendMessage('ai', data.reply);
            messages.push({ role: 'assistant', content: data.reply });

            if (data.logs) streamLogs(data.logs);
        } catch (err) {
            console.error(err);
            document.getElementById(typingId).remove();
            appendMessage('ai', "Error connecting to AI service. Please try again.");
        }
    }
}

// --- CSV Logic ---
document.getElementById('csv-file').addEventListener('change', function (e) {
    if (this.files[0]) {
        document.getElementById('file-name').textContent = this.files[0].name + ` (${(this.files[0].size / 1024).toFixed(1)} KB)`;
        document.getElementById('file-name').style.color = "var(--acc-purple)";
        document.getElementById('file-name').style.fontWeight = "600";
    }
});

async function processCSV() {
    const fileInput = document.getElementById('csv-file');
    const resultDiv = document.getElementById('csv-result');
    const btnIcon = document.querySelector('.execute-btn i');

    if (!fileInput.files[0]) return alert("Please drag & drop or upload a CSV file first.");

    const ops = Array.from(document.querySelectorAll('.csv-op:checked')).map(cb => cb.value).join(',');
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fd.append('operations', ops);

    resultDiv.classList.remove('hidden');
    resultDiv.style.background = "#F8FAFC";
    resultDiv.style.color = "#64748B";
    resultDiv.innerHTML = '<div class="smooth-spinner"></div> Executing Data Pipeline...';
    btnIcon.className = "fas fa-spinner fa-spin";

    try {
        const res = await fetch('/api/process-csv', { method: 'POST', body: fd });
        const data = await res.json();

        if (data.logs) streamLogs(data.logs);

        if (data.status === 'success') {
            resultDiv.style.background = "#DCFCE7";
            resultDiv.style.color = "#166534";
            resultDiv.innerHTML = `<strong>✅ ${data.message}</strong><br>Dataset saved locally: <em>${data.output_path}</em>`;
        } else throw new Error(data.message);
    } catch (err) {
        resultDiv.style.background = "#FEF2F2";
        resultDiv.style.color = "#991B1B";
        resultDiv.innerHTML = `<strong>❌ Pipeline Error:</strong> ${err.message}`;
    } finally {
        btnIcon.className = "fas fa-play";
    }
}

// --- RAG Knowledge Base Logic ---
document.getElementById('rag-file').addEventListener('change', function (e) {
    if (this.files[0]) {
        document.getElementById('rag-file-name').textContent = this.files[0].name + ` (${(this.files[0].size / 1024).toFixed(1)} KB)`;
        document.getElementById('rag-file-name').style.color = "var(--acc-purple)";
        document.getElementById('rag-file-name').style.fontWeight = "600";
    }
});

async function processRAG() {
    const fileInput = document.getElementById('rag-file');
    const resultDiv = document.getElementById('rag-result');
    const btnIcon = document.querySelector('#rag-btn i');

    if (!fileInput.files[0]) return alert("Please upload a PDF or TXT file first.");

    const fd = new FormData();
    fd.append('file', fileInput.files[0]);

    resultDiv.classList.remove('hidden');
    resultDiv.style.background = "#F8FAFC";
    resultDiv.style.color = "#64748B";
    resultDiv.innerHTML = '<div class="smooth-spinner"></div> Embedding Knowledge into Vector DB...';
    btnIcon.className = "fas fa-spinner fa-spin";

    try {
        const res = await fetch('/api/rag-upload', { method: 'POST', body: fd });
        const data = await res.json();

        if (data.logs) streamLogs(data.logs);

        if (data.status === 'success') {
            resultDiv.style.background = "#DCFCE7";
            resultDiv.style.color = "#166534";
            resultDiv.innerHTML = `<strong>✅ ${data.message}</strong><br>LLaMA 3.2 is now trained on this document!`;
        } else throw new Error(data.message);
    } catch (err) {
        resultDiv.style.background = "#FEF2F2";
        resultDiv.style.color = "#991B1B";
        resultDiv.innerHTML = `<strong>❌ Vectorization Error:</strong> ${err.message}`;
    } finally {
        btnIcon.className = "fas fa-project-diagram";
    }
}

// --- Profile Logic ---
function saveProfile(e) {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';

    setTimeout(() => {
        btn.innerHTML = '<i class="fas fa-check"></i> Saved successfully';
        btn.style.background = "#10B981";

        // Sync names back to Header
        const updatedName = document.getElementById('prof-name').value;
        document.getElementById('nav-user-name').textContent = updatedName;

        setTimeout(() => {
            btn.innerHTML = 'Save Changes';
            btn.style.background = "var(--acc-purple)";
        }, 3000);
    }, 800);
}
