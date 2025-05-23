from fastapi import Header, HTTPException, status
from typing import Optional

def verify_access_token_cookie(cookie: Optional[str] = Header(None, alias="cookie")):
    if not cookie or not cookie.startswith("AccessToken="):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 정보가 없습니다. (401 Unauthorized) from fastAPI"
        )

    return cookie