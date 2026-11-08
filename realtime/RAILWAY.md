# Найпростіший запуск: Railway (замість власного VPS)

Репозиторій містить готовий long-running Python / Telethon сервер.
Railway надає контейнер та HTTPS-домен; Caddy не потрібен.

1. Створіть Railway-проєкт із GitHub репозиторію
   vladimirpovkh-creator/kyiv-outages-dashboard.
2. Для сервісу задайте змінну RAILWAY_DOCKERFILE_PATH = realtime/Dockerfile,
   кореневий каталог репозиторію має залишатися / (Dockerfile копіює scripts/).
   Налаштуйте один екземпляр (репліку), без Cron.
3. Вимкніть Serverless / App Sleeping, щоб Telegram-сесія була підключена 24/7.
   Для стабільного restart policy може знадобитися платний Railway план.
4. У Railway Service Variables додайте секрети TELEGRAM_API_ID,
   TELEGRAM_API_HASH і TELEGRAM_SESSION. Не надсилайте їх у чат чи GitHub.
   **Створіть окрему StringSession для Railway через QR-логін**:
   не використовуйте той самий рядок TELEGRAM_SESSION, з яким паралельно
   працює GitHub Actions. Одночасне використання одного Telegram auth key
   на різних серверах може викликати AUTH_KEY_DUPLICATED.
5. Сервіс повинен слухати 0.0.0.0:$PORT (код уже підтримує PORT).
   Railway → Settings → Networking → Generate Domain.
   Увімкніть Healthcheck Path = /health.
6. За виданою HTTPS-адресою перевірте /health (200) і /status (JSON).
   Переконайтесь, що checked_at регулярно оновлюється та на тестовому
   фактичному перемиканні state змінюється правильно.
7. Тільки після перевірки змініть data/realtime-config.json:
   {"api_url":"https://<ваш-домен>.up.railway.app"}
   Після GitHub Pages deployment статус на сайті піде напряму з Railway
   з опитуванням раз на 5 секунд.
8. Після стабільної роботи вимкніть лише старий розклад
   Forum Prazkyi topic 63 power monitor у GitHub Actions;
   історичний збирач не вимикайте.

Нульової затримки немає: Telegram може затримувати події, сервер може
втратити з'єднання, браузер може бути у фоновому режимі. За нормальної
роботи — кілька секунд; резервна звірка кожні 30 секунд.
