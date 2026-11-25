# Okna45 Store: GitHub Pages, приложения и обновления

Store **только скачивает** приложения и отдельные обновления ОС. Публикация — вручную с компьютера на GitHub: токены, запись через API и вкладка Publish не нужны. Постоянно работающий сервер не требуется. Для локальной сборки нужен **Python 3.10+**, без дополнительных библиотек; код приложений при сборке не выполняется.

**Адрес: <https://niktehnologes.github.io/okna45-store/>.** Новая доставка **только локально**: 13 apps / 12 OS variants, графическая **0.2.6 с исправлением неподвижной заставки** и отдельные EXE/APK. Онлайн каталог агент не изменяет. **[Сначала установка/restore/публикация](GUI_OS_026.md)**, затем [AI/Messenger/Snake](NETWORK_APPS.md). Pico HTTPS/heap ещё не проверены.

Начиная с **0.2.1** этот URL используется **по умолчанию в Store и apt**. Уже сохранённые сервер и apt-источник не перезаписываются чтением настроек; Save/Check приложений по-прежнему явно связывают apt с выбранным сервером Store. Файлы GitHub нужно загрузить вручную, опубликованный 0.2.0 не заменён агентом.

**0.2.6**: boot → graphics без PicoTerm, demand-loading/optional-string fixes сохранены. После первого кадра player отправляет только changed pixels, не отбрасывает подготовленный tile по missed deadline. С 0.2.4/старше нужен **host updater/bootstrap** для `.oba`; установленная 0.2.5 принимает system 0.2.6 штатно. Full SIN — `updates/0.2.6/`; 0.2.0–0.2.5 сохранены.

## Подготовить отдельный репозиторий GitHub

```powershell
python -B tools/build_store.py --refresh
python -B tools/deliver_release.py
```

Подготовленная папка — **`github_store/`**, сайт — **`github_store/docs/`**. Пока это локальные файлы: репозиторий и публичный deployment автоматически не создаются.

1. Используйте существующий публичный `niktehnologes/okna45-store`; создавать другой без необходимости не нужно.
2. Загрузите **содержимое `github_store/docs/`** в текущий Pages root или `/docs`. Не загружайте основной проект/flash/пароли/заметки, `catalog.json` храните локально.
3. Сохраните существующий Pages `main → /(root)` либо `main → /docs`. Старые blobs/packages/downloads не удаляйте; список — `uploads/PUBLISH_FILES.txt`.
4. Дождитесь Pages deployment. Адрес обычно `https://ВАШ_АККАУНТ.github.io/okna45-store/`, но берите фактический адрес из Settings → Pages.
5. В Store default URL уже задан; Setup/Save только для смены/старого override. Адрес сайта, не `github.com/...` или отдельного SIN.

Инструкция также лежит в `github_store/README.md`. Никакого workflow для приёма публикаций или ключа на Pico нет. Pages сам использует свой стандартный процесс deployment после ручной загрузки файлов. При недоступности Pages по плану/политике аккаунта подойдёт другой статический HTTP(S)-хостинг с теми же файлами.

## Локальный сервер — запасной вариант

```powershell
python -B store_server.py
```

- Адрес по умолчанию: **http://127.0.0.1:8787/**.
- При первом запуске берёт apps из `zerobook/repo/`, OS из `updates/0.2.5/`. Уже seeded catalog startup не перезаписывает; refresh вызывается явно при локальной подготовке.
- Данные сохраняются в `store_data/`. Эта папка **не выдаётся целиком** по HTTP: доступны только каталог и content-addressed `blobs/`. Ключи больше не создаются; если остался прежний `keys.json`, он не используется и не выдаётся.
- Чтобы Pico в локальной сети увидел сервер: `python -B store_server.py --host 0.0.0.0`. В ОС задайте **LAN IP компьютера**, например `http://192.168.1.10:8787`, не `127.0.0.1`. Разрешите TCP 8787 в firewall только своей сети.
- `--port`, `--data`, `--repo`, `--updates` меняют пути/порт; `--empty` запускает без первичного наполнения. Повторный старт не перезаписывает публикации начальными примерами.

Сервис read-only: прежние `POST /api/publish/*` возвращают **405**, утилита компьютера также не отправляет HTTP. Для проверки статической сборки на компьютере достаточно `python -B -m http.server 8787 --directory github_store/docs`; для Pico в LAN добавьте `--bind 0.0.0.0` и ограничьте firewall своей сетью. **HTTP не обеспечивает подлинность источника; SHA256 не является подписью.** Это личный каталог доверенных авторов.

## Подключить ОС

В эмуляторе запускайте **без `--offline`**, иначе HTTP отключён:

```powershell
python -B run_emu.py --sandbox --port 8002
```

Desktop загружается сам после пяти циклов заставки. Start → **System → Store**:

