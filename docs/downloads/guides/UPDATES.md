# Okna45 0.2.6: установка, обновление и SIN1

## 1. Рекомендуемый первый переход — новый host updater

**[Папка 0.2.6](../0.2.6/Okna45-0.2.6/)** / **[ZIP](../0.2.6/Okna45-0.2.6.zip)** и **[Windows updater](../tools/Okna45-Updater.exe)**. Сохраните Notes, закройте USB editors, выберите `os-files.json` folder и Pico COM либо отдельную папку flash. **[Установка и restore](GUI_OS_026.md)**.

`os-files.json` — explicit root OS allowlist с SHA256/size/channel, `delete_unlisted:false`. New asset **`ok45_bootanim.oba` OBA2** разрешён только как system file, произвольные assets/JSON/каталоги не разрешены. `repo` не копируется; существующие notes/settings/apps/data/scripts/repo не удаляются. Modified drivers/recovery/OS files требуют явного разрешения и предварительно сохраняются. Pending journals и `.mpy` shadows `.py` блокируют update.

**0.2.4 и старше не поддерживают asset в guest allowlist**, старый Store отвергнет current system SIN; Software first не исправляет updater. Используйте host updater/bootstrap. Установленная 0.2.5 принимает system 0.2.6: исправлен player, asset прежний. Software sources не менялись, full container 0.2.6 синхронизирует baseline. Старые EXE сохранены, OBA2 поддерживает только новый.

