#!/usr/bin/env python3
"""
Сборка статического сайта bauhouzz.

Что делает:
  * берёт исходные изображения из raw/ (имена — md5 от URL, как их скачал crawler);
  * уменьшает их до 1800 px по длинной стороне и сохраняет в assets/img/<slug>/NN.jpg;
  * генерирует index.html, prices.html, projects/*.html, art/*.html, consent.html, 404.html.

Как добавить проект:
  1. положить фотографии в raw/ (или сразу готовые в assets/img/<slug>/);
  2. добавить объект в content/projects.json (slug, title, subtitle, intro, groups[].images);
  3. запустить: python3 tools/build.py

Запуск из корня репозитория.
"""
import hashlib
import html
import json
import os
import shutil
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")
RAW = os.path.join(ROOT, "raw")
IMG = os.path.join(ROOT, "assets", "img")
MAX_SIDE = 1800
QUALITY = 86
MIN_WIDTH = 600

# Префикс пути. Пусто для корня (user.github.io, org.github.io, свой домен),
# "/bauhouzz" — если сайт живёт как проект: https://user.github.io/bauhouzz/
BASE = os.environ.get("SITE_BASE", "").rstrip("/")

SITE = json.load(open(os.path.join(CONTENT, "site.json"), encoding="utf-8"))
DATA = json.load(open(os.path.join(CONTENT, "projects.json"), encoding="utf-8"))


def e(s):
    return html.escape(s or "", quote=True)


def raw_path(url):
    name = hashlib.md5((url + "\n").encode()).hexdigest()[:16] + ".bin"
    return os.path.join(RAW, name)


def prepare(slug, url, num):
    """Возвращает (относительный путь, ширина, высота) или None."""
    out_dir = os.path.join(IMG, slug)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "%02d.jpg" % num)
    rel = "assets/img/%s/%02d.jpg" % (slug, num)

    if os.path.exists(out):
        with Image.open(out) as im:
            return rel, im.width, im.height

    src = raw_path(url)
    if not os.path.exists(src):
        print("  ! нет файла для", url[-60:])
        return None
    try:
        with Image.open(src) as im:
            if im.width < MIN_WIDTH:
                return None
            # 1200x630 — превью для соцсетей, а не фотография проекта
            if (im.width, im.height) == (1200, 630):
                return None
            im = im.convert("RGB")
            im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
            im.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
            return rel, im.width, im.height
    except Exception as ex:  # noqa: BLE001
        print("  ! пропущено:", url[-50:], ex)
        return None


def usable(url):
    """Отсекает иконки и превью для соцсетей — по фактическому размеру файла."""
    src = raw_path(url)
    if not os.path.exists(src):
        return False
    try:
        with Image.open(src) as im:
            return im.width >= MIN_WIDTH and (im.width, im.height) != (1200, 630)
    except Exception:  # noqa: BLE001
        return False


def build_item(item):
    """Готовит изображения проекта, возвращает структуру с локальными путями."""
    slug = item["slug"]
    cover = None
    groups = []
    used = set()
    n = 1
    for g in item.get("groups", []):
        shots = []
        for url in g.get("images", []):
            r = prepare(slug, url, n)
            if not r:
                continue
            used.add(url)
            n += 1
            shots.append(r)
            if cover is None:
                cover = r
        if shots:
            groups.append({"caption": g.get("caption", ""), "shots": shots})

    # изображения вне блоков «gallery» (слайдеры, карусели) — отдельной группой
    rest = [u for u in item.get("all_images", []) if u not in used and usable(u)]
    if rest:
        shots = []
        for url in rest:
            r = prepare(slug, url, n)
            if r:
                n += 1
                shots.append(r)
        if shots:
            groups.append({"caption": "", "shots": shots})

    # обложка: отдельная картинка из карточки, если она есть
    if item.get("cover"):
        r = prepare(slug, item["cover"], 0)
        if r:
            cover = r
    return {"slug": slug, "cover": cover, "groups": groups}


