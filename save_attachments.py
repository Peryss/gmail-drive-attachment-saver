import os
import base64
import io
import datetime
import json
import hashlib
import time
import re

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.auth.transport.requests import Request

# === Load Configuration ===
with open("config.json", "r") as f:
    config = json.load(f)

SCOPES = config["scopes"]
BASE_FOLDER_NAME = config["base_folder_name"]
AFTER_DATE = config["after_date"]
MAX_RESULTS = config["max_results"]
LOG_FILE = config["log_file"]
IGNORED_EXTENSIONS = [ext.lower() for ext in config["ignored_extensions"]]

# === Log File Handling ===
def load_download_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️ Warning: {LOG_FILE} was empty or invalid. Reinitializing log.")
            return {}
    return {}

def save_download_log(log):
    with open(LOG_FILE, "w") as f:
        json.dump(log, f)

# === Google Auth ===
def authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

# === Google Drive Folder Handling ===
def get_or_create_drive_folder(drive, name, parent_id=None):
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = drive.files().list(q=query, spaces='drive', fields='files(id)', pageSize=1).execute()
    folders = results.get('files', [])
    if folders:
        return folders[0]['id']
    metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
    }
    if parent_id:
        metadata['parents'] = [parent_id]
    folder = drive.files().create(body=metadata, fields='id').execute()
    return folder['id']

# === Recursively Find Attachments ===
def find_attachments(parts):
    attachments = []
    for part in parts:
        if part.get('parts'):
            attachments.extend(find_attachments(part['parts']))
        elif part.get('filename') and part.get('body', {}).get('attachmentId'):
            attachments.append(part)
    return attachments

# === Retry-Safe Upload ===
def upload_with_retry(drive, file_metadata, media, retries=3):
    for attempt in range(retries):
        try:
            return drive.files().create(body=file_metadata, media_body=media, fields='id').execute()
        except Exception as e:
            print(f"⚠️ Upload failed (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                print(f"⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("❌ Giving up after 3 failed attempts.")
                raise

# === Helper: Extract sender email ===
def get_sender_email(headers):
    for h in headers:
        if h['name'].lower() == 'from':
            return h['value']
    return ""

# === Main Logic ===
def save_attachments():
    creds = authenticate()
    gmail = build('gmail', 'v1', credentials=creds)
    drive = build('drive', 'v3', credentials=creds)

    query = f"has:attachment after:{AFTER_DATE.replace('/', '/')}"
    messages_response = gmail.users().messages().list(userId='me', q=query, maxResults=MAX_RESULTS).execute()
    messages = messages_response.get('messages', [])
    if not messages:
        print("No emails with attachments found.")
        return

    base_folder_id = get_or_create_drive_folder(drive, BASE_FOLDER_NAME)
    starred_folder_id = get_or_create_drive_folder(drive, "⭐ Starred", parent_id=base_folder_id)
    download_log = load_download_log()

    for msg in messages:
        msg_data = gmail.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        label_ids = msg_data.get('labelIds', [])
        headers = msg_data['payload'].get('headers', [])

        # Get sender email
        sender_field = get_sender_email(headers)
        sender_email = sender_field.split("<")[-1].replace(">", "").strip().lower()
        safe_sender = re.sub(r'[^\w\.-@]', '_', sender_email)

        # Determine timestamp and folder structure
        timestamp_ms = int(msg_data.get('internalDate', 0))
        email_date = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
        month_folder_name = email_date.strftime('%Y-%m')
        month_folder_id = get_or_create_drive_folder(drive, month_folder_name, parent_id=base_folder_id)

        # Define target folder
        is_starred = 'STARRED' in label_ids
        if is_starred:
            sender_folder_id = get_or_create_drive_folder(drive, safe_sender, parent_id=starred_folder_id)
            target_folder_id = sender_folder_id
        else:
            target_folder_id = month_folder_id

        attachments = find_attachments([msg_data['payload']])

        for part in attachments:
            filename = part.get("filename")
            body = part.get("body", {})
            att_id = body.get("attachmentId")
            if not (filename and att_id):
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext in IGNORED_EXTENSIONS:
                print(f"⏭ Skipping ignored file type: {filename}")
                continue

            attachment = gmail.users().messages().attachments().get(
                userId='me', messageId=msg['id'], id=att_id).execute()
            file_data = base64.urlsafe_b64decode(attachment['data'].encode('UTF-8'))

            # Generate content hash
            file_hash = hashlib.sha256(file_data).hexdigest()
            if file_hash in download_log:
                print(f"⏭ Skipping duplicate file: {filename}")
                continue

            file_metadata = {
                'name': filename,
                'parents': [target_folder_id]
            }
            media = MediaIoBaseUpload(io.BytesIO(file_data), mimetype='application/octet-stream')
            upload_with_retry(drive, file_metadata, media)

            print(f"✅ Saved: {filename} to {'⭐ Starred/' + safe_sender if is_starred else month_folder_name}")
            download_log[file_hash] = True

    save_download_log(download_log)

if __name__ == '__main__':
    save_attachments()
