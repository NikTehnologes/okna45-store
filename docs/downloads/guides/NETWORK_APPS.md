# Сначала установка и публикация, затем AI / Messenger / Snake

## 1. Сначала исправить и обновить ОС

Для графической **Okna45 0.2.6 с исправленной RGB332-заставкой** используйте **[папку ОС/updater](GUI_OS_026.md)**: `uploads/os/Okna45-0.2.6`, `uploads/tools/Okna45-Updater.exe`. `repo` не переносится, данные не удаляются. 0.2.0–0.2.5 сохранены. С 0.2.4/старше нужен host updater/bootstrap: старый Store не знает `.oba`. Установленная 0.2.5 принимает system 0.2.6; app SIN не пересобираются ради этого.

## 2. Обновить каталог магазина вручную

Доставка подготовлена в **`github_store/docs/`**. GitHub агент не менял.

1. Откройте свой `niktehnologes/okna45-store` → Add file → Upload files.
2. Pages **main → /(root)**: содержимое `github_store/docs/` загрузить в корень. Pages **main → /docs**: в `docs/`. Сохраняйте старые файлы/структуру.
3. Для app-only нужны актуальный **`index.json`**, **`packages/ai-1.0.0.sin`**, **`packages/messenger-2.0.0.sin`**, **`packages/snake-1.0.1.sin`** и соответствующие новые **blobs**. Точный список — [`uploads/PUBLISH_FILES.txt`](../PUBLISH_FILES.txt).
4. Если первые пять дополнительных игр/Checklist ещё не выложены, загрузите также их пять SIN/blobs: новый index содержит **13 пакетов**, ни один указанный payload не должен отсутствовать.
5. Для всей доставки проще загрузить **содержимое `docs/` без удаления старых файлов**. `downloads/` содержит OS ZIP, updater, Messenger EXE/APK и инструкции; `updates.json` и OS blobs — независимые каналы ОС. Затем вручную подтвердите загрузку и дождитесь Pages deployment.

Старый **snake-1.0.0.sin** и blob сохранены: initializer изменился, поэтому текущая доставка имеет версию **1.0.1**, а не заменяет старые байты. `catalog.json` остаётся на компьютере. Не публикуйте `wifi.json`, UUID/истории Messenger, `/data/`, основной проект или debug signing key.

## 3. Установить / запустить Pico-приложения

1. Start → Network → WiFi → Scan / SSID / Key → Save / Link.
2. Start → System → Store → **Apps → Check**, выбрать `ai`, `messenger` или `snake` → **Get**. Сайт задан по умолчанию: `https://niktehnologes.github.io/okna45-store`; сохранённые настройки имеют приоритет.
3. После установки запустите значок, **Start → Network → AI/Messenger**, **Start → Games → Snake**, либо **Run** с ID. Apps/Get и `apt install NAME` устанавливают, а не запускают автоматически.
4. Перед вводом/стрелками в приложение **Tab → Input**; Tab возвращает указатель. Готовые заглавные/символы CardKB поддерживаются, Ctrl/Shift-события не нужны.

Через графическую Console:

```text
apt update
apt install ai
apt install messenger
apt install snake
open ai
open messenger
open snake
```

Независимые offline SIN лежат в **`uploads/apps/2026-11-24/`**:

| Приложение | SIN | Байты | SHA256 |
|---|---|---:|---|
| AI | `ai-1.0.0.sin` | 12144 | `3b81ff1949fadf0e62b1c6b26c7b3a415fc3e4ebb19754806bdf93703482882d` |
| Messenger Pico | `messenger-2.0.0.sin` | 30587 | `e81c522542e3479a8d27bfd7dc56d3b6d25bcd8ea6b73cc4cc681c9e06e53c13` |
| Snake | `snake-1.0.1.sin` | 6101 | `e2420bf30c13b4616c440c55bd44a1c22fd1a0c69c1ff0b24b8e92c4373c5137` |

Скопируйте только выбранный SIN обычным загрузчиком в Pico, перезагрузите и в Console выполните, например **`install /ai-1.0.0.sin`**; или выберите app SIN в Files → Open. Контейнер удаляйте вручную только после успешной установки. Offline установка не проверяет TLS. `repo` не требуется.

Store SIN меняет `source` в manifest на `blobs/SHA256`: его контейнерный хэш может отличаться от исходного SIN, payload-код/хэш совпадают. Используйте `uploads/SHA256SUMS.txt` для uploads, `github_store/docs/downloads/SHA256SUMS.txt` для копий сайта.

## 4. Windows EXE и Android APK — готовые сборки

| Платформа | Готовый файл | Как запустить |
|---|---|---|
| Windows x64 | [`uploads/messenger/windows/Okna45-Messenger-v2.exe`](../messenger/windows/Okna45-Messenger-v2.exe) | Запустить; Python не требуется. EXE без издательской подписи, Windows может показать предупреждение о неизвестном издателе |
| Android 6.0+ | [`uploads/messenger/android/Okna45-Messenger-v2-2.0.0-debug.apk`](../messenger/android/Okna45-Messenger-v2-2.0.0-debug.apk) | Перенести на телефон и вручную установить из доверенного файлового менеджера; это подписанный **debug APK**, не Play/release-доставка |

Android — **нативная Java**, без Python/Qt внутри. Windows — Python/PySide6, Qt runtime включён. Это новые клиенты совместимого v2 протокола, не побайтовая упаковка старого интерфейса. Оригинальные **`messenger/v1/` и `messenger/v2/`** не менялись.

