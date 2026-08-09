# Deployment Guide: n8n on Render (Hobby / Free Tier)

This guide provides step-by-step instructions to self-host n8n on Render.com using the **Render Blueprint** method.

---

## ⚡ Important Render Hobby Tier Gotchas & Workarounds

| Challenge | Render Limitation | Solution / Best Practice |
| :--- | :--- | :--- |
| **Service Sleep** | Render Free Web Services sleep after 15 mins of inactivity | Set up a free external cron ping (e.g., [Cron-Job.org](https://cron-job.org)) hitting `https://your-app.onrender.com/healthz` every 10 minutes. |
| **Free DB Expiration** | Render Free PostgreSQL database expires after **30 days** | **Option A**: Upgrade Render DB to Starter plan ($7/mo).<br>**Option B**: Use a free managed PostgreSQL instance from **Supabase** or **Neon.tech** (free forever). |
| **Cold Starts** | First request after sleep takes 30–60s | The keep-alive cron job prevents sleeping. |

---

## 🚀 Deployment Methods

### Method 1: Render Blueprint (1-Click YAML) — Recommended

1. **Fork or Push to GitHub/GitLab**:
   Push the files in `d:\zdiiv\N8N\render\` (including `render.yaml`) to a GitHub or GitLab repository.

2. **Deploy on Render**:
   - Go to [Render Dashboard](https://dashboard.render.com/).
   - Click **New +** → **Blueprint**.
   - Connect your GitHub/GitLab repository.
   - Render will detect `render.yaml` and provision both:
     - `n8n` (Web Service)
     - `n8n-db` (PostgreSQL Database)

3. **Configure Host & Webhook URL**:
   In the Render Web Service settings for `n8n`, update these two environment variables:
   - `N8N_HOST`: `your-app-name.onrender.com`
   - `WEBHOOK_URL`: `https://your-app-name.onrender.com/`

---

### Method 2: Render Web Service with External Free Database (Supabase / Neon)

If you want a **100% free permanent database** (avoiding Render's 30-day DB expiration):

1. Create a free PostgreSQL database on **[Supabase](https://supabase.com)** or **[Neon](https://neon.tech)**.
2. In Render Dashboard, click **New +** → **Web Service**.
3. Select **Existing Image** and enter:
   `docker.n8n.io/n8nio/n8n:latest`
4. Set Instance Type to **Free** (or Starter for no sleep).
5. Add Environment Variables:

| Environment Variable | Value |
| :--- | :--- |
| `PORT` | `5678` |
| `N8N_PORT` | `5678` |
| `N8N_PROTOCOL` | `https` |
| `NODE_ENV` | `production` |
| `N8N_HOST` | `your-app-name.onrender.com` |
| `WEBHOOK_URL` | `https://your-app-name.onrender.com/` |
| `N8N_ENCRYPTION_KEY` | *(Generate random 32-byte hex key)* |
| `DB_TYPE` | `postgresdb` |
| `DB_POSTGRESDB_HOST` | `db.xxxx.supabase.co` (or your Neon host) |
| `DB_POSTGRESDB_PORT` | `5432` |
| `DB_POSTGRESDB_DATABASE` | `postgres` |
| `DB_POSTGRESDB_USER` | `postgres` |
| `DB_POSTGRESDB_PASSWORD` | `your-db-password` |
| `DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED` | `false` |
| `EXECUTIONS_DATA_PRUNE` | `true` |
| `EXECUTIONS_DATA_MAX_AGE` | `168` |

---

## 🛠️ Step 3: Prevent Inactivity Sleeping (Keep-Alive Cron)

Because Render Free web services spin down after 15 minutes of idle time:

1. Go to **[cron-job.org](https://cron-job.org)** (free).
2. Create a new cron job:
   - **URL**: `https://your-app-name.onrender.com/healthz`
   - **Schedule**: Every 10 minutes (`*/10 * * * *`)
3. This keeps n8n awake 24/7 so incoming webhooks and schedule triggers execute without delay.

---

## 🔒 Post-Deployment Checklist

- [ ] Log in to `https://your-app-name.onrender.com` and complete the initial admin setup.
- [ ] Create an API Key in **Settings → n8n API**.
- [ ] Update `d:\zdiiv\N8N\n8n_config.json` on your local system with the base URL and API key so your AI assistant can manage your workflows directly!
