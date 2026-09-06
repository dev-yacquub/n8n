# 🤖 SocialCommander AI — Multi-Platform AI Master Agent
## Multi-Tenant Facebook Page AI Manager & Cross-Platform Commander

Manage your entire **Facebook Page** autonomously through a personal **Telegram Bot** powered by an advanced AI reasoning agent. Every Telegram user can independently connect their own Facebook account, manage pages, respond to customer messages, gather post insights, and publish ad posts or campaigns.

---

## 🌟 Facebook Page Capabilities (Multi-Tenant)

| Feature | Description | Command / Prompt |
|:---|:---|:---:|
| **Independent Multi-Tenant** | Each Telegram user connects their own Facebook tokens and pages independently with zero data leakage. | `/connect`, `/pages` |
| **Dynamic Token Collection** | Automatically validates User or Page Access Tokens via Meta Graph API, discovering all managed pages. | `/connect` |
| **Page Profile & Stats** | Fetches follower counts, page likes, category, ratings, and verification status. | `/start` (Page Profile button) |
| **Post Creation** | Generates engaging, high-converting posts (text, photos, media) with custom hooks and hashtags. | Send text or photo |
| **Ad Publishing (CTA Posts)** | Creates sponsored/ad-style posts with official action buttons (`[Shop Now]`, `[Learn More]`, `[Sign Up]`, `[Contact Us]`). | `/ad` or prompt |
| **Meta Ads Campaigns** | Creates Ad Campaigns in Meta Ad Accounts (`act_...`) with budget and objective controls. | Prompt AI |
| **Inbox Customer Messaging** | Reads unread conversations in the Facebook Messenger Page Inbox and drafts/sends replies to customers. | `/inbox` or prompt |
| **Post Insights & Metrics** | Collects reach, likes, comments, shares, and engagement summaries for recent posts. | `/insights` or prompt |
| **Comment Management** | Fetches comments on posts and drafts/publishes direct replies to user inquiries. | Prompt AI |

---

## 🚀 Quick Start

### 1. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 2. Run Automated Verification Tests
```powershell
python test_multi_tenant.py
```

### 3. Start the Telegram Bot
```powershell
python main.py
```

---

## 🔑 Facebook Connection Guide

Any Telegram user can connect their Facebook Page in 3 easy steps:

1. Send `/connect` to the bot on Telegram.
2. The bot will prompt for your **Facebook Access Token** (Page Access Token or User Access Token).
   - Get your token at: [Meta Graph API Explorer](https://developers.facebook.com/tools/explorer/)
   - Permissions needed: `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`, `pages_messaging`, `pages_read_user_content`.
3. The bot validates the token against the Graph API in real time:
   - If multiple pages are found, an inline menu appears to let you tap the page you want to manage.
   - If one page is found, it is automatically bound and activated!

To switch active pages later, simply type `/pages`.

---

## 💬 How To Interact via Telegram

### Facebook Page Management (English & Somali)
- *"Waxaad Facebook ku qortaa qoraal soo jiidasho leh oo ku saabsan adeegyadayada cusub"*
- *"Check my Facebook inbox messages and summarize what customers are asking"*
- *"Reply to the message from Ahmed saying we can deliver the item by 3 PM"*
- *"Publish a Facebook ad post for our 30% discount with a Shop Now button to https://example.com/shop"*
- *"How did my last 5 Facebook posts perform? Show me likes, comments, and reach"*
- *"Reply to the positive comments on my latest post with a thank you"*

### Photo & Creative Publishing
- Attach any image in Telegram and write caption: *"Publish this photo to my Facebook Page with an inspiring quote"*

---

## 🛡️ Safety & Human-in-the-Loop Confirmation

Every write operation (publishing posts, launching ads, sending customer messages, replying to comments) triggers an interactive Telegram preview card:
- **[🚀 Confirm & Send]**: Safely executes the action on Facebook using the user's specific page token.
- **[❌ Cancel]**: Aborts the operation immediately.
- **[✏️ Revise / Edit]**: Lets you adjust the prompt or message before publishing.
