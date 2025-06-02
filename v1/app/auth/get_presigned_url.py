import requests
from auth.get_access_token import login_and_get_token

access_token = login_and_get_token()
auth_url = 'https://moongsan.com/api/image/presign'


def get_presigned_url(access_token: str = access_token, auth_url: str = auth_url):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    resp = requests.get(auth_url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    return data