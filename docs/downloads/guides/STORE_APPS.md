# Сначала установка / публикация, затем маленькие приложения

## 1. Исправить / обновить ОС

**[Полная инструкция 0.2.6](GUI_OS_026.md)**: **[updater EXE](../tools/Okna45-Updater.exe)** и **[папка](../0.2.6/Okna45-0.2.6/)** / **[ZIP](../0.2.6/Okna45-0.2.6.zip)**. Выберите папку с `os-files.json`, backup до замен, repo/user files не копируются/не удаляются. Сохраните заметки/черновики, закройте USB editors.

С 0.2.4/старше **нельзя** применить current system SIN старым Store: `.oba` нет в allowlist, нужен host updater либо [USB bootstrap](UPDATES.md). Установленная 0.2.5 принимает system 0.2.6 штатно. Старый список 11 модулей только для исторической 0.2.3. Current delivery ставится по полному manifest, без подделки baselines. ENOMEM/TLS на Pico не подтверждены исправленными.

## 2. Ручная публикация

Подготовленные файлы — **`github_store/docs/`**, сейчас **13 apps / 12 OS variants**. Никаких token/commit/push/live requests агентом не выполняется.

1. Существующий `niktehnologes/okna45-store` → Add file → Upload files.
2. Pages main `/(root)` — содержимое docs в корень; Pages `/docs` — в docs. Сохраните рабочую структуру.
3. Новый **index.json + каждый указанный app blob + packages/SIN**, для ОС **updates.json + OS blobs**, для людей **downloads** с EXE/APK/ZIP/guide. **[Точный список](../PUBLISH_FILES.txt)**, [SHA256](../SHA256SUMS.txt).
4. Старые blobs/packages/downloads не удаляйте. `catalog.json` храните локально; основной project/flash/signing keys/passwords/UUID/истории не выкладывайте.
5. Самостоятельно подтвердите upload и дождитесь Pages deployment. Одна загрузка SIN без index/blobs не добавляет app в Store.

Default URL `https://niktehnologes.github.io/okna45-store` задан в коде, saved overrides сохраняются. Полное описание — [STORE.md](STORE.md). Новая доставка локальная, online доступность не проверялась.

## 3. Установить и запустить

1. Desktop после пяти циклов заставки → Network → WiFi → Scan/SSID/Key/Save/Link.
2. Start → System → Store → **Apps → Check** → `todo/pong/tetris/mines/flappy` → **Get**. Setup/Save только если меняете source.
3. Затем значок / Start → Tools (Checklist) или Games / Run с ID. Get только устанавливает, автоматически app не запускает. Первые 12 icons, Start включает все программы с pages.
4. **Tab → Input** до передачи игровых стрелок/символов; Tab/Esc — pointer. Ctrl/Shift-events не нужны, готовые uppercase/symbols сохранены.
5. Перед update/remove закройте app; `/data/NAME` сохраняется. Minimize продолжает выполнение, явно Pause если хотите остановить.

В graphical Console:

```text
apt update
apt install todo
apt install pong
open todo
open pong
```

Офлайн: выбранный `github_store/docs/packages/NAME-1.0.0.sin` скопируйте вручную в Pico, Console **`install /NAME-1.0.0.sin`**, затем Run/Start. SIN удаляйте только вручную после успеха. Repo не требуется; offline не проверяет TLS. App source `zerobook/repo/files/` хранится на host, не весь repo на flash.

## Приложения — после инструкции

Все пять — отдельные маленькие **window** apps 1.0.0, без dependencies/private framebuffer; используют общий desktop RGB565 stripe 5120 bytes. Не импортируются при boot; close отменяет задачи/unload, installed file остаётся.

| ID | Приложение | Управление в Input |
|---|---|---|
| `todo` | Checklist; задачи сохраняются в `/data/todo/` | Текст/Enter — добавить, стрелки — выбрать; экранные controls для отметки/удаления |
| `pong` | Pong Lite; стартует на паузе | Стрелки / экранные Play/Pause, R/New — новая игра |
| `tetris` | Tetris Lite; стартует на паузе | Стрелки — движение/поворот/спуск, Play/Pause, R/New |
| `mines` | Mines Lite; без постоянного timer | Стрелки — клетка, Enter — открыть, flag/New controls |
| `flappy` | Flappy Lite; стартует на паузе | Enter/Space или Flap, Pause/New |

Точные клавиши конкретного app также видны в его controls/semantic. Games cooperative: CPU loop/blocking вызов задержит весь desktop, окна не дают preemption.

Далее **[AI 1.0.0 / Messenger 2.0.0 / Snake 1.0.1, Windows EXE и Android APK](NETWORK_APPS.md)**. Messenger nominal **500 ms** сохранён, live server не вызывался; Android debug signing. [Отчёт](report-2026-11-25.md).

## Новая версия приложения (не требуется перед текущей ручной загрузкой)

```powershell
python -B tools/build_repo.py
python -B tools/build_apps.py todo pong tetris mines flappy --output uploads/apps/НОВАЯ_ПАПКА
python -B tools/publish.py uploads/apps/НОВАЯ_ПАПКА/NAME-НОВАЯ_ВЕРСИЯ.sin
```

При changed code **сначала увеличьте package version**, обновите hashes. Same-version different bytes запрещены; старые app SIN/blob остаются. `publish.py` локальный, code не выполняет; OS release не пересобирается ради app.