def nav(root, active=""):
    c = SITE["contacts"]
    links = [
        ("index.html#portfolio", "Портфолио"),
        ("prices.html", "Услуги и цены"),
        ("index.html#about", "Об авторе"),
        ("index.html#contacts", "Контакты"),
    ]
    out = []
    for href, label in links:
        cls = ' class="is-active"' if active and active in href else ""
        out.append('<a href="%s%s"%s>%s</a>' % (root, href, cls, e(label)))
    out.append('<a class="nav__cta" href="%sindex.html#contacts">Обсудить проект</a>' % root)
    return """
<header class="nav">
  <div class="nav__inner">
    <a class="brand" href="%(root)sindex.html">Ольга Баурина</a>
    <button class="nav__burger" aria-label="Меню" aria-expanded="false"><span></span></button>
    <nav class="nav__links">%(links)s</nav>
  </div>
</header>""" % {"root": root, "links": "\n      ".join(out)}


def footer(root):
    c = SITE["contacts"]
    return """
<footer class="footer">
  <div class="wrap footer__row">
    <span>© %(name)s, %(role)s. Все права защищены.</span>
    <span>
      <a href="mailto:%(email)s">%(email)s</a> ·
      <a href="%(tg)s" target="_blank" rel="noopener">Telegram</a> ·
      <a href="%(wa)s" target="_blank" rel="noopener">WhatsApp</a>
    </span>
    <span><a href="%(root)sconsent.html">Политика конфиденциальности</a></span>
  </div>
</footer>""" % {
        "name": e(SITE["name"]), "role": e(SITE["role"]),
        "email": e(c["email"]), "tg": e(c["telegram"]), "wa": e(c["whatsapp"]),
        "root": root,
    }


def page(title, desc, root, body, extra="", og=None, active=""):
    og_tag = '<meta property="og:image" content="%s">' % e(og) if og else ""
    return """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
%(og)s
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="%(root)sassets/css/main.css">
<link rel="icon" href="%(root)sassets/img/favicon.svg" type="image/svg+xml">
%(extra)s
</head>
<body>
%(nav)s
%(body)s
%(footer)s
<div class="lightbox" role="dialog" aria-modal="true" aria-label="Просмотр фотографии">
  <button class="lightbox__close" aria-label="Закрыть">×</button>
  <button class="lightbox__btn lightbox__btn--prev" aria-label="Предыдущая">‹</button>
  <img alt="">
  <button class="lightbox__btn lightbox__btn--next" aria-label="Следующая">›</button>
  <div class="lightbox__count"></div>
</div>
<script src="%(root)sassets/js/main.js" defer></script>
</body>
</html>""" % {
        "title": e(title), "desc": e(desc), "root": root, "body": body,
        "nav": nav(root, active), "footer": footer(root), "extra": extra, "og": og_tag,
    }


def card(item, root, prepared):
    cov = prepared["cover"]
    img = ('<img src="%s%s" alt="%s" loading="lazy" decoding="async">'
           % (root, cov[0], e(item["title"]))) if cov else ""
    return """
<a class="card reveal" href="%(root)s%(section)s/%(slug)s.html">
  <div class="card__media">%(img)s</div>
  <div class="card__meta">
    <div>
      <div class="card__title">%(title)s</div>
      <div class="card__sub">%(sub)s</div>
    </div>
    <div class="card__year">%(year)s</div>
  </div>
</a>""" % {
        "root": root, "section": item["section"], "slug": item["slug"], "img": img,
        "title": e(item["title"]), "sub": e(item["subtitle"]), "year": e(item.get("year", "")),
    }


# ---------------------------------------------------------------- index

