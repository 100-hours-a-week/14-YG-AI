import requests
import os
from dotenv import load_dotenv

load_dotenv()

from auth.get_access_token import login_admin_and_get_token

def get_presigned_url():
    access_token = login_admin_and_get_token()
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    auth_url = os.getenv("BACKEND_URL") + 'api/image/presign'

    resp = requests.get(auth_url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    return data