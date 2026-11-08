# Oracle Cloud Always Free — Telethon монітор ForumPrazkyi/63

Мета: прибрати GitHub Actions з критичного шляху стану світла 5.2. Підтримувати
безперервне Telegram-підключення на VM Oracle, віддавати лише статус через HTTPS
і оновлювати картку сайту кожні 5 секунд.

## 1. Створення безкоштовної VM

1. Створіть обліковий запис на https://www.oracle.com/cloud/free/ .
   Oracle може вимагати банківську картку для верифікації; **не переходьте
   на Pay As You Go** і не створюйте ресурси, які не позначено Always Free.
2. Під час створення оберіть домашній регіон, де доступні Always Free VM.
   Безкоштовні VM створюються лише в домашньому регіоні облікового запису.
3. OCI Console → Compute → Instances → Create instance.
   - Image: Ubuntu 24.04 (ARM64 для A1; x86_64 для E2).
   - Shape: **VM.Standard.A1.Flex, Always Free**; 1 OCPU, 6 GB RAM
     (або VM.Standard.E2.1.Micro, Always Free, якщо A1 недоступна).
   - Boot volume: 47–50 GB у межах безкоштовного обсягу.
   - VCN: public subnet із публічною IPv4-адресою.
   - SSH: згенеруйте ключ і збережіть приватний файл лише у себе.
4. У Networking → VCN → Security List / NSG дозволяйте inbound TCP:
   80 (Caddy TLS), 443 (HTTPS); 22 (SSH **лише з вашої IP/32**).
   Не відкривайте 8080. В Ubuntu перевірте також host firewall / iptables.
   Не вимикайте SSH під час налаштування firewall.

Якщо Console показує «Out of host capacity», інстанс не створено: змініть
availability domain (якщо доступний) або повторіть пізніше. Це не помилка коду.

Доступні квоти на момент підготовки: 1500 OCPU-годин і 9000 GB-годин
Ampere A1 на місяць (еквівалент до 2 OCPU та 12 GB RAM), а також до двох
E2 Micro; перевіряйте мітку Always Free в консолі:
https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

## 2. Безкоштовний HTTPS-домен

Сайт працює через HTTPS, тому адресу сервера треба також опублікувати через HTTPS.

- Створіть безкоштовний субдомен у https://www.duckdns.org/ , наприклад
  `svitlo-monitor.duckdns.org` (це лише приклад, не готова адреса).
- У DuckDNS прив'яжіть субдомен до публічної IPv4-адреси OCI VM.
- Зачекайте на DNS-оновлення; перевірте відповідність через `dig +short`.
- Caddy із файлу `realtime/Caddyfile` автоматично отримає TLS-сертифікат,
  якщо з інтернету доступні 80/443 та DNS правильно вказує на VM.

Безкоштовний DNS-провайдер не гарантує SLA. Використовуйте статичну (резервовану,
у межах доступних безкоштовних квот) публічну IPv4 або налаштуйте DuckDNS update
у разі зміни IP. Токен DuckDNS ніколи не публікуйте у репозиторії.

## 3. Налаштування Ubuntu + Docker

Приклад входу (замініть значення на власні, **не надсилайте приватний SSH-ключ**):

```sh
ssh -i ~/.ssh/oracle_svitlo.key ubuntu@YOUR_VM_PUBLIC_IP
```

На VM:

```sh
sudo apt-get update
sudo apt-get install -y ca-certificates curl git docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
# Перезайдіть по SSH, щоб почала діяти група docker.
git clone https://github.com/vladimirpovkh-creator/kyiv-outages-dashboard.git
cd kyiv-outages-dashboard/realtime
cp .env.example .env
chmod 600 .env
nano .env
```

Якщо `docker-compose-v2` недоступний у дистрибутиві, встановіть офіційний
Docker Compose plugin і переконайтесь, що працює `docker compose version`.

У **локальному файлі на сервері** `.env` введіть:

```dotenv
MONITOR_DOMAIN=YOUR_SUBDOMAIN.duckdns.org
TELEGRAM_API_ID=YOUR_ID
TELEGRAM_API_HASH=YOUR_HASH
TELEGRAM_SESSION=YOUR_NEW_SESSION_STRING
```

**Важливо:** для Oracle створіть **нову незалежну Telegram StringSession**.
Не копіюйте в Oracle ту саму авторизаційну сесію, що вже працює в GitHub
Actions — одночасне використання того самого Telegram auth key із різних IP
може зневалідити її (AUTH_KEY_DUPLICATED). Виконуйте окрему авторизацію
технічного Telegram-акаунта на довіреному пристрої та зберігайте StringSession
лише у `.env` сервера. Не показуйте її у чаті чи GitHub.

Запуск:

```sh
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl -fsS https://YOUR_SUBDOMAIN.duckdns.org/health
curl -fsS https://YOUR_SUBDOMAIN.duckdns.org/status
```

У результаті `/health` має повертати `{"ok":true}`, а `/status` —
JSON із `state`, `changed_at`, `checked_at`, `message_id`.
`checked_at` повинен оновлюватися приблизно раз на 30 секунд.

Для діагностики:

```sh
docker compose logs --tail=100 monitor
docker compose logs --tail=100 https
```

## 4. Контрольний тест без вимикання GitHub

1. Перевірте, що сайт і далі показує старий стан через GitHub Pages.
2. На Oracle запущений Telethon-монітор: `/health` повертає 200.
3. Після реального перемикання в Telegram темі 63 `/status` має показати
   новий `on` або `off`, правильну дату і ID повідомлення.
4. Зіставте з джерелом вручну, особливо часовий пояс (поля API — UTC).
5. Перевірте, що після відключення Telegram/VM `/health` стає 503 або
   не відповідає, а сайт з активованою конфігурацією покаже unknown.

Після успішної перевірки **лише тоді** змініть
`data/realtime-config.json` у GitHub:

```json
{"api_url": "https://YOUR_SUBDOMAIN.duckdns.org"}
```

GitHub Pages тоді опитуватиме новий API **кожні 5 секунд**. Старий workflow
відключайте тільки після кількох підтверджених реальних перемикань.
`Build Forum Prazkyi actual outage history` має залишитися — він збирає архів.

## 5. Безкоштовність, контроль витрат і відмови

- Лише ресурси з міткою **Always Free** у межах квот. Платні ресурси за
  межами Always Free неприпустимі.
- Oracle може **вилучати малонавантажені** Always Free VM: не гарантується
  безстрокова доступність. Не створюйте штучного CPU-навантаження.
- Налаштуйте зовнішній uptime-контроль `/health` та сповіщення про 503.
- За нормального підключення: Telegram event → сервер → браузер (до 5 секунд
  додатково після зміни на сервері). Якщо подію пропущено — резервна звірка
  приблизно за 30 секунд плюс опитування сайту.
- Фоновий режим iPhone або втрата інтернету може затримувати відображення.
- Для високої доступності потрібен другий незалежний сервер або резервний
  механізм і контроль працездатності. Always Free не має SLA для нашого сценарію.

## Корисні джерела

- [OCI Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Oracle Cloud Free](https://www.oracle.com/cloud/free/)
- [DuckDNS FAQ](https://www.duckdns.org/faqs.jsp)