def build_index(prepared_all):
    root = ""
    projects = [x for x in DATA["projects"]]
    art = [x for x in DATA["art"]]
    cov = prepared_all[projects[0]["slug"]]["cover"]

    person = SITE["hero"].get("person") or {}
    person_html = ""
    if person.get("name"):
        photo = ""
        if person.get("photo"):
            photo = ('<img class="person__photo" src="%s%s" alt="%s" width="96" height="96">'
                     % ("", e(person["photo"]), e(person["name"])))
        person_html = """
      <div class="person">
        %s
        <div class="person__text">
          <div class="person__role">%s</div>
          <div class="person__name">%s</div>
        </div>
      </div>""" % (photo, e(person.get("role", "")), e(person["name"]))

    hero = """
<section class="hero">
  <div class="wrap hero__grid">
    <div>
      %(person)s
      <div class="eyebrow hero__eyebrow">%(eyebrow)s</div>
      <h1>%(heading)s</h1>
      <p class="lead hero__lead">%(lead)s</p>
      <div class="hero__actions">
        <a class="btn btn--solid" href="#portfolio">Смотреть портфолио</a>
        <a class="btn btn--ghost" href="#contacts">Обсудить проект</a>
      </div>
      <p class="hero__note">%(note)s</p>
    </div>
    <figure class="hero__media reveal">
      <img src="%(cover)s" alt="Интерьер, спроектированный Ольгой Бауриной" fetchpriority="high">
      <figcaption><span>%(cap)s</span><span>%(year)s</span></figcaption>
    </figure>
  </div>
</section>""" % {
        "person": person_html,
        "eyebrow": e(SITE["hero"]["eyebrow"]),
        "heading": e(SITE["hero"]["heading"]),
        "lead": e(SITE["hero"]["lead"]),
        "note": e(SITE["hero"]["note"]),
        "cover": cov[0] if cov else "",
        "cap": e(projects[0]["title"]),
        "year": e(projects[0].get("year", "")),
    }

    cards = "\n".join(card(p, root, prepared_all[p["slug"]]) for p in projects)
    art_cards = "\n".join(card(a, root, prepared_all[a["slug"]]) for a in art)

    services = "\n".join("""
    <article class="service">
      <div class="service__num">%(num)s</div>
      <h3>%(title)s</h3>
      <p>%(text)s</p>
    </article>""" % {"num": e(s["num"]), "title": e(s["title"]), "text": e(s["text"])}
        for s in SITE["services"])

    adv = "\n".join("""
    <div class="adv__item">
      <div class="adv__num">%(num)s</div>
      <h3>%(title)s</h3>
      <p>%(text)s</p>
    </div>""" % {"num": e(a["num"]), "title": e(a["title"]), "text": e(a["text"])}
        for a in SITE["advantages"])

    diplomas = "\n".join("""
    <div>
      <h3>%(school)s</h3>
      <ul>%(items)s</ul>
    </div>""" % {"school": e(d["school"]),
                 "items": "".join("<li>%s</li>" % e(i) for i in d["items"])}
        for d in SITE["diplomas"])

    c = SITE["contacts"]
    body = hero + """
<section class="section" id="portfolio">
  <div class="wrap">
    <div class="section__head">
      <div>
        <div class="eyebrow">Портфолио</div>
        <h2>Реализованные<br>проекты</h2>
      </div>
      <p>Квартиры и загородные дома — от небольшой студии до коттеджа на 245 м². Каждый проект начинается с планировки и заканчивается авторским надзором на объекте.</p>
    </div>
    <div class="cards">
%(cards)s
    </div>
  </div>
</section>

<section class="section" id="services">
  <div class="wrap">
    <div class="section__head">
      <div>
        <div class="eyebrow">Что входит в работу</div>
        <h2>Четыре шага<br>к готовому интерьеру</h2>
      </div>
      <p>Можно взять весь цикл целиком, а можно только тот этап, которого не хватает. Подробные составы и стоимость — на странице услуг.</p>
    </div>
  </div>
  <div class="services">
%(services)s
  </div>
  <div class="wrap" style="margin-top:34px">
    <a class="btn btn--ghost" href="prices.html">Услуги и цены</a>
  </div>
</section>

<section class="section" id="art">
  <div class="wrap">
    <div class="section__head">
      <div>
        <div class="eyebrow">Арт-проекты</div>
        <h2>Конкурсы<br>и выставки</h2>
      </div>
      <p>Работы для издания «Интерьер + Дизайн», выставки «Придумано и сделано в России» и Министерства образования Москвы.</p>
    </div>
    <div class="cards">
%(art)s
    </div>
  </div>
</section>

<section class="section" id="about">
  <div class="wrap">
    <div class="section__head">
      <div>
        <div class="eyebrow">Об авторе</div>
        <h2>Ольга Баурина</h2>
      </div>
      <p>Дизайнер интерьера. Создаю интерьеры для комфортной жизни: грамотно спланированный ремонт, авторский интерьер в вашем бюджете. Высшее художественное образование и Британская школа дизайна.</p>
    </div>
    <div class="diplomas reveal">
%(diplomas)s
    </div>
  </div>
</section>

<section class="section" id="advantages">
  <div class="wrap">
    <div class="section__head">
      <div>
        <div class="eyebrow">Почему со мной</div>
        <h2>Преимущества</h2>
      </div>
    </div>
    <div class="adv">
%(adv)s
    </div>
  </div>
</section>

<section class="section" id="contacts">
  <div class="wrap contact">
    <div>
      <div class="eyebrow">Контакты</div>
      <h2 style="margin:12px 0 18px">Бесплатная<br>консультация</h2>
      <p class="lead">Расскажите о задаче — отвечу и предложу, с чего начать. Обычно это разговор на 20 минут о планировке и бюджете.</p>
      <div class="contact__links">
        <a class="contact__link" href="mailto:%(email)s"><span>Почта</span><span>%(email)s</span></a>
        <a class="contact__link" href="%(tg)s" target="_blank" rel="noopener"><span>Telegram</span><span>%(tgl)s</span></a>
        <a class="contact__link" href="%(wa)s" target="_blank" rel="noopener"><span>WhatsApp</span><span>Написать</span></a>
      </div>
    </div>
    <form class="form" id="contact-form" novalidate>
      <div class="field">
        <input id="f-name" name="name" type="text" placeholder=" " autocomplete="name">
        <label for="f-name">Имя</label>
      </div>
      <div class="field">
        <input id="f-contact" name="contact" type="text" placeholder=" " autocomplete="email">
        <label for="f-contact">E-mail или телефон</label>
      </div>
      <div class="field">
        <textarea id="f-message" name="message" placeholder=" "></textarea>
        <label for="f-message">Комментарий</label>
      </div>
      <div class="form__foot">
        <button class="btn btn--solid" type="submit">Отправить заявку</button>
        <p class="form__hint">Нажимая кнопку, вы соглашаетесь с <a href="consent.html">политикой конфиденциальности</a>.</p>
      </div>
      <div class="form__status" role="status"></div>
    </form>
  </div>
</section>

<script>
(function () {
  var f = document.getElementById('contact-form');
  if (!f) return;
  f.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var name = f.name.value.trim();
    var contact = f.contact.value.trim();
    var msg = f.message.value.trim();
    var st = f.querySelector('.form__status');
    if (!name && !contact && !msg) {
      st.textContent = 'Заполните хотя бы одно поле.';
      return;
    }
    var body = 'Имя: ' + name + '\\nКонтакт: ' + contact + '\\n\\n' + msg;
    window.location.href = 'mailto:%(email)s?subject=' +
      encodeURIComponent('Заявка с сайта') + '&body=' + encodeURIComponent(body);
    st.textContent = 'Открываю почтовую программу — письмо уже готово.';
  });
})();
</script>
""" % {
        "cards": cards, "art": art_cards, "services": services,
        "adv": adv, "diplomas": diplomas,
        "email": e(c["email"]), "tg": e(c["telegram"]), "tgl": e(c["telegramLabel"]),
        "wa": e(c["whatsapp"]),
    }

    return page("%s — %s" % (SITE["name"], SITE["title"]), SITE["description"], root, body,
                og=cov[0] if cov else None)


