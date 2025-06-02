import requests

domain = 'https://moongsan.com/api/users/token'
email = '1234@gmail.com'
password = 'ht12345!'


def login_and_get_token(auth_url: str = domain, email: str = email, password: str = password) -> str:
    payload = {
        'email': email,
        'password': password
    }
    resp = requests.post(auth_url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    
    return resp.cookies.get('AccessToken')