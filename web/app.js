/* Cami Startup Canvas — read-only YAML snapshot.
   Vanilla JS, no build step. Data comes from data.js (generated from the question manifest).
   Spec: plans/000-facilitation-canvas/互動Canvas視覺與體驗Spec.md */
(() => {
  'use strict';
  const I18N=window.STUDIO_I18N, tr=(key,vars)=>I18N.t(key,vars);
  const isCore = () => window.STARTUP_CAMI_MODEL?.coreMode === true;
  const localValue = value => value?.[I18N.locale] ?? value?.en ?? '';
  const cn=name=>localValue(window.STARTUP_CAMI_MODEL?.coreContent?.categories?.[name]) || I18N.catalog().categories?.[name] || name;
  const completed = a => isCore() ? Boolean(a?.text?.trim()) : a?.recordStatus === 'accepted';
  const progressLabel = () => isCore() ? (I18N.locale==='zh-TW'?'已填':'filled') : tr('accepted');

  // ---------- constants ----------
  const coreCardWidth = viewportWidth => viewportWidth < 768 ? 560 : 1040;
  let CARD_W = isCore() ? coreCardWidth(window.innerWidth) : 560;
  const CARD_H = 460;
  const MIN_S = 0.05, MAX_S = 1.4; // below the spec 0.06 so Overview fits the whole world beside the open panel; area labels stay legible down to 0.05
  // Phones cannot show the whole world at a legible label size; Overview fits it anyway and names appear on tap.
  const minS = () => (S.mode === 'mobile' ? 0.018 : MIN_S);
  const START_S = 0.72;
  const STATUS = {
    'not-answered': { label: "Not answered", icon: 'stNot' },
    'draft': { label: "Unreviewed", icon: 'stDraft' },
    'answered': { label: "Accepted", icon: 'stAnswered' },
    'revisit': { label: "Needs review", icon: 'stRevisit' },
  };
  STATUS.saved = { label: 'Saved', icon: 'stDraft' };
  STATUS.unverifiable = { label: "Unverifiable", icon: 'stRevisit' };
  const params = new URLSearchParams(location.search);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  // ---------- tiny helpers ----------
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icon = (name, cls = 'i') => `<svg class="${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const now = () => new Date().toISOString();
  const fmtTime = (iso) => { try { return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }); } catch { return ''; } };
  const fmtDateTime = (iso) => { try { return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch { return iso; } };
  const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
  const hash = (s) => { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; };
  const ease = (t) => 1 - Math.pow(1 - t, 3);
  const forceReduce = params.get('motion') === 'reduce';
  if (forceReduce) document.documentElement.classList.add('reduce-motion');
  const noMotion = () => forceReduce || reducedMotion.matches;

  // ---------- data ----------
  let CARDS = [], CARD_BY_Q = {}, CARD_INDEX = {};
  let D, Q = {}, CATS = {}, contentCats = [], mainQs = [], cautions = [], routeIds = [], WB;

  // ---------- runtime state ----------
  const S = {
    cam: { x: 0, y: 0, s: START_S },
    level: 'question', farTitles: false,
    selectedId: null, rovingId: null, panelOpen: false,
    focusCategory: null,
    venture: null,
    backStack: [], prefs: { tips: {} },
    anim: null, camBeforePanel: null, camTouched: false,
    searchLimit: 30, searchActive: -1, searchHits: [],
    mode: 'desktop', sheet: 'half',
  };

  // =====================================================================
  // Boot & data loading
  // =====================================================================
  function boot() {
    document.body.insertAdjacentHTML('afterbegin', window.STUDIO_ART ? window.STUDIO_ART.sprite : '');
    loadData(false);
  }

  function loadData() {
    try {
      const model = window.STARTUP_CAMI_MODEL;
      const data = window.STUDIO_DATA;
      if (model) {
        if (model.readonly !== true) throw new Error(tr('This view only accepts readonly snapshots.'));
        const oldCats = Object.fromEntries(data.categories.map(c => [c.name, c]));
        data.categories = model.categories.map(c => ({...oldCats[c.name], ...c, cx: c.center?.x ?? c.cx, cy: c.center?.y ?? c.cy, caution: c.cautionOnly ?? c.caution}));
        data.questions = [...model.questions, ...(model.cautions || [])].filter((q,i,arr) => arr.findIndex(x => x.id === q.id) === i).map((q,i) => ({...q, order:i, x:q.localPosition?.x ?? q.x, y:q.localPosition?.y ?? q.y, rot:q.paperRotation ?? q.rot ?? 0, caution:q.cautionOnly ?? q.caution ?? false, audienceEn:q.audienceEn || q.audience}));
        for (const q of data.questions.filter(q=>q.caution)) {
          if (!data.categories.some(c=>c.name===q.category)) data.categories.push({...oldCats[q.category],name:q.category,cx:0,cy:0,caution:true});
        }
        data.contentSha256 = model.project.catalog_sha256 || data.contentSha256;
        if (isCore()) {
          data.route = data.questions.filter(q=>!q.caution).map(q=>({id:q.id}));
          data.mainOrder = data.categories.map(c=>c.name);
          data.mainRoad = data.mainOrder.slice(1).map((name,i)=>({from:data.mainOrder[i],to:name}));
          data.relations = []; data.branches = {};
          data.categories.forEach((c,i)=>{c.art ||= Object.values(oldCats)[i % Object.keys(oldCats).length]?.art;c.cx ||= 0;c.cy ||= 0;});
          data.questions.forEach(q=>{q.x ??= 0;q.y ??= 0;});
          document.documentElement.classList.add('core-canvas');
        }
      }
      init(validateData(data));
    } catch (err) { loadFailed(err); }
  }

  function validateData(d) {
    if (!d || !Array.isArray(d.questions) || !Array.isArray(d.categories)) throw new Error(tr('Question data is missing or malformed.'));
    const main = d.questions.filter((q) => !q.caution), cau = d.questions.filter((q) => q.caution);
    const cats = d.categories.filter((c) => !c.caution);
    if (isCore() ? (!main.length || cau.length || !cats.length || cats.some(c=>!main.some(q=>q.category===c.name))) : (main.length !== 351 || cau.length !== 11 || cats.length !== 28)) throw new Error(tr('unexpected counts',{questions:main.length,cautions:cau.length,categories:cats.length}));
    if (new Set(d.questions.map((q) => q.id)).size !== d.questions.length) throw new Error(tr('Question ids are not unique.'));
    return d;
  }

  function loadFailed(err) {
    const stage = $('#stage');
    const box = document.createElement('div');
    box.className = 'load-failed';
    box.setAttribute('role', 'alert');
    box.innerHTML = `<h1>${tr("Could not load the questions.")}</h1><p>${esc(err.message)}</p>
      <p>${tr("Nothing was changed on this device. This readonly snapshot does not modify YAML or browser storage.")}</p>
      <div class="row"><button class="btn btn-primary" type="button" id="retry-load">${tr("Retry")}</button>
      <button class="btn btn-ghost" type="button" id="error-summary">${tr("Download error summary")}</button></div>`;
    stage.append(box);
    $('#retry-load').onclick = () => { box.remove(); loadData(true); };
    $('#error-summary').onclick = () => download('startup-cami-load-error.txt', 'text/plain',
      `Cami Startup Canvas could not load its questions.\nTime: ${now()}\nPage: ${location.href}\nError: ${err && err.message}\nUser agent: ${navigator.userAgent}\n`);
  }

  // =====================================================================
  // Init: index data, build world, restore venture
  // =====================================================================
  function init(data) {
    D = data;
    D.categories.forEach((c) => { CATS[c.name] = { ...c, qs: [] }; });
    D.questions.forEach((q) => {
      const c = CATS[q.category];
      const qq = { ...q, _original: structuredClone(q), wx: c.cx + q.x, wy: c.cy + q.y };
      Q[q.id] = qq;
      c.qs.push(qq);
      (q.caution ? cautions : mainQs).push(qq);
    });
    contentCats = D.categories.filter((c) => !c.caution).map((c) => CATS[c.name]);
    restoreVenture();
    applyContentLocale();
    buildClusters(window.STARTUP_CAMI_MODEL?.clusters || window.STARTUP_CAMI_CLUSTERS);
    routeIds = D.route.map((r) => r.id);
    I18N.staticText();
    S.prefs = readPrefs();
    buildWorld();
    buildCollage();
    bindGlobal();
    measure();
    startCanvas();
  }


  function buildClusters(asset) {
    if (!asset || !Array.isArray(asset.cards) || (isCore() ? asset.cards.length !== mainQs.length : asset.cards.length !== 132)) throw new Error(tr('Cluster data is missing or incompatible.'));
    const expected=window.STARTUP_CAMI_MODEL ? asset.source_sha256 : asset.source_content_sha256;
    if (expected !== D.contentSha256) throw new Error(tr('Cluster data is missing or incompatible.'));
    const seen=new Set();
    CARDS=asset.cards.map(raw=>{
      const id=raw.lead_question_id;
      if(!Q[id] || !CATS[raw.primary_category])throw new Error('Invalid card lead or category');
      const members=raw.questions.map(m=>{
        const q=Q[m.question_id];
        if(!q || q.caution || seen.has(q.id) || q._original.question!==m.question || q.category!==m.original_category)throw new Error('Incompatible cluster member');
        seen.add(q.id); return {...m,id:q.id};
      });
      if(!members.some(m=>m.id===id && (m.presentation==='主問題' || (isCore() && m.presentation==='primary'))))throw new Error('Invalid primary question');
      const other=members.filter(m=>m.side==='on_the_other_hand');
      const card={id,members,other,primaryCategory:raw.primary_category,w:CARD_W,h:0,cautionIds:[]};
      CARD_INDEX[id]=card;members.forEach(m=>{CARD_BY_Q[m.id]=card;Q[m.id].cardId=id;});return card;
    });
    if(seen.size!==mainQs.length || mainQs.some(q=>!seen.has(q.id)))throw new Error('Incomplete cluster coverage');
    for(const reminder of asset.cautions || [])for(const id of reminder.attached_to_ids || []) {
      if(!Q[reminder.question_id]?.caution || !CARD_INDEX[id])throw new Error('Invalid caution attachment');
      CARD_INDEX[id].cautionIds.push(reminder.question_id);
    }
    layoutClusters();
  }

  function measureCardHeights() {
    // All paper dimensions use world units. Measure the actual localized contents at 1:1.
    const probe = document.createElement('div');
    probe.style.cssText = 'position:absolute;visibility:hidden;pointer-events:none;--s:1';
    const tiles = CARDS.map(card => {
      const tile = buildTile(Q[card.id]);
      tile.removeAttribute('id');
      refreshTile(card.id, tile);
      probe.append(tile);
      return tile;
    });
    document.body.append(probe);
    const selectedBefore=S.selectedId;
    CARDS.forEach((card,i)=>{
      let max=0;
      for(const member of card.members){S.selectedId=member.id;refreshTile(card.id,tiles[i]);max=Math.max(max,tiles[i].getBoundingClientRect().height);}
      card.h=Math.ceil(max);
    });
    S.selectedId=selectedBefore;
    probe.remove();
  }

  function layoutClusters() {
    measureCardHeights();
    // Conceptual neighbourhoods: purpose above; customer → evidence → solution → business;
    // founder/team below. Unequal islands and staggered paper retain the collage layout.
    const names=contentCats.map(c=>c.name);
    const rows=isCore() ? [names.slice(0,3),names.slice(3,7),names.slice(7)] : [
      ['Company Purpose','Market & Why Now','Unfair Advantage'],
      ['Situation & Trigger','Problem','Customer & Target Persona','Evidence','Validation Signal','Solution & Thin Product','Activation'],
      ['Pain & Impact','Current Alternative & Competitors','Users, Payers & Decision-Makers','Customer Discovery','Key Assumption','Success Criteria','Retention'],
      ['Founder Fit','Human Fit & Commitment','Team & Role Coverage','Decisions & Learning','Validation & Next Experiment','Technology & Design','Instrumentation'],
      ['Business Model & Monetization','Unit Economics & Financial Projections','Customer Acquisition','Growth']
    ];
    let y=0;
    rows.forEach((names,row)=>{
      let x=isCore() ? (row===1?0:360) : row===0?1200:row===4?7500:0,maxHeight=0;
      names.forEach(name=>{
        const c=CATS[name];c.cards=CARDS.filter(card=>card.primaryCategory===name);
        const columns=Math.min(3,Math.ceil(Math.sqrt(c.cards.length))),width=columns*(CARD_W+110)-110;
        let localY=0;
        for(let i=0;i<c.cards.length;i+=columns){
          const batch=c.cards.slice(i,i+columns),height=Math.max(...batch.map(card=>card.h));
          batch.forEach((card,j)=>{card.wx=x+j*(CARD_W+110)+CARD_W/2;card.wy=y+localY+card.h/2+(j%2?24:0);card.members.forEach(m=>{Q[m.id].wx=card.wx;Q[m.id].wy=card.wy;});});
          localY+=height+100;
        }
        c.box={l:x,t:y,r:x+width,b:y+localY-70,w:width,h:localY-70};
        c.cx=x+width/2;c.cy=y+(localY-70)/2;c.idx=contentCats.indexOf(c);c.artSize=180;
        c.crossCards=[...new Set(c.qs.map(q=>CARD_BY_Q[q.id]).filter(card=>card.primaryCategory!==name))];
        c.box.b+=c.crossCards.length*70;c.box.h=c.box.b-c.box.t;
        maxHeight=Math.max(maxHeight,c.box.h);x+=width+520;
      });y+=maxHeight+620;
    });
    const l = Math.min(...contentCats.map((c) => c.box.l)) - 300, t = Math.min(...contentCats.map((c) => c.box.t)) - 420;
    const r = Math.max(...contentCats.map((c) => c.box.r)) + 300, b = Math.max(...contentCats.map((c) => c.box.b)) + 260;
    WB = { l, t, r, b, w: r - l, h: b - t };
  }

  function savedNotes() {
    return (window.STARTUP_CAMI_MODEL?.interviewNotes || []).filter(note => note.source === 'note');
  }

  function notesFor(questionId) {
    return savedNotes().filter(note => note.questionIds.includes(questionId));
  }

  function notePreview(text, length) {
    const characters = Array.from(text);
    return characters.length > length ? characters.slice(0, length).join('') + '…' : text;
  }

  function noteRows(turns) {
    return turns.map(turn => {
      const questions = turn.questionIds.filter(id => Q[id]).map(id => Q[id].question);
      return `<details class="note-row">
        <summary><span>${esc(notePreview(turn.text, 88))}</span><small>${tr('Read full note')}</small></summary>
        <div class="note-full">${esc(turn.text)}</div>
        <p class="hint">${questions.length ? questions.map(esc).join(' · ') : tr('Not linked to a question yet')}</p>
      </details>`;
    }).join('');
  }

  function notesPanel(id) {
    const turns = notesFor(id);
    if (!turns.length) return '';
    const isAccepted = answerOf(id).recordStatus === 'accepted';
    return `<details class="founder-notes"><summary>${tr('Saved interview notes')} · ${turns.length}</summary>
      <p class="note-state">${tr(isAccepted ? 'Note saved · Answer accepted' : 'Note saved · Answer not accepted')}</p>
      ${noteRows(turns)}</details>`;
  }

  function openNotes() {
    const turns = savedNotes();
    showDialog(`<h2 id="dlg-title">${tr('Interview notes')} · ${turns.length}</h2>
      <p class="hint">${tr('Detailed notes saved in project YAML.')}</p>
      ${noteRows(turns)}
      <button type="button" class="btn" data-action="close-dialog">${tr('Close')}</button>`);
  }

  function cardProgress(card) {
    const accepted=card.members.filter(m=>completed(answerOf(m.id))).length;
    const pending=card.members.filter(m=>!completed(answerOf(m.id)));
    const otherPending=card.other.filter(m=>!completed(answerOf(m.id)));
    return {accepted,total:card.members.length,pending,otherPending};
  }

  function cardMembersHtml(id) {
    if(isCore())return coreFollowupsHtml(id);
    const card=CARD_BY_Q[id];if(!card)return '';
    const labels={'主問題':'Primary question','相近問法，語境仍保留':'Similar questions, original context','同一件事的補充檢查':'Additional checks','換個角度檢查':'On the other hand'};
    const stats=cardProgress(card);
    const groups=Object.entries(labels).map(([kind,label])=>{
      const members=card.members.filter(m=>m.presentation===kind);if(!members.length)return '';
      return `<details ${members.some(m=>m.id===id)?'open':''}><summary>${esc(tr(label))} · ${members.length}</summary>${members.map(m=>`<button class="cluster-member ${m.id===id?'current':''}" type="button" data-action="goto" data-id="${m.id}" ${m.id===id?'aria-current="true"':''}>${statusIcon(answerOf(m.id).status)}<span>${esc(Q[m.id].question)}<small>${esc(cn(Q[m.id].category))} · ${esc(I18N.locale==='zh-TW'?Q[m.id].audience:Q[m.id].audienceEn)}</small></span></button>`).join('')}</details>`;
    }).join('');
    const reminders=card.cautionIds.length?`<details class="cluster-cautions"><summary>${tr('Interview cautions')} · ${card.cautionIds.length}</summary>${card.cautionIds.map(cid=>`<p>${esc(Q[cid].question)}<small>${esc(Q[cid].sourceSection)} · ${esc(Q[cid].sourceRange)}</small></p>`).join('')}</details>`:'';
    return `<section class="cluster-members" aria-label="${tr('Questions on this card')}"><h3>${tr('Questions on this card')} · ${stats.accepted}/${stats.total} ${progressLabel()}</h3>${groups}${reminders}</section>`;
  }

  function coreFollowupsHtml(id) {
    const q=Q[id];
    const groups=[['alternateQuestions',I18N.locale==='zh-TW'?'換句話問':'Other ways to ask'],['followups',I18N.locale==='zh-TW'?'追問與評估條件':'Follow-ups and evaluation checks']];
    return groups.map(([key,title])=>{
      const items=(q[key] || []).map(item=>typeof item==='string'?item:localValue(item)).filter(Boolean);
      return items.length ? `<details class="cluster-members"><summary>${esc(title)} · ${items.length}</summary><ul>${items.map(item=>`<li>${esc(item)}</li>`).join('')}</ul></details>` : '';
    }).join('');
  }

  function applyContentLocale() {
    const translations=I18N.catalog().questions || {};
    for(const q of Object.values(Q)) {
      const original=q._original, localized=translations[q.id] || {};
      for(const key of ['question','help','audience','audienceEn','sourceSection','sourceRange','editorialNote']) q[key]=localized[key] ?? original[key];
      if(isCore())q.question=localValue(original.prompt) || original.question;
      q.grounding=isCore() ? null : localized.grounding || window.STARTUP_CAMI_TRANSLATIONS?.['zh-TW']?.questions?.[q.id]?.grounding || null;
    }
    if(isCore() && S.venture)for(const [id,a] of Object.entries(S.venture.answers))a.text=localValue(window.STARTUP_CAMI_MODEL.answers[id]?.textI18n) || window.STARTUP_CAMI_MODEL.answers[id]?.text || '';
  }
  function changeLocale(value) {
    cancelAnim();
    I18N.setLocale(value); $('#language-select').value=I18N.locale; applyContentLocale(); I18N.staticText();
    const selected=S.selectedId, camera={...S.cam};
    const keepFit=selected && !S.camTouched && tileVisible(selected, 0);
    const anchor=selected && {x:Q[selected].wx,y:Q[selected].wy};
    layoutClusters();
    if(anchor){camera.x+=Q[selected].wx-anchor.x;camera.y+=Q[selected].wy-anchor.y;}
    buildCollage();
    hidePreview(true); closeMenus(); culled.clear(); $('#world').replaceChildren(); buildWorld();
    refreshAllTiles(); renderProgress(); renderOutline(); renderOutlineCurrent();
    if(S.panelOpen)renderPanel(); updateSaveStatus();
    S.cam=camera;
    if(keepFit) {
      const q=Q[selected], fit=cardFitScale(CARD_BY_Q[selected],mapArea());
      if(fit < camera.s || !tileVisible(selected,0)) S.cam=cardReadingCamera(q.id,Math.min(camera.s,fit));
    }
    applyCamera(true); if(selected)setRoving(selected);
    if($('#search-input').value)runSearch();
    window.parent.postMessage({type:'startup-cami:locale',locale:I18N.locale},location.origin==='null'?'*':location.origin);
  }

  function startCanvas() {
    const ui = S.venture.ui;
    refreshAllTiles();
    renderGuide();
    renderOutline();
    renderProgress();
    measure();
    const pending = progressData(mainQs, S.venture.answers).pending;
    const next = window.STARTUP_CAMI_MODEL && nextIncomplete(pending);
    const sel = next?.id || (ui.selectedId && Q[ui.selectedId] && !Q[ui.selectedId].caution ? ui.selectedId : mainQs.find(q=>completed(answerOf(q.id)))?.id || routeIds[0]);
    setRoving(sel);
    if (next) {
      selectQuestion(sel, { history: false, openPanel: true, restoring: true });
      if (S.mode === 'mobile') setSheet('peek');
      const target = cardReadingCamera(sel,cardFitScale(CARD_BY_Q[sel], mapArea()));
      setCam(target.x, target.y, target.s);
    } else if (ui.camera && Number.isFinite(ui.camera.s) && (!ui.camera.mode || ui.camera.mode === S.mode)) {
      S.cam = { ...ui.camera, s: clamp(ui.camera.s, minS(), MAX_S) };
      applyCamera(true);
      selectQuestion(sel, { fly: false, history: false, openPanel: ui.panelOpen !== false, restoring: true });
    } else {
      S.cam.s = START_S;
      const phone = S.mode === 'mobile';
      selectQuestion(sel, { fly: false, history: false, openPanel: !phone && !answerOf(sel).text, restoring: true });
      placeTileAt(sel, 0.44, 0.46);
    }
    updateSaveStatus(S.venture.updatedAt ? 'reopened' : null);
    document.documentElement.classList.add('ready');
  }

  // =====================================================================
  // Read-only snapshot (navigation state exists only in memory)
  // =====================================================================
  function readPrefs() { return {tips:{}}; }
  function writePrefs() {} // Browsing preferences live in memory only.
  function scheduleUiSave() {} // Navigation never writes project data.
  function persistIfDirty() {} // Legacy navigation hook; no persistence in a view.
  function restoreVenture() {
    const m = window.STARTUP_CAMI_MODEL || {project:{}, answers:{}, source:{}};
    const input = Array.isArray(m.answers) ? Object.fromEntries(m.answers.map(a=>[a.question_id,a])) : m.answers || {};
    const answers = {};
    for (const [id,a] of Object.entries(input)) {
      if (!Q[id] || Q[id].caution) continue;
      const recordStatus = a.effective_status || a.status || 'unreviewed';
      const status = ({accepted:'answered',saved:'saved',unreviewed:'draft',needs_review:'revisit',unverifiable:'unverifiable'})[recordStatus] || 'draft';
      answers[id] = {...a, text:a.text || '', status, recordStatus, evidence:(a.claims || []).map(c=>({text:c.text || c.claim || '',state:c.evidence_status || c.status || 'reported',source_refs:c.source_refs || []}))};
    }
    S.venture = {name:m.project.name || m.project.title || 'Cami Startup Canvas', answers, ui:{route:{on:false,index:0,branch:null},visited:[],history:[],exampleSeen:{}}};
    return true;
  }
  function answerOf(id) { return S.venture.answers[id] || {text:'',status:'not-answered',recordStatus:'not-answered',evidence:[],scores:{}}; }
  function updateSaveStatus() {
    const source=window.STARTUP_CAMI_MODEL?.source, e=$('#save-status');
    e.textContent=source ? tr('yaml revision',{revision:source.revision ?? '?'}) : tr('Read-only · Question catalog preview');
    e.title=source ? tr(window.STARTUP_CAMI_LIVE ? 'live source hash hint' : 'source hash hint',{sha:source.sha256 || tr('none')}) : tr('Generate a snapshot from your startup project YAML to see answers.');
  }


  // Pure progress calculation: only current accepted answers count; cautions never count.
  function progressData(questions, answers) {
    const active = questions.filter(q => !q.caution && !q.cautionOnly);
    const pending = active.filter(q => !completed(answers[q.id]));
    const count = status => active.filter(q => answers[q.id]?.recordStatus === status).length;
    const accepted = active.length - pending.length;
    return {total:active.length,accepted,pending,percent:active.length ? Math.floor(accepted / active.length * 100) : 0,
      missing:active.filter(q=>!answers[q.id]?.text?.trim()).length,
      review:count('unreviewed')+count('needs_review'),unverifiable:count('unverifiable')};
  }
  function previousAnswered() {
    const answered = mainQs.filter(q => completed(answerOf(q.id)));
    const current = answered.findIndex(q => q.id === S.selectedId);
    return answered[current < 0 ? answered.length - 1 : current - 1];
  }
  function updatePreviousAnswered() {
    const button = $('#previous-answered');
    if (button) button.disabled = !previousAnswered();
  }
  function nextIncomplete(pending) {
    return pending.find(q => q.id === window.STARTUP_CAMI_MODEL?.next_question_id) || pending[0];
  }
  function renderProgress() {
    const p = progressData(mainQs, S.venture.answers);
    const next = nextIncomplete(p.pending);
    $('#progress-summary').classList.toggle('all-filled',!next);
    const source = window.STARTUP_CAMI_MODEL?.source;
    const cardsDone = CARDS.filter(c => cardProgress(c).accepted === c.members.length).length;
    const sourceLabel = source ? tr('yaml revision',{revision:source.revision}) : tr('Catalog preview · no project loaded');
    $('#progress-summary').innerHTML = `
      <div class="progress-heading">
        <button type="button" id="next-missing" class="resume-question" ${next ? '' : 'disabled'}>
          <small>${next ? tr('Next question') + ' · ' + esc(cn(next.category)) : isCore() ? (I18N.locale==='zh-TW'?'全部已填':'All filled') : tr('Complete')}</small>
          <strong id="next-question-title">${next ? esc(next.question) : isCore() ? (I18N.locale==='zh-TW'?'選一張便條紙，檢視你的答案':'Choose a card to review your answer') : tr('Nothing outstanding in this snapshot.')}</strong>
        </button>
        <div class="progress-disclosure">
          <button type="button" id="progress-details" aria-expanded="false" aria-controls="progress-counts">
            <strong>${p.accepted} / ${p.total} ${progressLabel()} <span>${p.accepted && !p.percent ? '&lt;1' : p.percent}%</span></strong> ▾
          </button>
          <div hidden id="progress-counts" class="progress-counts">
            ${p.missing} ${tr('not answered')}${isCore() ? '' : ` · ${p.review} ${tr('need review')} · ${p.unverifiable} ${tr('unverifiable')}`}<br>
            ${cardsDone}/${CARDS.length} ${tr('cards complete')} · ${esc(sourceLabel)}
          </div>
        </div>
      </div>
      <progress max="${p.total || 1}" value="${p.accepted}" aria-label="${isCore() ? (I18N.locale==='zh-TW'?'已填回答':'Answers filled') : tr('Answers accepted')}">${p.percent}%</progress>`;
    $('#all-notes').hidden = !savedNotes().length;
    const disclosure = $('.progress-disclosure');
    const trigger = $('#progress-details');
    const showCounts = open => {
      $('#progress-counts').hidden = !open;
      trigger.setAttribute('aria-expanded', String(open));
    };
    let pinned = false;
    trigger.onclick = () => { pinned = !pinned; showCounts(pinned); };
    disclosure.onpointerenter = event => { if (event.pointerType === 'mouse') showCounts(true); };
    disclosure.onpointerleave = () => { if (!pinned) showCounts(false); };
    trigger.onfocus = () => { if (trigger.matches(':focus-visible')) showCounts(true); };
    trigger.onblur = () => { pinned = false; showCounts(false); };
    trigger.onkeydown = event => { if (event.key === 'Escape') { event.stopPropagation(); pinned = false; showCounts(false); } };
    updatePreviousAnswered();
    $('#previous-answered').onclick = () => {
      const target = previousAnswered();
      closeMenus();
      if (target) selectQuestion(target.id,{fly:true,center:true,openPanel:true,focusPanel:true});
    };
    $('#next-missing').onclick = () => {
      if (!next) return;
      if (S.selectedId === next.id && S.panelOpen && tileVisible(next.id, 0)) {
        $('#panel-q').focus();
        return;
      }
      selectQuestion(next.id,{fly:true,center:true,openPanel:true,focusPanel:true});
    };
  }

  const world = () => $('#world');
  function buildWorld() {
    const w = world();
    const frag = document.createDocumentFragment();
    for (const c of contentCats) {
      const g = document.createElement('div');
      g.className = 'cat-group';
      g.setAttribute('role', 'group');
      g.setAttribute('aria-label', cn(c.name));
      const titleMax = Math.max(c.box.w - c.artSize - 40, 260);
      const title = document.createElement('div');
      title.className = 'cat-title' + (c.idx % 2 ? ' alt' : '') + (c.idx % 3 === 0 ? ' spark' : '');
      title.style.cssText = `--x:${c.box.l};--y:${c.box.t - 52};--tw:${titleMax}`;
      title.innerHTML = `<button type="button" class="cat-title-btn" data-cat="${esc(c.name)}" tabindex="-1" aria-label="${esc(tr('show area',{name:cn(c.name)}))}">${esc(cn(c.name))}</button>`;
      const plaque = document.createElement('div');
      plaque.className = 'cat-plaque';
      plaque.setAttribute('aria-hidden', 'true');
      plaque.style.cssText = `--x:${c.box.l};--y:${c.box.t - 88};--pw:${c.box.w}`;
      plaque.innerHTML = `<span class="pl-name">${esc(cn(c.name))}</span><span class="pl-count" data-count="${esc(c.name)}"></span>`;
      g.append(title, plaque);
      for (const card of c.cards) g.append(buildTile(Q[card.id]));
      c.crossCards.forEach((card,i)=>{
        const link=document.createElement('button');link.type='button';link.className='cross-card';link.dataset.action='goto';
        link.dataset.id=card.members.find(m=>Q[m.id].category===c.name).id;
        link.style.cssText=`--x:${c.box.l};--y:${c.box.b-(c.crossCards.length-i)*70};--cw:${c.box.w}`;
        link.textContent=`↗ ${cn(card.primaryCategory)} · ${Q[link.dataset.id].question}`;g.append(link);
      });
      frag.append(g);
    }
    const labels = document.createElement('div');
    labels.className = 'labels-layer';
    labels.id = 'labels-layer';
    frag.append(labels);
    w.append(frag);
  }

  const questionNumber = id => mainQs.findIndex(q => q.id === id) + 1;
  const numberedQuestion = q => isCore() ? `${questionNumber(q.id)}. ${q.question}` : q.question;

  function buildTile(q) {
    const card=CARD_BY_Q[q.id], b=document.createElement('article');
    b.className='tile cluster-tile';b.id=`t-${card.id}`;b.dataset.id=card.id;b.setAttribute('role','group');
    b.style.cssText=`--x:${card.wx};--y:${card.wy};--cw:${card.w};--ch:${card.h};--rot:${q.rot}deg`;
    b.innerHTML=`${isCore() ? `<span class="question-number" aria-hidden="true">${questionNumber(q.id)}</span>` : ''}<span class="tile-body"><span class="shade"></span><span class="paper"></span><span class="tape" style="--tw:60;--tx:40%;--tr:-3deg"></span></span><button type="button" class="tile-main" tabindex="-1"><span class="tile-text">${esc(q.question)}</span><span class="card-progress"></span><span class="card-missing"></span><span class="stamp"></span><span class="clip" hidden></span></button><div class="card-answer"></div><div class="card-notes"></div><div class="card-other"></div>`;
    return b;
  }

  // Torn colored scraps behind each title, plus illustrations, in world units (SVG).
  function tornRect(x, y, w, h, seed, depth = 14) {
    const pts = [];
    const n = Math.max(6, Math.round(w / 60)), m = Math.max(3, Math.round(h / 50));
    let r = seed;
    const rnd = () => { r = (Math.imul(r, 1103515245) + 12345) >>> 0; return (r % 1000) / 1000; };
    for (let i = 0; i <= n; i++) pts.push([x + (w * i) / n, y + (rnd() - 0.5) * depth]);
    for (let i = 1; i <= m; i++) pts.push([x + w + (rnd() - 0.5) * depth, y + (h * i) / m]);
    for (let i = n - 1; i >= 0; i--) pts.push([x + (w * i) / n, y + h + (rnd() - 0.5) * depth]);
    for (let i = m - 1; i >= 1; i--) pts.push([x + (rnd() - 0.5) * depth, y + (h * i) / m]);
    return 'M' + pts.map((p) => p.map((v) => v.toFixed(1)).join(' ')).join(' L') + ' Z';
  }

  function buildCollage() {
    const gc = $('#g-collage'), ga = $('#g-art');
    let html = '';
    // Large ambient scraps at the edges of the world (decoration only).
    const amb = [
      [WB.l + 200, WB.t + 160, 1500, 520, '#2448E8', -4], [WB.r - 1700, WB.t + 120, 1500, 460, '#D64024', 3],
      [WB.l + 300, WB.b - 640, 1300, 480, '#D64024', 2], [WB.r - 1500, WB.b - 600, 1300, 460, '#2448E8', -3],
    ];
    amb.forEach(([x, y, w, h, col, rot], i) => {
      html += `<path d="${tornRect(x, y, w, h, 77 + i, 40)}" fill="${col}" opacity=".9" transform="rotate(${rot} ${x + w / 2} ${y + h / 2})"/>`;
      html += `<path d="${tornRect(x + 30, y + 40, w * 0.92, h * 0.3, 91 + i, 30)}" fill="url(#halftone)" transform="rotate(${rot} ${x + w / 2} ${y + h / 2})"/>`;
    });
    for (const c of contentCats) {
      const col = c.idx % 2 ? '#D64024' : '#2448E8';
      const w = clamp(c.box.w * 0.62, 520, 980), h = 190;
      const x = c.box.l - 90, y = c.box.t - 250;
      const rot = ((hash(c.name) % 5) - 2) * 0.9;
      html += `<path class="scrap" d="${tornRect(x, y, w, h, hash(c.name), 22)}" fill="${col}" transform="rotate(${rot} ${x + w / 2} ${y + h / 2})"/>`;
      // A second scrap in the other colour peeks out from under one corner of the cards.
      const hv = hash(c.name + 'b');
      const col2 = c.idx % 2 ? '#2448E8' : '#D64024';
      const w2 = 380 + (hv % 260), h2 = 240 + ((hv >> 4) % 160);
      const left = (hv >> 8) % 2 === 0;
      const x2 = left ? c.box.l - 150 : c.box.r - w2 + 150, y2 = c.box.b - h2 + 140;
      const rot2 = (((hv >> 12) % 7) - 3) * 1.4;
      html += `<path d="${tornRect(x2, y2, w2, h2, hv, 26)}" fill="${col2}" transform="rotate(${rot2} ${x2 + w2 / 2} ${y2 + h2 / 2})"/>`;
      html += `<path d="${tornRect(x2 + 24, y2 + 30, w2 * 0.5, h2 * 0.45, hv + 3, 18)}" fill="url(#halftone)" transform="rotate(${rot2} ${x2 + w2 / 2} ${y2 + h2 / 2})"/>`;
    }
    gc.innerHTML = html;
    let art = '';
    for (const c of contentCats) {
      const s = c.artSize;
      const x = c.box.r - s, y = c.box.t - 30 - s;
      art += `<g class="art" data-cat="${esc(c.name)}"><use href="#art-${c.art}" x="${x}" y="${y}" width="${s}" height="${s}"/><rect x="${x}" y="${y}" width="${s}" height="${s}" fill="transparent"/></g>`;
    }
    ga.innerHTML = art;
    drawRoads();
  }

  // ---------- geometry for paths ----------
  function edgePoint(rect, tx, ty, pad = 0) {
    const cx = (rect.l + rect.r) / 2, cy = (rect.t + rect.b) / 2;
    const hw = (rect.r - rect.l) / 2 + pad, hh = (rect.b - rect.t) / 2 + pad;
    const dx = tx - cx, dy = ty - cy;
    if (!dx && !dy) return [cx, cy];
    const k = Math.min(hw / Math.abs(dx || 1e-9), hh / Math.abs(dy || 1e-9));
    return [cx + dx * k, cy + dy * k];
  }
  function curve(a, b, bend = 0.18) {
    const [x1, y1] = a, [x2, y2] = b;
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1;
    const nx = -dy * bend, ny = dx * bend;
    const c1 = [x1 + dx * 0.25 + nx, y1 + dy * 0.25 + ny], c2 = [x1 + dx * 0.75 + nx, y1 + dy * 0.75 + ny];
    return { d: `M${x1} ${y1} C${c1[0]} ${c1[1]} ${c2[0]} ${c2[1]} ${x2} ${y2}`, mid: [mx + nx * 0.75, my + ny * 0.75], end: [x2, y2], c2 };
  }
  function arrowHead(end, from, size) {
    const ang = Math.atan2(end[1] - from[1], end[0] - from[0]);
    const a1 = ang + Math.PI * 0.82, a2 = ang - Math.PI * 0.82;
    return `M${end[0] + Math.cos(a1) * size} ${end[1] + Math.sin(a1) * size} L${end[0]} ${end[1]} L${end[0] + Math.cos(a2) * size} ${end[1] + Math.sin(a2) * size}`;
  }
  const catRect = (c) => ({ l: c.box.l, t: c.box.t, r: c.box.r, b: c.box.b });
  const tileRect = (q) => { const c=CARD_BY_Q[q.id];return {l:q.wx-c.w/2,t:q.wy-c.h/2,r:q.wx+c.w/2,b:q.wy+c.h/2}; };

  function roadBetween(ra, rb, bend, size, pad) {
    const ca = [(ra.l + ra.r) / 2, (ra.t + ra.b) / 2], cb = [(rb.l + rb.r) / 2, (rb.t + rb.b) / 2];
    const a = edgePoint(ra, cb[0], cb[1], pad), b = edgePoint(rb, ca[0], ca[1], pad);
    const c = curve(a, b, bend);
    return { ...c, head: arrowHead(c.end, c.c2, size) };
  }

  function drawRoads() { $('#g-roads').innerHTML=''; }

  // Lines for the current selection (max four), or for a focused category.
  function drawLinks() {
    const g = $('#g-links'), labels = $('#labels-layer');
    const s = S.cam.s;
    let html = '', lab = '';
    if (S.focusCategory) {
      const c = CATS[S.focusCategory];
      const rows = D.relations.filter((r) => r.from === c.name || r.to.includes(c.name));
      for (const r of rows) {
        const targets = r.from === c.name ? r.to : [c.name];
        const from = r.from === c.name ? c : CATS[r.from];
        for (const tn of targets) {
          const t = CATS[tn];
          if (t === from) continue;
          const road = roadBetween(catRect(from), catRect(t), 0.16, 18 / s, 90);
          html += `<path class="link-cat" d="${road.d}"/><path class="link-cat" d="${road.head}"/>`;
          lab += `<span class="link-label" style="--x:${road.mid[0]};--y:${road.mid[1]}">${esc(tr(r.label))}</span>`;
        }
      }
    } else if (S.selectedId && S.level !== 'world') {
      for (const rel of relatedOf(S.selectedId)) {
        const qa = Q[S.selectedId], qb = Q[rel.id];
        if (Math.hypot(qa.wx - qb.wx, qa.wy - qb.wy) < 420) continue; // adjacent cards: the neighbour itself is the relation
        const road = roadBetween(tileRect(Q[S.selectedId]), tileRect(Q[rel.id]), 0.22, 12 / s, 16);
        html += `<path class="link-q ${rel.kind}" d="${road.d}"/><path class="link-q ${rel.kind}" d="${road.head}"/>`;
      }
    }
    g.innerHTML = html;
    labels.innerHTML = lab;
  }

  // =====================================================================
  // Camera
  // =====================================================================
  let stageRect = { w: 1, h: 1, top: 64 };
  function measure() {
    const r = $('#stage').getBoundingClientRect();
    stageRect = { w: r.width, h: r.height, top: r.top, left: r.left };
    const w = window.innerWidth;
    S.mode = w < 768 ? 'mobile' : w < 1200 ? 'tablet' : 'desktop';
    document.documentElement.dataset.mode = S.mode;
    const mm = $('#minimap-canvas');
    const [mw, mh] = S.mode === 'desktop' ? [160, 120] : [120, 90];
    if (mm.width !== mw * devicePixelRatio) { mm.width = mw * devicePixelRatio; mm.height = mh * devicePixelRatio; mm.style.width = mw + 'px'; mm.style.height = mh + 'px'; }
  }

  // Map area = part of the stage not covered by the panel/sheet.
  function mapArea() {
    const { w, h } = stageRect;
    const ol = S.mode !== 'mobile' && !$('#outline').hidden ? 412 : 0;
    if (!S.panelOpen) return { l: ol, t: 0, w: w - ol, h };
    if (S.mode === 'mobile') { const sh = Math.min(sheetPx(), $('#panel').getBoundingClientRect().height || sheetPx()); return { l: 0, t: 0, w, h: Math.max(120, h - sh) }; }
    const pw = (S.mode === 'desktop' ? 400 : 360) + 32;
    return { l: ol, t: 0, w: Math.max(200, w - pw - ol), h };
  }

  function worldToScreen(x, y) {
    const { s } = S.cam;
    return [(x - S.cam.x) * s + stageRect.w / 2, (y - S.cam.y) * s + stageRect.h / 2];
  }
  function screenToWorld(px, py) {
    const { s } = S.cam;
    return [(px - stageRect.w / 2) / s + S.cam.x, (py - stageRect.h / 2) / s + S.cam.y];
  }

  let lastS = null, commitT = null;
  function commitScale(s) {
    const wd = world();
    wd.style.setProperty('--s', s);
    lastS = s;
    updateLevel();
    drawRoads();
    drawLinks();
    $('#zoom-level').textContent = `${Math.round(s * 100)}%`;
  }
  function applyCamera(force) {
    const { x, y, s } = S.cam;
    const { w, h } = stageRect;
    const tx = w / 2 - x * s, ty = h / 2 - y * s;
    const wd = world();
    // While the scale is changing, the laid-out world is only GPU-scaled; layout at the new
    // scale is committed once zooming pauses, so text returns to crisp screen-size type.
    if (force || lastS === null) commitScale(s);
    const k = s / lastS;
    wd.style.transform = k === 1 ? `translate3d(${tx}px, ${ty}px, 0)` : `translate3d(${tx}px, ${ty}px, 0) scale(${k})`;
    if (k !== 1) {
      $('#zoom-level').textContent = `${Math.round(s * 100)}%`;
      clearTimeout(commitT);
      commitT = setTimeout(() => { commitScale(S.cam.s); applyCamera(); }, 140);
    }
    $('#world-svg').setAttribute('viewBox', `${x - w / 2 / s} ${y - h / 2 / s} ${w / s} ${h / s}`);
    cullTiles();
    drawMinimap();
    // Signposts and tips are measured DOM; refresh them once the camera settles.
    const stage = $('#stage');
    stage.classList.add('moving');
    clearTimeout(settleT);
    settleT = setTimeout(() => { stage.classList.remove('moving'); positionTips(); updateSigns(); }, 120);
    if (S.previewId && !S.previewPinned) hidePreview(true);
    scheduleUiSave();
  }
  let settleT = null;

  // Keep only tiles within one screen of the viewport in layout (spec 十: virtualise off-screen questions).
  const culled = new Set();
  function cullTiles() {
    const { w, h } = stageRect, s = S.cam.s;
    const mx = w / s, my = h / s; // one extra screen on every side
    const l = S.cam.x - w / 2 / s - mx, r = S.cam.x + w / 2 / s + mx, t = S.cam.y - h / 2 / s - my, b = S.cam.y + h / 2 / s + my;
    for (const card of CARDS) {
      const q=Q[card.id];
      const off = (q.wx + CARD_W / 2 < l || q.wx - CARD_W / 2 > r || q.wy + card.h / 2 < t || q.wy - card.h / 2 > b) && card !== CARD_BY_Q[S.selectedId] && card !== CARD_BY_Q[S.rovingId];
      if (off !== culled.has(q.id)) {
        const el = tileEl(q.id);
        if (!el) continue;
        el.classList.toggle('off', off);
        if (off) culled.add(q.id); else culled.delete(q.id);
      }
    }
  }

  function updateLevel() {
    const s = S.cam.s, H = 0.02;
    let lv = S.level;
    if (lv === 'world') { if (s > 0.2 + H) lv = s >= 0.65 + H ? 'question' : 'category'; }
    else if (lv === 'category') { if (s < 0.2 - H) lv = 'world'; else if (s > 0.65 + H) lv = 'question'; }
    else { if (s < 0.65 - H) lv = s < 0.2 - H ? 'world' : 'category'; }
    if (s < 0.2 - H) lv = 'world';
    if (s > 0.65 + H) lv = 'question';
    let far = S.farTitles;
    if (far && s > 0.42 + H) far = false; else if (!far && s < 0.42 - H) far = true;
    const stage = $('#stage');
    if (lv !== S.level || !stage.classList.contains(`lv-${lv}`)) {
      stage.classList.remove('lv-world', 'lv-category', 'lv-question');
      stage.classList.add(`lv-${lv}`);
      S.level = lv;
    }
    S.farTitles = far;
    stage.classList.toggle('titles-far', far);
    // Card text: screen-size type, never world-scaled.
    const cardH = CARD_H * s, pad = 20 * s, cardW = CARD_W * s;
    const fs = lv === 'question' ? 20 : 15, lh = lv === 'question' ? 28 : 20;
    const lines = Math.min(lv === 'question' ? 3 : 2, Math.floor((cardH - 2 * pad) / lh));
    const textOn = lv !== 'world' && cardW >= 124 && lines >= 1;
    const wd = world();
    wd.style.setProperty('--qfs', fs + 'px');
    wd.style.setProperty('--qlh', lh + 'px');
    wd.style.setProperty('--lines', Math.max(1, lines));
    wd.style.setProperty('--tfs', clamp(52 * s, 28, 48) + 'px');
    wd.style.setProperty('--pfs', clamp(220 * s - 0.5, 11.5, 18) + 'px');
    stage.classList.toggle('text-off', !textOn);
    stage.classList.toggle('labels-off', s < 0.045); // plaques cannot fit below this scale
  }

  function setCam(x, y, s) {
    S.cam = { x: clamp(x, WB.l, WB.r), y: clamp(y, WB.t, WB.b), s: clamp(s, minS(), MAX_S) };
    applyCamera();
  }

  function cancelAnim() { if (S.anim) { cancelAnimationFrame(S.anim.raf); S.anim = null; } }

  // Camera target so world point (wx,wy) lands at fraction (fx,fy) of the map area.
  function camFor(wx, wy, s, fx = 0.5, fy = 0.5) {
    const a = mapArea();
    const px = a.l + a.w * fx, py = a.t + a.h * fy;
    return { x: wx - (px - stageRect.w / 2) / s, y: wy - (py - stageRect.h / 2) / s, s };
  }

  function flyTo(target, opts = {}) {
    cancelAnim();
    const from = { ...S.cam };
    target = { x: clamp(target.x, WB.l, WB.r), y: clamp(target.y, WB.t, WB.b), s: clamp(target.s, minS(), MAX_S) };
    if (noMotion() || opts.instant) { S.cam = target; applyCamera(); opts.done && opts.done(); return; }
    const viewW = stageRect.w / from.s, viewH = stageRect.h / from.s;
    const far = Math.abs(target.x - from.x) > viewW || Math.abs(target.y - from.y) > viewH;
    const dur = opts.duration || (far ? 300 : 220);
    const midS = far ? Math.min(from.s, target.s) * 0.55 : null;
    const t0 = performance.now();
    const step = (t) => {
      const k = clamp((t - t0) / dur, 0, 1);
      let s;
      if (far) {
        const split = 120 / 300;
        s = k < split ? from.s + (midS - from.s) * ease(k / split) : midS + (target.s - midS) * ease((k - split) / (1 - split));
      } else s = from.s + (target.s - from.s) * ease(k);
      const e = ease(k);
      S.cam = { x: from.x + (target.x - from.x) * e, y: from.y + (target.y - from.y) * e, s };
      applyCamera();
      if (k < 1) S.anim.raf = requestAnimationFrame(step);
      else { S.anim = null; S.cam = target; applyCamera(); opts.done && opts.done(); }
    };
    S.anim = { raf: requestAnimationFrame(step) };
  }

  function placeTileAt(id, fx, fy) {
    const q = Q[id];
    S.cam = camFor(q.wx, q.wy, S.cam.s, fx, fy);
    applyCamera(true);
  }

  function cardFitScale(card,area) {
    return Math.max(minS(),Math.min(START_S,(area.w-32)/card.w,...(isCore()?[]:[(area.h-32)/card.h])));
  }

  function cardReadingCamera(id, scale) {
    const q=Q[id],card=CARD_BY_Q[id],area=mapArea();
    // 長卡片以可讀寬度定位到頂端，其餘內容透過平移閱讀，不因張數增加縮成小字。
    const overflow=isCore()?Math.max(0,card.h*scale-(area.h-32)):0;
    return camFor(q.wx,q.wy-overflow/(2*scale),scale);
  }

  function tileScreenRect(id) {
    const q = Q[id];
    const [x, y] = worldToScreen(q.wx, q.wy);
    const w = CARD_W * S.cam.s, h = CARD_BY_Q[id].h * S.cam.s;
    return { l: x - w / 2, t: y - h / 2, r: x + w / 2, b: y + h / 2 };
  }
  function tileVisible(id, margin = 8) {
    const r = tileScreenRect(id), a = mapArea();
    return r.l >= a.l + margin && r.r <= a.l + a.w - margin && r.t >= a.t + margin && r.b <= a.t + a.h - margin;
  }

  function zoomAt(px, py, ns, animate) {
    ns = clamp(ns, minS(), MAX_S);
    const [wx, wy] = screenToWorld(px, py);
    const target = { x: wx - (px - stageRect.w / 2) / ns, y: wy - (py - stageRect.h / 2) / ns, s: ns };
    if (animate) flyTo(target, { duration: 180 }); else { S.cam = target; applyCamera(); }
    S.camTouched = true;
  }

  function overview() {
    const a = mapArea();
    const band = S.mode === 'mobile' ? 70 : 100; // keep the bottom controls off the map
    const top = isCore() ? 52 : 12; // category titles and question badges remain inside the viewport
    const s = clamp(Math.min((a.w - 24) / WB.w, (a.h - band - top) / WB.h), minS(), 0.19);
    const fy = (top + (a.h - band - top) / 2) / a.h;
    flyTo(camFor(WB.l + WB.w / 2, WB.t + WB.h / 2, s, 0.5, fy));
    S.focusCategory = null; drawLinks();
    dismissTip('overview');
    S.camTouched = true;
    if (s < 0.045) toast(tr("Tap an area to zoom in, or open the question list."));
  }

  function zoomToCategory(name) {
    const c = CATS[name];
    const a = mapArea();
    const s = clamp(Math.min(a.w / (c.box.w + 500), a.h / (c.box.h + 700)), 0.23, 0.72);
    flyTo(camFor((c.box.l + c.box.r) / 2, (c.box.t + c.box.b) / 2 - 140, s));
    S.focusCategory = name;
    drawLinks();
    S.camTouched = true;
  }

  function backToQuestion() {
    if (!S.selectedId) return;
    S.focusCategory = null;
    const q = Q[S.selectedId];
    flyTo(camFor(q.wx, q.wy, S.cam.s < 0.65 ? START_S : S.cam.s));
    drawLinks();
  }

  // ---------- edge signposts: point to related areas that are off screen ----------
  function signTargets() {
    // The area nearest the centre of the visible map decides which neighbours get a signpost.
    const a = mapArea();
    const [mx, my] = screenToWorld(a.l + a.w / 2, a.t + a.h / 2);
    let name = null, bd = Infinity;
    for (const c of contentCats) {
      const dx = Math.max(c.box.l - mx, 0, mx - c.box.r), dy = Math.max(c.box.t - my, 0, my - c.box.b);
      const d = Math.hypot(dx, dy);
      if (d < bd) { bd = d; name = c.name; }
    }
    if (S.focusCategory) name = S.focusCategory;
    if (!name) return [];
    const out = [];
    const add = (n) => { if (n !== name && CATS[n] && !CATS[n].caution && !out.includes(n)) out.push(n); };
    D.mainRoad.forEach((r) => { if (r.from === name) add(r.to); if (r.to === name) add(r.from); });
    D.relations.forEach((r) => { if (r.from === name) r.to.forEach(add); if (r.to.includes(name)) add(r.from); });
    return out;
  }
  function updateSigns() {}

  function layoutOverlays() {
    const g = $('#guide'), z = $('.zoom'), m = $('#minimap');
    if (!g || S.mode === 'mobile') { if (g) { g.style.left = ''; g.style.bottom = ''; } if (z) z.style.left = ''; return; }
    const a = mapArea();
    const zr = z.getBoundingClientRect().right - stageRect.left;
    const ml = m.offsetParent ? m.getBoundingClientRect().left - stageRect.left : a.w;
    const gw = g.offsetWidth;
    let center = a.l + a.w / 2;
    z.style.left = (a.l + 16) + 'px';
    const lo = zr + 12 + gw / 2, hi = ml - 12 - gw / 2;
    if (lo <= hi) { center = clamp(center, lo, hi); g.style.bottom = ''; }
    else {
      center = clamp(center, a.l + 16 + gw / 2, a.l + a.w - 16 - gw / 2);
      const lift = Math.max(z.offsetHeight, m.offsetParent ? m.offsetHeight : 0) + 30;
      g.style.bottom = lift + 'px';
    }
    g.style.left = center + 'px';
    positionTips();
  }

  // ---------- minimap ----------
  function drawMinimap() {}

  function minimapToWorld(ev) {
    const cv = $('#minimap-canvas'), r = cv.getBoundingClientRect();
    const px = (ev.clientX - r.left) * (cv.width / r.width), py = (ev.clientY - r.top) * (cv.height / r.height);
    return [WB.l + (px - S.mm.ox) / S.mm.k, WB.t + (py - S.mm.oy) / S.mm.k];
  }

  // =====================================================================
  // Tiles: status, classes, roving tabindex
  // =====================================================================
  function tileEl(id) { return document.getElementById(`t-${CARD_BY_Q[id]?.id || id}`); }

  function keyPointRecord(id) {
    const records=window.STARTUP_CAMI_MODEL?.keyPoints?.[id];
    if(isCore() && records?.formal)return {...records.formal,points:records.formal.pointsI18n?.[I18N.locale] || records.formal.points,role:'formal'};
    if(!records)return null;
    if(records.points)return records;
    const role=answerOf(id).text?'formal':'pending';
    return records[role] ? {...records[role],role} : null;
  }
  function refreshTile(id, b=tileEl(id)) {
    const card=CARD_BY_Q[id];if(!card || !b)return;
    const stats=cardProgress(card),selected=card===CARD_BY_Q[S.selectedId];
    const activeId=selected ? S.selectedId : card.id;
    b.classList.toggle('is-selected',selected);b.classList.toggle('st-answered',stats.accepted===stats.total);
    const button=b.querySelector('.tile-main');button.setAttribute('aria-label',`${numberedQuestion(Q[activeId])} — ${stats.accepted}/${stats.total} ${progressLabel()}`);
    button.querySelector('.tile-text').textContent=Q[activeId].question;
    button.dataset.action='goto';button.dataset.id=activeId;
    if(selected)button.setAttribute('aria-current','true');else button.removeAttribute('aria-current');
    b.querySelector('.card-progress').textContent=`${stats.accepted}/${stats.total} ${progressLabel()}`;
    const points=keyPointRecord(activeId);
    const label=points?.role==='pending' ? (I18N.locale==='zh-TW'?'待評估':'Pending review') : '';
    b.querySelector('.card-answer').innerHTML=points?.points?.length
      ? `<div class="keypoint-grid">${points.points.map(point=>`<button type="button" class="keypoint" data-action="goto" data-id="${esc(activeId)}">${esc(point)}</button>`).join('')}</div>${label?`<p class="keypoint-state">${label}</p>`:''}`
      : '';
    b.querySelector('.card-notes').innerHTML=`<button type="button" data-action="goto" data-id="${esc(activeId)}">${I18N.locale==='zh-TW'?'完整答案':'Full answer'}${card.members.length>1?` · ${card.members.length} ${I18N.locale==='zh-TW'?'個相關問題':'related questions'}`:''}</button>`;
    const marked = stats.pending.find(member => member.id === window.STARTUP_CAMI_MODEL?.next_question_id);
    const missing = marked || stats.pending[0];
    b.classList.toggle('has-next-question', Boolean(marked));
    b.querySelector('.card-missing').textContent = marked ? tr('Next incomplete') : '';
    b.querySelector('.stamp').innerHTML=icon(isCore() && stats.accepted===stats.total?'stDraft':stats.accepted===stats.total?'stAnswered':'stNot');
    const target=stats.otherPending[0] || card.other[0];
    b.querySelector('.card-other').innerHTML=target?`<button type="button" data-action="goto" data-id="${target.id}" class="other-hand ${card.other.some(m=>m.id===S.selectedId)?'current':''}"><strong>${tr('On the other hand')} · ${stats.otherPending.length} ${tr('incomplete')}</strong><span>${esc(Q[target.id].question)}</span></button>`:'';
  }

  function refreshAllTiles() {
    CARDS.forEach((card) => refreshTile(card.id));
    updateCounts();
    setRoving(S.rovingId || routeIds[0]);
  }

  function updateCounts() {
    for (const c of contentCats) {
      const n = c.qs.filter((q) => completed(answerOf(q.id))).length;
      const el = document.querySelector(`[data-count="${CSS.escape(c.name)}"]`);
      if (el) el.textContent = `${n}/${c.qs.length} ${progressLabel()}`;
    }
  }

  function setRoving(id) {
    if (S.rovingId && tileEl(S.rovingId)) tileEl(S.rovingId).querySelector('.tile-main').tabIndex = -1;
    S.rovingId = id;
    if (tileEl(id)) tileEl(id).querySelector('.tile-main').tabIndex = 0;
  }

  function neighborOf(id, dir) {
    const a = Q[id];
    let best = null, bs = Infinity;
    for (const card of CARDS) {
      const q=Q[card.id];
      if (q.id === id) continue;
      const dx = q.wx - a.wx, dy = q.wy - a.wy;
      const [p, sec] = dir === 'ArrowRight' ? [dx, dy] : dir === 'ArrowLeft' ? [-dx, dy] : dir === 'ArrowDown' ? [dy, dx] : [-dy, dx];
      if (p <= 30) continue;
      const score = p + 2.4 * Math.abs(sec);
      if (score < bs) { bs = score; best = q.id; }
    }
    return best;
  }

  function focusTile(id, { reveal = true } = {}) {
    setRoving(id);
    const b = tileEl(id);
    if (!b) return;
    if (reveal && !tileVisible(id, 24)) {
      const q = Q[id];
      const s = S.cam.s < 0.4 ? START_S : S.cam.s;
      flyTo(camFor(q.wx, q.wy, s), { duration: 180 });
    }
    (b.querySelector('.tile-main') || b).focus({ preventScroll: true });
  }

  // =====================================================================
  // Selection, panel
  // =====================================================================
  function selectQuestion(id, opts = {}) {
    const q = Q[id];
    if (!q || q.caution) return;
    if (S.composing) return; // never switch questions during IME composition
    const prev = S.selectedId;
    if (prev && prev !== id) {
      persistIfDirty();
      if (opts.history !== false) S.backStack.push(prev);
      if (S.backStack.length > 50) S.backStack.shift();
    }
    S.selectedId = id;
    updatePreviousAnswered();
    if (prev !== id) S.exampleOpen = false;
    S.focusCategory = null;
    S.structureUndo = null;
    const ui = S.venture.ui;
    if (!ui.visited.includes(id)) ui.visited.push(id);
    ui.history = [id, ...ui.history.filter((x) => x !== id)].slice(0, 10);
    const ri = routeIds.indexOf(id);
    if (ri >= 0 && (ri === ui.route.index || ri === ui.route.index + 1)) ui.route.index = ri; // free jumps do not skip route steps
    if (prev) refreshTile(prev);
    setRoving(id);
    mainQs.forEach((qq) => { if (tileEl(qq.id).classList.contains('is-next') || qq.id === suggestedNextId()) refreshTile(qq.id); });
    refreshTile(id);
    const t = tileEl(id);
    if (!noMotion()) { t.classList.remove('just-selected'); void t.offsetWidth; t.classList.add('just-selected'); }

    const wasOpen = S.panelOpen;
    if (opts.openPanel !== false) openPanel(opts);
    if (opts.fly) {
      const s = opts.center ? cardFitScale(CARD_BY_Q[id],mapArea()) : (S.cam.s < 0.65 ? cardFitScale(CARD_BY_Q[id],mapArea()) : S.cam.s);
      if (!tileVisible(id, 40) || opts.center) flyTo(cardReadingCamera(id,s));
    } else if (!opts.restoring && S.panelOpen && !wasOpen) {
      avoidPanelCover(id);
    } else if (!opts.restoring && S.panelOpen && !tileVisible(id, 0)) {
      avoidPanelCover(id);
    }
    drawLinks();
    drawMinimap();
    renderGuide();
    renderOutlineCurrent();
    if (opts.fromMap) dismissTip('tile');
    scheduleUiSave();
  }

  function avoidPanelCover(id) {
    if (tileVisible(id, 0)) return;
    if (!S.camBeforePanel) S.camBeforePanel = { ...S.cam };
    const q = Q[id];
    flyTo(camFor(q.wx, q.wy, S.cam.s), { duration: 200 });
    S.camTouched = false;
  }

  function openPanel(opts = {}) {
    const panel = $('#panel');
    const wasOpen = S.panelOpen;
    S.panelOpen = true;
    hidePreview(true);
    panel.hidden = false;
    document.documentElement.classList.add('panel-open');
    if (!wasOpen) {
      S.camBeforePanel = null;
      S.camTouched = false;
      if (!noMotion()) { panel.classList.remove('closing'); panel.classList.remove('opening'); void panel.offsetWidth; panel.classList.add('opening'); }
      if (S.mode === 'mobile') setSheet('half');
    }
    renderPanel({ focusHeading: opts.focusPanel });
    renderTips();
    requestAnimationFrame(() => { layoutOverlays(); updateSigns(); });
    drawMinimap();
  }

  function closePanel({ returnFocus = true } = {}) {
    if (!S.panelOpen) return;
    persistIfDirty();
    const panel = $('#panel');
    S.panelOpen = false;
    document.documentElement.classList.remove('panel-open');
    const done = () => { panel.hidden = true; panel.classList.remove('closing'); };
    if (noMotion()) done(); else { panel.classList.remove('opening'); panel.classList.add('closing'); setTimeout(done, 140); }
    if (S.camBeforePanel && !S.camTouched) flyTo(S.camBeforePanel, { duration: 140 });
    S.camBeforePanel = null;
    hidePreview(true);
    drawMinimap();
    renderTips();
    requestAnimationFrame(() => { layoutOverlays(); updateSigns(); });
    scheduleUiSave();
    if (returnFocus && S.selectedId) focusTile(S.selectedId, { reveal: false });
  }

  function relatedOf(id) {
    const q = Q[id];
    const out = [];
    const add = (qid, kind, tag, note) => { if (qid && qid !== id && Q[qid] && !Q[qid].caution && !out.some((o) => CARD_BY_Q[o.id] === CARD_BY_Q[qid]) && CARD_BY_Q[qid] !== CARD_BY_Q[id] && out.length < 4) out.push({ id: qid, kind, tag, note }); };
    const ri = routeIds.indexOf(id);
    if (ri >= 0) add(routeIds[ri + 1], 'next', tr("Suggested next"));
    const list = CATS[q.category].qs, i = list.indexOf(q);
    add(list[i - 1] && list[i - 1].id, 'same', tr("Same category"));
    add(list[i + 1] && list[i + 1].id, 'same', tr("Same category"));
    for (const r of D.relations) {
      let targets = [];
      if (r.from === q.category) targets = r.to;
      else if (r.to.includes(q.category)) targets = [r.from];
      for (const tn of targets) {
        const first = CATS[tn].qs.find((x) => answerOf(x.id).status !== 'answered') || CATS[tn].qs[0];
        add(first.id, 'cat', tr("Related category"), r.label);
      }
    }
    if (out.length < 4) { add(list[i - 2] && list[i - 2].id, 'same', tr("Same category")); add(list[i + 2] && list[i + 2].id, 'same', tr("Same category")); }
    return out;
  }

  function statusIcon(status) { return `<span class="st-ico st-${status}">${icon(STATUS[status].icon)}</span>`; }

  function groundingHtml(q) {
    const g=q.grounding; if(!g)return '';
    return `<div class="source-grounding"><h4>${tr('Source grounding')}</h4><p>${esc(g.file)} · ${tr('Pages')}: ${esc(g.page)}</p>${g.note ? `<p class="hint">${esc(g.note)}</p>` : ''}<blockquote lang="${/[\u3400-\u9fff]/.test(g.quote)?'zh-TW':'en'}">${esc(g.quote)}</blockquote>${I18N.locale==='en' && g.translation ? `<p lang="en">${esc(g.translation)}</p>` : ''}</div>`;
  }

  function renderPanel({ keepFocus = false, focusHeading = false } = {}) {
    const panel = $('#panel');
    const id = S.selectedId;
    if (!id) return;
    const q = Q[id], a = answerOf(id), h = q.help;
    const ui = S.venture.ui;
    const active = document.activeElement;
    const activeId = keepFocus && active && panel.contains(active) ? active.id : null;
    const exampleOpen = !!S.exampleOpen;
    const related = relatedOf(id);
    const back = S.backStack.length ? S.backStack[S.backStack.length - 1] : null;
    const inRoute = ui.route.on && routeIds.indexOf(id) >= 0 && ui.route.index === routeIds.indexOf(id) && ui.route.index < routeIds.length - 1;
    panel.innerHTML = `
      <div class="sheet-handle" aria-hidden="true"><span></span></div>
      <div class="panel-head">
        ${back ? `<button type="button" class="icon-btn" data-action="back" aria-label="${esc(tr('back to named',{question:Q[back].question}))}" title="${tr("Back")}">${icon('back')}</button>` : ''}
        <nav class="crumb" aria-label="${tr("Breadcrumb")}"><button type="button" class="crumb-cat" data-action="zoom-category" data-cat="${esc(q.category)}">${esc(cn(q.category))}</button><span aria-hidden="true">›</span><span>${tr("Question")}</span></nav>
        <div class="menu-wrap">
          <button type="button" class="icon-btn" data-action="toggle-history" aria-expanded="false" aria-controls="history-menu" aria-label="${tr("Recently viewed questions")}" title="${tr("Recently viewed")}">${icon('history')}</button>
          <div class="menu history-menu" id="history-menu" hidden>
            <p class="menu-note">${tr("Recently viewed (browsing history, not revisions)")}</p>
            ${ui.history.filter((x) => Q[x]).map((x) => `<button type="button" class="menu-item" data-action="goto" data-id="${x}">${statusIcon(answerOf(x).status)}<span>${esc(Q[x].question)}</span></button>`).join('')}
          </div>
        </div>
        <button type="button" class="icon-btn close-btn" data-action="close-panel" aria-label="${tr("Close question panel")}">${icon('close')}</button>
      </div>
      <div class="panel-scroll" id="panel-scroll">
        <h2 class="panel-q" id="panel-q" tabindex="-1">${esc(numberedQuestion(q))}</h2>
        ${keyPointRecord(id)?.points?.length ? `<div class="panel-keypoints">${keyPointRecord(id).points.map(point=>`<span>${esc(point)}</span>`).join('')}</div>` : ''}${window.STARTUP_CAMI_MODEL?.keyPoints?.[id]?.pending?.points?.length && answerOf(id).text ? `<p>${I18N.locale==='zh-TW'?'待評估回答的重點':'Pending answer key points'}</p><div class="panel-keypoints">${window.STARTUP_CAMI_MODEL.keyPoints[id].pending.points.map(point=>`<span>${esc(point)}</span>`).join('')}</div>` : ''}
        ${q.question !== q._original.question ? `<details class="original-question"><summary>${tr('Original English question')}</summary><p lang="en">${esc(q._original.question)}</p></details>` : ''}
        ${a.text || !window.STARTUP_CAMI_MODEL?.pendingAnswers?.[id]?.text ? `<section class="answer" aria-label="${tr("Recorded answer")}">
          <h3 class="lbl">${tr('Recorded answer')} · ${esc(tr(STATUS[a.status].label))}</h3>
          <div class="readonly-answer">${a.text ? esc(a.text) : `<em>${isCore() ? (I18N.locale==='zh-TW'?'尚未填答':'No answer yet') : tr("No accepted answer has been recorded in YAML.")}</em>`}</div>
          ${!isCore() && a.scores && Object.keys(a.scores).length ? `<p class="hint">${a.recordStatus === 'accepted' ? tr("Current recorded evaluation") : tr("Previous evaluation \u2014 no longer current or not verifiable")}</p><dl class="score-list">${Object.entries(a.scores).map(([key,value])=>`<dt>${esc(tr(key))}</dt><dd>${esc(typeof value === 'object' ? value.score : value)} / 2</dd>`).join('')}</dl>` : ''}
        </section>` : ''}
        ${window.STARTUP_CAMI_MODEL?.pendingAnswers?.[id]?.text ? `<section class="answer"><h3>${window.STARTUP_CAMI_MODEL.pendingAnswers[id].role==='rewrite_needs_save'?(I18N.locale==='zh-TW'?'原回答；改寫尚未保存':'Original answer; rewrite not saved'):window.STARTUP_CAMI_MODEL.pendingAnswers[id].role==='history_only'?(I18N.locale==='zh-TW'?'歷史內容':'Historical content'):(I18N.locale==='zh-TW'?'待評估回答':'Pending answer')}</h3><div class="readonly-answer">${esc(window.STARTUP_CAMI_MODEL.pendingAnswers[id].text)}</div><p>${esc((window.STARTUP_CAMI_MODEL.pendingAnswers[id].evaluation?.blocking_issues || []).map(x=>typeof x==='string'?x:(x.message || x.reason || '')).filter(Boolean).join('\n') || (I18N.locale==='zh-TW'?'尚未通過評估':'Not yet accepted'))}</p></section>` : ''}
        ${!isCore() ? `<details id="ai-context"><summary id="ai-context-summary">${I18N.locale==='zh-TW'?'繼續與 AI 討論':'Continue with AI'}</summary><p>${I18N.locale==='zh-TW'?'複製以下內容交給 AI：':'Copy this context to your AI:'}</p><textarea id="ai-context-text" aria-label="AI context" readonly rows="6" style="width:100%;box-sizing:border-box">${esc('/startup-cami-office\nProject: '+JSON.stringify(window.STARTUP_CAMI_MODEL?.project || {})+'\nOriginal question ID: '+id+'\nQuestion: '+q._original.question+'\nRevision: '+window.STARTUP_CAMI_MODEL?.project?.revision+'\nBody role: '+(window.STARTUP_CAMI_MODEL?.pendingAnswers?.[id]?.role || a.recordStatus)+'\nEvaluation: '+JSON.stringify(window.STARTUP_CAMI_MODEL?.pendingAnswers?.[id]?.evaluation || null)+'\nReload the latest project YAML and evaluation before continuing this exact question. This copied context may be stale; never accept an answer based on it alone.')}</textarea></details>` : ''}
        ${notesPanel(id)}
        ${cardMembersHtml(id)}
        ${isCore() ? `<nav class="question-sequence" aria-label="${I18N.locale==='zh-TW'?'答題順序':'Question order'}">${[mainQs[questionNumber(id)-2],mainQs[questionNumber(id)]].map((target,i)=>target?`<button type="button" class="btn btn-ghost" data-action="goto" data-id="${target.id}">${i===0?(I18N.locale==='zh-TW'?'上一題':'Previous'):(I18N.locale==='zh-TW'?'下一題':'Next')} · ${questionNumber(target.id)}</button>`:'').join('')}</nav>` : ''}
        ${!isCore() ? `<p class="why"><span class="lbl">${tr("Why this matters")}</span>${h ? esc(h.why) : tr("Example not available yet.")}</p>` : ''}



        ${!isCore() ? `<details class="example" id="example" ${exampleOpen ? 'open' : ''}>
          <summary><span class="lbl">${tr("Example")}</span>${icon('chevdown', 'i i-sm')}</summary>
          ${h ? `<p class="ex-tag">${tr("Illustrative example \u2014 not your answer")}</p>
          <p class="ex-text">${esc(h.example)}</p>
          <p class="ex-avoid"><span class="lbl-inline">${tr("Common trap")}</span> ${esc(h.avoid)}</p>` : `<p class="ex-text">${tr("Example not available yet")}</p>`}
        </details>` : ''}

        ${a.evidence.length ? `<details class="evidence"><summary>${tr("Claims recorded by the evaluation")} · ${a.evidence.length}</summary>
          ${a.recordStatus !== 'accepted' ? `<p class="hint">${tr('The evaluation is not current or cannot be verified.')}</p>` : ''}
          <ul class="ev-list">${a.evidence.map(e=>`<li><p>${esc(e.text)}</p><p class="ev-meta">${esc(tr(e.state))}${e.source_refs.length ? ' · '+esc(e.source_refs.map(x=>typeof x === 'string' ? x : JSON.stringify(x)).join(', ')) : ''}</p></li>`).join('')}</ul></details>` : ''}

        <section class="related" aria-labelledby="rel-h">
          <h3 class="lbl" id="rel-h">${tr("Related questions")}</h3>
          <ul>${related.map((r) => `<li><button type="button" class="rel-btn" data-action="goto" data-id="${r.id}"><span class="rel-tag ${r.kind}">${esc(tr(r.tag))}${r.note ? ` · ${esc(tr(r.note))}` : ''}</span><span class="rel-q">${esc(Q[r.id].question)}</span><span class="rel-cat">${esc(cn(Q[r.id].category))} · ${tr(STATUS[answerOf(r.id).status].label)}</span></button></li>`).join('')}</ul>
        </section>

        ${!isCore() ? `<details class="source">
          <summary><span class="lbl">${tr("Source")}</span>${icon('chevdown', 'i i-sm')}</summary>
          <dl>
            <dt>${tr("Course section")}</dt><dd lang="${I18N.locale}">${esc(q.sourceSection)}</dd>
            <dt>${tr("Pages")}</dt><dd lang="${I18N.locale}">${esc(q.sourceRange)}</dd>
            <dt>${tr("How to use")}</dt><dd>${esc(I18N.locale==='zh-TW' ? q.audience : q.audienceEn)}</dd>
            ${q.editorialNote ? `<dt>${tr("Editorial note")}</dt><dd lang="${I18N.locale}">${esc(q.editorialNote.replace(/[（）]/g, ''))}</dd>` : ''}
          </dl>
          ${groundingHtml(q)}
        </details>` : ''}
        ${S.mode === 'mobile' && ui.route.on && suggestedNextId() ? `<div class="panel-foot"><button type="button" class="btn btn-primary" data-action="next">${tr('Next question')}${icon('next', 'i i-sm')}</button></div>` : inRoute ? `<div class="panel-foot"><button type="button" class="btn btn-link" data-action="skip">${tr("Skip for now")}</button></div>` : ''}
      </div>`;
    const ex = $('#example'); if (ex) ex.addEventListener('toggle', () => { S.exampleOpen = ex.open; });
    if (activeId && document.getElementById(activeId)) {
      const el = document.getElementById(activeId);
      el.focus({ preventScroll: true });
    } else if (focusHeading) $('#panel-q').focus({ preventScroll: true });
  }

  function traversalOrder() {
    const ui = S.venture.ui;
    const cats = [];
    const push = (n) => { if (!cats.includes(n) && CATS[n] && !CATS[n].caution) cats.push(n); };
    if (ui.route.branch && D.branches[ui.route.branch]) D.branches[ui.route.branch].order.forEach(push);
    D.mainOrder.forEach(push);
    contentCats.forEach((c) => push(c.name));
    return cats.flatMap((n) => CATS[n].qs.map((q) => q.id));
  }

  function suggestedNextId() {
    if (!S.venture) return null;
    const ui = S.venture.ui;
    if (!ui.route.on) return null;
    const i = ui.route.index;
    if (i < routeIds.length - 1) {
      if (S.selectedId === routeIds[i] || ui.visited.includes(routeIds[i])) return routeIds[i + 1];
      return routeIds[i];
    }
    if (!ui.route.branch && !ui.route.free) return null; // waiting for "Choose where to explore next"
    const visited = new Set(ui.visited);
    return traversalOrder().find((qid) => !visited.has(qid) && qid !== S.selectedId) || null;
  }

  function nextQuestion(fromSkip) {
    persistIfDirty();
    const cur = S.selectedId;
    const ui = S.venture.ui;
    const target = suggestedNextId();
    // Browsing a question does not change its acceptance status.
    if (!target) {
      if (ui.route.index >= routeIds.length - 1) { ui.route.index = routeIds.length; renderGuide(); }
      return;
    }
    const ri = routeIds.indexOf(target);
    if (ri >= 0) ui.route.index = ri;
    // Route lights up first, then the camera moves.
    const t = tileEl(target);
    t.classList.add('is-next');
    selectQuestion(target, { fly: true, center: true, focusPanel: fromSkip });
  }

  function renderGuide() {}


  function chooseBranch(k) {
    const ui = S.venture.ui;
    ui.route.branch = k; ui.route.index = routeIds.length;
    const b = D.branches[k];
    renderGuide();
    zoomToCategory(b.anchor);
    CARDS.forEach((card) => refreshTile(card.id));
    scheduleUiSave();
  }

  // =====================================================================
  // Hover / focus preview
  // =====================================================================
  let pvOpenT = null, pvCloseT = null;
  function schedulePreview(id, anchor) {
    clearTimeout(pvCloseT);
    clearTimeout(pvOpenT);
    if(S.mode==='mobile' || S.panelOpen)return;
    pvOpenT = setTimeout(() => showPreview(id, anchor), 280);
  }
  function scheduleHide() { clearTimeout(pvOpenT); clearTimeout(pvCloseT); pvCloseT = setTimeout(() => hidePreview(), 160); }

  function showPreview(id, anchor) {
    if(S.mode==='mobile' || S.panelOpen)return;
    const q = Q[id], h = q.help;
    const pv = $('#preview');
    S.previewId = id;
    if(isCore()) {
      pv.innerHTML=`<p class="pv-q">${esc(q.question)}</p><ul>${(keyPointRecord(id)?.points || []).map(point=>`<li>${esc(point)}</li>`).join('')}</ul><button type="button" class="btn btn-primary btn-sm" data-action="open-from-preview" data-id="${id}">${tr("Open question")}</button>`;
    } else pv.innerHTML = `<p class="pv-q">${esc(q.question)}</p>
      <p class="pv-why"><span class="lbl">${tr("Why ask this?")}</span>${h ? esc(h.why) : tr("Example not available yet.")}</p>
      ${h ? `<p class="pv-ex"><span class="lbl">${tr("Example")}</span><span class="ex-tag">${tr("Illustrative example \u2014 not your answer")}</span>${esc(h.example)}</p>` : ''}
      <button type="button" class="btn btn-primary btn-sm" data-action="open-from-preview" data-id="${id}">${tr("Open question")}</button>`;
    pv.hidden = false;
    pv.classList.remove('show'); void pv.offsetWidth; pv.classList.add('show');
    const r = (anchor || tileEl(id)).getBoundingClientRect();
    const pw = pv.offsetWidth, ph = pv.offsetHeight;
    const top = stageRect.top + 8, bottom = window.innerHeight - 8;
    const panelL = S.panelOpen && S.mode !== 'mobile' ? $('#panel').getBoundingClientRect().left - 8 : window.innerWidth - 8;
    let x = r.right - 24, y = r.top - ph + 36; // prefer up-right
    if (x + pw > panelL || y < top) { x = r.left - pw + 24; y = r.bottom - 24; } // flip to down-left
    x = clamp(x, 8, Math.max(8, panelL - pw)); y = clamp(y, top, Math.max(top, bottom - ph));
    pv.style.left = x + 'px'; pv.style.top = y + 'px';
    pv.setAttribute('aria-label', tr('preview named',{question:q.question}));
    const t = tileEl(id); if (t) t.setAttribute('aria-describedby', `src-${id} preview`);
    dismissTip('hover');
  }

  function hidePreview(immediate) {
    clearTimeout(pvOpenT); clearTimeout(pvCloseT);
    const pv = $('#preview');
    if (S.previewId) { const t = tileEl(S.previewId); if (t) t.setAttribute('aria-describedby', `src-${S.previewId}`); }
    S.previewId = null;
    pv.hidden = true;
    pv.classList.remove('show');
  }

  // =====================================================================
  // Tips (three static first-time hints)
  // =====================================================================
  function tipDefs() {
    const coarse = matchMedia('(pointer: coarse)').matches || S.mode === 'mobile';
    const sel = S.selectedId || routeIds[0];
    const neighbor = neighborOf(sel, 'ArrowRight') || neighborOf(sel, 'ArrowDown');
    return [
      { key: 'tile', text: 'Each paper card is one question. Click a card to open it.', anchor: () => tileScreenRect(sel), place: 'below' },
      coarse ? null : { key: 'hover', text: 'Rest the pointer on a card to preview an example.', anchor: () => neighbor && tileScreenRect(neighbor), place: 'above' },
      { key: 'overview', text: 'See all 28 areas at once.', anchor: () => { const r = $('#overview-btn').getBoundingClientRect(); return { l: r.left - stageRect.left, t: r.top - stageRect.top, r: r.right - stageRect.left, b: r.bottom - stageRect.top }; }, place: 'above' },
    ].filter(Boolean);
  }
  function renderTips() {}

  function positionTips() {
    const defs = tipDefs();
    $$('#tips .tip').forEach((el) => {
      const d = defs.find((x) => x.key === el.dataset.tip);
      const r = d && d.anchor();
      if (!r) { el.hidden = true; return; }
      const a = mapArea();
      const w = el.offsetWidth || 220, hh = el.offsetHeight || 44;
      let x = (r.l + r.r) / 2 - w / 2, y = d.place === 'below' ? r.b + 10 : r.t - hh - 10;
      if (d.key === 'overview') {
        const g = $('#guide').getBoundingClientRect();
        x = r.l - 40;
        if (x + w > g.left - stageRect.left - 8) y = Math.min(y, g.top - stageRect.top - hh - 10);
      }
      const visible = r.r > 0 && r.l < a.w && r.b > 0 && r.t < a.h && (d.key === 'overview' || S.level !== 'world');
      el.hidden = !visible;
      x = clamp(x, 8, a.w - w - 8); y = clamp(y, 8, stageRect.h - hh - 8);
      el.style.transform = `translate(${x}px, ${y}px)`;
    });
  }
  function dismissTip(key) {
    if (S.prefs.tips[key]) return;
    S.prefs.tips[key] = true;
    writePrefs();
    const el = $(`#tips .tip[data-tip="${key}"]`); if (el) el.remove();
  }

  // =====================================================================
  // Search & Outline
  // =====================================================================
  function runSearch(reset = true) {
    const input = $('#search-input'), box = $('#search-results');
    const term = input.value.trim().toLowerCase();
    if (reset) { S.searchLimit = 30; S.searchActive = -1; }
    if (!term) { box.hidden = true; input.setAttribute('aria-expanded', 'false'); box.innerHTML = ''; return; }
    const words = term.split(/\s+/).filter(Boolean);
    const all = D.questions.filter((q0) => {
      const q = Q[q0.id];
      const hay = `${isCore()?JSON.stringify({prompt:q.prompt,alternateQuestions:q.alternateQuestions,followups:q.followups,headlines:window.STARTUP_CAMI_MODEL?.keyPoints?.[q.id]?.formal?.pointsI18n,answer:window.STARTUP_CAMI_MODEL?.answers?.[q.id]?.textI18n}):''} ${q.question} ${q._original.question} ${cn(q.category)} ${q.category} ${q.caution ? '' : answerOf(q.id).text}`.toLowerCase().replace(/[’']/g, "'");
      return words.every((w) => hay.includes(w.replace(/[’']/g, "'")));
    }).map((q) => Q[q.id]);
    S.searchHits = all;
    const shown = all.slice(0, S.searchLimit);
    box.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    if (!all.length) {
      box.innerHTML = `<p class="sr-empty" role="option" aria-disabled="true">${tr("No matching questions. Try a category or a shorter phrase.")}</p>`;
      return;
    }
    box.innerHTML = `<p class="sr-count">${tr('question count',{count:all.length})}</p>` + shown.map((q, i) => `<div class="sr-item${i === S.searchActive ? ' active' : ''}" role="option" id="sr-${i}" data-id="${q.id}" aria-selected="${i === S.searchActive}">
        <span class="sr-q">${esc(q.question)}</span>
        <span class="sr-meta">${esc(cn(q.category))} · ${q.caution ? tr("Avoid or defer") : tr(STATUS[answerOf(q.id).status].label)}</span></div>`).join('') +
      (all.length > shown.length ? `<button type="button" class="sr-more" data-action="search-more">${tr('show more',{count:Math.min(30, all.length-shown.length)})}</button>` : '');
    input.setAttribute('aria-activedescendant', S.searchActive >= 0 ? `sr-${S.searchActive}` : '');
  }

  function chooseSearch(id) {
    const q = Q[id];
    $('#search-results').hidden = true;
    $('#search-input').setAttribute('aria-expanded', 'false');
    if (q.caution) { openOutline('avoid', id); return; }
    selectQuestion(id, { fly: true, center: true, focusPanel: true });
  }

  function renderOutline() {
    const o = $('#outline');
    const tab = o.dataset.tab || 'all';
    o.innerHTML = `<div class="outline-head">
        <h2>${tr("Question list")}</h2>
        <button type="button" class="icon-btn" data-action="close-outline" aria-label="${tr("Close question list")}">${icon('close')}</button>
      </div>
      ${!isCore() ? `<div class="tabs" role="tablist">
        <button type="button" role="tab" aria-selected="${tab === 'all'}" data-action="outline-tab" data-tab="all">${tr("All questions")}</button>
        <button type="button" role="tab" aria-selected="${tab === 'avoid'}" data-action="outline-tab" data-tab="avoid">${tr("Questions to avoid or defer")}</button>
      </div>` : ''}
      <div class="outline-body" role="tabpanel">${tab === 'all' ? outlineAll() : outlineAvoid()}</div>`;
  }
  function outlineAll() {
    return `<div class="outline-tools"><button type="button" class="btn btn-ghost btn-sm" data-action="expand-all">${tr("Expand all")}</button><button type="button" class="btn btn-ghost btn-sm" data-action="collapse-all">${tr("Collapse all")}</button>${!isCore()?`<button type="button" class="btn btn-link btn-sm" data-action="founder-start">${tr("Start from Founder Fit")}</button>`:''}</div>
      <p class="hint">${tr('question summary',{questions:mainQs.length,categories:contentCats.length})}</p>
      <ul class="ol-cats">${contentCats.map((c) => `<li>
        <button type="button" class="ol-cat" data-action="ol-toggle" aria-expanded="false" aria-controls="olc-${c.idx}"><svg class="i i-sm chev" aria-hidden="true"><use href="#i-chevron"/></svg><span>${esc(cn(c.name))}</span><span class="ol-count" data-olcount="${esc(c.name)}"></span></button>
        <ul class="ol-qs" id="olc-${c.idx}" hidden>${c.qs.map((q) => `<li><button type="button" class="ol-q" data-action="goto" data-id="${q.id}" data-olq="${q.id}">${statusIcon(answerOf(q.id).status)}<span>${esc(numberedQuestion(q))}</span></button></li>`).join('')}</ul></li>`).join('')}</ul>`;
  }
  function outlineAvoid() {
    return `<p class="hint">${tr("Counterexamples from the course. They are kept for reference and are not part of the suggested route.")}</p>
      <ul class="ol-avoid">${cautions.map((q) => `<li><details id="avoid-${q.id}"><summary>${esc(q.question)}</summary>
        ${q.help ? `<p><span class="lbl">${tr("Why avoid or defer")}</span>${esc(q.help.why)}</p><p><span class="lbl">${tr("Ask or observe instead")}</span><span class="ex-tag">${tr("Illustrative example")}</span>${esc(q.help.example)}</p><p><span class="lbl">${tr("Trap")}</span>${esc(q.help.avoid)}</p>` : ''}
        <p class="src" lang="${I18N.locale}">${esc(q.sourceSection)}${q.editorialNote ? ` · ${esc(q.editorialNote)}` : ''}</p>${groundingHtml(q)}</details></li>`).join('')}</ul>`;
  }
  function renderOutlineCounts() {
    for (const c of contentCats) {
      const el = document.querySelector(`[data-olcount="${CSS.escape(c.name)}"]`);
      if (el) el.textContent = `${c.qs.filter(q => !completed(answerOf(q.id))).length} ${tr('remaining')}`;
    }
    $$('[data-olq]').forEach((b) => { const st = answerOf(b.dataset.olq).status; const ic = b.querySelector('.st-ico'); if (ic && !ic.classList.contains(`st-${st}`)) ic.outerHTML = statusIcon(st); });
  }
  function renderOutlineCurrent() {
    $$('.ol-q[aria-current]').forEach((b) => b.removeAttribute('aria-current'));
    const b = S.selectedId && document.querySelector(`[data-olq="${S.selectedId}"]`);
    if (b) b.setAttribute('aria-current', 'true');
    renderOutlineCounts();
  }
  function openOutline(tab, focusId) {
    const o = $('#outline');
    if (tab) o.dataset.tab = tab;
    renderOutline();
    renderOutlineCounts();
    o.hidden = false;
    document.documentElement.classList.add('outline-open');
    requestAnimationFrame(() => { layoutOverlays(); updateSigns(); });
    $('#outline-btn').setAttribute('aria-expanded', 'true');
    if (focusId && Q[focusId].caution) { const d = document.getElementById(`avoid-${focusId}`); if (d) { d.open = true; d.querySelector('summary').focus(); d.scrollIntoView({ block: 'center' }); } }
    else if (S.selectedId && (!tab || tab === 'all')) {
      const b = document.querySelector(`[data-olq="${S.selectedId}"]`);
      if (b) { const ul = b.closest('.ol-qs'); ul.hidden = false; ul.previousElementSibling.setAttribute('aria-expanded', 'true'); b.setAttribute('aria-current', 'true'); (b.querySelector('.tile-main') || b).focus({ preventScroll: true }); b.scrollIntoView({ block: 'center' }); }
    } else (o.querySelector('[role="tab"][aria-selected="true"]') || o.querySelector('button')).focus();
  }
  function closeOutline() {
    const o = $('#outline');
    if (o.hidden) return;
    o.hidden = true;
    document.documentElement.classList.remove('outline-open');
    requestAnimationFrame(() => { layoutOverlays(); updateSigns(); });
    $('#outline-btn').setAttribute('aria-expanded', 'false');
    $('#outline-btn').focus();
  }

  // =====================================================================
  // Export / import
  // =====================================================================
  function exportRows(answeredOnly) {
    return mainQs.filter((q) => !answeredOnly || completed(answerOf(q.id))).map((q) => ({ q, a: answerOf(q.id) }));
  }

  function toMarkdown(only) {
    const m=window.STARTUP_CAMI_MODEL || {};
    let text=`# ${S.venture.name} — ${tr('context copy')}\n\n> ${tr('derived notice')}\n> ${tr('yaml revision',{revision:m.source?.revision ?? tr('catalog preview')})}; SHA-256: ${m.source?.sha256 || tr('none')}.\n\n`;
    for(const {q,a} of exportRows(only)) text+=`## ${q.question}\n\n${tr('Category')}: ${cn(q.category)}\n${tr('Status')}: ${tr(STATUS[a.status].label)}\n\n${a.text || '_'+tr('Not answered')+'_'}\n\n${isCore() ? '' : tr('Source')+': '+q.sourceSection+' — '+q.sourceRange+'\n\n'}`;
    return text;
  }

  function download(name, mime, text) {
    const blob = new Blob([text], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = name;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }
  const fileStem = () => `startup-cami-${(S.venture.name || 'venture').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'venture'}-${new Date().toISOString().slice(0, 10)}`;
  const answeredOnly = () => $('#answered-only').checked;

  async function copyContext() {
    persistIfDirty();
    const md = toMarkdown(answeredOnly());
    try {
      if (!navigator.clipboard || params.get('simulate') === 'no-clipboard') throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(md);
      toast(tr("Copied as context."));
    } catch {
      closeMenus();
      showDialog(`<h2 id="dlg-title">${tr("Copy as context")}</h2>
        <p>${tr("This browser did not allow copying. Select the text below, or download it as Markdown.")}</p>
        <textarea class="copy-area" readonly aria-label="${tr("Context text")}">${esc(md)}</textarea>
        <div class="row"><button type="button" class="btn btn-primary" data-action="download-md">${tr("Download Markdown")}</button><button type="button" class="btn btn-ghost" data-action="close-dialog">${tr("Close")}</button></div>`);
      const ta = $('.copy-area'); ta.focus(); ta.select();
    }
  }

  let dialogReturn = null;
  function showDialog(html, { dismissable = true } = {}) {
    const layer = $('#dialog-layer');
    dialogReturn = document.activeElement;
    layer.innerHTML = `<div class="dialog" role="dialog" aria-modal="true" aria-labelledby="dlg-title" data-dismissable="${dismissable}">${html}</div>`;
    layer.hidden = false;
    const f = layer.querySelector('button, textarea, input'); if (f) f.focus();
  }
  function closeDialog() {
    const layer = $('#dialog-layer');
    layer.hidden = true; layer.innerHTML = '';
    if (dialogReturn && dialogReturn.focus) dialogReturn.focus();
  }

  let toastT = null;
  function toast(msg, isErr) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.toggle('is-error', !!isErr);
    t.classList.add('show');
    clearTimeout(toastT);
    toastT = setTimeout(() => t.classList.remove('show'), 3600);
  }

  function closeMenus() {
    $$('.menu').forEach((m) => { m.hidden = true; });
    $$('[aria-haspopup], [data-action="toggle-history"]').forEach((b) => b.setAttribute('aria-expanded', 'false'));
  }

  // =====================================================================
  // Mobile sheet
  // =====================================================================
  function vvh() { return window.visualViewport ? window.visualViewport.height : window.innerHeight; }
  function sheetPx() { const f = { peek: 0.28, half: 0.62, full: 0.9 }[S.sheet] || 0.62; return Math.round(vvh() * f); }
  function setSheet(state) {
    S.sheet = state;
    document.documentElement.style.setProperty('--sheet-h', sheetPx() + 'px');
    $('#panel').dataset.sheet = state;
  }

  // =====================================================================
  // Events
  // =====================================================================
  function bindGlobal() {
    const stage = $('#stage');
    let drag = null, spaceHeld = false, suppressClick = false;
    const pointers = new Map();
    let pinch = null;

    stage.addEventListener('pointerdown', (e) => {
      if (e.target.closest('.zoom, .minimap, .guide, .tips, .toast, .load-failed, .loading')) return;
      if (e.button === 2) return;
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      cancelAnim();
      if (pointers.size === 2) {
        const [p1, p2] = [...pointers.values()];
        pinch = { d: Math.hypot(p1.x - p2.x, p1.y - p2.y), s: S.cam.s, mid: [(p1.x + p2.x) / 2, (p1.y + p2.y) / 2] };
        drag = null; suppressClick = true;
        return;
      }
      const tile = e.target.closest('.tile');
      const panMode = e.button === 1 || (e.button === 0 && (spaceHeld || !tile)) || (e.button === 0 && tile);
      if (!panMode) return;
      if (e.button === 1) e.preventDefault();
      drag = { x: e.clientX, y: e.clientY, cam: { ...S.cam }, tile, moved: false, type: e.pointerType, force: e.button === 1 || spaceHeld };
      if (tile && !drag.force) tile.classList.add('pressed');
    });
    window.addEventListener('pointermove', (e) => {
      if (pointers.has(e.pointerId)) pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pinch && pointers.size === 2) {
        const [p1, p2] = [...pointers.values()];
        const d = Math.hypot(p1.x - p2.x, p1.y - p2.y);
        const mid = [(p1.x + p2.x) / 2, (p1.y + p2.y) / 2];
        const px = mid[0] - stageRect.left, py = mid[1] - stageRect.top;
        const ns = clamp(pinch.s * (d / pinch.d), minS(), MAX_S);
        const [wx, wy] = screenToWorld(pinch.mid[0] - stageRect.left, pinch.mid[1] - stageRect.top);
        S.cam = { x: wx - (px - stageRect.w / 2) / ns, y: wy - (py - stageRect.h / 2) / ns, s: ns };
        pinch.mid = mid; pinch.s = ns; pinch.d = d;
        applyCamera(); S.camTouched = true;
        return;
      }
      if (!drag) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      const th = drag.type === 'touch' ? 10 : 6;
      if (!drag.moved && Math.hypot(dx, dy) > th) {
        drag.moved = true;
        if (drag.tile) drag.tile.classList.remove('pressed');
        stage.classList.add('panning');
        hidePreview(true);
      }
      if (drag.moved) {
        S.cam = { x: clamp(drag.cam.x - dx / S.cam.s, WB.l, WB.r), y: clamp(drag.cam.y - dy / S.cam.s, WB.t, WB.b), s: S.cam.s };
        applyCamera();
        S.camTouched = true;
      }
    });
    const endPointer = (e) => {
      pointers.delete(e.pointerId);
      if (pinch && pointers.size < 2) { pinch = null; setTimeout(() => { suppressClick = false; }, 50); }
      if (!drag) return;
      if (drag.tile) drag.tile.classList.remove('pressed');
      if (drag.moved || drag.force) { suppressClick = true; setTimeout(() => { suppressClick = false; }, 0); }
      stage.classList.remove('panning');
      drag = null;
    };
    window.addEventListener('pointerup', endPointer);
    window.addEventListener('pointercancel', endPointer);
    stage.addEventListener('auxclick', (e) => { if (e.button === 1) e.preventDefault(); });

    // Tile click / keyboard activation
    stage.addEventListener('click', (e) => {
      if(suppressClick){e.preventDefault();e.stopPropagation();return;}
      if(e.target.closest('[data-action]'))return;
      const tile = e.target.closest('.tile');
      if (tile) {
        if (suppressClick) { e.preventDefault(); return; }
        if ($('#stage').classList.contains('labels-off') && e.detail !== 0) { zoomToCategory(CARD_BY_Q[tile.dataset.id].primaryCategory); return; }
        const kb = e.detail === 0;
        hidePreview(true);
        selectQuestion(tile.dataset.id, { fromMap: true, fly:true, center:true, focusPanel: kb });
        return;
      }
      const tb = e.target.closest('.cat-title-btn');
      if (tb && !suppressClick) { zoomToCategory(tb.dataset.cat); return; }
    });
    stage.addEventListener('dblclick', (e) => {
      const art = e.target.closest('.art');
      if (art) zoomToCategory(art.dataset.cat);
      // double-click on the paper background does nothing (spec)
    });

    // Hover preview
    stage.addEventListener('pointerover', (e) => {
      if (e.pointerType === 'touch') return;
      const tile = e.target.closest('.tile');
      if (!tile || drag || (e.relatedTarget && tile.contains(e.relatedTarget))) return;
      tile.classList.add('hover');
      schedulePreview(tile.dataset.id, tile);
    });
    stage.addEventListener('pointerout', (e) => {
      const tile = e.target.closest('.tile');
      if (!tile || (e.relatedTarget && tile.contains(e.relatedTarget))) return;
      tile.classList.remove('hover');
      if (S.previewId === tile.dataset.id || pvOpenT) scheduleHide();
    });
    const pv = $('#preview');
    pv.addEventListener('pointerenter', () => clearTimeout(pvCloseT));
    pv.addEventListener('pointerleave', () => scheduleHide());
    pv.addEventListener('focusout', (e) => { if (!pv.contains(e.relatedTarget) && !(e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('.tile'))) scheduleHide(); });

    // Keyboard on tiles
    stage.addEventListener('focusin', (e) => {
      const tile = e.target.closest('.tile');
      if (!tile) return;
      setRoving(tile.dataset.id);
      if (e.target.matches('.tile-main:focus-visible')) {
        if (!tileVisible(tile.dataset.id, 8)) focusTile(tile.dataset.id);
        schedulePreview(tile.dataset.id, tile);
      }
    });
    stage.addEventListener('focusout', (e) => {
      const tile = e.target.closest('.tile');
      if (tile && !(e.relatedTarget && pv.contains(e.relatedTarget))) scheduleHide();
    });
    stage.addEventListener('keydown', (e) => {
      const tile = e.target.closest('.tile');
      if (!tile) return;
      if (['ArrowRight', 'ArrowLeft', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
        e.preventDefault();
        const n = neighborOf(tile.dataset.id, e.key);
        if (n) { hidePreview(true); focusTile(n); }
      }
    });

    // Wheel: pan; ctrl/cmd + wheel (and trackpad pinch) zooms around the cursor
    stage.addEventListener('wheel', (e) => {
      if (e.target.closest('.zoom, .guide, .load-failed')) return;
      e.preventDefault();
      cancelAnim();
      const unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? stageRect.h : 1;
      if (e.ctrlKey || e.metaKey) {
        const dy = clamp(e.deltaY * unit, -60, 60);
        zoomAt(e.clientX - stageRect.left, e.clientY - stageRect.top, S.cam.s * Math.exp(-dy * 0.006));
      } else {
        S.cam = { x: clamp(S.cam.x + (e.deltaX * unit) / S.cam.s, WB.l, WB.r), y: clamp(S.cam.y + (e.deltaY * unit) / S.cam.s, WB.t, WB.b), s: S.cam.s };
        applyCamera();
        S.camTouched = true;
      }
    }, { passive: false });
    stage.addEventListener('scroll', () => { stage.scrollTop = 0; stage.scrollLeft = 0; });

    // Minimap
    const mm = $('#minimap');
    let mmDrag = false;
    const mmMove = (e) => { const [wx, wy] = minimapToWorld(e); cancelAnim(); setCam(wx, wy, S.cam.s); S.camTouched = true; };
    mm.addEventListener('pointerdown', (e) => { mmDrag = true; try { mm.setPointerCapture(e.pointerId); } catch { /* capture is optional */ } mmMove(e); });
    mm.addEventListener('pointermove', (e) => { if (mmDrag) mmMove(e); });
    mm.addEventListener('pointerup', () => { mmDrag = false; });

    // Space to pan (never inside inputs)
    window.addEventListener('keydown', (e) => {
      const typing = e.target.closest && e.target.closest('input, textarea, select, [contenteditable]');
      if (e.code === 'Space' && !typing && !e.target.closest('button')) { spaceHeld = true; stage.classList.add('space-pan'); e.preventDefault(); }
      if (e.key === 'Escape') onEscape(e);
      if (!typing && e.key === '/' ) { e.preventDefault(); $('#search-input').focus(); }
      if (!typing && !e.target.closest('button') && (e.key === '+' || e.key === '=')) zoomAt(mapArea().w / 2, mapArea().h / 2, S.cam.s * 1.25, true);
      if (!typing && !e.target.closest('button') && e.key === '-') zoomAt(mapArea().w / 2, mapArea().h / 2, S.cam.s / 1.25, true);
    });
    window.addEventListener('keyup', (e) => { if (e.code === 'Space') { spaceHeld = false; stage.classList.remove('space-pan'); } });

    // Delegated actions
    document.addEventListener('click', onAction);
    document.addEventListener('input', onInput);

    // Search keyboard
    const si = $('#search-input');
    si.addEventListener('keydown', (e) => {
      const hits = S.searchHits.slice(0, S.searchLimit);
      if (e.key === 'ArrowDown') { e.preventDefault(); S.searchActive = Math.min(hits.length - 1, S.searchActive + 1); runSearch(false); scrollActive(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); S.searchActive = Math.max(0, S.searchActive - 1); runSearch(false); scrollActive(); }
      else if (e.key === 'Enter') { e.preventDefault(); const h = hits[S.searchActive >= 0 ? S.searchActive : 0]; if (h) chooseSearch(h.id); }
    });
    si.addEventListener('focus', () => { if (si.value.trim()) runSearch(false); });
    const scrollActive = () => { const a = $('#search-results .sr-item.active'); if (a) a.scrollIntoView({ block: 'nearest' }); };
    $('#search-results').addEventListener('mousedown', (e) => e.preventDefault());
    $('#search-results').addEventListener('click', (e) => { const it = e.target.closest('.sr-item'); if (it) chooseSearch(it.dataset.id); });
    document.addEventListener('pointerdown', (e) => {
      if (!e.target.closest('.search')) { $('#search-results').hidden = true; si.setAttribute('aria-expanded', 'false'); }
      if (!e.target.closest('.menu-wrap')) closeMenus();
    });


    // Mobile sheet drag
    const panel = $('#panel');
    let sh = null;
    panel.addEventListener('pointerdown', (e) => {
      if (S.mode !== 'mobile' || !e.target.closest('.sheet-handle, .panel-head') || e.target.closest('button')) return;
      sh = { y: e.clientY, h: sheetPx() };
      panel.setPointerCapture(e.pointerId);
    });
    panel.addEventListener('pointermove', (e) => {
      if (!sh) return;
      const h = clamp(sh.h - (e.clientY - sh.y), vvh() * 0.2, vvh() * 0.92);
      document.documentElement.style.setProperty('--sheet-h', h + 'px');
    });
    panel.addEventListener('pointerup', (e) => {
      if (!sh) return;
      const h = sh.h - (e.clientY - sh.y), f = h / vvh();
      setSheet(f > 0.76 ? 'full' : f < 0.45 ? 'peek' : 'half');
      sh = null;
      if (S.selectedId && !tileVisible(S.selectedId)) { const q = Q[S.selectedId]; flyTo(camFor(q.wx, q.wy, S.cam.s)); }
    });
    document.addEventListener('focusin', (e) => {
      if (S.mode === 'mobile' && e.target.closest('#panel') && e.target.matches('textarea, input')) {
        if (S.sheet !== 'full') setSheet('full');
        setTimeout(() => e.target.scrollIntoView({ block: 'center' }), 250);
      }
    });

    const onResize = () => {
      measure();
      const nextWidth=isCore()?coreCardWidth(window.innerWidth):CARD_W;
      if(nextWidth!==CARD_W) {
        CARD_W=nextWidth;CARDS.forEach(card=>card.w=CARD_W);
        layoutClusters();buildCollage();hidePreview(true);culled.clear();$('#world').replaceChildren();buildWorld();refreshAllTiles();
        if(S.selectedId) {
          const q=Q[S.selectedId],target=cardReadingCamera(q.id,cardFitScale(CARD_BY_Q[q.id],mapArea()));
          cancelAnim();S.cam=target;S.camTouched=false;
        }
      }
      if (S.mode === 'mobile' && S.panelOpen) setSheet(S.sheet);
      applyCamera(true);
      positionTips();
      layoutOverlays();
      if (S.selectedId && !S.camTouched && !tileVisible(S.selectedId, 0)) {
        const q = Q[S.selectedId];
        S.cam = cardReadingCamera(q.id,cardFitScale(CARD_BY_Q[q.id], mapArea()));
        applyCamera(true);
      }
    };
    window.addEventListener('resize', onResize);
    if (window.visualViewport) window.visualViewport.addEventListener('resize', () => { if (S.mode === 'mobile' && S.panelOpen) setSheet(S.sheet); });
  }

  function onEscape(e) {
    const layer = $('#dialog-layer');
    if (!layer.hidden) { const d = layer.querySelector('.dialog'); if (d && d.dataset.dismissable === 'true') closeDialog(); return; }
    if (S.previewId || pvOpenT) { hidePreview(true); return; }
    if (!$('#search-results').hidden) { $('#search-results').hidden = true; $('#search-input').setAttribute('aria-expanded', 'false'); return; }
    if ($$('.menu').some((m) => !m.hidden)) { closeMenus(); return; }
    if (!$('#outline').hidden && $('#outline').contains(document.activeElement)) { closeOutline(); return; }
    if (S.panelOpen) {
      if (e.target.matches && e.target.matches('#panel textarea, #panel input')) { $('#panel-q').focus(); return; } // never clears typing
      closePanel();
    }
  }

  function onAction(e) {
    const b = e.target.closest('[data-action]');
    if (!b) return;
    const a = b.dataset.action;
    switch (a) {
      case 'open-notes': closeMenus(); openNotes(); break;
      case 'open-outline': e.preventDefault(); openOutline('all'); break;
      case 'close-outline': closeOutline(); break;
      case 'outline-tab': $('#outline').dataset.tab = b.dataset.tab; renderOutline(); renderOutlineCounts(); renderOutlineCurrent(); $(`#outline [data-tab="${b.dataset.tab}"]`).focus(); break;
      case 'ol-toggle': { const ul = document.getElementById(b.getAttribute('aria-controls')); ul.hidden = !ul.hidden; b.setAttribute('aria-expanded', String(!ul.hidden)); break; }
      case 'expand-all': case 'collapse-all': $$('.ol-cat').forEach((c) => { const ul = document.getElementById(c.getAttribute('aria-controls')); ul.hidden = a === 'collapse-all'; c.setAttribute('aria-expanded', String(a === 'expand-all')); }); break;
      case 'goto': {
        const id = b.dataset.id;
        closeMenus();
        if (S.mode === 'mobile' && b.closest('#outline')) closeOutline();
        selectQuestion(id, { fly: true, center: true, focusPanel: e.detail === 0 || !!b.closest('#outline') });
        break;
      }
      case 'back': { const prev = S.backStack.pop(); if (prev) selectQuestion(prev, { fly: true, history: false, focusPanel: true }); break; }
      case 'toggle-history': { const m = $('#history-menu'); m.hidden = !m.hidden; b.setAttribute('aria-expanded', String(!m.hidden)); if (!m.hidden) { const f = m.querySelector('button'); if (f) f.focus(); } break; }
      case 'close-panel': closePanel(); break;
      case 'zoom-category': zoomToCategory(b.dataset.cat); break;
      case 'zoom-in': zoomAt(mapArea().w / 2, mapArea().h / 2, S.cam.s * 1.25, true); break;
      case 'zoom-out': zoomAt(mapArea().w / 2, mapArea().h / 2, S.cam.s / 1.25, true); break;
      case 'overview': overview(); break;
      case 'back-to-question': backToQuestion(); break;
      case 'next': nextQuestion(false); break;
      case 'skip': nextQuestion(true); break;
      case 'route-off': S.venture.ui.route.on = false; renderGuide(); CARDS.forEach((card) => refreshTile(card.id)); scheduleUiSave(); break;
      case 'route-on': S.venture.ui.route.on = true; renderGuide(); CARDS.forEach((card) => refreshTile(card.id)); scheduleUiSave(); break;
      case 'branch': chooseBranch(b.dataset.branch); break;
      case 'founder-start': {
        const first = CATS['Founder Fit'].qs[0].id;
        if (S.mode === 'mobile') closeOutline();
        selectQuestion(first, { fly: true, center: true, focusPanel: true });
        break;
      }
      case 'open-from-preview': { const id = b.dataset.id; hidePreview(true); selectQuestion(id, { fromMap: true, focusPanel: true }); break; }
      case 'dismiss-tip': dismissTip(b.dataset.tip); break;
      case 'search-more': S.searchLimit += 30; runSearch(false); break;
      case 'copy-context': copyContext(); break;
      case 'download-md': persistIfDirty(); download(`${fileStem()}-context.md`, 'text/markdown', toMarkdown(answeredOnly())); toast(tr("Markdown context downloaded.")); break;
      case 'close-dialog': closeDialog(); break;
      default: break;
    }
    if (b.id === 'export-btn' || a === undefined) { /* handled below */ }
  }

  function onInput(e) { if (e.target.id === 'search-input') runSearch(true); }

  // Toolbar buttons that are not data-action driven
  function bindToolbar() {
    $('#language-select').value=I18N.locale;
    $('#language-select').addEventListener('change',e=>changeLocale(e.target.value));
    $('#outline-btn').addEventListener('click', () => { if ($('#outline').hidden) openOutline(); else closeOutline(); });
    $('#export-btn').addEventListener('click', (e) => {
      const m = $('#export-menu');
      const open = m.hidden;
      closeMenus();
      m.hidden = !open;
      e.currentTarget.setAttribute('aria-expanded', String(open));
      if (open) m.querySelector('button:not([hidden]):not(:disabled), select')?.focus();
    });
  }

  // 題目集合改變時，不將舊畫布的選題、鏡頭與閱讀位置套用到新畫布。
  function questionDomain() { return mainQs.map(q=>q.id).join('|'); }
  function layoutIdentity() { return `${isCore()?'core':'legacy'}:${CARD_W}:3`; }
  function readingRestorePlan(saved) {
    const sameDomain=!saved.questionDomain || saved.questionDomain===questionDomain();
    const valid=Boolean(saved.selectedId && Q[saved.selectedId] && !Q[saved.selectedId].caution && sameDomain);
    const finiteCamera=saved.cam && ['x','y','s'].every(key=>Number.isFinite(saved.cam[key])) && saved.cam.s>0;
    const layoutCompatible=saved.layoutKey===layoutIdentity();
    let cam=valid && finiteCamera && layoutCompatible?saved.cam:null;
    const anchor=saved.selectedAnchor,q=Q[saved.selectedId];
    if(cam && anchor && ['x','y'].every(key=>Number.isFinite(anchor[key])))cam={...cam,x:cam.x+q.wx-anchor.x,y:cam.y+q.wy-anchor.y};
    return {valid,selectedId:valid?saved.selectedId:mainQs[0]?.id,cam};
  }

  // Expose a small hook for automated checks (read-only helpers).
  window.__studio = {
    captureReading: () => ({ questionDomain:questionDomain(),layoutKey:layoutIdentity(),selectedAnchor:S.selectedId?{x:Q[S.selectedId].wx,y:Q[S.selectedId].wy}:null, selectedId:S.selectedId, panelOpen:S.panelOpen, cam:{...S.cam}, scroll:[...document.querySelectorAll('[id]')].filter(e=>e.scrollTop||e.scrollLeft).map(e=>[e.id,e.scrollTop,e.scrollLeft]), details:[...document.querySelectorAll('details[id][open]')].map(e=>e.id), focus:document.activeElement?.id, focusAction:document.activeElement?.dataset?.action, focusTarget:document.activeElement?.dataset?.id }),
    restoreReading: saved => {
      const plan=readingRestorePlan(saved);
      if(!plan.valid) {
        if(!plan.selectedId)return;
        closePanel({returnFocus:false});
        selectQuestion(plan.selectedId,{fly:false,history:false,openPanel:false,focusPanel:false,restoring:true});
        requestAnimationFrame(()=>requestAnimationFrame(()=>{
          const q=Q[plan.selectedId],target=cardReadingCamera(q.id,cardFitScale(CARD_BY_Q[q.id],mapArea()));
          cancelAnim();setCam(target.x,target.y,target.s);S.camTouched=false;
        }));
        return;
      }
      selectQuestion(plan.selectedId,{fly:false,center:false,openPanel:saved.panelOpen,focusPanel:false});
      if(!saved.panelOpen) closePanel({returnFocus:false});
      requestAnimationFrame(()=>requestAnimationFrame(()=>{
        if(plan.cam) {cancelAnim();setCam(plan.cam.x,plan.cam.y,plan.cam.s);}
        else {
          const q=Q[plan.selectedId],target=cardReadingCamera(q.id,cardFitScale(CARD_BY_Q[q.id],mapArea()));
          cancelAnim();setCam(target.x,target.y,target.s);S.camTouched=false;
        }
        for(const id of saved.details||[]) {const e=document.getElementById(id);if(e)e.open=true;}
        for(const [id,top,left] of saved.scroll||[]) {const e=document.getElementById(id);if(e){e.scrollTop=top;e.scrollLeft=left;}}
        const focus=saved.focus?document.getElementById(saved.focus):[...document.querySelectorAll('[data-action]')].find(e=>e.dataset.action===saved.focusAction && e.dataset.id===saved.focusTarget);
        focus?.focus({preventScroll:true});
      }));
    },
    locale:()=>I18N.locale, changeLocale, state: S, cards: () => CARDS, cardFor: id => CARD_BY_Q[id], Q: () => Q, cats: () => CATS, setCam: (x, y, s) => { cancelAnim(); setCam(x, y, s); },
    toMarkdown: (o) => toMarkdown(!!o), selectQuestion: (id) => selectQuestion(id, { fly: true, center: true }),
    worldToScreen: (x, y) => worldToScreen(x, y), routeIds: () => routeIds.slice(),
  };

  document.addEventListener('DOMContentLoaded', () => { bindToolbar(); boot(); });
})();
