/* Flat cut-paper illustrations (one per Category) and UI icons, as one inline SVG sprite.
   Palette: ink #24211D, ivory #FFF9E9, cobalt #2448E8, vermilion #D64024, tape #E8C986.
   Each illustration: round 1.8 ink strokes, at most three fills, halftone dots for shading. */
(function () {
  const K = '#24211D', W = '#FFF9E9', B = '#2448E8', R = '#D64024', T = '#E8C986';
  const g = (inner) => `<g fill="none" stroke="${K}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${inner}</g>`;
  // Paper backing: a torn ivory cut-out behind every illustration so it reads as a sticker.
  const back = (d) => `<path d="${d}" fill="${W}" stroke="none"/>`;
  const art = {
    compass: back('M14 60 L22 28 L54 12 L90 18 L108 50 L102 90 L66 108 L28 100 Z') + g(`
      <circle cx="60" cy="60" r="36" fill="${T}"/><circle cx="60" cy="60" r="28" fill="${W}"/>
      <path d="M60 34 L67 60 L60 86 L53 60 Z" fill="${W}"/><path d="M60 34 L67 60 L53 60 Z" fill="${R}"/>
      <circle cx="60" cy="60" r="3" fill="${K}"/><path d="M56 22 L56 14 L64 22 L64 14"/>`),
    toolbox: back('M10 46 L18 30 L102 26 L112 48 L108 98 L14 102 Z') + g(`
      <rect x="18" y="44" width="84" height="50" rx="4" fill="${R}"/><path d="M18 62 H102"/>
      <path d="M44 44 V34 Q44 30 48 30 H72 Q76 30 76 34 V44" fill="none"/>
      <rect x="54" y="56" width="12" height="12" rx="2" fill="${W}"/><path d="M26 80 h8 M86 80 h8" stroke-dasharray="1 4"/>`),
    clock: back('M16 56 L26 22 L60 12 L96 24 L108 60 L96 98 L58 110 L22 96 Z') + g(`
      <circle cx="60" cy="62" r="36" fill="${B}"/><circle cx="60" cy="62" r="28" fill="${W}"/>
      <path d="M60 62 V42 M60 62 L74 70"/><circle cx="60" cy="62" r="2.5" fill="${K}"/>
      <path d="M28 30 L40 22 M92 30 L80 22" stroke-width="4"/><path d="M60 38 v3 M84 62 h-3 M60 86 v-3 M36 62 h3"/>`),
    bridge: back('M8 66 L16 40 L58 34 L104 42 L114 72 L104 96 L14 96 Z') + g(`
      <path d="M14 58 L106 70" stroke-width="4"/><path d="M22 59 V92 M98 69 V92" stroke-width="3"/>
      <path d="M22 59 Q60 30 98 69" fill="none"/><path d="M40 47 V61 M60 44 V64 M80 52 V67"/>
      <path d="M8 92 Q30 86 50 92 T112 92" stroke="${B}" stroke-width="3"/><path d="M60 64 l6 8 l-8 4" stroke="${R}" stroke-width="2.4"/>`),
    person: back('M20 104 L18 60 L34 24 L62 10 L92 26 L104 64 L102 106 Z') + g(`
      <path d="M26 104 Q26 74 60 72 Q94 74 94 104 Z" fill="${B}"/>
      <circle cx="60" cy="44" r="20" fill="${T}"/><path d="M42 40 Q50 20 70 26 Q80 30 80 42" fill="${K}"/>
      <path d="M54 50 q6 4 12 0"/>`),
    stamps: back('M8 70 L14 30 L46 18 L80 22 L112 36 L110 100 L12 102 Z') + g(`
      <rect x="14" y="74" width="26" height="12" rx="2" fill="${R}"/><path d="M27 74 V58"/><circle cx="27" cy="52" r="7" fill="${W}"/>
      <rect x="47" y="70" width="26" height="12" rx="2" fill="${B}"/><path d="M60 70 V50"/><circle cx="60" cy="44" r="7" fill="${W}"/>
      <rect x="80" y="74" width="26" height="12" rx="2" fill="${T}"/><path d="M93 74 V58"/><circle cx="93" cy="52" r="7" fill="${W}"/>
      <path d="M12 96 H108" stroke-dasharray="2 5"/>`),
    fork: back('M10 104 L16 40 L44 14 L80 14 L108 40 L110 104 Z') + g(`
      <path d="M48 106 L56 66 L30 24 M72 106 L64 66 L90 24" fill="none"/>
      <path d="M56 66 L60 40 L64 66" fill="${T}"/><path d="M60 100 V90 M60 82 V74" stroke-width="2.4"/>
      <path d="M26 22 L22 34 L34 30 Z" fill="${R}"/><path d="M94 22 L98 34 L86 30 Z" fill="${B}"/>`),
    map: back('M8 34 L40 22 L80 30 L112 20 L110 94 L80 102 L40 92 L10 102 Z') + g(`
      <path d="M14 36 L40 26 L80 34 L106 24 V90 L80 98 L40 88 L14 98 Z" fill="${T}"/>
      <path d="M40 26 V88 M80 34 V98"/><path d="M24 80 Q40 60 58 70 T92 48" stroke="${R}" stroke-dasharray="3 4" stroke-width="2.2"/>
      <path d="M92 36 q-7 0 -7 7 q0 6 7 13 q7 -7 7 -13 q0 -7 -7 -7z" fill="${B}"/>`),
    puzzle: back('M14 24 L56 12 L104 22 L110 70 L98 108 L40 106 L12 84 Z') + g(`
      <path d="M22 30 H50 Q48 20 58 20 Q68 20 66 30 H94 V56 Q104 54 104 64 Q104 74 94 72 V98 H66 Q68 88 58 88 Q48 88 50 98 H22 V72 Q12 74 12 64 Q12 54 22 56 Z" fill="${B}"/>
      <path d="M36 46 l4 4 M44 46 l4 4 M36 54 l4 4" stroke="${W}"/>`),
    clipboard: back('M16 20 L52 10 L100 16 L108 60 L100 110 L20 108 L12 64 Z') + g(`
      <rect x="24" y="22" width="72" height="84" rx="4" fill="${T}"/><rect x="32" y="30" width="56" height="70" fill="${W}"/>
      <rect x="44" y="16" width="32" height="12" rx="3" fill="${R}"/>
      <path d="M40 48 H80 M40 60 H76 M40 72 H80 M40 84 H66"/>`),
    chairs: back('M8 50 L20 22 L60 16 L100 24 L112 58 L104 104 L16 106 Z') + g(`
      <path d="M18 30 V96 M18 66 H44 V96 M18 66 L18 30" fill="none"/><rect x="18" y="30" width="8" height="36" fill="${B}"/>
      <path d="M18 66 H44 V72 H18 Z" fill="${B}"/>
      <path d="M102 30 V96 M102 66 H76 V96" fill="none"/><rect x="94" y="30" width="8" height="36" fill="${R}"/>
      <path d="M102 66 H76 V72 H102 Z" fill="${R}"/><path d="M50 50 q10 -8 20 0" stroke-dasharray="2 4"/>`),
    sticky: back('M14 18 L60 10 L106 16 L110 64 L102 108 L18 104 L10 60 Z') + g(`
      <path d="M22 22 H98 V82 L78 102 H22 Z" fill="${T}"/><path d="M98 82 H78 V102" fill="${W}"/>
      <path d="M48 46 Q48 34 60 34 Q72 34 72 46 Q72 54 60 58 V66" stroke-width="4"/><circle cx="60" cy="78" r="3" fill="${K}"/>
      <rect x="44" y="14" width="32" height="12" fill="${R}" opacity=".85" stroke="none"/>`),
    tube: back('M30 10 L80 8 L96 40 L90 112 L36 112 L24 60 Z') + g(`
      <path d="M48 16 V82 Q48 100 60 100 Q72 100 72 82 V16" fill="${W}"/>
      <path d="M48 56 H72 V82 Q72 100 60 100 Q48 100 48 82 Z" fill="${R}"/>
      <path d="M42 16 H78"/><circle cx="56" cy="44" r="3"/><circle cx="64" cy="34" r="2"/><path d="M84 26 l8 -6 M86 38 l10 0"/>`),
    envelope: back('M8 34 L40 20 L84 22 L114 36 L110 96 L60 106 L12 96 Z') + g(`
      <rect x="16" y="32" width="88" height="60" rx="3" fill="${W}"/>
      <path d="M16 32 L60 66 L104 32" fill="${B}"/><path d="M16 92 L48 62 M104 92 L72 62"/>
      <circle cx="60" cy="72" r="7" fill="${R}"/>`),
    ruler: back('M8 52 L30 24 L112 40 L110 72 L84 100 L10 84 Z') + g(`
      <path d="M14 70 L96 30 L108 52 L26 92 Z" fill="${T}"/>
      <path d="M28 64 l5 9 M38 59 l3 6 M48 54 l5 9 M58 49 l3 6 M68 44 l5 9 M78 39 l3 6 M88 34 l5 9"/>`),
    sketch: back('M12 20 L60 10 L108 18 L112 70 L104 110 L18 108 L10 64 Z') + g(`
      <rect x="20" y="22" width="68" height="80" rx="3" fill="${W}"/>
      <rect x="30" y="32" width="48" height="26" fill="${B}"/><path d="M30 66 H78 M30 74 H66" />
      <rect x="30" y="82" width="22" height="10" rx="2" fill="${R}"/>
      <path d="M96 30 L104 38 L76 96 L66 100 L68 90 Z" fill="${T}"/>`),
    tools: back('M12 30 L40 12 L84 14 L110 40 L106 92 L70 110 L24 104 L10 70 Z') + g(`
      <path d="M30 92 L76 46" stroke-width="7" stroke="${K}"/><path d="M30 92 L76 46" stroke-width="3.6" stroke="${B}"/>
      <path d="M72 50 Q66 34 80 26 L86 36 L94 32 Q98 46 82 52 Z" fill="${W}"/>
      <path d="M86 92 L44 50" stroke-width="7"/><path d="M86 92 L44 50" stroke-width="3.6" stroke="${R}"/>
      <path d="M44 50 L34 30 L40 28 L50 46 Z" fill="${W}"/>`),
    signpost: back('M14 30 L40 10 L92 12 L112 34 L106 110 L20 110 Z') + g(`
      <path d="M58 22 V106" stroke-width="3"/><path d="M60 26 H98 L106 34 L98 42 H60 Z" fill="${R}"/>
      <path d="M58 50 H22 L14 58 L22 66 H58 Z" fill="${B}"/><path d="M60 74 H90 L96 80 L90 86 H60 Z" fill="${T}"/>
      <path d="M44 106 H74"/>`),
    lamp: back('M18 28 L50 10 L96 16 L110 50 L102 108 L20 110 L12 70 Z') + g(`
      <path d="M30 104 H74"/><path d="M50 104 L38 70 L64 42" stroke-width="2.6"/>
      <path d="M58 30 L90 22 L98 52 L70 56 Z" fill="${R}"/><path d="M80 56 L92 92" stroke="${T}" stroke-width="10" opacity=".9"/>
      <circle cx="38" cy="70" r="4" fill="${W}"/>`),
    loop: back('M12 50 L28 18 L72 10 L106 30 L110 76 L84 108 L36 108 L10 82 Z') + g(`
      <path d="M86 44 A30 30 0 1 0 90 72" stroke-width="7" stroke="${K}"/><path d="M86 44 A30 30 0 1 0 90 72" stroke-width="4" stroke="${B}"/>
      <path d="M76 40 L90 42 L92 28" fill="none" stroke-width="3"/><circle cx="60" cy="60" r="8" fill="${R}"/>`),
    tape: back('M10 40 L34 14 L84 12 L110 40 L108 98 L62 110 L14 96 Z') + g(`
      <circle cx="46" cy="62" r="30" fill="${T}"/><circle cx="46" cy="62" r="10" fill="${W}"/>
      <path d="M46 92 H104 V80 H72" fill="${W}"/><path d="M80 92 v-6 M88 92 v-4 M96 92 v-6"/>
      <rect x="58" y="34" width="12" height="10" fill="${R}"/>`),
    receipt: back('M22 8 L94 10 L102 60 L98 114 L24 114 L16 60 Z') + g(`
      <path d="M30 14 H90 V104 L84 98 L78 104 L72 98 L66 104 L60 98 L54 104 L48 98 L42 104 L36 98 L30 104 Z" fill="${W}"/>
      <path d="M40 30 H80 M40 42 H70 M40 54 H76 M40 70 H80" /><path d="M64 80 H80" stroke="${R}" stroke-width="3"/>
      <rect x="40" y="76" width="16" height="8" fill="${B}"/>`),
    scale: back('M10 46 L30 14 L90 14 L110 46 L104 108 L16 108 Z') + g(`
      <path d="M60 22 V100 M42 100 H78"/><path d="M24 36 L96 32" stroke-width="2.6"/><circle cx="60" cy="22" r="4" fill="${R}"/>
      <path d="M24 36 L14 66 H38 Z" fill="${B}"/><path d="M96 32 L86 60 H108 Z" fill="${T}"/>
      <path d="M14 66 Q26 76 38 66 M86 60 Q97 70 108 60"/>`),
    units: back('M8 44 L24 16 L96 14 L112 42 L110 102 L12 104 Z') + g(`
      <rect x="16" y="66" width="24" height="24" fill="${B}"/><rect x="48" y="66" width="24" height="24" fill="${B}"/><rect x="80" y="66" width="24" height="24" fill="${B}"/>
      <rect x="48" y="36" width="24" height="24" fill="${R}"/><rect x="80" y="36" width="24" height="24" fill="${R}"/>
      <rect x="80" y="8" width="24" height="24" fill="${T}" transform="translate(0 2)"/><path d="M14 98 H108"/>`),
    backpack: back('M20 30 L50 8 L80 10 L104 34 L104 112 L18 112 Z') + g(`
      <path d="M46 24 Q46 14 60 14 Q74 14 74 24" fill="none"/>
      <path d="M30 40 Q30 24 60 24 Q90 24 90 40 V104 H30 Z" fill="${R}"/>
      <rect x="40" y="64" width="40" height="28" rx="4" fill="${T}"/><path d="M40 74 H80"/><path d="M60 40 v14" />`),
    team: back('M8 56 L22 24 L60 12 L98 22 L114 58 L110 104 L10 106 Z') + g(`
      <path d="M12 98 Q12 76 32 74 Q52 76 52 98 Z" fill="${T}"/><circle cx="32" cy="58" r="11" fill="${W}"/>
      <path d="M68 98 Q68 76 88 74 Q108 76 108 98 Z" fill="${B}"/><circle cx="88" cy="58" r="11" fill="${W}"/>
      <path d="M38 102 Q38 74 60 72 Q82 74 82 102 Z" fill="${R}"/><circle cx="60" cy="52" r="13" fill="${W}"/>`),
    table: back('M8 60 L18 26 L60 14 L102 26 L114 64 L100 100 L20 102 Z') + g(`
      <ellipse cx="60" cy="62" rx="36" ry="18" fill="${T}"/><path d="M60 80 V100 M46 100 H74"/>
      <circle cx="20" cy="58" r="7" fill="${B}"/><circle cx="100" cy="58" r="7" fill="${B}"/>
      <circle cx="40" cy="34" r="7" fill="${R}"/><circle cx="80" cy="34" r="7" fill="${R}"/><circle cx="60" cy="96" r="0"/>`),
    notebook: back('M14 20 L58 8 L108 20 L112 70 L100 112 L16 110 L8 64 Z') + g(`
      <rect x="22" y="26" width="72" height="80" rx="3" fill="${W}"/>
      <path d="M30 20 v12 M42 20 v12 M54 20 v12 M66 20 v12 M78 20 v12" stroke-width="2.4"/>
      <path d="M34 50 H82 M34 62 H74 M34 74 H80"/><path d="M94 70 Q104 84 86 106 L60 106 Q80 92 94 70 Z" fill="${B}"/>`),
    caution: back('M14 18 L60 10 L106 16 L110 64 L102 108 L18 104 L10 60 Z') + g(`
      <path d="M60 24 L100 94 H20 Z" fill="${T}"/><path d="M60 50 V72" stroke-width="4"/><circle cx="60" cy="83" r="3" fill="${K}"/>`),
  };
  const ic = (d, extra = '') => `<g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ${extra}>${d}</g>`;
  const icons = {
    search: ic('<circle cx="11" cy="11" r="6.5"/><path d="M16 16 L21 21"/>'),
    export: ic('<path d="M12 15 V4 M7.5 8.5 L12 4 L16.5 8.5"/><path d="M5 12 V19 H19 V12"/>'),
    outline: ic('<path d="M9 6 H20 M9 12 H20 M9 18 H20"/><circle cx="4.5" cy="6" r="1" fill="currentColor"/><circle cx="4.5" cy="12" r="1" fill="currentColor"/><circle cx="4.5" cy="18" r="1" fill="currentColor"/>'),
    close: ic('<path d="M6 6 L18 18 M18 6 L6 18"/>'),
    plus: ic('<path d="M12 5 V19 M5 12 H19"/>'),
    minus: ic('<path d="M5 12 H19"/>'),
    overview: ic('<path d="M4 9 V4 H9 M15 4 H20 V9 M20 15 V20 H15 M9 20 H4 V15"/>'),
    back: ic('<path d="M10 6 L4 12 L10 18 M4 12 H20"/>'),
    target: ic('<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.5" fill="currentColor"/>'),
    history: ic('<path d="M4 12 A8 8 0 1 0 7 5.8"/><path d="M4 4 V8 H8"/><path d="M12 8 V12 L15 14"/>'),
    chevron: ic('<path d="M9 6 L15 12 L9 18"/>'),
    chevdown: ic('<path d="M6 9 L12 15 L18 9"/>'),
    next: ic('<path d="M5 12 H19 M13 6 L19 12 L13 18"/>'),
    copy: ic('<rect x="8" y="8" width="11" height="12" rx="2"/><path d="M5 15 V5 Q5 4 6 4 H15"/>'),
    download: ic('<path d="M12 4 V15 M7.5 10.5 L12 15 L16.5 10.5"/><path d="M5 19 H19"/>'),
    upload: ic('<path d="M12 15 V4 M7.5 8.5 L12 4 L16.5 8.5"/><path d="M5 19 H19"/>'),
    trash: ic('<path d="M5 7 H19 M9 7 V4 H15 V7 M7 7 L8 20 H16 L17 7"/>'),
    // Status stamps
    stNot: ic('<circle cx="12" cy="12" r="6.5"/>'),
    stDraft: ic('<path d="M5 19 L6 14.5 L15.5 5 L19 8.5 L9.5 18 Z"/><path d="M13.5 7 L17 10.5"/>'),
    stAnswered: '<circle cx="12" cy="12" r="7.5" fill="currentColor"/><path d="M8.5 12.2 L11 14.6 L15.8 9.6" fill="none" stroke="#FFF9E9" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    stRevisit: ic('<path d="M6 21 V4"/><path d="M6 4.5 H18 L15 8.5 L18 12.5 H6" fill="currentColor"/>'),
    clip: ic('<path d="M16 7 L9 14 Q7.5 15.5 9 17 Q10.5 18.5 12 17 L19 10 Q22 7 19 4 Q16 1 13 4 L6 11 Q2 15 6 19 Q10 23 14 19 L18 15"/>'),
  };
  let sprite = '<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true"><defs>';
  for (const [k, v] of Object.entries(art)) sprite += `<symbol id="art-${k}" viewBox="0 0 120 120">${v}</symbol>`;
  for (const [k, v] of Object.entries(icons)) sprite += `<symbol id="i-${k}" viewBox="0 0 24 24">${v}</symbol>`;
  sprite += '</defs></svg>';
  window.STUDIO_ART = { sprite, keys: Object.keys(art) };
})();
