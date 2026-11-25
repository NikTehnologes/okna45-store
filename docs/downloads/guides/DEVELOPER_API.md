# Okna45: API приложений v1

ОС **0.2.6**, публичный модуль `ok45_api` (API v1 без изменений). Доверенные приложения работают в одном MicroPython-интерпретаторе с ОС: это **не security sandbox**. Установка/обновление — [GUI_OS_026.md](GUI_OS_026.md).

## Минимальное окно

```python
from ok45_api import Application, ENTER

class Main(Application):
    interval_ms = 1000

    def __init__(self, context, window):
        super().__init__(context, window)
        self.count = 0

    def controls(self):
        return self.toolbar((('add', 'Add'),))

    def activate(self, control):
        if control['action'] == 'add':
            self.count += 1
            self.invalidate()

    def key(self, code):
        if code == ENTER:
            self.activate({'action': 'add'})

    def semantic(self):
        return {'count': self.count, 'lines': ['Count: %d' % self.count]}
```

Рабочий пример: `zerobook/repo/files/counter.py`. `apt update`, `apt install counter`; затем Start → Apps → Counter. Автономный пакет: `updates/0.2.0/counter-1.0.0.sin`.

## Жизненный цикл

| Метод / поле | Контракт |
|---|---|
| `Main(context, window)` | Конструктор; `window.id`, `window.rect`, `window.client()` доступны сразу |
| `key(code)` | Готовый ASCII-символ или CardKB-код в режиме ввода |
| `tick()` | Короткий периодический шаг; `interval_ms` ограничивается 20–60000 ms |
| `draw(canvas, rect)` | Повторяется для отдельных повреждённых полос; не менять состояние и не писать файлы |
| `invalidate(rect=None)` | Запрос рисования client-области или абсолютного прямоугольника |
| `controls()` | Список `{action,label,rect:[x,y,w,h],enabled,selected}`; `button:false` для строк/полей |
| `toolbar(((action,label), ...))` | Нижний ряд кнопок; базовый `click()` проверяет `enabled` и вызывает `activate()` |
| `semantic()` | Маленький JSON-совместимый словарь; `lines` рисует базовый класс и читает LLM |
| `moved(dx,dy)`, `mode_changed()` | Базовый класс запрашивает перерисовку |
| `close()` | `True` разрешает закрытие; `False` оставляет окно для собственного подтверждения |

Canvas: `fill(rect,color)`, `text(x,y,text,color)`, `line(x0,y0,x1,y1,color)`, `bevel`, `button`, `icon`. Координаты абсолютные, **320×240**; рисование ограничено client-областью и текущей полосой. Из API экспортируются `rgb`, `BLACK`, `WHITE`, `LIGHT`, `SILVER`, `SHADOW`, `NAVY`, `GREEN`, `TEAL`, `WIDTH`, `HEIGHT` (RGB565).

Desktop использует **одну RGB565-полосу 5120 байт**; clipped FrameBuffer — view этой памяти. Boot RGB332 — отдельный этап: buffer 2560 и dirty map 160 bytes, GRAM дисплея сохраняет фон, после initial отправляются только changed pixels; всё освобождено до desktop. Не храните Canvas между вызовами и не рисуйте напрямую SPI/`term.gfx` из окна.

CardKB: `ENTER=13`, `ESC=27`, `TAB=9`, `BACKSPACE=8`, `DELETE=127`, `LEFT=180`, `UP=181`, `DOWN=182`, `RIGHT=183`. Ctrl/Shift/Alt-событий нет; заглавные и символы — готовый ASCII. Tab/Esc обрабатывает ОС. Стрелки и Enter получает приложение только в input mode.

## Context

- `data_path(relative='settings.json')` → `/data/PACKAGE/relative`.
- `read_text(relative, default='', limit=8192)`, `save_text(relative,text)`; максимум 8192 UTF‑8 байт/файл.
- `load_json(relative='settings.json', default=None)`, `save_json(value, relative='settings.json')`.
- `spawn(name,iterator)` → ID. Генератор уступает `yield DELAY_MS` или `yield None`; `pause(id,paused=True)`, `cancel(id)` разрешены только для своего окна. Закрытие окна отменяет его задачи; освобождайте ресурсы в `try/finally` генератора.
- `launch(app_id, path=...)`, `applications()`, `input(enabled=True)`, `status(text)`.
- `localtime(seconds=None)`, `timezone()`; UTC RTC + фиксированное смещение, без автоматического DST.
- `network()` → WiFiService: `scan`, `connect(ssid,password)`, `poll`, `save(ssid,password)`, `off`, `snapshot`.
- `ticks_ms`, `ticks_diff`, `ticks_add` экспортируются для таймеров.

Код встроенных приложений теперь загружается по одному размеченному блоку из `/ok45_apps.py`, только при открытии; **не импортируйте `ok45_apps` как общий API**. Несколько окон одной программы делят её класс; последнее закрытое окно освобождает код и данные. Свёрнутое окно остаётся запущенным. Store/WiFi/Run импортируются отдельно; временные installer/network-модули выгружаются, когда не нужны. Модули, загруженные до desktop, и зависимости неизвестного пользовательского приложения не удаляются во время его работы. При выходе освобождаются окна, задачи и RGB-полоса. Публичный `ok45_api.Application`/`Context` не изменён.

