#!/bin/bash

echo "🔎 Поиск упоминаний 'redis' в проекте..."
grep -Ri "redis" . --exclude-dir={.git,__pycache__,venv} > redis_references.txt

echo "🔎 Проверка docker-compose.yml на наличие Redis..."
if [ -f docker-compose.yml ]; then
    grep -i redis docker-compose.yml >> redis_references.txt
fi

echo "🔎 Поиск скриптов, запускающих Redis..."
find . -type f -name "*.sh" -exec grep -i redis {} + >> redis_references.txt

echo "🔎 Проверка crontab (root и текущий пользователь)..."
sudo crontab -l | grep redis >> redis_references.txt 2>/dev/null
crontab -l | grep redis >> redis_references.txt 2>/dev/null

echo "🔎 Проверка systemd и init.d..."
systemctl list-unit-files | grep redis >> redis_references.txt 2>/dev/null
ls /etc/init.d/ | grep redis >> redis_references.txt 2>/dev/null

echo "✅ Готово! Все результаты поиска сохранены в 'redis_references.txt'."
echo "Открой файл для анализа: cat redis_references.txt"
