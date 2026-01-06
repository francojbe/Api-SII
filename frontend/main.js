import './style.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001';
const API_KEY = 'mi_llave_secreta_123';

// Selectores UI
const scoutBtn = document.getElementById('scout-btn');
const closeBtn = document.getElementById('close-session-btn');
const loader = document.getElementById('loader');
const resultsDisplay = document.getElementById('results-display');
const chatContainer = document.getElementById('chat-container');
const chatInput = document.getElementById('chat-input');
const chatSendBtn = document.getElementById('chat-send-btn');
const f29Screenshot = document.getElementById('f29-screenshot');

// Estado interno del chat
let chatHistory = [];

const fmt = (val) => new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' }).format(val);

function addChatBubble(text, role) {
    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${role}`;
    // Reemplazar saltos de línea con <br>
    bubble.innerHTML = text.replace(/\n/g, '<br>');
    chatContainer.appendChild(bubble);

    // Auto-scroll
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

async function startScouting() {
    const rut = document.getElementById('rut').value;
    const clave = document.getElementById('clave').value;
    const periodVal = document.getElementById('periodo').value.split('-');

    loader.style.display = 'flex';
    resultsDisplay.style.display = 'none';
    scoutBtn.disabled = true;

    // Limpiar chat anterior
    chatContainer.innerHTML = '';
    chatHistory = [];

    try {
        const response = await fetch(`${API_BASE}/sii/f29-scouting`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
            body: JSON.stringify({
                rut,
                clave,
                anio: periodVal[1],
                mes: periodVal[0],
                es_propuesta: true
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            displayResults(data);
        } else {
            alert('Error: ' + (data.detail || 'Fallo en la conexión con el SII'));
        }
    } catch (err) {
        console.error(err);
        alert('Error crítico al conectar con el servidor.');
    } finally {
        loader.style.display = 'none';
        scoutBtn.disabled = false;
    }
}

function displayResults(data) {
    const s = data.scouting.propuesta;

    if (s && s['538']) document.getElementById('val-538').textContent = fmt(s['538']);
    if (s && s['537']) document.getElementById('val-537').textContent = fmt(s['537']);
    if (s && s['504']) document.getElementById('val-504').textContent = fmt(s['504']);

    // Mostrar mensaje inicial del Bot
    if (data.analisis_ia) {
        addChatBubble(data.analisis_ia, 'assistant');
        // Guardar en historial
        chatHistory.push({ role: "assistant", content: data.analisis_ia });
    }

    resultsDisplay.style.display = 'flex';
    document.getElementById('status-text').textContent = 'Activa';
    document.getElementById('status-text').style.color = '#34d399';

    // Habilitar chat
    chatInput.disabled = false;
    chatSendBtn.disabled = false;
}

async function sendChatMessage() {
    const message = chatInput.value.trim();
    if (!message) return;

    const rut = document.getElementById('rut').value;

    // 1. Mostrar mensaje del usuario
    addChatBubble(message, 'user');
    chatInput.value = '';
    chatInput.disabled = true;
    chatSendBtn.disabled = true;

    try {
        // 2. Enviar a backend con historial
        const response = await fetch(`${API_BASE}/sii/chat-interaction`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
            body: JSON.stringify({
                rut,
                message,
                history: chatHistory
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            const reply = data.reply;
            addChatBubble(reply, 'assistant');

            // Actualizar historial local
            chatHistory.push({ role: "user", content: message });
            chatHistory.push({ role: "assistant", content: reply });
        } else {
            addChatBubble("⚠️ Hubo un error al procesar tu mensaje.", 'assistant');
        }

    } catch (err) {
        console.error(err);
        addChatBubble("⚠️ Error de conexión con el Asistente.", 'assistant');
    } finally {
        chatInput.disabled = false;
        chatSendBtn.disabled = false;
        chatInput.focus();
    }
}

async function closeSession() {
    const rut = document.getElementById('rut').value;
    try {
        await fetch(`${API_BASE}/sii/session-close`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'x-api-key': API_KEY },
            body: JSON.stringify({ rut, clave: "" })
        });
        alert('Sesión cerrada correctamente.');
        location.reload();
    } catch (err) {
        alert('Error al cerrar la sesión.');
    }
}

// Event Listeners
if (scoutBtn) scoutBtn.addEventListener('click', startScouting);
if (closeBtn) closeBtn.addEventListener('click', closeSession);
if (chatSendBtn) chatSendBtn.addEventListener('click', sendChatMessage);

// Enviar con Enter
if (chatInput) {
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChatMessage();
    });
}

const logoEl = document.getElementById('app-logo');
if (logoEl) logoEl.src = "/logo.png";
