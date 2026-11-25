# Сначала установка: Okna45 0.2.6 — исправленная RGB332-заставка

## 1. Установка / ремонт / обновление выбором папки

| Доставка | Путь |
|---|---|
| Полная папка версии | [`uploads/os/Okna45-0.2.6/`](../0.2.6/Okna45-0.2.6/) |
| ZIP папки | [`uploads/os/Okna45-0.2.6.zip`](../0.2.6/Okna45-0.2.6.zip) |
| Windows updater с поддержкой OBA2 | [`uploads/tools/Okna45-Updater.exe`](../tools/Okna45-Updater.exe) |
| Python / launcher | [`tools/update_os.py`](../tools/update_os.py), [`tools/update_os.cmd`](../tools/update_os.cmd) |
| Независимые SIN / USB bootstrap | [`updates/0.2.6/`](../0.2.6/) |
| Список ручной публикации / SHA256 | [`uploads/PUBLISH_FILES.txt`](../PUBLISH_FILES.txt), [`uploads/SHA256SUMS.txt`](../SHA256SUMS.txt) |

1. Сохраните открытые Notes/черновики. Для первой установки сохраните полную личную копию flash: backup updater содержит заменяемые ОС-файлы, **не все пользовательские данные**.
2. Закройте Thonny/mpremote/другие USB editors. Для папки флеша остановите использующий её эмулятор.
3. Распакуйте ZIP. В updater выберите **`Okna45-0.2.6` с `os-files.json`**, не внутреннюю `files/`.
4. Выберите Pico COM либо конкретную папку flash и подтвердите. **RPI-RP2 — не диск Python-файлов.** Дождитесь backup/проверки/установки.
5. Backup — `%USERPROFILE%\Okna45-backups\...\`; после успешного USB update Pico перезапускается.

**С 0.2.4 и старше нужен этот новый host updater либо USB bootstrap.** Старый guest Store не знает `ok45_bootanim.oba`; Software first это не исправляет. Уже установленная 0.2.5 понимает OBA2: исправление player можно применить system SIN 0.2.6 штатно. Выпуск содержит оба **full канала 0.2.6**; software sources не изменились, но контейнер новой версии синхронизирует baseline. Для fresh install host папка содержит всё необходимое. Не удаляйте/подделывайте базы версий.

```powershell
python -B tools/update_os.py
python -B tools/update_os.py --release uploads/os/Okna45-0.2.6 --port COM5
python -B tools/update_os.py --release uploads/os/Okna45-0.2.6 --folder F:/PicoFlash
```

Замените COM/путь своими. Python 3.10+; USB требует `pyserial`, EXE уже включает его. Агент устройство не прошивал.

### Защита и restore

`os-files.json` — host allowlist: root `path/source/channel/size/sha256`, `delete_unlisted:false`. Только перечисленные Python-модули и **один именованный system asset** OBA2; произвольные `.oba`/JSON/каталоги не разрешены. Хэши проверяются до/после замены. `repo` не копируется, существующие repo/settings/notes/scripts/apps/data не удаляются.

- Unknown/modified ОС-файлы и drivers/recovery требуют явного разрешения; прежние bytes сохраняются.
- Pending journals блокируют update: сначала штатное recovery. `.mpy` shadows проверяются только для `.py`.
- Stable `boot.py`, `ok45_boot.py`, `ili9341.py` не изменены относительно 0.2.5; обычный SIN их не заменяет.
- Проверенные system/software/host baselines синхронизируются с записанными backup; нельзя фальсифицировать JSON для обхода protection.
- Host update — последовательные temporary-file/rename операции, `main.py` последним, **не whole-device atomic transaction**.

При ошибке rollback только начатых замен. При USB/power loss не загружайте смешанную ОС: подключите Pico и выберите **«Восстановить только ОС-файлы из backup…»** с `host-update.json`.

```powershell
python -B tools/update_os.py --restore-backup C:/Users/ИМЯ/Okna45-backups/ПАПКА --port COM5
```

Restore проверяет before/after hashes, удаляет только созданные этой операцией файлы, позднее изменённые не затирает без разрешения. Asset входит в backup/restore, личные unlisted files — нет. [USB bootstrap / staging / SIN](UPDATES.md).

## 2. Сначала ручная публикация, затем приложения

Доставка **только локально**: `github_store/docs/`, **13 приложений / 12 вариантов ОС**, оба full канала 0.2.6. Агент не использует token/commit/push/uploads/live AI/messages.

1. Существующий `niktehnologes/okna45-store` → Add file → Upload files.
2. Pages main `/(root)` — содержимое docs в корень; `/docs` — в docs. Сохраните рабочую структуру.
3. Обновлённые index/updates/pages + все referenced blobs/packages/downloads. **[Точный список](../PUBLISH_FILES.txt)** и [SHA256](../SHA256SUMS.txt).
4. Старые blobs/packages/downloads не удаляйте. `catalog.json` храните локально; project/flash/passwords/UUID/histories/signing keys не публикуйте.
5. Самостоятельно подтвердите upload и дождитесь Pages deployment. Одних app SIN недостаточно для Apps/Get.

Default `https://niktehnologes.github.io/okna45-store`; saved overrides имеют приоритет. Apps Check — apps, OS Check — OS, Setup Check — оба. [STORE.md](STORE.md).

