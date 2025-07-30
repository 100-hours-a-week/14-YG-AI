FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --use-deprecated=legacy-resolver \
    -r requirements.txt

FROM python:3.11-slim
WORKDIR /app

# 1) 필수 패키지 설치 (curl, unzip 등)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      sudo wget gnupg gnupg1 gnupg2 unzip curl && \
    rm -rf /var/lib/apt/lists/*

# 2) Google Chrome 공식 저장소 추가
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub \
      | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list

# 3) Chrome 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

RUN rm -f /usr/local/bin/chromedriver

# 4) Chrome 137+ 버전에 맞는 ChromeDriver 다운로드 (새로운 API 사용)
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}') && \
    echo "Chrome version: $CHROME_VERSION" && \
    if [[ "$CHROME_VERSION" > "114" ]]; then \
        wget -O /tmp/chromedriver.zip \
             "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip" && \
        cd /tmp && \
        unzip chromedriver.zip && \
        mv chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
        rm -rf chromedriver*; \
    else \
        CHROME_MAJOR=${CHROME_VERSION%%.*} && \
        DRIVER_VERSION=$(curl -fsS "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_MAJOR}" \
                         || curl -fsS https://chromedriver.storage.googleapis.com/LATEST_RELEASE) && \
        wget -O /tmp/chromedriver.zip \
             "https://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip" && \
        unzip /tmp/chromedriver.zip -d /usr/local/bin && \
        rm /tmp/chromedriver.zip; \
    fi && \
    chmod +x /usr/local/bin/chromedriver && \
    chromedriver --version

# 5) Python 바이너리 복사
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# 6) 앱 파일 복사 및 권한 설정
RUN mkdir -p /var/moongsan/secret && chown 1000:1000 /var/moongsan/secret
COPY app/ ./

EXPOSE 8100
ENTRYPOINT ["bash","-c","\
    rm -rf /root/.config/google-chrome/Singleton* 2>/dev/null; \
    uvicorn main:app --host 0.0.0.0 --port 8100 --log-level debug --access-log \
      2>&1 | tee -a /var/moongsan/log/ai_moongsan.log"]