# ---------------------------------------------------------------- project page

def build_project(item, prepared, prev_item, next_item):
    root = "../"
    groups_html = []
    for g in prepared["groups"]:
        shots = g["shots"]
        if not shots:
            continue
        cap = '<div class="group__cap">%s</div>' % e(g["caption"]) if g["caption"] else ""
        hero = ('<img src="%s%s" alt="%s" loading="lazy" decoding="async">'
                % (root, shots[0][0], e(item["title"])))
        rest = ""
        if len(shots) > 1:
            imgs = "".join('<img src="%s%s" alt="%s" loading="lazy" decoding="async">'
                           % (root, s[0], e(item["title"])) for s in shots[1:])
            rest = '<div class="shots">%s</div>' % imgs
        groups_html.append('<div class="group">%s<div class="shots shots--hero">%s</div>%s</div>'
                           % (cap, hero, rest))

    prev_html = ""
    if prev_item:
        prev_html = ('<a href="%s.html"><span>Предыдущий</span><span class="project__nav-title">%s</span></a>'
                     % (e(prev_item["slug"]), e(prev_item["title"])))
    next_html = ""
    if next_item:
        next_html = ('<a href="%s.html" style="text-align:right"><span>Следующий</span>'
                     '<span class="project__nav-title">%s</span></a>'
                     % (e(next_item["slug"]), e(next_item["title"])))

    body = """
<main class="project">
  <div class="wrap">
    <div class="project__head">
      <div>
        <a class="back" href="../index.html#portfolio">← Все проекты</a>
        <div class="eyebrow">%(kind)s · %(year)s</div>
        <h1>%(title)s</h1>
        <div class="project__sub">%(sub)s</div>
      </div>
      <p class="project__intro">%(intro)s</p>
    </div>
    <div class="gallery">
%(groups)s
    </div>
    <nav class="project__nav">
      <div>%(prev)s</div>
      <div>%(next)s</div>
    </nav>
  </div>
</main>""" % {
        "kind": e(item.get("kind", "Проект")), "year": e(item.get("year", "")),
        "title": e(item["title"]), "sub": e(item["subtitle"]), "intro": e(item["intro"]),
        "groups": "\n".join(groups_html), "prev": prev_html, "next": next_html,
    }
    return page("%s — %s" % (item["title"], SITE["name"]),
                "%s. %s" % (item["title"], item["subtitle"]), root, body,
                active="portfolio")


