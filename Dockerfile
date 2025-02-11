FROM python:3.9-slim

# 安裝依賴及Zerotier
RUN apt-get update && \
    apt-get install -y curl gnupg && \
    curl -s https://install.zerotier.com | bash

# 複製應用代碼
COPY . .


# 安裝Python依賴
RUN pip install -r requirements.txt

# 複製啟動腳本並設置權限
COPY start.sh /start.sh
RUN chmod +x /start.sh

# 暴露端口
EXPOSE 8080

ENTRYPOINT ["/start.sh"]
CMD ["python", "app.py"] 