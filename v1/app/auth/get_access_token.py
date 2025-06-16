import requests
import os
from dotenv import load_dotenv

load_dotenv()

def login_admin_and_get_token() -> str:
    email = '1234@gmail.com'
    password = 'ht12345!'
    payload = {
        'email': email,
        'password': password
    }

    auth_url = os.getenv("BACKEND_URL") + 'api/users/token'

    resp = requests.post(auth_url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    
    return resp.cookies.get('AccessToken')