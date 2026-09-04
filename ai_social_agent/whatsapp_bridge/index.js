const express = require('express');
const pino = require('pino');
const qrcodeTerminal = require('qrcode-terminal');
const QRCode = require('qrcode');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());

const PORT = process.env.PORT || 3001;
const AUTH_DIR = path.join(__dirname, 'auth_info_baileys');

let sock = null;
let currentQR = null;
let currentQRDataUrl = null;
let isConnected = false;
let connectedUser = null;

let makeWASocket, DisconnectReason, useMultiFileAuthState, fetchLatestBaileysVersion;

async function loadBaileys() {
    const b = await import('@whiskeysockets/baileys');
    makeWASocket = b.default || b.makeWASocket;
    DisconnectReason = b.DisconnectReason;
    useMultiFileAuthState = b.useMultiFileAuthState;
    fetchLatestBaileysVersion = b.fetchLatestBaileysVersion;
}

async function connectToWhatsApp() {
    if (!makeWASocket) {
        await loadBaileys();
    }
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version, isLatest } = await fetchLatestBaileysVersion();
    
    console.log(`[WhatsApp Bridge] Starting with Baileys version: ${version.join('.')} (isLatest: ${isLatest})`);

    sock = makeWASocket({
        version,
        auth: state,
        logger: pino({ level: 'silent' }),
        printQRInTerminal: false,
        browser: ['SocialCommander AI', 'Chrome', '1.0.0']
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            currentQR = qr;
            console.log('\n============================================================');
            console.log('       WHATSAPP LINKED DEVICE QR CODE');
            console.log('  Open WhatsApp on phone > Linked Devices > Link a Device');
            console.log('============================================================\n');
            qrcodeTerminal.generate(qr, { small: true });
            console.log(`\nOr view QR in browser at: http://localhost:${PORT}/qr\n`);
            
            try {
                currentQRDataUrl = await QRCode.toDataURL(qr);
                await QRCode.toFile(path.join(__dirname, 'qr.png'), qr);
            } catch (err) {
                console.error('[WhatsApp Bridge] Error generating QR image:', err);
            }
        }

        if (connection === 'close') {
            isConnected = false;
            connectedUser = null;
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log(`[WhatsApp Bridge] Connection closed (code: ${statusCode}). Reconnecting: ${shouldReconnect}`);

            if (shouldReconnect) {
                setTimeout(connectToWhatsApp, 3000);
            } else {
                console.log('[WhatsApp Bridge] Logged out. Delete auth_info_baileys and restart to re-link.');
            }
        } else if (connection === 'open') {
            isConnected = true;
            currentQR = null;
            currentQRDataUrl = null;
            connectedUser = sock.user;
            const phoneNumber = sock.user?.id ? sock.user.id.split(':')[0] : 'Unknown';
            console.log('\n============================================================');
            console.log(`✅ [WhatsApp Bridge] Connected successfully as: +${phoneNumber}`);
            console.log('============================================================\n');
        }
    });
}

// --- API Endpoints ---

app.get('/status', (req, res) => {
    res.json({
        success: true,
        connected: isConnected,
        user: connectedUser ? {
            id: connectedUser.id,
            name: connectedUser.name || '',
            phone: connectedUser.id ? connectedUser.id.split(':')[0] : ''
        } : null,
        has_qr: !!currentQR,
        qr_url: currentQR ? `http://localhost:${PORT}/qr` : null
    });
});

app.get('/qr', (req, res) => {
    if (isConnected) {
        return res.send(`
            <html>
                <head><title>WhatsApp Bridge - Connected</title></head>
                <body style="font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background: #0f172a; color: #f8fafc;">
                    <h1 style="color: #22c55e;">✅ WhatsApp is Connected!</h1>
                    <p>Connected Account: <strong>+${connectedUser?.id?.split(':')[0] || ''}</strong></p>
                    <p style="color: #94a3b8;">You can close this tab. The bot is ready to send messages.</p>
                </body>
            </html>
        `);
    }

    if (!currentQRDataUrl) {
        return res.send(`
            <html>
                <head>
                    <title>WhatsApp Bridge - Generating QR</title>
                    <meta http-equiv="refresh" content="3">
                </head>
                <body style="font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background: #0f172a; color: #f8fafc;">
                    <h2>Generating WhatsApp QR Code...</h2>
                    <p style="color: #94a3b8;">Please wait, auto-refreshing in 3 seconds...</p>
                </body>
            </html>
        `);
    }

    res.send(`
        <html>
            <head>
                <title>Link WhatsApp - SocialCommander AI</title>
                <meta http-equiv="refresh" content="15">
            </head>
            <body style="font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; background: #0f172a; color: #f8fafc; margin: 0; padding: 20px;">
                <div style="background: #1e293b; padding: 30px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); text-align: center; max-width: 420px;">
                    <h2 style="margin-top: 0; color: #38bdf8;">📱 Link Your WhatsApp</h2>
                    <p style="color: #94a3b8; font-size: 14px; margin-bottom: 20px;">
                        1. Open WhatsApp on your phone<br>
                        2. Tap <strong>Settings</strong> ➔ <strong>Linked Devices</strong><br>
                        3. Tap <strong>Link a Device</strong> and scan below:
                    </p>
                    <div style="background: white; padding: 15px; border-radius: 12px; display: inline-block;">
                        <img src="${currentQRDataUrl}" width="280" height="280" style="display: block;" />
                    </div>
                    <p style="color: #64748b; font-size: 12px; margin-top: 15px;">This page auto-refreshes automatically.</p>
                </div>
            </body>
        </html>
    `);
});

app.post('/send-message', async (req, res) => {
    try {
        const { to, message } = req.body;
        if (!to || !message) {
            return res.status(400).json({ success: false, error: 'Missing "to" or "message" in request body.' });
        }

        if (!isConnected || !sock) {
            return res.status(503).json({ success: false, error: 'WhatsApp is not connected. Scan QR code first.' });
        }

        const cleanDigits = to.replace(/\D/g, '');
        const jid = `${cleanDigits}@s.whatsapp.net`;

        const result = await sock.sendMessage(jid, { text: message });
        const messageId = result?.key?.id || 'sent';

        res.json({
            success: true,
            messageId,
            recipient: cleanDigits,
            message: `Message sent to +${cleanDigits}`
        });
    } catch (err) {
        console.error('[WhatsApp Bridge] Error sending message:', err);
        res.status(500).json({ success: false, error: err.message || String(err) });
    }
});

app.post('/send-image', async (req, res) => {
    try {
        const { to, imageUrl, caption } = req.body;
        if (!to || !imageUrl) {
            return res.status(400).json({ success: false, error: 'Missing "to" or "imageUrl" in request body.' });
        }

        if (!isConnected || !sock) {
            return res.status(503).json({ success: false, error: 'WhatsApp is not connected. Scan QR code first.' });
        }

        const cleanDigits = to.replace(/\D/g, '');
        const jid = `${cleanDigits}@s.whatsapp.net`;

        const result = await sock.sendMessage(jid, {
            image: { url: imageUrl },
            caption: caption || ''
        });
        const messageId = result?.key?.id || 'sent';

        res.json({
            success: true,
            messageId,
            recipient: cleanDigits,
            message: `Image sent to +${cleanDigits}`
        });
    } catch (err) {
        console.error('[WhatsApp Bridge] Error sending image:', err);
        res.status(500).json({ success: false, error: err.message || String(err) });
    }
});

app.listen(PORT, '127.0.0.1', () => {
    console.log(`[WhatsApp Bridge] HTTP Server listening on http://127.0.0.1:${PORT}`);
    connectToWhatsApp();
});