# ---------------------------------------------------------------- prices

def build_prices():
    root = ""
    cards = []
    for i, p in enumerate(SITE["prices"]):
        items = "".join("<li>%s</li>" % e(x) for x in p["items"])
        featured = " price--featured" if i == 2 else ""
        cards.append("""
    <article class="price%(f)s">
      <div class="price__num">%(num)s</div>
      <h3>%(title)s</h3>
      <p class="price__text">%(text)s</p>
      <div class="price__sum">%(price)s</div>
      <div class="price__note">%(note)s</div>
      %(example)s
      %(ul)s
      <a class="btn btn--ghost" href="index.html#contacts">Заказать</a>
    </article>""" % {
            "f": featured, "num": e(p["num"]), "title": e(p["title"]), "text": e(p["text"]),
            "price": e(p["price"]), "note": e(p["note"]),
            "example": ('<div class="price__example">%s</div>' % e(p["example"])) if p.get("example") else "",
            "ul": "<ul>%s</ul>" % items if items else "<div style='height:22px'></div>",
        })

    stages = "".join("""
    <div class="stage">
      <div class="stage__num">%(num)s</div>
      <h3>%(title)s</h3>
      <p>%(text)s</p>
    </div>""" % {"num": "%02d" % int(s["num"]), "title": e(s["title"]), "text": e(s["text"])}
        for s in SITE["stages"])

    body = """
<main style="padding-top:calc(var(--nav-h) + 40px)">
  <section class="wrap">
    <div class="eyebrow">Услуги</div>
    <h1 style="font-size:clamp(38px,6vw,84px);margin:12px 0 18px">Цены и услуги</h1>
    <p class="lead" style="margin-bottom:46px">Дизайн-проект квартиры или дома в трёх вариантах — от планировки до полного комплекта с визуализациями. Можно добавить авторское сопровождение и комплектацию.</p>
    <div class="price-grid">
%(cards)s
    </div>
  </section>

  <section class="section" style="margin-top:clamp(50px,7vw,100px)">
    <div class="wrap">
      <div class="section__head">
        <div>
          <div class="eyebrow">Порядок работы</div>
          <h2>Этапы работ</h2>
        </div>
        <p>Десять шагов от первой встречи до финальной съёмки. На каждом этапе вы видите результат и можете скорректировать направление.</p>
      </div>
      <div class="stages">%(stages)s</div>
    </div>
  </section>

  <section class="section">
    <div class="wrap" style="text-align:center">
      <h2 style="margin-bottom:18px">Не знаете, какой формат нужен?</h2>
      <p class="lead" style="margin:0 auto 26px">Напишите или позвоните — разберёмся вместе и подберём подходящий состав работ.</p>
      <a class="btn btn--solid" href="index.html#contacts">Бесплатная консультация</a>
    </div>
  </section>
</main>""" % {"cards": "".join(cards), "stages": stages}

    return page("Услуги и цены — %s" % SITE["name"],
                "Дизайн-проект квартиры и дома: базовый, технический и полный. Авторское сопровождение и комплектация.", root, body,
                active="prices")


