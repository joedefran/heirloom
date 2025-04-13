from flask import Flask, redirect, request, session, url_for
import uuid
import google.auth.transport.requests
import google.oauth2.credentials
from googleapiclient.discovery import build
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(24) # important for sessions

CLIENT_ID = "YOUR_CLIENT_ID" #From google cloud console
CLIENT_SECRET = "YOUR_CLIENT_SECRET" #From google cloud console
REDIRECT_URI = "YOUR_REDIRECT_URI" #example: yourwebsite.com/oauth2callback

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_db_connection():
    conn = sqlite3.connect('urls.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_credentials():
    creds = None
    if 'credentials' in session:
        creds = google.oauth2.credentials.Credentials(**session['credentials'])
    return creds

@app.route('/create')
def create_url():
    unique_id = str(uuid.uuid4())
    session['unique_id'] = unique_id
    conn = get_db_connection()
    conn.execute('INSERT INTO urls (unique_id, video_url, status) VALUES (?, ?, ?)', (unique_id, None, 'pending'))
    conn.commit()
    conn.close()
    return redirect(url_for('authorize'))

@app.route('/authorize')
def authorize():
    flow = google.oauth2.flow.Flow.from_client_secrets_file(
        'client_secret.json', SCOPES,
        redirect_uri=REDIRECT_URI)
    authorization_url, state = flow.authorization_url(
        access_type='offline', include_granted_scopes='true')
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    state = session['state']
    flow = google.oauth2.flow.Flow.from_client_secrets_file(
        'client_secret.json', SCOPES,
        redirect_uri=REDIRECT_URI, state=state)
    flow.fetch_token(authorization_response=request.url)
    session['credentials'] = {
        'token': flow.credentials.token,
        'refresh_token': flow.credentials.refresh_token,
        'token_uri': flow.credentials.token_uri,
        'client_id': flow.credentials.client_id,
        'client_secret': flow.credentials.client_secret,
        'scopes': flow.credentials.scopes}

    return redirect(url_for('process_url', unique_id=session['unique_id']))

@app.route('/process/<unique_id>')
def process_url(unique_id):
    conn = get_db_connection()
    url_data = conn.execute('SELECT * FROM urls WHERE unique_id = ?', (unique_id,)).fetchone()
    if url_data['video_url']:
        return redirect(url_data['video_url'])

    creds = get_credentials()
    if url_data['status'] == 'pending' and creds:
        drive_service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': 'My Video', 'mimeType': 'video/mp4'}
        file = drive_service.files().create(body=file_metadata, media_body=None, fields='id').execute()
        video_url = f'https://drive.google.com/file/d/{file.get("id")}/view?usp=sharing'
        conn.execute('UPDATE urls SET video_url = ?, status = ? WHERE unique_id = ?', (video_url, 'created', unique_id))
        conn.commit()
        conn.close()
        return redirect(video_url)
    elif creds == None:
      return redirect(url_for('authorize'))
    return "processing"

if __name__ == '__main__':
    conn = get_db_connection()
    conn.execute('CREATE TABLE IF NOT EXISTS urls (unique_id TEXT PRIMARY KEY, video_url TEXT, status TEXT)')
    conn.close()
    app.run(debug=True)

# Sources:
# 1. https://github.com/jerem64/API_Flask_OpenAI_CV
# 2. https://stackoverflow.com/questions/56281798/flask-server-side-sessions-lost-using-google-oauth
# 3. https://github.com/Madhav-MKNC/testing-gdrive-picker
# 4. https://github.com/bydefaultcoder/ConvinTask
# 5. https://github.com/tomy0000000/Tubee subject to MIT