Host update backup: `%USERPROFILE%\Okna45-backups\...\`. Отдельные temporary/rename операции, `main.py` последним; это не whole-device atomic transaction. При обрыве не загружайте смешанную ОС: **Restore backup** с `host-update.json`. Restore касается только записанных изменений, включая asset и baselines; unlisted files остаются.

## 2. Что в новом выпуске

| Файл в [`updates/0.2.6/`](../0.2.6/) | Назначение |
|---|---|
| `okna45-system-0.2.6.sin` | Main/desktop/kernel/API/services, исправленный changed-pixel RGB332 player и `.oba` |
| `okna45-software-0.2.6.sin` | Demand-loaded окна/WiFi/Run/Store/commands; прежние source bytes в новом full контейнере |
| `bootstrap_updates.py` | Одноразовая установка recovery/updater allowlist через USB REPL, не runtime |
| `release.json`, `SHA256SUMS.txt` | Реальные channel hashes/versions и checksum |

Это **full** каналы, не delta. Normal SIN не заменяют `boot.py`, `ok45_boot.py`, `ili9341.py`, личные данные/repo. Host folder включает stable files для fresh install; modified copies только с разрешением. 0.2.0–0.2.5 и Archive/v1 сохранены.

App SIN независимы: [uploads/apps/2026-11-24/](../apps/2026-11-24/) — AI 1.0.0, Messenger 2.0.0, Snake **1.0.1**. Другие app SIN — `github_store/docs/packages/`. Установка/публикация прежде описаний: [STORE_APPS.md](STORE_APPS.md), [NETWORK_APPS.md](NETWORK_APPS.md).

## 3. Низкоуровневый USB bootstrap вместо EXE

Только если понимаете REPL/flash операции. **Агент эти команды на Pico не выполнял.** Сначала backup, остановить ОС, завершить pending recovery. Bootstrap не атомарный и не должен заменять recovery во время journal.

```powershell
mpremote run updates/0.2.6/bootstrap_updates.py
```

Далее оба full SIN, **по одному контейнеру** из-за flash ~800 КБ. Запуск `main.py` между ними запрещён. После bootstrap/нового REPL reset старые модули должны быть выгружены. Для штатного mpremote используйте свежий raw soft-reset контекст, который не запускает main.

Сначала software (пример, замените соединение своим):

```powershell
mpremote fs cp updates/0.2.6/okna45-software-0.2.6.sin :okna45-software-0.2.6.sin
mpremote exec "from ok45_update import Updater; list(Updater().apply_job('/okna45-software-0.2.6.sin'))"
mpremote fs rm :okna45-software-0.2.6.sin
```

Удаление выше — **только своего staging SIN после успешного Apply**, не repo/data. Затем system, снова из свободного REPL, не запускайте desktop:

```powershell
mpremote fs cp updates/0.2.6/okna45-system-0.2.6.sin :okna45-system-0.2.6.sin
mpremote exec "from ok45_update import Updater; list(Updater().apply_job('/okna45-system-0.2.6.sin'))"
mpremote fs rm :okna45-system-0.2.6.sin
mpremote exec "import machine; machine.reset()"
```

**Guest full staging может не помещаться**: нужны `.sin` + новые файлы + 32 КиБ reserve/журнал, кроме старой ОС/данных. При отказе не стирайте личные данные и не обходите space checks — используйте host updater, который не хранит полный SIN и staging одновременно. Physical Pico/USB/LittleFS/power-loss ещё не проверены.

## 4. После установки OBA2-aware updater

Store → **OS → Check → Sys/Soft → Apply**, по одному каналу. Apps Check — только apps, OS Check — OS, Setup Check — оба. Apply после Save/Discard/Cancel выгружает desktop и reset; Console `updates apply` делает то же. Командный `update /FILE.sin` требует maintenance, не применения core при живом desktop.

```text
update status
updates check
updates download system
updates status
updates apply
```

`apt update/upgrade` не обновляют ОС: только app index/packages. `install /APP.sin` и `apt` работают в graphical Console/Packages; закройте окна обновляемого app. `.sin` — контейнер данных, не исполняемый Python installer.

## 5. Проверки / recovery / места

- Пути, versions/API/size и SHA256 проверяются для **всех payloads**, включая уже совпадающие. Truncated/trailing bytes запрещают commit.
- Guest update сначала stages новые файлы, затем journal/rename/новый baseline; boot recovery до main откатывает неподтверждённую транзакцию или завершает cleanup подтверждённой.
- Каналы независимы: failure второго не откатывает первый. Старый baseline сохраняйте, не удаляйте system/software JSON для обхода modified-file protection.
- Downgrade запрещён; delta `from` соответствует учтённой channel version. Full разрешён для untracked; это не «version текущего main».
- Место — `statvfs` с file rounding, не guarantee LittleFS/power-loss. Runtime **279896 bytes**, 4096 estimate **409600 / 420000**, не RAM; старые unlisted files отдельно.
- Boot не распаковывается: **17183-byte OBA2**, buffer 2560, palette 512, dirty map 160, native window 512. Первый кадр один раз, дальше only changed horizontal runs в LCD GRAM; prepared tile finishes even if late, frame selection elapsed-time без очереди. После пяти циклов unload, desktop stripe 5120.
- SHA256 — целостность, **не подпись автора/security sandbox**. Нужны доверенные источники; HTTPS/Pico heap ещё не проверены.

## 6. Формат и локальная сборка

SIN1: `b'SIN1'` + little-endian uint32 JSON length + UTF-8 manifest (до 16384 bytes) + raw payloads подряд. System/software: `{format:1,kind,version,api:1,files:[{path,size,sha256}],from:[...]}`. Apps: `{format:1,kind:'software',packages:[...]}`. До 48 OS файлов, 65536 bytes/file, 393216 payload bytes; app transaction до 65536. OBA внутри SIN **уже сжат**, дополнительных animation-файлов после boot не создаётся.

```powershell
# Только НОВАЯ версия: сначала обновить versions/source; старую directory не перезаписывать.
python -B tools/build_updates.py --version 0.2.6 --os-only
python -B tools/prepare_os.py --zip
python -B tools/build_store.py --refresh
python -B tools/deliver_release.py
```

**0.2.6 уже собрана**, первые две команды сейчас должны отказать от перезаписи. Apps — `build_apps.py`, не OS rebuild. Delta только при прежнем stable recovery; release.json хранит actual channel_versions. Ручная публикация — [STORE.md](STORE.md), список — `uploads/PUBLISH_FILES.txt`.

Историческая 0.2.3-инструкция сохранена на host как `UPDATES_023.md`, это не список замены current sources. **[Итоговый отчёт](report-2026-11-25.md).**
