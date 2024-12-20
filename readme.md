# Discord CDN Proxy API

## 🛠️ Описание

Этот проект представляет собой прокси-сервер для работы с вложениями Discord. Он предоставляет следующие возможности:
- 📤 Загружать изображения в канал Discord.
- 📥 Получать вложения напрямую в виде файла, а не ссылки на файл.

## 🚀 Установка и запуск

### 1️⃣ Установите зависимости
Убедитесь, что Poetry установлен. Если нет, выполните следующую команду для установки:

```bash
pip install poetry
```

После этого установите зависимости проекта:

```bash
poetry install
```

### 2️⃣ Настройте переменные окружения
Создайте файл `.env` или задайте переменные окружения:

```env
DISCORD_TOKEN=<ваш токен Discord>
PORT=8000
DEV_MODE=false
DEFAULT_CHANNEL_ID=1319786706177884232
```

### 3️⃣ Запустите сервер

```bash
poetry run python main.py
```

Сервер будет запущен по адресу: [http://0.0.0.0:8000](http://0.0.0.0:8000).

## 🌐 Эндпоинты

### `GET /`
Получает вложение Discord напрямую в виде файла.

#### Параметры
- `url` (string): URL вложения из Discord.

#### Пример запроса
```bash
curl "http://0.0.0.0:8000/?url=https://cdn.discordapp.com/attachments/<channel_id>/<message_id>/<filename>"
```

#### Пример ответа
Возвращает содержимое файла напрямую.

---

### `POST /upload/`
Загружает изображение в указанный канал Discord.

#### Параметры
- `file` (multipart/form-data): Файл для загрузки.

#### Пример запроса с использованием `curl`
```bash
curl -X POST "http://0.0.0.0:8000/upload/" \
    -F "file=@/path/to/your/image.png"
```

#### Пример ответа
```json
{
    "url": "https://cdn.discordapp.com/attachments/<channel_id>/<message_id>/<filename>"
}
```

## ⚙️ Настройки

### Переменные окружения
- `DISCORD_TOKEN`: Токен вашего бота Discord.
- `PORT`: Порт для запуска приложения (по умолчанию: `8000`).
- `DEV_MODE`: Если установлено в `true`, включает режим разработки (дополнительная отладочная информация).
- `DEFAULT_CHANNEL_ID`: ID канала Discord для загрузки изображений.

## 🔧 Настройка Nginx

Для использования Nginx в качестве обратного прокси добавьте следующий блок конфигурации в файл вашего Nginx:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Перезапустите Nginx, чтобы применить изменения:

```bash
sudo systemctl restart nginx
```

Теперь ваше приложение доступно по адресу `http://yourdomain.com`.

## 📋 Примечания
- Убедитесь, что токен Discord имеет права на отправку сообщений и загрузку файлов в канал.
- Кэширование работает с ограничением в 1000 записей и временем жизни 1 час.

## 📜 Лицензия
Этот проект распространяется под [MIT License](https://github.com/BazZziliuS/Discord-Cdn-Proxy/blob/main/LICENSE).