# Okna45 / ZeroBook: краткая инструкция для LLM

## Подключение

Панель и API: `http://127.0.0.1:8000`. Описание: `GET /api/v1/capabilities`; схема: `GET /api/v1/openapi.json`.

Для ручной проверки без сети:

```powershell
python -B run_emu.py --sandbox --deterministic --offline
```

`--sandbox` — копия флеша, не изоляция вредоносного Python. `--offline` не блокирует произвольные сокеты.

**Автоматические проверки — только коротким скриптом `python -B tools/check_quick.py`; долгие браузерные/полные прогоны — только по просьбе пользователя.** Store HTTP требует запуска **без `--offline`** и доступного статического GitHub Pages/HTTP(S)-сайта; запасной сервер — `python -B store_server.py` (8787). Инструкция: [`STORE.md`](STORE.md). Подготовка репозитория локальная, создание/загрузка GitHub — вручную; не выполнять сетевые публикации за пользователя.

## Рабочий цикл

1. Прочитайте `GET /api/v1/state`. Сохраните `session_id`.
2. Дождитесь `ready=true`: `POST /api/v1/wait` с `{"until":"ready","timeout":15}`. В 0.2.6 до этого пять циклов (~9,7 s + initial draw/завершение tile), desktop ещё не импортирован. Ready/счётчик screen_version сами по себе **не доказывают движение анимации**.
3. Для команды отправьте `POST /api/v1/command` с `command`, стабильным `request_id`, `wait` и `timeout`.
4. Читайте **`job.output`**, а не только последние строки на экране. Для графики используйте PNG; подписи не описывают все пиксели.
5. В приложении или диалоге отправляйте `/keys`, а не новую `/command`.

```python
from ztest import Client

c = Client()
assert c.wait('ready', timeout=15)['matched']
r = c.command('info', request_id='agent-info-001', timeout=10)
if r['timed_out']:
    r = c.job(r['job']['id'], wait='complete', timeout=10)
print(r['job']['output'])

app = c.command('cube', wait='input', timeout=10)
c.screenshot('shots/agent-cube.png', scale=1)
c.keys(['ESC'])
assert c.wait('ready', timeout=10)['matched']
```

## Рабочий стол Okna45

**0.2.6 загружается в desktop автоматически**, после RGB332-заставки; `desktop` не нужен. `/desktop` — **наблюдение, не управление**. `/command` при idle pointer ставит текст в настоящую очередь CardKB; observer открывает graphical job, не скрытый host exec. В input mode вводите через `/keys`, чтобы не затереть чужой черновик. Полное описание: [`CONTROLS.md`](CONTROLS.md).

- **CardKB не передаёт Ctrl/Shift/Alt-события.** Заглавные и спецсимволы — обычный готовый ASCII-текст. Старые Ctrl-команды окон удалены.
- `input_mode='pointer'`: стрелки двигают на `pointer.step`, Enter нажимает под остриём. Tab — input, Esc — Start, не PicoTerm; диалог Esc отменяет.
- `input_mode='input'`: стрелки/символы/Enter получает приложение, `~` тоже текст. Tab/Esc — pointer. Reset/maintenance отдельно требуют Save/Discard/Cancel для Notes.
- `input_mode='move'`: окно взято за заголовок; стрелки сдвигают окно вместе с указателем, Enter завершает перенос.
- `/desktop` содержит `pointer.target`, taskbar `controls`, `menu.tabs/entries/controls`, `applications`, `icons`, `windows[].controls/content.controls`. Прямоугольники `[x,y,w,h]` в **320×240**. Сначала наведите остриё реальными стрелками, затем Enter.
- Start: выберите `applications[].category` нужной программы, нажмите соответствующий `menu.tabs`, затем плитку `menu.entries`. По 6 плиток/страницу; используйте `page_prev/page_next` из `menu.controls`. Не применяйте координаты старого плоского меню.
- Установленные программы: window — API-окно, обычный terminal/script — graphical text window с print/input/scroll/Stop/Again; desktop остаётся. Full/Gfx — optional compatibility, не resident PicoTerm. Значки под окнами не нажимаются: hit-testing верхнего окна приоритетнее.
- Notes: `content.caret` содержит строку, колонку, scroll, rect и фазу мигания. В input курсор мигает; для статического PNG можно вернуться в pointer mode. WiFi `semantic` содержит лишь длину/маску пароля, но file API конфигурацию не шифрует.
- Переключение и восстановление окна — его кнопка панели задач, **не Tab**. `Save`, `Input`, `Pause`, `Cancel` — экранные кнопки; неактивные имеют `enabled=false`.
- `keys_processed` — курсор **завершённой обработки** клавиш. После `/keys` дождитесь нужного значения и состояния; `accepted` подтверждает только очередь. Для снимка дождитесь `renderer.pending == 0` у неподвижных окон. Для задач с анимацией очередь может постоянно пополняться.
- Диалог Notes: кнопки Save/Discard/Cancel или готовая буква Y/N **без Enter**. Esc/Cancel отменяет и закрытие, и запрос выхода. Ошибка сохранения оставляет диалог открытым. Старый `edit` по-прежнему требует Y/N **с Enter**.
- Notes New/Open/Save As: `content.dialog` — действие файла, `filename` — поле; печатайте путь в input mode, **Enter подтверждает**, Tab переключает указатель/поле, Esc отменяет. Не отправляйте Y/N как ответ сохранения, пока активен диалог имени. Пользовательские `.py` редактируются; Run сначала сохраняет и запускает.
- Run (`run_app`) — путь/команда/ID; Store (`store`) — **Apps/OS/Setup**, `read_only=true`. OS Sys/Soft отдельные, Apply unload/reboot. **0.2.4/старше → 0.2.6 только host updater/bootstrap**, старая `.oba` allowlist несовместима; 0.2.5 понимает новый system. После нового session_id сбросьте курсоры.
- С 0.2.1 Store/apt по умолчанию используют `https://niktehnologes.github.io/okna45-store` (apt — `/index.json`), ручной ввод/Save не нужны перед первым Check. В 0.2.3 **Apps → Check** проверяет только приложения, **OS → Check** — только ОС, **Setup → Check**/`updates check` — оба по очереди. Сохранённые источники имеют приоритет при чтении; Save/Check приложений явно выбирает источник Store. Для офлайн apt-примера выполните `apt source /repo/index.json`; не менять пользовательский источник ради теста.
- Console/Packages/text scripts: `content.scroll/max_scroll`; ↑/↓ — строка, ←/→ — страница **в input mode**, End — свежий вывод. TextGrid/history доступны только в optional legacy. Не принимайте старые строки за свежий output.
- Текстовое наблюдение включает `input_mode`, положение указателя, меню, окна и статус. Это состояние гостя; графический результат проверяйте PNG.

