#!/bin/bash
# Register Shiftty bot name, description, and commands with Telegram
TOKEN="8931639383:AAGGVHUbarwOvkYdLWXS_DuTWWlJTlTrMsM"

echo "Setting bot name..."
curl -s -X POST "https://api.telegram.org/bot$TOKEN/setMyName" -d "name=Shiftty"

echo "Setting bot description..."
curl -s -X POST "https://api.telegram.org/bot$TOKEN/setMyDescription" \
  -d "description=בוט ניהול משמרות מילואים — בדוק מתי המשמרת הבאה שלך, קבל תזכורות יומיות ועוד."

echo "Setting short description..."
curl -s -X POST "https://api.telegram.org/bot$TOKEN/setMyShortDescription" \
  -d "short_description=בוט משמרות מילואים"

echo "Setting commands..."
curl -s -X POST "https://api.telegram.org/bot$TOKEN/setMyCommands" \
  -H "Content-Type: application/json" \
  -d '{"commands": [{"command": "start", "description": "התחל / הרשמה"}]}'

echo "Done!"
