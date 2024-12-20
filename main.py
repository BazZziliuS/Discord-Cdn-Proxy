from fastapi import FastAPI, Request, Response, Query, UploadFile, File
from fastapi.responses import JSONResponse, RedirectResponse
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import os
import aiohttp
from cachetools import TTLCache
from pydantic import BaseModel

class Settings(BaseModel):
    # Настройки приложения
    discord_token: str = 'Bot ' + os.getenv("DISCORD_TOKEN", "MTMxOTc4MjI5OTg4MDkxOTExMg.Gqsf55.3znKwQDx71wbjkAi9VQIc-ZP2Vid2IKm9l-F1E")
    port: int = int(os.getenv("PORT", 8000))
    default_channel_id: str = "1319786706177884232"
    dev_mode: bool = os.getenv("DEV_MODE", "false").lower() == "true"

settings = Settings()

app = FastAPI()

# Кэш с TTL 1 час (максимум 1000 записей)
cache = TTLCache(maxsize=1000, ttl=3600)

HEARTBEAT = "heartbeat"

# Статистика работы приложения
stats = {
    "started": datetime.utcnow(),
    "calls": 0,
    "original": 0,
    "refreshed": 0,
    "memory": 0,
    "heartbeats": 0,
    "exceptions": 0,
    "cache_size": 0
}

def parse_valid_url(url: str):
    # Проверка корректности URL
    try:
        return urlparse(url)
    except Exception:
        return None

@app.options("/")
async def handle_options(request: Request):
    # Обработка CORS для OPTIONS-запросов
    origin = request.headers.get("origin", "*")
    headers = {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": request.headers.get("access-control-request-headers", ""),
        "Access-Control-Max-Age": "86400",
    }
    return Response(status_code=204, headers=headers)

def add_cors_headers(response: Response, origin: str = "*"):
    # Добавление заголовков CORS в ответ
    response.headers["Access-Control-Allow-Origin"] = origin
    return response

def create_redirect_response(href: str, expires: datetime, custom: str):
    # Создание редиректа на указанный URL
    response = RedirectResponse(href)
    response.headers["Expires"] = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")
    response.headers["x-discord-cdn-proxy"] = custom
    return response

@app.get("/")
async def refresh_url(url: str = Query(..., description="Discord CDN URL")):
    # Обновление вложения Discord
    stats["calls"] += 1

    if not settings.discord_token:
        return JSONResponse(
            content={"message": "DISCORD_TOKEN is not configured"},
            status_code=400
        )

    parsed_url = parse_valid_url(url)
    if not parsed_url:
        return JSONResponse(
            content={"message": "Provide a valid Discord CDN URL."},
            status_code=400
        )

    # Проверка heartbeat-запроса
    if url == HEARTBEAT:
        stats["cache_size"] = len(cache)
        return JSONResponse(content=stats, status_code=200)

    params = parse_qs(parsed_url.query)

    # Проверка на истечение срока действия ссылки
    if "ex" in params and "is" in params and "hm" in params:
        expires = datetime.fromtimestamp(int(params["ex"][0], 16))
        if expires > datetime.utcnow():
            stats["original"] += 1
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as image_response:
                    if image_response.status == 200:
                        content = await image_response.read()
                        return Response(content=content, media_type="image/png")

    file_name = os.path.basename(parsed_url.path)

    # Проверка наличия ссылки в кэше
    cached_url = cache.get(file_name)
    if cached_url and cached_url["expires"] > datetime.utcnow():
        stats["memory"] += 1
        async with aiohttp.ClientSession() as session:
            async with session.get(cached_url["href"]) as image_response:
                if image_response.status == 200:
                    content = await image_response.read()
                    return Response(content=content, media_type="image/png")

    payload = {"attachment_urls": [url]}
    headers = {
        "Authorization": settings.discord_token,
        "Content-Type": "application/json"
    }

    # Запрос к Discord API для обновления ссылки
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://discord.com/api/v9/attachments/refresh-urls",
                json=payload,
                headers=headers
            ) as response:
                if response.status != 200:
                    stats["exceptions"] += 1
                    return JSONResponse(
                        content={"message": f"Failed to refresh URL: {response.reason}"},
                        status_code=response.status
                    )
                refreshed_data = await response.json()
        except aiohttp.ClientError as e:
            stats["exceptions"] += 1
            return JSONResponse(
                content={"message": f"Failed to refresh URL: {str(e)}"},
                status_code=500
            )

    if refreshed_data and "refreshed_urls" in refreshed_data and refreshed_data["refreshed_urls"]:
        refreshed_url = refreshed_data["refreshed_urls"][0]["refreshed"]
        refreshed_parsed = parse_valid_url(refreshed_url)
        refreshed_params = parse_qs(refreshed_parsed.query)
        expires = datetime.fromtimestamp(int(refreshed_params["ex"][0], 16))

        # Сохранение обновлённой ссылки в кэше
        cache[file_name] = {"href": refreshed_url, "expires": expires}
        stats["refreshed"] += 1

        async with aiohttp.ClientSession() as session:
            async with session.get(refreshed_url) as image_response:
                if image_response.status == 200:
                    content = await image_response.read()
                    return Response(content=content, media_type="image/png")

    return JSONResponse(
        content={"message": "Unexpected response from Discord API."},
        status_code=500
    )

@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    # Загрузка изображения в канал Discord (использует ID канала из настроек)
    headers = {
        "Authorization": settings.discord_token
    }

    # Чтение содержимого файла
    file_data = await file.read()

    # Отправка файла через Discord API
    async with aiohttp.ClientSession() as session:
        try:
            form = aiohttp.FormData()
            form.add_field(
                "file", file_data, filename=file.filename, content_type=file.content_type
            )

            async with session.post(
                f"https://discord.com/api/v10/channels/{settings.default_channel_id}/messages",
                data=form,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_details = await response.text()
                    return JSONResponse(
                        content={
                            "message": f"Failed to upload file: {response.reason}",
                            "details": error_details
                        },
                        status_code=response.status
                    )

                response_data = await response.json()

                # Сохранение ссылки на файл в кэше
                attachment_url = response_data['attachments'][0]['url']
                cache[file.filename] = {
                    "href": attachment_url,
                    "expires": datetime.utcnow()
                }

                return JSONResponse(content={"url": attachment_url}, status_code=200)

        except aiohttp.ClientError as e:
            return JSONResponse(
                content={"message": f"Failed to upload file: {str(e)}"},
                status_code=500
            )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
