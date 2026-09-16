# Worklog

## 2026-09-16 — GameBoy RPG profile README

**Що зроблено:** README замінено на «портативну консоль»: 5 анімованих SVG-екранів (title, dialogue, charsheet, inventory, worldmap) + quest log у `<details>`. Скрипт `scripts/build_assets.py` генерує всі екрани; workflow щоночі перебудовує charsheet і worldmap.

**Рішення:**
- Власні SVG замість github-readme-stats/snk: єдина DMG-палітра, піксельний шрифт, анімації через CSS у `<img>` (скрипти в SVG GitHub не виконує, CSS/SMIL — так).
- Шрифт Press Start 2P вбудовано base64 як ASCII-сабсет WOFF2 (7 KB замість 118 KB) — зовнішні шрифти в `<img>` не завантажуються.
- XP рахується як сума комітів у default-гілках усіх власних репо (приватні включно), а не з contribution graph: історія комітів зроблена під іншим e-mail і в графі профілю не видна (там було б 3 коміти). Карта світу = max(офіційний календар, коміти по днях із власних репо).
- Без секрету `PROFILE_TOKEN` workflow виходить з warning і нічого не пише: дефолтний `GITHUB_TOKEN` бачить лише це репо і перший прогін «понизив» профіль до LV 1 / 2 repos. Відхилено fallback на `GITHUB_TOKEN`.
- Усі проєкти в quest log — `🔒 LOCKED`, без лінків (репо приватні; рішення власника).

**Змінені файли:** `README.md`, `assets/*.svg`, `scripts/gb.py`, `scripts/build_assets.py`, `scripts/profile_config.json`, `scripts/fonts/*`, `.github/workflows/update-profile.yml`, `.gitattributes`, `docs/superpowers/specs/2026-09-16-gameboy-rpg-profile-design.md`.

**Перевірено:** усі SVG валідні (`xml.dom.minidom`); локальний рендер у браузері — анімації йдуть; сторінка github.com/TrebaDripat відображає екрани через camo; `gh workflow run` ×2: перший (до guard) зробив bot-коміт з деградованими даними, другий — warning + «no changes».

**Відкрито:** власник має додати secret `PROFILE_TOKEN` (fine-grained PAT, All repositories, Contents: read + Metadata: read) — до того нічні оновлення не працюють. Карта світу реально майже порожня (активність лише за останні тижні) — це чесні дані.