1. Запустите клиент → **Мой ID**, отправьте UUID другу другим каналом.
2. **Добавить** → UUID друга → открыть контакт. Отправка — явная кнопка Send/Отправить.
3. Открытый чат автоматически опрашивается с номинальным интервалом **500 мс**; Pause/Live/Sync управляют опросом. Один сетевой запрос за раз, ошибочные send не повторяются автоматически, черновик не удаляется до подтверждения.
4. Windows продолжает polling при сворачивании и дожидается текущего запроса перед закрытием. Android сохраняет таймер открытого чата при уходе в фон, **но Android/Doze может задержать или остановить процесс**; постоянные background 500 мс без foreground service не обещаются.

Данные Windows: **`%LOCALAPPDATA%\Okna45\Messenger-v2\`**, кнопка «Папка данных». `number.txt`, `data.json`, `chats/`, `receipts/`. Windows «Импорт v2» читает выбранную старую папку с `number.txt/data.json/chat.json`, создаёт backup текущих данных и не меняет исходную папку. Остановите старый клиент перед использованием импортированного UUID. Android хранит данные в приватной папке приложения; его удаление обычно удаляет эти данные. Импорт старой desktop-папки в Android в этой версии **не реализован**.

**Не запускайте два получателя одного UUID для одного peer-чата:** `/g` забирает общую очередь, они будут конкурировать за сообщения. Сетевые connect/read таймауты — 10 с, это не строгая верхняя граница DNS/всей операции.

Непустой сырой ответ сохраняется перед декодированием. При ошибке Live останавливается, receipt/частичный ответ сохраняется; Sync сначала восстанавливает полный receipt без двойного добавления. Неполный `.part` не удаляется автоматически. Пустые нормальные polling-ответы не вызывают сохранение истории; Windows/Android держат маленький ответ в RAM и не пишут пустой poll на storage.

Бинарники успешно собраны, но **не проходили ручную проверку на вашем Windows/телефоне или живом сервере**. При следующей версии Android используйте тот же signing key; debug key не является release-key для магазина.

## Приложения — после инструкции

### AI Chat Lite — `ai` 1.0.0

- Основной провайдер **LLM7**: `https://api.llm7.io/v1/chat/completions`, модель `gpt-oss:20b`.
- Альтернатива **Pollinations**: `https://text.pollinations.ai/`, переключение вручную кнопкой провайдера. Нет скрытого отправления того же диалога второму провайдеру после ошибки первого.
- Нет сети при открытии. **Только явный Send/Enter** отправляет текст. До 160 ASCII-символов черновика; до шести сообщений и 2048 UTF-8 байт content; Save, Stop, Clear и прокрутка. Данные в `/data/ai/`.
- Не посылайте секреты/пароли: провайдер получает переданную историю. Ответы API/доступность модели на эту дату живыми запросами не проверялись. TLS Pico требует совместимого `urequests(stream=True, raw, timeout)` и heap.

### Messenger v2 — `messenger` 2.0.0

Сервер **`https://zx700ai.alwaysdata.net/`**, совместим с предоставленным `server.py`:

- `/s`: `{"message": json.dumps({"key": MY_UUID + PEER_UUID, "b64urlm": URLSAFE_BASE64_TEXT})}`.
- `/g`: `{"message": PEER_UUID + MY_UUID}`; ответ `status:ok`, список Base64 или `MessageNotFound`.
- Pico начинает с offline контактов: восемь UUID, один открытый peer; чат автоматически опрашивается **500 мс, включая свёрнутое окно**. Pause / Live / Sync; открытые HTTP/TLS могут задерживать весь cooperative desktop. Опрос/Store/install не запускаются параллельно.
- Отправка до 160 ASCII-символов. Один входящий message до 1024 UTF-8 bytes; история до 16 сообщений / 4096 content bytes, saved chat до 8192 bytes; raw cap 32 КиБ. Данные в `/data/messenger/`, My ID сохраняется между запусками.
- Pico `inbox.json`/`inbox.part` — **не plain JSON**: впереди 54-byte peer/token receipt header, затем raw server response. Сохраните файл целиком для восстановления. Ошибка/неполный ответ приостанавливает live, неопределённый send не повторяется сам.

**Ограничение сервера принципиальное:** `/g` удаляет очередь **до отправки HTTP-ответа**. Обрыв до получения bytes может потерять сообщения; клиентский receipt не добавляет серверные ACK/message IDs. Нет авторизации UUID, E2EE или подтверждения доставки получателю. HTTPS защищает транспорт, не заменяет эти свойства. Все server-side исправления потребовали бы отдельного согласованного изменения протокола; сервер не менялся.

### Snake Lite — `snake` 1.0.1

20×14 клеток, integer-координаты, фиксированный массив тела **560 bytes** (`array('H', ...)`), общий compositor без собственного framebuffer. Начинает на паузе: Enter/Space/P или Play; стрелки/WASD меняют направление, R/New перезапускает. Свёрнутая запущенная игра продолжает шаги, Pause нужно нажать явно. 560 bytes — только массив тела, не суммарная RAM приложения.

## Повторная сборка только при изменении исходников

```powershell
python -B tools/build_repo.py
python -B tools/build_apps.py ai messenger snake --output uploads/apps/НОВАЯ_ПАПКА
```

Сначала увеличьте version изменённого приложения. Сборщик отказывается менять уже существующий same-version SIN; старые OS release directories неизменяемы. Windows source/build — `messenger/windows/`; Android Gradle-проект — `messenger/android/` (JDK 17, SDK 35, Android Gradle Plugin 8.7.3 / Gradle 8.9+). Android `build.ps1` принимает `-Sdk`, `-Gradle`, `-JavaHome`; проект соседа использовался только как источник установленных инструментов. Если локальная PowerShell policy запрещает `.ps1`, запускайте Python PyInstaller / Gradle напрямую, не меняйте глобальные security policies ради сборки.
