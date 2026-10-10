(() => {
  if (window.__cur) return;
  // the page is zoomed; measure how CSS px map to viewport px so the cursor sits where rects say
  const probe = document.createElement('div');
  probe.style.cssText = 'position:fixed;left:100px;top:0;width:1px;height:1px;';
  document.documentElement.appendChild(probe);
  const Z = probe.getBoundingClientRect().left / 100 || 1;
  probe.remove();
  const c = document.createElement('div');
  c.style.cssText = 'position:fixed;left:0;top:0;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;'
    + 'background:rgba(255,240,204,.95);box-shadow:0 0 0 2px rgba(8,8,10,.6),0 0 16px rgba(204,145,102,.85);'
    + 'z-index:2147483647;pointer-events:none;transition:transform .15s ease;';
  document.documentElement.appendChild(c);
  let x = 960, y = 540, last = null;
  const place = () => { c.style.left = (x / Z) + 'px'; c.style.top = (y / Z) + 'px'; };
  const ev = (el, type, Ctor) => el.dispatchEvent(new Ctor(type, { bubbles: true, cancelable: true, clientX: x, clientY: y, pointerType: 'mouse', view: window }));
  // hover: synthetic pointer and mouse events on whatever is under the cursor
  const hover = () => {
    const el = document.elementFromPoint(x, y);
    if (!el) return;
    if (el !== last) {
      if (last) { ev(last, 'pointerout', PointerEvent); ev(last, 'mouseout', MouseEvent); ev(last, 'pointerleave', PointerEvent); ev(last, 'mouseleave', MouseEvent); }
      ev(el, 'pointerover', PointerEvent); ev(el, 'mouseover', MouseEvent); ev(el, 'pointerenter', PointerEvent); ev(el, 'mouseenter', MouseEvent);
      last = el;
    }
    ev(el, 'pointermove', PointerEvent); ev(el, 'mousemove', MouseEvent);
  };
  const ease = k => k < .5 ? 4*k*k*k : 1 - Math.pow(-2*k + 2, 3) / 2;
  const anim = (ms, fn) => new Promise(res => {
    const t0 = performance.now();
    const step = now => { const k = Math.min(1, (now - t0) / ms); fn(k); k < 1 ? requestAnimationFrame(step) : res(); };
    requestAnimationFrame(step);
  });
  place();
  window.__cur = {
    Z,
    async move(tx, ty, ms, linear) {
      const sx = x, sy = y;
      await anim(Math.max(ms, 1), k => { const e = linear ? k : ease(k); x = sx + (tx - sx) * e; y = sy + (ty - sy) * e; place(); hover(); });
    },
    async moveTo(sel, ms, fx = .5, fy = .5) {
      const r = document.querySelector(sel).getBoundingClientRect();
      await this.move(r.left + r.width * fx, r.top + r.height * fy, ms);
    },
    async sweep(sel, fx0, fx1, fy, ms) {
      const r = document.querySelector(sel).getBoundingClientRect();
      await this.move(r.left + r.width * fx0, r.top + r.height * fy, 600);
      await this.move(r.left + r.width * fx1, r.top + r.height * fy, ms, true);
    },
    ripple() {
      c.style.transform = 'scale(.7)'; setTimeout(() => c.style.transform = '', 160);
      const r = document.createElement('div');
      r.style.cssText = `position:fixed;left:${x / Z}px;top:${y / Z}px;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;`
        + 'border:2px solid rgba(255,240,204,.9);z-index:2147483646;pointer-events:none;'
        + 'transition:transform .6s ease-out,opacity .6s ease-out;';
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => { r.style.transform = 'scale(3.2)'; r.style.opacity = '0'; });
      setTimeout(() => r.remove(), 700);
    },
    async click(sel, ms = 700) {
      await this.moveTo(sel, ms);
      this.ripple();
      ev(document.querySelector(sel), 'pointerdown', PointerEvent);
      document.querySelector(sel).click();
    },
  };
  window.__scroll = async (sel, offset, ms) => {
    document.documentElement.style.scrollBehavior = 'auto';
    const el = document.querySelector(sel);
    const sy = window.scrollY;
    // rects and scroll offsets are both in viewport px here
    const target = sy + (el.getBoundingClientRect().top - offset);
    await anim(ms, k => { window.scrollTo(0, sy + (target - sy) * ease(k)); hover(); });
  };
  // Camera: glide in on one element so it fills the frame. The browser re-renders text and
  // charts at the new size, so a close-up stays as sharp as the wide shot.
  const find = (sel) => {
    if (!sel.startsWith('text=')) return document.querySelector(sel);
    const want = sel.slice(5);
    const hits = [...document.querySelectorAll('body *')].filter(e => e.children.length < 40 && e.textContent.includes(want));
    return hits.length ? hits[hits.length - 1].closest('.grid, section, div') : null;
  };
  let cam = { s: 1, tx: 0, ty: 0 };
  window.__cam = async (sel, maxScale, ms, up = 0) => {
    const el = find(sel);
    if (!el) return 'missing ' + sel;
    const b = document.body;
    b.style.transformOrigin = '0 0';
    // measure in the untransformed layout
    const prev = b.style.transform; b.style.transition = 'none'; b.style.transform = 'none';
    const r = el.getBoundingClientRect();
    b.style.transform = prev; void b.offsetWidth;
    const s = Math.max(1, Math.min(maxScale, (1920 * 0.9) / r.width, (1080 * 0.84) / r.height));
    const px = r.left + r.width / 2, py = r.top + r.height / 2 + up, sy = window.scrollY;
    const tx = (960 - s * px) / Z, ty = (540 + sy - s * (py + sy)) / Z;
    cam = { s, tx, ty };
    // the sticky nav misplaces itself inside a moved page, so it steps out while the camera is in
    const nav = document.querySelector('body > div header, header');
    if (nav) { nav.style.transition = 'opacity .25s ease'; nav.style.opacity = '0'; }
    b.style.transition = `transform ${ms}ms cubic-bezier(.45,0,.2,1)`;
    b.style.transform = `translate(${tx}px, ${ty}px) scale(${s})`;
    await new Promise(res => setTimeout(res, ms * (window.__SLOW || 3) + 50));
    return s;
  };
  window.__camReset = async (ms) => {
    const b = document.body;
    b.style.transition = `transform ${ms}ms cubic-bezier(.45,0,.2,1)`;
    b.style.transform = 'translate(0px, 0px) scale(1)';
    await new Promise(res => setTimeout(res, ms * (window.__SLOW || 3) + 50));
    b.style.transition = 'none'; b.style.transform = 'none';
    const nav = document.querySelector('body > div header, header');
    if (nav) nav.style.opacity = '1';
  };
  window.__scrollBy = async (sel, dy, ms) => {
    const box = document.querySelector(sel);
    let el = box;
    for (const d of [box, ...box.querySelectorAll('*')]) { if (d.scrollHeight > d.clientHeight + 20 && getComputedStyle(d).overflowY !== 'visible') { el = d; break; } }
    const s0 = el.scrollTop;
    await anim(ms, k => { el.scrollTop = s0 + dy * ease(k); });
  };
})();
