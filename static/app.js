/* 仝娘之家 · 只做三件事：
   1. 详情页背景切换
   2. 首页新闻滑动拖动
   3. 提示词复制按钮
   其它全部由 Python + Jinja2 完成 */

(function () {
  'use strict';

  // ---- 2. 首页新闻滑动拖动 ----
  const slider = document.getElementById('news-slider');
  if (slider) {
    let down = false, moved = false, x0 = 0, s0 = 0;

    const onDown = (x) => {
      down = true; moved = false;
      x0 = x; s0 = slider.scrollLeft;
      slider.classList.add('active');
    };
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

    slider.addEventListener('dragstart', (e) => e.preventDefault());
    slider.addEventListener('mousedown', (e) => { e.preventDefault(); onDown(e.pageX); });
    slider.addEventListener('mouseleave', onUp);
    slider.addEventListener('mouseup', onUp);
    slider.addEventListener('mousemove', (e) => onMove(e.pageX, e));
    slider.addEventListener('touchstart', (e) => onDown(e.touches[0].pageX), { passive: true });
    slider.addEventListener('touchend', onUp);
    slider.addEventListener('touchmove', (e) => onMove(e.touches[0].pageX, e), { passive: false });
    slider.addEventListener('click', (e) => {
      if (moved) { e.preventDefault(); e.stopPropagation(); }
    });
  }

  // ---- 3. 提示词复制按钮 ----
  document.querySelectorAll('.prompt-copy-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      const code = btn.parentElement.querySelector('.prompt-content');
      if (!code) return;
      const text = code.textContent;

      const done = () => {
        btn.textContent = '已复制 ✓';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.textContent = '复制';
          btn.classList.remove('copied');
        }, 1500);
      };

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
      } else {
        fallbackCopy(text, done);
      }
    });
  });

  function fallbackCopy(text, done) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); done(); } catch (err) {}
    document.body.removeChild(ta);
  }
})();