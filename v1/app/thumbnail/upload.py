import requests

def upload_thumbnail(presigned_url: str, file_path: str = 'img/thumbnail.png', content_type: str = 'image'):
    with open(file_path, 'rb') as f:
        files = {'file': (file_path, f, content_type)}

        resp = requests.put(presigned_url, data=f, headers={'Content-Type': content_type})
    try:
        resp.raise_for_status()
        print(f"[OK] Uploaded {file_path} to S3 via presigned URL")
    except requests.HTTPError as e:
        print(f"[ERROR] Upload failed: {e}\nResponse body: {resp.text}")


def get_presigned_url(auth_url: str, access_token: str):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    resp = requests.get(auth_url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    return data

def login_and_get_token(auth_url: str, email: str, password: str) -> str:
    payload = {
        'email': email,
        'password': password
    }
    resp = requests.post(auth_url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    
    return resp.cookies.get('AccessToken')


if __name__ == '__main__':
    access_token = login_and_get_token('https://moongsan.com/api/users/token', '1234@gmail.com', 'ht12345!')
    presigned_url = get_presigned_url('https://moongsan.com/api/image/presign', access_token)
    
    print(presigned_url['key'])
    print(presigned_url['url'])

    upload_thumbnail(presigned_url['url'])
