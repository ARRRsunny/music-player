#!/bin/bash

# 啟動Zerotier服務
zerotier-one -d

# 加入Zerotier網路（通過環境變量傳入網路ID）
zerotier-cli join $ZEROTIER_NETWORK_ID

# 等待獲取IP（可根據需要調整等待時間）
sleep 10

# 自動授權（若網路為私有，需使用API Token）
# 獲取節點ID
NODE_ID=$(zerotier-cli info | cut -d ' ' -f 3)
# 使用API自動批准（需提供ZEROTIER_API_TOKEN）
curl -s -X POST \
  -H "Authorization: bearer $ZEROTIER_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"config": {"authorized": true}}' \
  "https://api.zerotier.com/api/v1/network/$ZEROTIER_NETWORK_ID/member/$NODE_ID" > /dev/null

# 啟動Flask應用
flask run --host=0.0.0.0 --port=8080