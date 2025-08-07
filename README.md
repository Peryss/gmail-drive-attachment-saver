# 📥 Gmail to Google Drive Attachment Saver

A Python automation tool that connects to your Gmail account, fetches email attachments after a specific date, and saves them to Google Drive with a clear folder structure.

---

## ✨ Features

- **Non-starred emails** → Saved by month (`YYYY-MM`)
- **Starred emails** → Saved by sender (`⭐ Starred/<sender_email>/`)
- Skips duplicate files using SHA256 hash checks
- Skips unwanted file types (configurable, e.g., `.jpg`, `.png`)
- Google Drive folder auto-creation
- Retry mechanism for uploads
- Simple configuration via `config.json`

---

## 📂 Example Folder Structure

Saved Attachments/
├── 2025-05/
│   ├── contract.pdf
│   └── report.xlsx
├── 2025-06/
│   └── notes.docx
└── ⭐ Starred/
    ├── boss@example.com/
    │   └── project_plan.pdf
    └── hr@company.com/
        └── resume.docx

---

## 🚀 Setup

### 1️⃣ Clone the repo
```bash
git clone git@github.com:Peryss/gmail-drive-attachment-saver.git
cd gmail-drive-attachment-saver
```

### 2️⃣ Create and activate a virtual environment
```bash
python3 -m venv venv
source venv/bin/activate   # On Linux/Mac
venv\Scripts\activate      # On Windows
```

### 3️⃣ Install dependencies
```bash
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 4️⃣ Get your Google API credentials
 - Go to Google Cloud Console
 - Create a project & enable the Gmail API and Google Drive API
 - Create OAuth 2.0 credentials and download the client_secret.json
 - Place client_secret.json in the project folder

 ## ⚙️ Configuration

 Edit the config.json file:
 ```json
 {
  "scopes": [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file"
  ],
  "base_folder_name": "Saved Attachments",
  "after_date": "2025/05/01",
  "max_results": 100,
  "log_file": "downloaded_attachments.json",
  "ignored_extensions": [".jpg", ".jpeg", ".png"]
}
```

## ▶️ Usage

Run the script:
```bash
python save_attachments.py
```

The first time you run it:
 - A browser window will open asking you to log into your Google account
 - Approve the Gmail and Drive permissions
 - A token.json will be saved locally so you don’t need to log in again