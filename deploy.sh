#!/usr/bin/env bash
# Публикация сайта на GitHub Pages.
# Запускать из корня репозитория: ./deploy.sh [имя-репозитория]
set -euo pipefail

GH="${GH:-$HOME/bin/gh}"
[ -x "$GH" ] || GH="$(command -v gh || true)"
if [ -z "$GH" ]; then
  echo "Не найден gh. Установите: https://cli.github.com/"
  exit 1
fi

REPO="${1:-bauhouzz}"

if ! "$GH" auth status >/dev/null 2>&1; then
  echo "Нужна авторизация в GitHub — откроется браузер и код подтверждения."
  "$GH" auth login --hostname github.com --git-protocol https --web
fi

OWNER="$("$GH" api user --jq .login)"

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Создаю репозиторий $OWNER/$REPO…"
  "$GH" repo create "$REPO" --public --source=. --remote=origin --push
else
  git push -u origin HEAD
fi

echo "Включаю GitHub Pages…"
"$GH" api -X POST "repos/$OWNER/$REPO/pages" \
  -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 || \
"$GH" api -X PUT "repos/$OWNER/$REPO/pages" \
  -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 || true

echo
echo "Готово. Через минуту сайт будет доступен:"
echo "  https://$OWNER.github.io/$REPO/"
echo
echo "Свой домен: Settings → Pages → Custom domain → bauhouzz.ru"
echo "и DNS-записи A/CNAME (см. README.md)."
