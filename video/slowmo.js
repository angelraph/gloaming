// Half-speed page clock for smooth capture: the recorder plays the footage back at double
// speed, so a slow machine's 13-15 captured fps becomes 26-30 fps on screen.
(() => {
  const S = 1 / (window.__SLOW || 3);
  const pn = performance.now.bind(performance);
  const t0 = pn();
  const now = () => t0 + (pn() - t0) * S;
  performance.now = now;
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => raf(() => cb(now()));
})();
