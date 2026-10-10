const $ = s => document.querySelector(s);
let deck = null, library = [], hand = [], mulligans = 0, bottomNeeded = 0, metadata = {}, playStarted = false;
let savedDecks = [], editingId = null;
let conversation = [], chatBusy = false, chatEpoch = 0;
const cardCache = new Map(), cardPending = new Map();
function moxfieldUrl(value) {
  if (!value?.trim()) return '';
  const url = new URL(value.trim());
  if (url.protocol !== 'https:' || !['moxfield.com','www.moxfield.com'].includes(url.hostname) || url.username || url.password || !/^\/decks\/[A-Za-z0-9_-]+\/?$/.test(url.pathname)) throw new Error('Use a Moxfield deck URL such as https://moxfield.com/decks/your-deck-id.');
  return 'https://moxfield.com' + url.pathname.replace(/\/$/,'');
}
function updateSourceLinks() {
  let url = ''; try { url = moxfieldUrl(deck?.sourceUrl); } catch {}
  for (const id of ['#deck-source-link','#active-source-link']) {
    $(id).href = url || 'https://moxfield.com';
    $(id).textContent = url ? 'Open this deck on Moxfield ↗' : 'Open Moxfield · sign in ↗';
  }
}
function resetConversation(clear=true) {
  conversation = []; chatEpoch++;
  if(clear && typeof sessionStorage!=='undefined') try {sessionStorage.removeItem('libby-chat-'+(deck?.id || 'general'));}catch{}
  $('#messages').replaceChildren(make('div',deck ? `Let’s talk about ${deck.name}. Ask about strategy, card swaps, or your next opening hand.` : 'Add a deck, then ask me about its strategy, card choices, or opening hands.','message'));
  $('#chat-context').textContent = deck ? `Talking about ${deck.name}` : 'Add a deck to give AI your list';
}
function restoreConversation() {
  resetConversation(false);
  if(typeof sessionStorage==='undefined')return;
  try {const saved=JSON.parse(sessionStorage.getItem('libby-chat-'+(deck?.id || 'general')) || '[]'); if(Array.isArray(saved)) conversation=saved.filter(t=>['user','assistant'].includes(t?.role)&&typeof t.content==='string'&&t.content.length<=8000).slice(-20); conversation.forEach(t=>message(t.content,t.role==='user'));}catch{}
}
function storeConversation(){if(typeof sessionStorage!=='undefined')try{sessionStorage.setItem('libby-chat-'+(deck?.id || 'general'),JSON.stringify(conversation));}catch{}}
$('#clear-chat').onclick = () => resetConversation();
const make = (tag, text, cls) => { const el = document.createElement(tag); el.textContent = text; if (cls) el.className = cls; return el; };
function tab(id) {
  const routes={chat:'/',deck:'/upload',analyze:'/analyze',play:'/playtest'};
  if(typeof window!=='undefined') {
    const path=window.location.pathname.replace(/\/$/,'') || '/';
    const target=routes[id] || '/';
    if(path!==target){window.location.href=target;return;}
    document.body.dataset.page=id;
  }
  document.querySelectorAll('.tab').forEach(e=>e.hidden=e.id!==id);
  document.querySelectorAll('[data-tab]').forEach(e=>{e.classList.toggle('selected',e.dataset.tab===id);e.setAttribute?.('aria-current',e.dataset.tab===id?'page':'false');});
}

