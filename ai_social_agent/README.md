# 🤖 SocialCommander AI — Multi-Platform AI Master Agent

Control all your social media, messaging channels, newsletters, and emails through a single **Telegram Bot** powered by an AI Agent.

---

## 🌟 Supported Channels

| Platform | Actions Supported | Status |
|:---|:---|:---:|
| **Telegram** | Bot interface, inline approval buttons, photo uploads | 🟢 Ready |
| **Facebook Pages** | Text posts, photo posts with captions, analytics | 🟢 Configured |
| **Instagram Business** | Photos, captions, hashtags, recent media & comments | 🟢 Configured |
| **WhatsApp Cloud** | Direct messages, media attachments, template notifications | 🟡 Add Phone ID |
| **Gmail** | Read unread, search threads, draft emails, send emails | 🟡 Add App Password |
| **Substack** | Newsletter drafts, Substack Notes, public post retrieval | 🟡 Add Subdomain |
| **n8n Automation** | Trigger workflows, check executions, image synthesis | 🟢 Configured |

---

## 🚀 Quick Start

### 1. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 2. Verify Connections & Run Diagnostics
```powershell
python test_connectors.py
```

### 3. Start the Telegram Bot
```powershell
python main.py
```

---

## 🔑 Platform Setup Guide

### 1. Facebook & Instagram
Already pre-configured with your Meta Graph API tokens and Page/Account IDs in `.env`.
To update tokens in the future:
- `FACEBOOK_PAGE_ID` & `FACEBOOK_ACCESS_TOKEN`
- `INSTAGRAM_ACCOUNT_ID` & `INSTAGRAM_ACCESS_TOKEN`

### 2. WhatsApp Cloud API
1. Open [Meta for Developers](https://developers.facebook.com/) -> Select your App.
2. Under **WhatsApp** -> **API Setup**:
   - Copy your **Phone number ID** into `WHATSAPP_PHONE_NUMBER_ID`.
   - Copy your **Temporary / Permanent Access Token** into `WHATSAPP_ACCESS_TOKEN`.

### 3. Gmail (App Password - Zero Setup Hassle)
1. Go to your [Google Account Security](https://myaccount.google.com/security).
2. Enable **2-Step Verification** if not already enabled.
3. Search for **App passwords** (or go to `myaccount.google.com/apppasswords`).
4. Enter an app name (e.g. `SocialCommander`) and click **Create**.
5. Copy the 16-character password into `.env`:
   ```env
   GMAIL_EMAIL=yourname@gmail.com
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   ```

### 4. Substack
1. In `.env`, set your publication subdomain:
   ```env
   SUBSTACK_SUBDOMAIN=yourpublication
   ```
2. To allow the bot to create drafts and post notes:
   - Open your Substack publication in Chrome/Edge.
   - Press `F12` -> Go to **Application** tab -> **Cookies** -> `https://substack.com`.
   - Copy the value of the `connect.sid` cookie into `.env`:
     ```env
     SUBSTACK_COOKIE_SID=s%3A...
     ```

---

## 💬 How To Interact via Telegram

### Social Media Publishing
- *"Waxaad Facebook iyo Instagram ku qortaa qoraal ku saabsan faa'iidooyinka AI iyo sida dhalinyarada Soomaaliyeed uga faa'iideysan karaan."*
- Attach a photo and send: *"Publish this photo to Instagram and Facebook with an inspiring motivation caption."*

### Email Management
- *"Check my unread emails from today."*
- *"Send an email to john@example.com with subject 'Project Update' saying the initial deployment is finished."*
- *"Draft an email to the scholarship board asking about application status."*

### WhatsApp Messaging
- *"Send a WhatsApp message to +252615000000 saying the meeting is confirmed for 4 PM."*

### Substack Publishing
- *"Draft a newsletter article for my Substack comparing deep learning models with code examples."*
- *"Publish a Substack Note sharing my thought on autonomous AI agents."*

---

## 🛡️ Safety & Human-in-the-Loop Confirmation
Every destructive or public action (publishing to Facebook/IG, sending an email, sending a WhatsApp message, or creating a Substack draft) triggers an **Interactive Telegram Preview**:
- Tap `[🚀 Confirm & Publish]` to execute immediately.
- Tap `[✏️ Revise / Edit]` to instruct the AI on changes.
- Tap `[❌ Cancel]` to abort.
