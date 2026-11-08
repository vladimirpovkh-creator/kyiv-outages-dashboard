# Постійний монітор ForumPrazkyi/63

GitHub Actions cron не гарантує точність запуску. Цей сервер підтримує постійне Telegram-з'єднання, приймає повідомлення теми 63 і віддає стан HTTPS API без GitHub Pages у критичному шляху.

- Нові повідомлення та редагування Telegram запускають звірку із серверною темою 63.
- Резервна звірка кожні 30 секунд.
- /status повертає лише on/off/unknown, час події та час перевірки.
- Сайт опитує /status кожні 5 секунд після активації.
- Якщо звірка не проводилася понад 2 хвилини або подія старша за 24 години, відображається unknown.
- Жодні тексти повідомлень або дані акаунтів не публікуються.

## Установка на цілодобовий Ubuntu VPS

Потрібен VPS із Docker Engine + Docker Compose, домен з DNS A-записом на IP VPS,
а також відкриті TCP-порти 80 і 443 для автоматичного TLS від Caddy.

1. На VPS через SSH виконайте:

    git clone https://github.com/vladimirpovkh-creator/kyiv-outages-dashboard.git
    cd kyiv-outages-dashboard/realtime
    cp .env.example .env
    chmod 600 .env

2. Командою nano .env **лише на VPS** заповніть:
   - MONITOR_DOMAIN — піддомен, наприклад status.example.org, без https://
   - TELEGRAM_API_ID — ID нового Telegram-застосунку
   - TELEGRAM_API_HASH — його конфіденційний Hash
   - TELEGRAM_SESSION — існуючий StringSession окремого Telegram-акаунта

   Не надсилайте ці секрети в чат, Issues чи git. Не комітьте .env.

3. Запустіть:

    docker compose up -d --build
    docker compose ps
    curl --fail https://status.example.org/health
    curl --fail https://status.example.org/status

   Замініть status.example.org на ваш піддомен.
   Для діагностики: docker compose logs --tail=100 monitor.

4. Перевірте на реальній події, що /status змінюється з on на off (або навпаки),
   а checked_at регулярно оновлюється. Поки цього не сталося, старий
   GitHub Actions monitor залишайте увімкненим.

5. Після успішної перевірки задайте в data/realtime-config.json:

    {"api_url":"https://status.example.org"}

   Сайт почне опитувати HTTPS API кожні 5 секунд. Якщо API недоступне,
   статус повинен стати unknown, а не показувати старі дані GitHub Pages.

6. Після декількох успішних перемикань вимкніть старий workflow
   .github/workflows/forum-prazkyi-monitor.yml у GitHub Actions.
   Архівні перерахунки Forum залишаються окремими.

## Працездатність і відмови

- /health повертає 200 лише за працездатного Telegram підключення та свіжої звірки;
  інакше 503. Налаштуйте зовнішню перевірку /health з оповіщенням.
- Втрата сервера, зв'язку або Telegram-сесії має призводити до unknown.
- За нормальних умов зміна відобразиться через кілька секунд.
  Пропущену подію виявить звірка за 30 секунд плюс інтервал сайту 5 секунд.
- Нульову затримку або 100% безвідмовність забезпечити неможливо;
  для підвищення надійності потрібен резервний сервер/чергування.