document.querySelectorAll('[data-tab]').forEach(e => e.onclick = () => tab(e.dataset.tab));
function parseList(text) {
  const cards = new Map(); let excluded = false;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim(); if (!line || line.startsWith('//')) continue;
    if (/^(sideboard|maybeboard|considering)\s*:?$/i.test(line)) { excluded = true; continue; }
    if (/^(commander|commanders|mainboard|deck)\s*:?$/i.test(line)) { excluded = false; continue; }
    if (excluded) continue;
    const m = line.match(/^(\d+)\s*x?\s+(.+)$/i);
    if (!m) throw new Error(`Could not read: ${line}. Use quantity + card name.`);
    const quantity = Number(m[1]), name = m[2].replace(/\s+\([A-Za-z0-9]+\)\s+\S+.*$/, '').trim();
    if (!name || name.length > 200 || quantity < 1 || quantity > 100) throw new Error('Each entry needs 1–100 copies and a valid card name.');
    const key = name.toLowerCase(), existing = cards.get(key);
    cards.set(key, {name: existing?.name || name, quantity: quantity + (existing?.quantity || 0)});
  }
  const result = [...cards.values()];
  if (!result.length || result.reduce((n,c) => n + c.quantity,0) > 250) throw new Error('Import between 1 and 250 total cards.');
  return result;
}
function count() { return deck?.cards.reduce((n,c) => n + c.quantity, 0) || 0; }
function commanderNames() { return [deck?.commander,deck?.partner].filter(Boolean); }
function isCommander(name) { return commanderNames().some(n=>n.toLowerCase()===name.toLowerCase()); }
function commanderPresent() { return commanderNames().length>0 && commanderNames().every(n=>deck.cards.some(c=>c.name.toLowerCase()===n.toLowerCase())); }
function libraryCards() { return deck.cards.flatMap(c => Array(c.quantity - (isCommander(c.name) ? 1 : 0)).fill(c.name)); }
function stats() {
  const known = deck.cards.filter(c => metadata[c.name]);
  const lands = known.filter(c => /\bLand\b/.test(metadata[c.name].type_line || '')).reduce((n,c) => n + c.quantity,0);
  return {total: count(), unique: deck.cards.length, known: known.reduce((n,c) => n+c.quantity,0), lands};
}
function analysisText() {
  if (!deck) return 'Import a deck in Deck library first.';
  const s = stats(), issues = [];
  if (s.total !== 100) issues.push(`Commander normally requires 100 cards including the commander; this list has ${s.total}.`);
  if (!deck.commander) issues.push('Set your commander before testing hands.');
  else if (!commanderPresent()) issues.push('Your commander must appear in the imported list.');
  const duplicates = deck.cards.filter(c => c.quantity > 1 && !/^(Snow-Covered )?(Plains|Island|Swamp|Mountain|Forest|Wastes)$/i.test(c.name));
  if (duplicates.length) issues.push(`Review repeated nonbasic cards: ${duplicates.map(c=>c.name).join(', ')}. Some cards explicitly allow extra copies.`);
  return `${deck.name}: ${s.total} cards, ${s.unique} unique names.\n${issues.length ? issues.join('\n') : 'Card count and commander presence pass basic checks.'}\nScryfall data available for ${s.known}/${s.total} cards. ${s.lands} confirmed land cards${s.known < s.total ? ' (incomplete count)' : ''}.\nRefresh card data for verified Commander construction checks.`;
}
function renderDeck() {
  $('#workspace-name').textContent = deck.name;
  if(typeof renderDeckBrowser==='function')renderDeckBrowser();
  $('#active-name').textContent = deck.name; $('#active-count').textContent = `${count()} cards · ${deck.commander || 'Commander not set'}`;
  $('#analysis').replaceChildren(make('h2','Deck fundamentals'),make('p',analysisText(),'message'));
  const btn = make('button','Fetch card data from Scryfall'); btn.onclick = loadCards; $('#analysis').append(btn);
}
function saveLibrary() {
  try {
    localStorage.setItem('mtgvibes-library', JSON.stringify(savedDecks));
    if (deck) localStorage.setItem('mtgvibes-deck', JSON.stringify(deck));
    else localStorage.removeItem('mtgvibes-deck');
    return true;
  } catch { message('Browser storage is unavailable. Download your list to keep a backup.'); return false; }
}
function renderLibrary() {
  $('#sidebar-decks').replaceChildren();
  if(!savedDecks.length) $('#sidebar-decks').append(make('p','Your decks will appear here.','muted'));
  savedDecks.forEach(saved=>{ const button=make('button','',saved.id===editingId?'selected':''); const thumb=make('img','');thumb.alt='';thumb.src=saved.coverData || '/api/card-image?name='+encodeURIComponent(saved.coverCard || saved.commander || saved.cards[0].name);thumb.onerror=()=>{thumb.hidden=true;};button.append(thumb,make('span',saved.name)); button.onclick=()=>{if(saved.id!==editingId){activateDeck(saved);saveLibrary();}}; $('#sidebar-decks').append(button); });
  const select = $('#saved-decks'); select.replaceChildren();
  if (!savedDecks.length) select.append(make('option','No saved decks yet'));
  for (const saved of savedDecks) { const option = make('option',saved.name); option.value = saved.id; select.append(option); }
  select.value = editingId || '';
  $('#export-deck').disabled = !deck;
  $('#delete-deck').disabled = !deck;
}
function activateDeck(value) {
  deck = value; editingId = value?.id || null; metadata = {};
  library = []; hand = []; playStarted = false; bottomNeeded = 0;
  $('#deck-name').value = value?.name || '';
  $('#commander').value = value?.commander || '';
  $('#partner').value = value?.partner || '';
  $('#moxfield-url').value = value?.sourceUrl || '';
  $('#cover-card').value=value?.coverCard || '';
  if(typeof setCoverDraft==='function')setCoverDraft(value?.coverData || '');
  $('#list').value = value?.cards.map(c=>`${c.quantity} ${c.name}`).join('\n') || '';
  $('#import-error').textContent = '';
  if (value) renderDeck();
  else { $('#workspace-name').textContent='Add your first deck'; $('#active-name').textContent='Your next great deck'; $('#active-count').textContent='No active list'; $('#analysis').replaceChildren(); }
  updateSourceLinks(); restoreConversation(); renderLibrary(); renderHand();
  if(typeof resetBoard==='function') resetBoard();
  if(typeof renderCommanderCheck==='function')renderCommanderCheck();
}
$('#manage-decks').onclick = () => tab('deck');
$('#quick-add').onclick = () => { activateDeck(null); tab('deck'); $('#deck-name').focus(); };
$('#play-import').onclick = () => tab('deck');
$('#quick-analyze').onclick = () => { tab('chat'); send('Libby, analyze my active deck. Explain its game plan, strengths, weaknesses, and possible improvements.'); };
$('#libby').onclick = () => { $('#prompt').focus();  };
$('#sidebar-add').onclick=()=>{activateDeck(null);tab('deck');};
$('#quick-play').onclick = () => { tab('play'); if(deck && !playStarted) newHand(); };
$('#new-deck').onclick = () => { activateDeck(null); tab('deck'); $('#deck-name').focus(); };
$('#saved-decks').onchange = e => { const value = savedDecks.find(d=>d.id===e.target.value); if(value) { activateDeck(value); saveLibrary(); } };
$('#delete-deck').onclick = () => {
  if (!deck || !confirm(`Delete “${deck.name}” from this browser? Your Moxfield deck will not be changed.`)) return;
  savedDecks = savedDecks.filter(d=>d.id!==editingId); activateDeck(savedDecks[0] || null); saveLibrary();
};
$('#export-deck').onclick = () => {
  if(!deck) return;
  const url = URL.createObjectURL(new Blob([deck.cards.map(c=>`${c.quantity} ${c.name}`).join('\n')],{type:'text/plain'}));
  const link = make('a','Download'); link.href=url; link.download=deck.name.replace(/[^a-z0-9_-]/gi,'_')+'.txt'; link.click(); URL.revokeObjectURL(url);
};
$('#deck-file').onchange = async e => {
  const file = e.target.files[0]; if(!file) return;
  if(file.size>100000) { $('#import-error').textContent='Choose a text file smaller than 100 KB.'; return; }
  try { $('#list').value=await file.text(); $('#import-error').textContent='File loaded. Enter the commander and click Save deck & analyze.'; }
  catch { $('#import-error').textContent='Could not read that file. Try pasting the list instead.'; }
};
async function loadCards() {
  const btn = $('#analysis button'); btn.disabled = true; let failed = 0;
  const current = deck;
  for (const card of current.cards) {
    if(deck!==current) return;
    if (metadata[card.name]) continue;
    try { const r = await fetch('/api/card?name=' + encodeURIComponent(card.name)); const data = await r.json(); if (!r.ok) { failed++; if (r.status === 502) break; } else metadata[card.name] = data; }
    catch { failed++; break; }
  }
  if(deck!==current) return;
  renderDeck(); if (failed) $('#analysis').append(make('p','Some card data could not be fetched. Try again later; counts above show only verified cards.','muted'));
}
$('#import-form').onsubmit = e => {
  e.preventDefault();
  try {
    const cards = parseList($('#list').value), commander = $('#commander').value.trim(), partner=$('#partner').value.trim();
    if(partner && (!commander || partner.toLowerCase()===commander.toLowerCase() || !cards.some(c=>c.name.toLowerCase()===partner.toLowerCase()))) throw new Error('Choose two different commanders and include both in the list.');
    if (commander && !cards.some(c=>c.name.toLowerCase() === commander.toLowerCase())) throw new Error('Include your commander in the pasted list.');
    if(savedDecks.length>=30 && !editingId) throw new Error('You can save up to 30 decks on this device. Download a backup before deleting an older deck.');
    const next = {id: editingId || crypto.randomUUID(), name: $('#deck-name').value.trim() || 'Commander deck', commander, partner, sourceUrl: moxfieldUrl($('#moxfield-url').value), cards,coverCard:$('#cover-card').value.trim(),coverData:typeof coverDraft!=='undefined'?coverDraft:deck?.coverData || ''};
    const index = savedDecks.findIndex(d=>d.id===next.id);
    if(index<0) savedDecks.push(next); else savedDecks[index]=next;
    activateDeck(next); const persisted=saveLibrary(); $('#import-error').textContent=persisted?'Deck saved. Open Deck analysis or Playtest from the menu.':'Deck loaded, but browser storage is full. Download your list before leaving this page.';
  } catch(error) { $('#import-error').textContent = error.message; }
};
function shuffle(cards) {
  for (let i = cards.length - 1; i > 0; i--) {
    const range = i + 1, limit = Math.floor(4294967296 / range) * range;
    let value; do { value = crypto.getRandomValues(new Uint32Array(1))[0]; } while (value >= limit);
    const j = value % range; [cards[i],cards[j]] = [cards[j],cards[i]];
  } return cards;
}
function newHand(isMulligan = false) {
  if (!deck || !deck.commander || !commanderPresent()) { $('#play-status').textContent = 'Import your list and set a commander included in it first.'; return; }
  mulligans = isMulligan ? mulligans + 1 : 0;
  library = shuffle(libraryCards()); hand = library.splice(0,7); playStarted = true;
  bottomNeeded = Math.min(Math.max(0,mulligans-1),hand.length); renderHand();
  if(typeof resetBoard==='function') resetBoard();
}
function renderHand() {
  $('#play-empty').hidden = !!deck;
  $('#hand').replaceChildren();
  hand.forEach((name,index) => {
    const card = make('button','','card');
    card.setAttribute?.('aria-label',bottomNeeded ? `Put ${name} on the bottom` : `View ${name}`);
    const img = make('img',''); img.alt = name; img.loading = 'eager'; img.hidden = true;
    card.append(img); card.append(make('span',name,'card-name'));
    if(typeof wireGameCard==='function')wireGameCard(card,'hand',index);
    img.onload=()=>{img.hidden=false;}; img.onerror=()=>{img.hidden=true; $('#image-status').textContent='An image could not load. Click Retry images to try again.';}; img.src='/api/card-image?name='+encodeURIComponent(name);
    card.onclick = () => { if(bottomNeeded) { if(typeof checkpoint==='function')checkpoint(); library.push(hand.splice(index,1)[0]); bottomNeeded--; renderHand(); } else if(typeof selectGameCard==='function') selectGameCard('hand',index); else showCard(name); };
    $('#hand').append(card);
  });
  if (!playStarted) $('#play-status').textContent = 'Import a deck, then shuffle to start testing.';
  else $('#play-status').textContent = `${hand.length} cards in hand · ${library.length} in library · ${mulligans} mulligan(s)${bottomNeeded ? ` · Select ${bottomNeeded} card(s) to bottom` : ''}`;
  $('#draw').disabled = !playStarted || bottomNeeded > 0 || !library.length;
  $('#mulligan').disabled = !playStarted || mulligans >= 8;
  $('#discuss-hand').disabled = !playStarted || bottomNeeded > 0 || chatBusy;
  if(typeof renderBoard==='function') renderBoard();
}
function imageUrl(data,face=0) {
  const value = data?.image_uris?.normal || data?.card_faces?.[face]?.image_uris?.normal;
  try { const url = new URL(value); return url.protocol==='https:' && url.hostname==='cards.scryfall.io' ? url.href : ''; } catch { return ''; }
}
async function getCard(name) {
  if(cardCache.has(name)) return cardCache.get(name);
  if(!cardPending.has(name)) cardPending.set(name,(async()=> {
    try { const response=await fetch('/api/card?name='+encodeURIComponent(name)); const data=await response.json(); if(!response.ok) throw new Error(data.error || 'Card unavailable'); cardCache.set(name,data); return data; }
    finally { cardPending.delete(name); }
  })());
  return cardPending.get(name);
}
async function showCard(name) {
  const detail=$('#card-detail'); detail.replaceChildren(make('h2',name)); $('#card-dialog').showModal();
  try {
    const data=await getCard(name); if(!$('#card-dialog').open || detail.firstChild.textContent!==name) return;
    const faces=data.image_uris ? [data] : data.card_faces || [data];
    faces.forEach((face,i)=> { const url=imageUrl(data,i); if(url) { const img=make('img',''); img.src='/api/card-image?name='+encodeURIComponent(name)+'&face='+i; img.alt=face.name || name; detail.append(img); } });
    detail.append(make('p',data.oracle_text || data.card_faces?.map(c=>c.oracle_text).join('\n') || ''));
  } catch { detail.append(make('p','Card images could not be loaded. Try again later.')); }
}
$('#close-card').onclick=()=>$('#card-dialog').close();
$('#discuss-hand').onclick=()=>{ if(typeof sessionStorage!=='undefined')sessionStorage.setItem('libby-game-question','true'); tab('chat'); };
$('#shuffle').onclick = () => newHand(); $('#mulligan').onclick = () => newHand(true);
$('#draw').onclick = () => { if (!bottomNeeded && library.length) { hand.push(library.shift()); renderHand(); } };
function message(text,user=false) { $('#messages').append(make('div',text,'message'+(user?' user':''))); $('#messages').scrollTop = $('#messages').scrollHeight; }
async function send(prompt) {
  if(chatBusy) return;
  message(prompt,true); const p = prompt.toLowerCase();
  if (/^(import|load|open).*deck/.test(p)) { tab('deck'); message('Paste your Moxfield text export in Deck library. Automatic Moxfield access is not connected.'); }
  else if (/^(test|draw).*hand/.test(p)) { tab('play'); newHand(); }
  else if (/^(find|search)\s+/i.test(prompt)) {
    try { const r = await fetch('/api/card?name=' + encodeURIComponent(prompt.replace(/^(find|search)\s+/i,''))); const card = await r.json(); if (!r.ok) throw new Error(card.error); message(`${card.name}\n${card.type_line}\n${card.oracle_text || card.card_faces?.map(c=>c.oracle_text).join('\n') || ''}`); const a = make('a','View on Scryfall ↗'); a.href = card.scryfall_uri; a.target = '_blank'; a.rel = 'noopener noreferrer'; $('#messages').lastChild.append(document.createElement('br'),a); }
    catch (error) { message(error.message); }
  } else {
    chatBusy = true; const currentDeck=deck, currentEpoch=chatEpoch;
    const button = $('#chat-form button'); button.disabled = true;
    const thinking = make('div','Thinking about your deck…','message'); $('#messages').append(thinking);
    try { const r = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:prompt,history:conversation.slice(-10),context:deck ? {deck:{name:deck.name,commander:deck.commander,partner:deck.partner || '',cards:deck.cards,sourceUrl:deck.sourceUrl},analysis:analysisText(),current_hand:playStarted ? [...hand] : null,game:typeof gameContext==='function'?gameContext():null,verified_cards:deck.cards.filter(c=>metadata[c.name] || cardCache.has(c.name)).map(c=>{const m=metadata[c.name] || cardCache.get(c.name); return {name:m.name,type_line:m.type_line,mana_value:m.cmc,color_identity:m.color_identity};})} : {}})}); const data = await r.json(); if(deck!==currentDeck || chatEpoch!==currentEpoch) return; message(data.answer || data.error); if(!r.ok) $('.notice').textContent=data.error; if(r.ok && data.answer) {if(deck && data.construction && typeof renderCommanderCheck==='function'){deck.commanderCheck=data.construction;saveLibrary();renderCommanderCheck();}conversation.push({role:'user',content:prompt},{'role':'assistant','content':data.answer.slice(0,8000)}); conversation=conversation.slice(-20);storeConversation();if(data.mode==='computed')$('.notice').textContent='Computed from Scryfall card data. AI chat may still require a working OpenAI connection.';} }
    catch { message('The server could not be reached. Try again.'); }
    finally { thinking.remove(); button.disabled = false; chatBusy=false; $('#discuss-hand').disabled=!playStarted || bottomNeeded>0; }
  }
}
$('#chat-form').onsubmit = e => { e.preventDefault(); const prompt = $('#prompt').value.trim(); if (prompt) { $('#prompt').value = ''; send(prompt); } };
document.querySelectorAll('[data-prompt]').forEach(e=> e.onclick=()=>send(e.dataset.prompt));
function validDeck(saved) {
  return saved && typeof saved.name === 'string' && typeof saved.commander === 'string' && Array.isArray(saved.cards) && saved.cards.length > 0 && saved.cards.length <= 250 && saved.cards.every(c=>typeof c.name==='string' && c.name.length>0 && Number.isInteger(c.quantity) && c.quantity>0 && c.quantity<=100) && saved.cards.reduce((n,c)=>n+c.quantity,0)<=250;
}
try {
  const storedLibrary = JSON.parse(localStorage.getItem('mtgvibes-library') || '[]');
  if(Array.isArray(storedLibrary)) savedDecks=storedLibrary.filter(d=>validDeck(d) && typeof d.id==='string').slice(0,30);
  const saved = JSON.parse(localStorage.getItem('mtgvibes-deck') || 'null');
  if (validDeck(saved)) {
    if(!savedDecks.length) savedDecks.push({...saved,id:saved.id||crypto.randomUUID()});
    activateDeck(savedDecks.find(d=>d.id===saved.id)||savedDecks[0]);
  }
} catch { /* Ignore invalid or unavailable browser storage. */ }
fetch('/api/health').then(r=>r.json()).then(data=> { $('.notice').textContent=data.ai_configured ? 'Libby’s key is configured. Click Libby or ask a question below.' : 'Libby isn’t connected yet. Deck import, analysis, and playtesting are available.'; }).catch(()=>{ $('.notice').textContent='Connection unavailable. Refresh to reconnect.'; });
renderLibrary();
updateSourceLinks();
renderHand();