Задачи **кооперативные**. Блокирующий код, NTP, CYW43 `scan()` и HTTP могут задержать весь desktop. Heap и время требуют проверки на Pico. Ошибка генератора отражается в Tasks; неисправный `draw()` способен остановить compositor. Не включайте секреты в `semantic`, status или labels.

## Launcher metadata

Добавьте в пакет apt или SIN:

```json
"desktop": {
  "title": "Counter", "type": "window", "category": "Apps",
  "entry": "apps/counter/main.py", "class": "Main", "api": 1,
  "size": [232, 150], "singleton": true,
  "icon": ["..####..", ".#....#.", "#..##..#", "#...#..#",
           "#..##..#", "#......#", ".#....#.", "..####.."]
}
```

`entry` — `.py`, принадлежащий пакету. Размер окна 160–312 × 100–196; категории **Tools, System, Network, Games, Apps**. Название 1–28 печатных ASCII-символов. Иконка 8×8 (увеличивается ×2) или 16×16: `.` прозрачно, `#` основной цвет, `+` акцент.

Без `desktop` пакет с корневым `NAME.py` получает terminal-launcher и стандартный значок: обычный script/`run(term,args)` открывает графическое текстовое окно, desktop остаётся активен. Data-only пакет не получает launcher. Первые 12 программ получают desktop icons; Start содержит все, по 6 на страницу. Реестр обновляется после операций в Console.

Terminal metadata поддерживает `"mode":"auto"|"terminal"|"gfx"` (по умолчанию auto). Launcher использует `run /NAME.py`: module-style `run(term,args)` и простой `print/input` получают text window с scrolling/Stop/Again. Generator `run` уступает управление через `yield DELAY_MS`; `input` прокачивает остальные tasks. `MODE='gfx'`/Full остаётся optional fullscreen, требует `ok45_legacy.py` и совместимых legacy sources, не входит в минимальный runtime.

## Программа прямо из Notes

Пакет для личного скрипта не требуется: **New → `/scripts/myapp.py` → Save → Run**. Оконный скрипт определяет `class Main(Application)` и импортирует `ok45_api`; Context имеет `args`. Данные идут в `/data/script_ИМЯ/`, tasks привязаны к окну. Auto-проверка текстовая; Run → Win выбирает вручную. Обычный `print/input` направляется в text window. `.mpy` не редактируемый source. Files → Open просматривает, Run запускает. Подробнее: [`STORE.md`](STORE.md).

**Stop не является preemptive interrupt.** Он отменяет cooperative generator между yield и ожидание input; `while True: pass`, blocking socket/time.sleep могут заморозить весь desktop. Закрытие освобождает код/данные после отмены tasks, сворачивание не отменяет и не unload. Нельзя обещать устранение ENOMEM только host-тестами.

Пакеты: `[a-z][a-z0-9_]*`, до 32 символов. Файлы: некритические корневые `.py` или `apps/NAME/...`. До 8 файлов/пакет, 32768 байт/файл, 65536 байт/транзакция, до 32 пакетов. Файл имеет `path`, безопасный относительный `source`, `size`, `sha256`; версии `major.minor.patch`, `depends` — до 8 имён. Закройте окна пакета перед обновлением/удалением; `/data/NAME` сохраняется.

## Собрать software `.sin`

```python
import hashlib, json
from pathlib import Path
from tools.build_updates import write_bundle

repo = Path('my-repository')
manifest = json.loads((repo / 'index.json').read_text(encoding='utf-8'))
payloads = []
for package in manifest['packages']:
    for file in package['files']:
        data = (repo / file['source']).read_bytes()
        file['size'], file['sha256'] = len(data), hashlib.sha256(data).hexdigest()
        payloads.append(data)
write_bundle(Path('my-app.sin'),
             {'format': 1, 'kind': 'software', 'packages': manifest['packages']}, payloads)
```

Для встроенного примера: `python -B tools/build_repo.py`, затем `python -B tools/build_updates.py`. Формат/обновления: [`UPDATES.md`](UPDATES.md). SHA256 проверяет целостность, **не автора**. `/api/v1/desktop` read-only; люди/LLM активируют ваши controls через CardKB `/keys`.

Репозиторий содержит **13 приложений**. Для новых optional apps — `build_repo.py`, затем `build_apps.py ai messenger snake --output uploads/apps`, только выбранные SIN, без перезаписи OS/bootstrap. Same-name changed container запрещён; сначала поднимите package version. `build_updates.py` нужен для **новой версии ОС**, не для app-only этапа.

**[Первые приложения и ремонт](STORE_APPS.md)**; **[AI/Messenger/Snake: инструкция перед приложениями](NETWORK_APPS.md)**. `tools/publish.py` на компьютере **только готовит локальный статический каталог** из app SIN/исходника, затем владелец вручную загружает файлы на GitHub Pages. Публикации с Pico, токенов и сетевого write API нет. Сборщик не выполняет код; пользователи устанавливают только доверенные программы, которые выполняются с привилегиями ОС.