Guest API — [`DEVELOPER_API.md`](DEVELOPER_API.md); установка — [`GUI_OS_026.md`](GUI_OS_026.md), SIN — [`UPDATES.md`](UPDATES.md), Store — [`STORE.md`](STORE.md). App install/apt идут в Console; core Apply — только после unload desktop/reboot. SHA256 не подпись. Не трогайте пользовательский sandbox: отдельная копия/порт.

Текущий ремонт: полный manifest **0.2.6**, не старый список 11 модулей. 0.2.0–0.2.5 и Archive/v1 не перезаписывать. Локальный Store: **13 packages / 12 OS variants**, ручная публикация; `--refresh` явный. AI 1.0.0/Messenger 2.0.0/Snake 1.0.1 unchanged. Только fake responses; без live AI/messages/physical writes. `_ORIG` исключён, источник LoadAnimation.gif.

Boot OBA2: 17183 bytes, все 96 кадров/задержки, 5 циклов, elapsed-time выбор без очереди. **0.2.6 не отбрасывает tile после decode**, только переключает время между commits; rotating cursor предотвращает starvation. Initial один раз, потом only changed pixel runs в LCD GRAM. Buffer 2560 + palette 512 + dirty map 160 + resident index 1868, native window 512 — не суммарный heap. Одно offline-наблюдение Pico-модели показало 36 разных LCD состояний, не hardware FPS. После unload desktop stripe 5120. Stop/generators cooperative, blocking/CPU loop не preemptible.

## Важные правила

- `/command` требует idle pointer/свободного legacy prompt. Активный graphical input, незавершённый job или чужая ожидающая команда дают 409. Запущенные фоновые окна сами по себе не разрешение перезапустить ОС.
- `wait=complete` ждёт завершения и возврата приглашения; `input` разрешает также `interactive`/`waiting_input`; `none` только ставит задачу в очередь.
- **HTTP 202 / `timed_out=true` не отменяет выполнение.** Сохраните ID и читайте `/jobs/{id}?wait=complete&timeout=10`. Не повторяйте команду с новым ID вслепую.
- Если ответ потерялся до получения ID, повторите **тот же** `request_id` и ту же команду. Защита действует пока задача хранится в истории (128 задач), а не бессрочно.
- `session_id` изменился — это другой процесс: старые ID задач и курсоры больше не соответствуют ему.
- `/events?after=N` и `/logs?after=N` экономят трафик и токены. Используйте `next`, проверяйте `truncated` и `cursor_reset`.
- Только ASCII-текст. Пакеты клавиш принимаются атомарно; максимум очереди — 4096.
- `ENTER=13`, `ESC=27`, `TAB=9`, `BACKSPACE=8`, `DELETE=127`; CardKB: `LEFT=180`, `UP=181`, `DOWN=182`, `RIGHT=183`. `CTRL_C` остаётся только старым API-алиасом Esc, не комбинацией CardKB.
- В старом редакторе `edit` навигация `hjkl`; Esc может вывести `Save?`. Для ответа: `{"text":"y","enter":true}`.
- `/flush` удаляет только ещё не обработанные клавиши. Esc отменяет уже набранную строку. Reset может потерять несохранённый редактор; не используйте его вместо обычного выхода без необходимости.
- `/files` и `/file` только читают флеш. Запись выполняется реальными командами ОС и клавиатурным вводом.
- `TextGrid` описывает терминал; `display_annotations` — подписи графики, `Okna45 windows` — модель гостевых окон. PNG/пиксельный снимок авторитетнее для графических проверок.
- Для обычных задач не читайте видеопоток: используйте текст, вывод задач и редкие PNG. `/display/stream` нужен именно для анализа промежуточной графики.
- Профиль `pico` приближённый, CPU ещё не калиброван по физическому устройству. `DISPLAY fps` — частота показа изменений RAM, не скорость CPU или число готовых кадров приложения.
- Flash пользователя: около **800 КБ** после MicroPython, под ОС **420 КБ**; это не RAM. `python -B tools/check_flash.py` считает runtime байты и отдельно примерное блочное округление, не фактический LittleFS. Не копировать старый установщик/локальный repo в обязательный runtime и не стирать существующие данные; небольшой flash обновлять по одному каналу.

CLI поддерживает `--json` до или после подкоманды. Коды выхода: 0 — успешно, 1 — ошибка гостевой задачи, 2 — ошибка клиента/API, 3 — истекло ожидание (задача не отменена).
