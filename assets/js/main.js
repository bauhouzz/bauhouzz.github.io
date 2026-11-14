/* Навигация, появление блоков, лайтбокс галереи. Без зависимостей. */
(function () {
  'use strict';

  /* ---------- шапка ---------- */
  var nav = document.querySelector('.nav');
  if (nav) {
    var onScroll = function () {
      nav.classList.toggle('is-stuck', window.scrollY > 24);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });

    var burger = nav.querySelector('.nav__burger');
    if (burger) {
      burger.addEventListener('click', function () {
        nav.classList.toggle('is-open');
        burger.setAttribute('aria-expanded', nav.classList.contains('is-open') ? 'true' : 'false');
      });
      nav.querySelectorAll('.nav__links a').forEach(function (a) {
        a.addEventListener('click', function () { nav.classList.remove('is-open'); });
      });
    }
  }

  /* ---------- появление блоков ---------- */
  var revealEls = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && revealEls.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add('is-in');
          io.unobserve(e.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.06 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add('is-in'); });
  }

  /* ---------- лайтбокс ---------- */
  var lb = document.querySelector('.lightbox');
  if (!lb) return;

  var lbImg = lb.querySelector('img');
  var counter = lb.querySelector('.lightbox__count');
  var items = [];
  var index = 0;

  function collect() {
    items = Array.prototype.slice.call(document.querySelectorAll('.shots img'));
  }

  function show(i) {
    if (!items.length) return;
    index = (i + items.length) % items.length;
    var el = items[index];
    lbImg.src = el.currentSrc || el.src;
    lbImg.alt = el.alt || '';
    if (counter) counter.textContent = (index + 1) + ' / ' + items.length;
  }

  function open(el) {
    collect();
    var i = items.indexOf(el);
    show(i < 0 ? 0 : i);
    lb.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    lb.querySelector('.lightbox__close').focus();
  }

  function close() {
    lb.classList.remove('is-open');
    document.body.style.overflow = '';
  }

  document.addEventListener('click', function (e) {
    var img = e.target.closest ? e.target.closest('.shots img') : null;
    if (img) { open(img); }
  });

  lb.addEventListener('click', function (e) {
    if (e.target === lb || e.target === lbImg) close();
  });

  lb.querySelector('.lightbox__close').addEventListener('click', close);
  lb.querySelector('.lightbox__btn--prev').addEventListener('click', function () { show(index - 1); });
  lb.querySelector('.lightbox__btn--next').addEventListener('click', function () { show(index + 1); });

  document.addEventListener('keydown', function (e) {
    if (!lb.classList.contains('is-open')) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowLeft') show(index - 1);
    if (e.key === 'ArrowRight') show(index + 1);
  });
})();
