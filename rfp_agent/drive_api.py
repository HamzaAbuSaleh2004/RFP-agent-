"""
Google Drive API helper for downloading templates and uploading generated PDFs.
Uses the same OAuth credentials as the MCP bridge but with write scope.
"""
import os
import io
import json
import webbrowser
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

BASE_DIR = Path(r"c:\Users\hamza\Desktop\LiverX\RFP")
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
# Separate token for write access so read-only MCP token is untouched
WRITE_TOKEN_PATH = BASE_DIR / ".gdrive-write-token.json"

# Request full drive.file scope (create/modify files this app creates)
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_service():
    """Return an authenticated Drive v3 service with read+write scope."""
    creds = None

    if WRITE_TOKEN_PATH.exists():
        with open(WRITE_TOKEN_PATH) as f:
            token_data = json.load(f)
        with open(CREDENTIALS_PATH) as f:
            cred_info = json.load(f)["installed"]

        creds = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=cred_info["token_uri"],
            client_id=cred_info["client_id"],
            client_secret=cred_info["client_secret"],
            scopes=SCOPES,
        )

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        # Save updated token
        with open(WRITE_TOKEN_PATH, "w") as f:
            json.dump(
                {
                    "access_token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes,
                },
                f,
                indent=2,
            )

    return build("drive", "v3", credentials=creds)


def search_file(name_query: str) -> list[dict]:
    """Search Drive for files matching a name. Returns list of {id, name, mimeType}."""
    service = _get_service()
    results = (
        service.files()
        .list(
            q=f"name contains '{name_query}' and trashed=false",
            fields="files(id, name, mimeType)",
            pageSize=10,
        )
        .execute()
    )
    return results.get("files", [])


def download_file(file_id: str, dest_path: str) -> str:
    """Download a Drive file by ID to dest_path. Handles Google Docs → PDF export."""
    service = _get_service()

    # Check mime type to decide export vs direct download
    meta = service.files().get(fileId=file_id, fields="mimeType,name").execute()
    mime = meta.get("mimeType", "")

    if mime == "application/vnd.google-apps.document":
        # Export Google Doc as PDF
        request = service.files().export_media(fileId=file_id, mimeType="application/pdf")
    else:
        request = service.files().get_media(fileId=file_id)

    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    return dest_path


def upload_file(local_path: str, filename: str) -> str:
    """Upload a PDF to Google Drive root. Returns the shareable view link."""
    service = _get_service()

    file_metadata = {"name": filename}
    media = MediaFileUpload(local_path, mimetype="application/pdf", resumable=True)

    file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id,webViewLink")
        .execute()
    )

    # Make it viewable by anyone with the link
    service.permissions().create(
        fileId=file["id"],
        body={"type": "anyone", "role": "reader"},
    ).execute()

    link = file.get("webViewLink") or f"https://drive.google.com/file/d/{file['id']}/view"
    return link
