# 🚀 Job Agent - 24/7 Hourly Indian Fresher Job Bot

Autonomous job monitoring agent that continuously scans **Google Jobs, LinkedIn, Internshala, Freshersworld, Jobicy, RemoteOK, Himalayas, Remotive, Greenhouse & Lever** specifically for **Indian fresher opportunities** (Kochi, Bengaluru, Hyderabad, Chennai, Mumbai, Pune, Delhi NCR, and India Remote).

---

## 🇮🇳 Strictly Indian Jobs Filter

- **Accepted Locations**: All major Indian tech & commercial hubs:
  `Kochi`, `Trivandrum`, `Kerala`, `Bengaluru`, `Hyderabad`, `Chennai`, `Mumbai`, `Navi Mumbai`, `Pune`, `Delhi NCR` (`Noida`, `Gurgaon`), `Coimbatore`, `Kolkata`, `Ahmedabad`, `Surat`, `India`, or `Remote in India`.
- **Blocked**: All foreign locations (USA, UK, Canada, Mexico, Germany, Australia, Europe, Latam, Spain, Brazil, etc.) and generic worldwide remote jobs without explicit India eligibility are **strictly rejected**.
- **Foreign Language Filter**: Rejects non-English foreign-language specific roles (Mandarin, German, French, Spanish, Japanese, etc.).

---

## ☁️ How to Host & Run 24/7 Every Hour

You have 3 easy ways to run this every hour:

### Option 1: GitHub Actions (Recommended — 100% Free Cloud, No PC Needed)
GitHub Actions runs the agent in the cloud **24/7 every single hour**, even when your computer is shut off.
1. Create a **Private** repository on GitHub (e.g. `job-agent`).
2. Push your `JOBBER` folder to this repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<YOUR_USERNAME>/job-agent.git
   git push -u origin main
   ```
3. In your GitHub repo, go to **Settings > Secrets and variables > Actions > New repository secret** and add:
   - `TELEGRAM_BOT_TOKEN`: `9298472471:AAFOl3KSWDJ0rOSxnvJRDRea-4-EuMbrxA4`
   - `TELEGRAM_CHAT_ID`: `8288731777`
4. **Done!** The workflow in [`.github/workflows/daily.yml`](file:///.github/workflows/daily.yml) will trigger every hour on the hour, scan all platforms for new Indian fresher jobs, push alerts directly to your Telegram, and save the tracker automatically.

---

### Option 2: Windows Background Task (Runs Hourly on your PC Silently)
If you want it running right now on your Windows machine in the background with **zero windows popping up**:
1. Double-click **`install_windows_hourly_task.bat`**.
2. It registers a task in Windows Task Scheduler called `JobAgentHourlyAlerts`.
3. It will silently wake up every 60 minutes, check for new jobs, and send notifications to your Telegram.
4. To remove it anytime, double-click **`uninstall_windows_hourly_task.bat`**.

---

### Option 3: Free Cloud PaaS (Render / Railway / Koyeb)
A complete `Dockerfile`, `Procfile`, and `render.yaml` are included in the repository:
1. Connect your repository to **Render.com** (New > Background Worker) or **Railway.app**.
2. Set Environment Variables:
   - `TELEGRAM_BOT_TOKEN`: `9298472471:AAFOl3KSWDJ0rOSxnvJRDRea-4-EuMbrxA4`
   - `TELEGRAM_CHAT_ID`: `8288731777`
   - `DRY_RUN`: `false`
3. The container will automatically execute `python main.py --watch --interval 60` and run 24/7.

---

## 🎯 3 Indian Fresher Tracks Monitored

1. 🎧 **Customer Care & Support**
   - Targets: Customer Care Executive, Customer Support Associate, Technical Support, Helpdesk, Voice/Non-Voice Process, Chat Support, BPO, Operations Associate.
   - Highlights: Fluent English, Malayalam & Hindi communication, problem-solving, CRM & ticketing tools.
2. 💻 **Frontend Developer**
   - Targets: React Developer, Frontend Engineer, Web Developer, UI/UX Developer.
   - Highlights: Omeagle WebRTC platform, Krynn Tools, React.js, Tailwind CSS, JavaScript.
3. 🛡️ **Cybersecurity & SOC Analyst**
   - Targets: SOC Analyst, Security Analyst, Pentesting, Vulnerability Management.
   - Highlights: Rednox Technologies Internship, ReconX, Nmap by Ash, Passmatic.

---

## 🛠️ CLI Quick Reference

| Command | Action |
| :--- | :--- |
| `python main.py --alerts --live` | Scans all sources now and pushes new Indian match cards |
| `python main.py --bot` | Runs the interactive Telegram Bot daemon |
| `python main.py --watch --interval 60` | Runs local continuous hourly loop |
| `python main.py --stats` | Shows total tracked, alerted, and applied jobs |
| `install_windows_hourly_task.bat` | 1-Click install of hourly background service on Windows |
| `uninstall_windows_hourly_task.bat` | 1-Click uninstall of hourly background service |
