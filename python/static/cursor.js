// Cursor aura — glowing dot + lagging ring + soft light glow.
// Self-contained: injects its own styles and elements. Skips touch devices
// and users with reduced-motion enabled.
(function () {
  if (window.matchMedia('(hover: none), (pointer: coarse)').matches) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var style = document.createElement('style');
  style.textContent = [
    '#cursor-dot, #cursor-ring, #cursor-glow {',
    '  position: fixed; top: 0; left: 0;',
    '  pointer-events: none; z-index: 9999;',
    '  will-change: transform;',
    '}',
    '#cursor-dot {',
    '  width: 6px; height: 6px; border-radius: 50%;',
    '  background: #7ec8ff;',
    '  box-shadow: 0 0 10px #3d8bff, 0 0 22px rgba(61,139,255,0.5);',
    '  margin: -3px 0 0 -3px;',
    '  transition: opacity 0.25s;',
    '}',
    '#cursor-ring {',
    '  width: 34px; height: 34px; border-radius: 50%;',
    '  border: 1.5px solid rgba(126,200,255,0.55);',
    '  margin: -17px 0 0 -17px;',
    '  transition: width 0.28s cubic-bezier(0.32,0.72,0,1),',
    '              height 0.28s cubic-bezier(0.32,0.72,0,1),',
    '              margin 0.28s cubic-bezier(0.32,0.72,0,1),',
    '              border-color 0.28s, opacity 0.25s, background 0.28s;',
    '}',
    '#cursor-ring.hovering {',
    '  width: 58px; height: 58px;',
    '  margin: -29px 0 0 -29px;',
    '  border-color: rgba(126,200,255,0.9);',
    '  background: rgba(61,139,255,0.06);',
    '}',
    '#cursor-glow {',
    '  width: 340px; height: 340px; border-radius: 50%;',
    '  margin: -170px 0 0 -170px;',
    '  background: radial-gradient(circle, rgba(61,139,255,0.075) 0%, rgba(167,139,250,0.03) 40%, transparent 70%);',
    '  mix-blend-mode: screen;',
    '  z-index: 3;',
    '}',
  ].join('\n');
  document.head.appendChild(style);

  var glow = document.createElement('div'); glow.id = 'cursor-glow';
  var ring = document.createElement('div'); ring.id = 'cursor-ring';
  var dot  = document.createElement('div'); dot.id  = 'cursor-dot';
  document.body.appendChild(glow);
  document.body.appendChild(ring);
  document.body.appendChild(dot);

  var cx = innerWidth / 2, cy = innerHeight / 2;
  var rx = cx, ry = cy, gx = cx, gy = cy;

  window.addEventListener('mousemove', function (e) { cx = e.clientX; cy = e.clientY; });

  (function loop() {
    requestAnimationFrame(loop);
    rx += (cx - rx) * 0.16;
    ry += (cy - ry) * 0.16;
    gx += (cx - gx) * 0.07;
    gy += (cy - gy) * 0.07;
    dot.style.transform  = 'translate(' + cx + 'px, ' + cy + 'px)';
    ring.style.transform = 'translate(' + rx + 'px, ' + ry + 'px)';
    glow.style.transform = 'translate(' + gx + 'px, ' + gy + 'px)';
  })();

  var hoverSel = 'a, button, input, select, textarea, [role="button"], .tab, .card, .metric-card, .range-btn';
  document.addEventListener('mouseover', function (e) {
    if (e.target.closest && e.target.closest(hoverSel)) ring.classList.add('hovering');
  });
  document.addEventListener('mouseout', function (e) {
    if (e.target.closest && e.target.closest(hoverSel)) ring.classList.remove('hovering');
  });
  document.addEventListener('mouseleave', function () { dot.style.opacity = ring.style.opacity = glow.style.opacity = '0'; });
  document.addEventListener('mouseenter', function () { dot.style.opacity = ring.style.opacity = glow.style.opacity = '1'; });
})();
