/* 仝娘之家 · 交互脚本 */
(function () {
  'use strict';

  // ---- 1. 首页新闻滑动 ----
  const slider = document.getElementById('news-slider');
  if (slider) {
    let down = false, moved = false, x0 = 0, s0 = 0;
    const onDown = (x) => { down = true; moved = false; x0 = x; s0 = slider.scrollLeft; slider.classList.add('active'); };
    const onMove = (x, e) => {
      if (!down) return;
      const walk = x - x0;
      if (Math.abs(walk) > 5) moved = true;
      if (e && e.cancelable) e.preventDefault();
      slider.scrollLeft = s0 - walk;
    };
    const onUp = () => {
      if (!down) return;
      down = false;
      slider.classList.remove('active');
      const card = slider.querySelector('.news-card');
      if (!card) return;
      const step = card.offsetWidth + 16;
      const target = Math.round(slider.scrollLeft / step);
      slider.scrollTo({ left: target * step, behavior: 'smooth' });
    };
    slider.addEventListener('dragstart', e => e.preventDefault());
    slider.addEventListener('mousedown', e => { e.preventDefault(); onDown(e.pageX); });
    slider.addEventListener('mouseleave', onUp);
    slider.addEventListener('mouseup', onUp);
    slider.addEventListener('mousemove', e => onMove(e.pageX, e));
    slider.addEventListener('touchstart', e => onDown(e.touches[0].pageX), { passive: true });
    slider.addEventListener('touchend', onUp);
    slider.addEventListener('touchmove', e => onMove(e.touches[0].pageX, e), { passive: false });
    slider.addEventListener('click', e => { if (moved) { e.preventDefault(); e.stopPropagation(); } });
  }

  // ---- 2. 提示词复制 ----
  document.querySelectorAll('.prompt-copy-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const code = btn.parentElement.querySelector('.prompt-content');
      if (!code) return;
      const text = code.textContent;
      const done = () => {
        btn.textContent = '已复制 ✓';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = '复制'; btn.classList.remove('copied'); }, 1500);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
      else fallbackCopy(text, done);
    });
  });
  function fallbackCopy(text, done) {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); done(); } catch (e) {}
    document.body.removeChild(ta);
  }

  // ---- 3. 自动补全 ----
  const searchForm = document.querySelector('.search-box');
  const searchInput = document.getElementById('searchinp');
  const suggestList = document.getElementById('suggest-list');

  if (searchForm && searchInput && suggestList) {
    const suggestUrl = searchForm.dataset.suggestUrl;
    let timer = null;
    let items = [];
    let activeIndex = -1;

    const hide = () => {
      suggestList.hidden = true;
      suggestList.innerHTML = '';
      items = [];
      activeIndex = -1;
    };

    const render = (list) => {
      items = list;
      activeIndex = -1;
      if (!list.length) { hide(); return; }
      suggestList.innerHTML = list.map((w, i) =>
        `<div class="suggest-item" data-index="${i}">${escapeHtml(w)}</div>`
      ).join('');
      suggestList.hidden = false;
    };

    const highlightItem = (i) => {
      suggestList.querySelectorAll('.suggest-item').forEach((el, idx) => {
        el.classList.toggle('active', idx === i);
      });
    };

    searchInput.addEventListener('input', () => {
      const q = searchInput.value.trim();
      if (!q) { hide(); return; }
      clearTimeout(timer);
      timer = setTimeout(async () => {
        try {
          const res = await fetch(`${suggestUrl}?q=${encodeURIComponent(q)}`);
          const data = await res.json();
          render(data);
        } catch (e) { hide(); }
      }, 120);
    });

    searchInput.addEventListener('keydown', (e) => {
      if (suggestList.hidden) return;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        activeIndex = Math.min(activeIndex + 1, items.length - 1);
        highlightItem(activeIndex);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        highlightItem(activeIndex);
      } else if (e.key === 'Enter' && activeIndex >= 0) {
        e.preventDefault();
        searchInput.value = items[activeIndex];
        hide();
        searchForm.submit();
      } else if (e.key === 'Escape') {
        hide();
      }
    });

    suggestList.addEventListener('mousedown', (e) => {
      const item = e.target.closest('.suggest-item');
      if (!item) return;
      e.preventDefault();
      searchInput.value = item.textContent;
      hide();
      searchForm.submit();
    });

    document.addEventListener('click', (e) => {
      if (!searchForm.contains(e.target)) hide();
    });

    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, t => ({
        '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
      }[t] || t));
    }
  }

  // ---- 4. 页面进入动画（由 CSS 完成，这里不做事） ----
})();