# ---------------------------------------------------------------- consent

def build_consent():
    body = """
<main style="padding-top:calc(var(--nav-h) + 40px)">
  <div class="wrap" style="max-width:820px">
    <div class="eyebrow">Документы</div>
    <h1 style="font-size:clamp(34px,5vw,60px);margin:12px 0 26px">Политика конфиденциальности</h1>
    <div class="lead" style="max-width:none;color:var(--ink-soft)">
      <p>Настоящая политика описывает, как обрабатываются персональные данные, которые вы оставляете на этом сайте.</p>
      <h3 style="margin:26px 0 10px">Какие данные собираются</h3>
      <p>Только те, которые вы указываете сами: имя, адрес электронной почты или номер телефона, текст комментария.</p>
      <h3 style="margin:26px 0 10px">Зачем</h3>
      <p>Чтобы ответить на вашу заявку и обсудить дизайн-проект. Данные не передаются третьим лицам и не используются для рассылок.</p>
      <h3 style="margin:26px 0 10px">Как отправляется форма</h3>
      <p>Форма на сайте не сохраняет данные на сервере: она открывает вашу почтовую программу с готовым письмом. Письмо уходит только после того, как вы его отправите.</p>
      <h3 style="margin:26px 0 10px">Удаление</h3>
      <p>Напишите на <a href="mailto:%(email)s" style="text-decoration:underline">%(email)s</a>, чтобы удалить переписку и данные.</p>
    </div>
  </div>
</main>""" % {"email": e(SITE["contacts"]["email"])}
    return page("Политика конфиденциальности — %s" % SITE["name"],
                "Политика обработки персональных данных.", "", body)


def build_404():
    body = """
<main class="center-page">
  <div>
    <div class="eyebrow">Страница не найдена</div>
    <h1>404</h1>
    <p class="lead" style="margin:10px auto 26px">Возможно, страница переехала. Вернитесь к портфолио.</p>
    <a class="btn btn--solid" href="/index.html">На главную</a>
  </div>
</main>"""
    return page("Страница не найдена — %s" % SITE["name"], "404", (BASE or "") + "/", body)


def favicon():
    os.makedirs(os.path.join(ROOT, "assets", "img"), exist_ok=True)
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" fill="#191712"/>
<text x="32" y="44" font-family="Georgia,serif" font-size="34" fill="#f7f4ef" text-anchor="middle">ОБ</text>
</svg>"""
    open(os.path.join(ROOT, "assets", "img", "favicon.svg"), "w", encoding="utf-8").write(svg)


def main():
    favicon()
    prepared = {}
    for item in DATA["projects"] + DATA["art"]:
        print("·", item["slug"])
        prepared[item["slug"]] = build_item(item)

    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(build_index(prepared))
    open(os.path.join(ROOT, "prices.html"), "w", encoding="utf-8").write(build_prices())
    open(os.path.join(ROOT, "consent.html"), "w", encoding="utf-8").write(build_consent())
    open(os.path.join(ROOT, "404.html"), "w", encoding="utf-8").write(build_404())

    for section, items in (("projects", DATA["projects"]), ("art", DATA["art"])):
        d = os.path.join(ROOT, section)
        os.makedirs(d, exist_ok=True)
        for i, item in enumerate(items):
            prev_item = items[i - 1] if i > 0 else None
            next_item = items[i + 1] if i + 1 < len(items) else None
            html_out = build_project(item, prepared[item["slug"]], prev_item, next_item)
            open(os.path.join(d, item["slug"] + ".html"), "w", encoding="utf-8").write(html_out)

    print("готово")


if __name__ == "__main__":
    sys.exit(main())
