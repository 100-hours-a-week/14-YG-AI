# ─── 1) 베이스 이미지
FROM python:3.10-slim

# ─── 2) 필수 패키지 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      wget unzip ca-certificates \
      fonts-liberation libglib2.0-0 libnss3 libx11-xcb1 \
      libxcomposite1 libxcursor1 libxdamage1 libxrandr2 \
      libxss1 libxtst6 lsb-release xdg-utils && \
    rm -rf /var/lib/apt/lists/*

# ─── 3) Chrome for Testing 다운로드 & 설치
RUN wget -O /tmp/chrome-for-testing.zip \
      https://storage.googleapis.com/chrome-for-testing-public/136.0.7103.49/linux64/chrome-linux64.zip && \
    unzip /tmp/chrome-for-testing.zip -d /opt && \
    rm /tmp/chrome-for-testing.zip && \
    rm -f /usr/bin/google-chrome && \
    ln -s /opt/chrome-linux64/chrome /usr/bin/google-chrome && \
    chmod +x /opt/chrome-linux64/chrome

# ─── 4) ChromeDriver 다운로드 & 설치
RUN wget -O /tmp/chromedriver.zip \
      https://storage.googleapis.com/chrome-for-testing-public/136.0.7103.49/linux64/chromedriver-linux64.zip && \
    unzip /tmp/chromedriver.zip -d /opt && \
    rm /tmp/chromedriver.zip && \
    rm -f /usr/bin/chromedriver && \
    ln -s /opt/chromedriver-linux64/chromedriver /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver

# ─── 5) 작업 디렉터리 & 파이썬 의존성
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── 6) 스크립트 복사 & 진입점
COPY scsh_local.py .
ENTRYPOINT ["python", "scsh_local.py"]
