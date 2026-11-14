#!/usr/bin/env bash
# Публикация сайта на GitHub Pages.
#
#   ./deploy.sh                      → репозиторий bauhouzz в личном аккаунте
#   ./deploy.sh bauhouzz             → то же
#   ./deploy.sh bauhouzz/bauhouzz    → репозиторий в организации bauhouzz
#   ./deploy.sh bauhouzz/bauhouzz.github.io → сайт в корне https://bauhouzz.github.io/
#
# Переменная SITE_BASE задаёт префикс пути при сборке:
#   не задана        → сайт в корне домена (user.github.io, org.github.io, свой домен)
#   SITE_BASE=/repo  → сайт как проект: https://user.github.io/repo/
set -euo pipefail

GH="${GH:-$HOME/bin/gh}"
[ -x "$GH" ] || GH="$(command -v gh || true)"
if [ -z "$GH" ]; then
  echo "Не найден gh. Установите: https://cli.github.com/"
  exit 1
fi

TARGET="${1:-bauhouzz}"

if ! "$GH" auth status >/dev/null 2>&1; then
  echo "Нужна авторизация в GitHub — откроется браузер и код подтверждения."
  "$GH" auth login --hostname github.com --git-protocol https --web
fi

OWNER="$("$GH" api user --jq .login)"

if [[ "$TARGET" == */* ]]; then
  FULL="$TARGET"
else
  FULL="$OWNER/$TARGET"
fi
NAME="${FULL#*/}"

# Префикс пути: корневой сайт (NAME.github.io) или проект
if [[ "$NAME" == *.github.io ]]; then
  export SITE_BASE=""
  PAGES_URL="https://${NAME}/"
else
  export SITE_BASE="/${NAME}"
  PAGES_URL="https://${FULL%%/*}.github.io/${NAME}/"
fi

echo "Пересобираю страницы (SITE_BASE='${SITE_BASE}')…"
python3 tools/build.py >/dev/null
git add -A
git diff --cached --quiet || git -c user.name="$(git config user.name || echo site)" \
  -c user.email="$(git config user.email || echo site@local)" commit -q -m "Сборка для публикации"

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Создаю репозиторий $FULL…"
  "$GH" repo create "$FULL" --public --source=. --remote=origin --push
else
  git push -u origin HEAD
fi

echo "Включаю GitHub Pages…"
"$GH" api -X POST "repos/$FULL/pages" \
  -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 || \
"$GH" api -X PUT "repos/$FULL/pages" \
  -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 || true

echo
echo "Готово. Через минуту сайт будет доступен:"
echo "  $PAGES_URL"
echo
echo "Свой домен: Settings → Pages → Custom domain → bauhouzz.ru"
echo "и DNS-записи A/CNAME (см. README.md)."