## 3. Что исправлено в плеере

0.2.5 могла навсегда оставлять первый кадр: подготовка tile дольше 20 ms → tile отбрасывался перед SPI → следующая подготовка тоже опаздывала. Старые проверки конца boot не доказывали движения. В коротком воспроизведении с 25-ms decode старый player отправил **0 обновлений после начальных 60 tiles**.

**ILI9341 хранит картинку в собственной GRAM.** В 0.2.6 полный первый кадр пишется один раз; дальше player сравнивает предыдущий/целевой sparse state и отправляет **только действительно изменившиеся горизонтальные pixel runs**. Фон не переписывается, LCD readback и полный framebuffer в RAM Pico не нужны. При пропусках старые pixels восстанавливаются из независимого целевого state, а не цепочки GIF deltas.

**Подготовленный tile дорисовывается даже при пересечении deadline.** Между commits player заново выбирает кадр по elapsed time; очередь просроченных кадров не создаёт. Rotating cursor не позволяет верхним tiles монополизировать медленный decoder. На очень медленном устройстве кадр может быть частичным, вместо неподвижной заставки; реальные 50 FPS не обещаются.

- Только выбранный `LoadAnimation.gif`, `_ORIG` исключён. **320×240, все 96 кадров/задержки, удалено 0**, номинально 50 FPS; **5 × 1940 = 9700 ms** после initial draw. Завершение уже начатого tile может добавить небольшой overrun.
- [RGB332 OBA2](../boot-animation/rgb332-fix-2026-11-25/ok45_bootanim.oba) **17183 bytes**, SHA256 `4f3f863b801e18265cdfb6a482b0ed56b8e01518393721158c8d7f4c61ffe180`; asset не потребовал изменения. [GIF-превью](../boot-animation/rgb332-fix-2026-11-25/LoadAnimation-RGB332-preview.gif). RGB332 3/3/2 top bits, full-range expansion, no dithering.
- Один **2560-byte** buffer для двух sparse states/in-place RGB565; palette **512**, dirty bit map **160**, native DEFLATE window **512**, resident index **1868** bytes; остальные **5912** index bytes streamed. Это payload sizes, **не суммарный MicroPython heap**.
- Desktop/apps не импортируются до окончания; file/buffers/player unload, GC, затем desktop создаёт прежнюю одну **5120-byte RGB565 stripe**. Распакованных GIF-папок/кадров на Pico нет.
- Runtime **48 files / 279896 source+asset bytes**, per-file 4096 rounding **409600 / 420000**. Estimate не LittleFS/RAM; старые unlisted files, данные и staging учитывайте отдельно.

## 4. Графический desktop / приложения

Esc из input — pointer, из pointer — Start, **не PicoTerm**. Tab — input/pointer; taskbar — focus/restore, `_` — minimize, `X` — close. Console — graphical window. Notes Run / Files Run / Run / Console `run /file.py` — text window с print/input/scroll/Stop/Again; Files Open — отдельно просмотр/папка/SIN.

Apps demand-loaded: minimize продолжает, close отменяет cooperative tasks/unload. Generator `run(term,args)` уступает через `yield DELAY_MS`; `input` прокачивает scheduler. Arbitrary CPU loops/blocking calls не preemptible. Full/Gfx — optional legacy sources вне minimal runtime. Сохранены time zones/WiFi/API/installed icons/.sin/uppercase/symbols/original SPI/CardKB pacing и optional-string fixes.

[CONTROLS.md](CONTROLS.md), [DEVELOPER_API.md](DEVELOPER_API.md), [LLM_GUIDE.md](LLM_GUIDE.md). **После установки:** [Checklist/игры](STORE_APPS.md), [AI/Messenger/Snake + реальные Windows EXE / Android debug APK](NETWORK_APPS.md). Messenger nominal **500 ms** сохранён; destructive `/g` без ACK/E2EE не гарантирует delivery.

## 5. Что проверено / что ещё нет

**Пользователь подтвердил установку текущей доставки проводом на реальное железо: «Работает и обновлятор и ОС».** Базовая установка/updater/запуск проверены не только в эмуляторе. [Сохранённое подтверждение](2026-11-25-device-feedback.json); версия устройства отдельно не сообщена, контекст — 0.2.6.

Все 96 decoded RGB332 frames и произвольный skipped/reverse order совпали с source. Проверка LCD writes запрещает отправку любого неизменившегося pixel. Slow-decoder regression больше не застывает.

Один короткий offline boot в модели Pico: **36 разных LCD состояний**, **17833 changed pixels**, **4086 sparse writes** после initial, playback **9702 ms**, desktop 0.2.6 активен, player unload. [JSON наблюдения](2026-11-25-boot026-observation.json). Это модель, **не замер физического Pico FPS/heap/TLS/LittleFS/power-loss**.

FPS/heap/сеть/power-loss и отдельная проверка анимации не подтверждены сообщением о запуске. При повторном ENOMEM нужны USB traceback, `sys.implementation`, `gc.mem_free()` после Ctrl+C. EXE без publisher signing, APK debug-signed; агент не использовал устройство/телефон/live messages/AI. **[Сохранённый отчёт](report-2026-11-25.md)**.