1. В **0.2.1+** действующий Pages уже выбран по умолчанию: в 0.2.3 нажмите **Apps → Check**. **Setup** нужен только для смены/старого сохранённого адреса: Server → ввод → Enter/Tab → Save. Для локального эмулятора с запасным сервером — `http://127.0.0.1:8787`; для Pico с локальным сервером — LAN IP компьютера.
2. Ключей нет: поля токена и вкладка Publish удалены. При сохранении настроек удаляется старое поле `token`, если оно оставалось от предыдущей версии.
3. В 0.2.3 **Apps → Check** обновляет только apt-каталог приложений; **OS → Check** — только каталог обновлений ОС. **Setup → Check** и `updates check` проверяют оба по очереди. **Save** требуется только после редактирования адреса. Во время сети списки текущей вкладки отпускаются; они восстанавливаются после задания. В первых версиях Check всегда проверял оба каталога.
4. **Apps**: выбрать строку, **Get** устанавливает/обновляет, **All** обновляет установленные приложения по одному, **Del** удаляет. `^ / v` или ↑/↓ в режиме ввода прокручивают каталог. `+` означает установлено. Закройте окна обновляемого приложения; его `/data/NAME/` сохраняется.
5. **OS**: Check → Sys/Soft → Apply, по одному каналу; размер/SHA256/download/staging/32 КиБ reserve проверяются до commit. Apply выгружает desktop, применяет, reset; Notes требуют Save/Discard/Cancel. **На старой ОС сначала host updater/bootstrap 0.2.5**, иначе `.oba` не разрешён. Guest full staging может не помещаться на ~800 КБ; используйте host updater, а не удаляйте данные.
6. **Stop** или закрытие Store отменяет загрузку, освобождает операцию и удаляет частичный файл. Скачанные целиком обновления сохраняются до Apply.

Настройки Store — `/system/store/config.json` (только адрес), downloads — `/system/store/downloads/`, список к применению — `/system/store/pending.json`. Обычные обновления ОС не меняют эти данные. HTTPS, реализация `urequests` с `stream=True`/`raw`, Wi‑Fi и доступный heap **ещё требуют проверки на физическом Pico**.

Аналогичные команды:

```text
updates check
apt install calculator
apt install stopwatch
apt install table
apt upgrade
updates download system
updates status
updates apply
```

`updates download system`/`software` — один канал. `all` только при достаточном месте; отказ второго не удаляет первый. `updates apply` из Console выгружает desktop/reset. Каналы независимы: второй failure не откатывает первый. Не подделывайте baseline; сначала разберите error/recovery.

Смена адреса: `updates server https://niktehnologes.github.io/okna45-store`. Локальный apt-пример: `apt source /repo/index.json`, затем `apt update`; HTTP для него не нужен. Store Check явно возвращает apt к каталогу выбранного Store-сервера.

Первое добавление Store на старый flash требует обоих актуальных `.sin`/bootstrap из [`UPDATES.md`](UPDATES.md). Дальнейшие загрузки идут с сервера. Для untracked-канала подходит только полный выпуск; delta выбирается только при совпадении учтённой версии.

## Notes и запуск собственных программ

Start → Tools → **Notes**:

- **New** → абсолютный путь, например `/scripts/hello.py` → Enter. Файл создаётся при **Save**, даже если пустой.
- **Open** загружает существующий файл; **Save As** сохраняет копию. Существующий чужой файл не перезаписывается через New/Save As — откройте его явно.
- `/scripts/*.py`, `/documents/` и некритические пользовательские `.py` редактируются. Системные файлы, `/system/`, `/repo/`, `/apps/` и неподдерживаемый текст остаются read-only.
- **Run** сохраняет `.py`, простой script/`run(term,args)` получает text window с print/input/scroll/Stop/Again; API — window. Minimized продолжает, close cancels/unloads. Files Open и Run разделены.
- Диалог пути принимает символы, Backspace/Delete, Enter и Esc; Tab переключает поле/указатель. В именах путей разрешены ASCII буквы, цифры, `_`, `-`, `.`, `/`, без пробелов и `..`. Код вводится ASCII; отступы — пробелами, Tab остаётся клавишей режима ОС.

Простой скрипт, написанный в Notes:

```python
name = input('Name: ')
print('Hello', name)
```

`print/input` идут в graphical text window/CardKB, не host console. `run(term,args)` с `term.write/input_line` совместим, generator уступает через yield. Arbitrary CPU loop/blocking call не прерываются Stop.

Минимальное окно — сохранить как `/scripts/window.py`:

```python
from ok45_api import Application

class Main(Application):
    title = 'My window'

    def semantic(self):
        return {'lines': ['Written in Notes!']}
```

Start → Tools → **Run**: ID, `/scripts/file.py [args]`, command. Auto распознаёт `Main(...)+ok45_api`/`MODE='gfx'` текстово; Win/Text/Full задают вручную. Full требует optional legacy files, исключённых из minimal runtime. Edit — Notes; нет Upload. Аргументы окна — `context.args`/`args`.

Из оболочки: `run /scripts/file.py [args]`; `run --terminal /file.py` и `run --gfx /file.py` принудительно выбирают режим. Оконный API и кооперативные задачи: [`DEVELOPER_API.md`](DEVELOPER_API.md). Вызовы, блокирующие интерпретатор, не становятся многозадачными от запуска через Run.

## Ручная публикация с компьютера

Сначала сохраните/скопируйте свой скрипт с Pico на компьютер обычным загрузчиком. `tools/publish.py` **подготавливает локальные файлы**, а не загружает их в GitHub:

```powershell
python -B tools/publish.py myscript.py --name myscript --version 1.0.0
python -B tools/publish.py mywindow.py --name mywindow --version 1.0.0 --type window
python -B tools/publish.py updates/0.2.3/todo-1.0.0.sin
```

Для другой папки сборки добавьте `--output ПУТЬ`; `--title`, `--summary`, `--category`, `--type auto|terminal|window|gfx` задают метаданные. Затем **вручную загрузите изменённые файлы `github_store/` в GitHub**, дождитесь Pages deployment и выполните Check в ОС. `--server`/`--token` больше не используются. Команда `publish` на Pico оставлена только как короткая подсказка, без сетевой записи.

Выпуски ОС явно отмечаются **`--os`** (это проверка типа файла, не сетевые права):

```powershell
python -B tools/publish.py updates/0.2.6/okna45-system-0.2.6.sin --os
python -B tools/publish.py updates/0.2.6/okna45-software-0.2.6.sin --os
```

Новая версия заменяет запись каталога. Повтор идентичной подготовки идемпотентен; **менять опубликованную версию нельзя** — увеличьте `major.minor.patch`. Имя `[a-z][a-z0-9_]*`, до 32 символов; имена ОС зарезервированы. Скрипты до **32768 UTF‑8 bytes**; несколько файлов/ресурсы — готовым app `.sin`. Сборщик не выполняет приложение.

`build_store.py` seeds только новый catalog; **`--refresh`** явно добавляет текущие apps и 0.2.4/0.2.5/current releases в existing catalog, same-version changed bytes запрещены. `publish.py` отдельно добавляет SIN/script. Старые docs/blobs/packages/downloads сохраняются; относительные URL работают в Pages subpath. `deliver_release.py` копирует verified downloads/guides/manifests, без сети.

**Если сайт разложен прямо в корне ветки main**, переносите **содержимое `github_store/docs/` в корень**, не внешнюю папку `docs`; Pages остаётся `main → /(root)`. Если используете `/docs` в GitHub, сохраняйте эту папку. Обновлённый `github_store/catalog.json` храните с компьютера для следующих сборок; старые blobs/downloads не удаляйте.

## Бюджет flash Pico W

По данным пользователя после MicroPython доступно около **800 КБ flash**, под установленную ОС — до **420 КБ**. Это **не RAM**. Консервативный контроль исходников использует 420000 байт; RAM RP2040 проверяется отдельно.

```powershell
python -B tools/check_flash.py
python -B tools/check_flash.py --build pico_runtime
```

Вторая команда необязательная: создаёт **только новую** папку обязательных файлов для свежей установки, не подключается к Pico и не стирает flash. Не копирует Wi‑Fi-пароль, заметки, локальный `/repo/`, `setup.py`, `NotMain.py` и необязательный `sdcard.py`; исходники остаются в основном проекте. Это не инструкция заменить весь существующий flash: обычные обновления — через каналы с сохранением данных. Сетевые библиотеки конкретной прошивки (`urequests`/NTP) и их место на flash учитывайте отдельно.

Аудит показывает **точную сумму байтов файлов** и отдельно грубую оценку округления до 4096 байт/файл. Windows «на диске» и эта оценка **не являются расходом LittleFS**: inline-файлы, блоки и metadata отличаются. К установленной ОС добавляются настройки, базы/каталоги, пользовательские приложения/данные и временные `.sin`/staging. Не расходуйте весь оставшийся объём на приложения; для текущего полного system-update оценочный временный запас — порядка **360 КиБ**, без гарантии для конкретного LittleFS.

Фактический расход: `df` в graphical Console либо пользовательский `mpremote run tools/pico_flash_usage.py` из REPL (прерывает ОС, ничего не пишет). Runtime 0.2.6: **279896 bytes / 409600-byte rounding estimate**, не замер LittleFS. До device measurement соблюдение 420 КБ **по реальной файловой системе** не заявляется.

## Консоль и быстрые проверки

- Оконная **Console/Packages**: `^ / v`, **End** к свежему выводу; в input mode ↑/↓ — строки, ←/→ — страница. Вывод ограничен **64 строками / 8192 bytes**; прокрутка работает и во время задания, набранная команда сохраняется.
- **Optional legacy PicoTerm**, не обычный boot: ↑/↓ — строки, ←/→ — страница, 64 ушедших ряда. Сырой fullscreen `readkey` сохраняет прежнее управление. Compatibility sources на host сохранены, из minimal flash исключены.

Короткий автоматический набор, без браузера/длинного запуска эмулятора:

```powershell
python -B tools/check_quick.py
```

Визуальное поведение и физические Wi‑Fi/HTTP, Pico heap, LittleFS и power-loss проверяет пользователь на устройстве. Успешные CPython/HTTP-проверки не являются аппаратным измерением.
