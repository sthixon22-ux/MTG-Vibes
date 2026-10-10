// Focused deck hubs, artwork customization, and deterministic deck statistics.
let coverDraft=deck?.coverData || '', deckView='images', statsPending=false;
function renderCommanderCheck(){
 const check=deck?.commanderCheck || deck?.statistics?.commander_check;
 const colorNames={W:'White',U:'Blue',B:'Black',R:'Red',G:'Green'};
 for(const selector of ['#commander-check','#libby-deck-check']){
  const target=$(selector);target.replaceChildren();
  target.classList.remove('has-issues');
  if(!deck){target.append(make('span','Choose a deck to check its Commander identity.'));continue;}
  if(!check){target.append(make('span','Commander identity not checked yet. Libby checks card data when you chat.'));
   const button=make('button','Check deck');button.onclick=refreshStatistics;target.append(button);continue;}
  const colors=check.identity_verified?(check.color_identity.map(c=>colorNames[c]).join(' · ') || 'Colorless'):'Identity unverified';
  target.append(make('strong',colors),make('span',check.status==='passed'?'Construction checks passed':`${check.issues.length} item${check.issues.length===1?'':'s'} to review`));
  target.classList.toggle('has-issues',check.status!=='passed');
  if(check.issues.length){const detail=make('details','','check-details');detail.append(make('summary','Details'));const list=make('div','','check-issues');check.issues.forEach(issue=>list.append(make('p',issue)));list.append(make('p',check.scope || 'Construction checks only.','muted'));const link=make('a','Official rules ↗');link.href='https://magic.wizards.com/en/rules';link.target='_blank';link.rel='noopener noreferrer';list.append(link);detail.append(list);target.append(detail);}
 }
}
function safeArtwork(value){return typeof value==='string'&&value.length<=250000&&/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(value)?value:'';}
function coverSource(value){return safeArtwork(value?.coverData) || (value ? '/api/card-image?name='+encodeURIComponent(value.coverCard || value.commander || value.cards[0]?.name || '') : '');}
function setCoverDraft(value){coverDraft=safeArtwork(value);updateCoverPreview();}
function updateCoverPreview(){const image=$('#cover-preview');const name=$('#cover-card').value.trim() || $('#commander').value.trim();image.hidden=!coverDraft&&!name;image.onload=()=>{image.hidden=false;};image.onerror=()=>{image.hidden=true;};if(coverDraft||name)image.src=coverDraft||'/api/card-image?name='+encodeURIComponent(name);}
$('#cover-card').onchange=$('#commander').onchange=updateCoverPreview;
$('#reset-cover').onclick=()=>{coverDraft='';$('#cover-file').value='';updateCoverPreview();};
$('#cover-file').onchange=async event=>{
 const file=event.target.files[0];if(!file)return;
 if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>5000000){$('#import-error').textContent='Choose a PNG, JPEG, or WebP image under 5 MB.';return;}
 try{
  const bitmap=await createImageBitmap(file);const canvas=document.createElement('canvas');const scale=Math.min(1,640/bitmap.width,480/bitmap.height);canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();let data=canvas.toDataURL('image/jpeg',.75);if(data.length>250000)data=canvas.toDataURL('image/jpeg',.4);if(data.length>250000)throw new Error('Image is too detailed. Choose a smaller image.');setCoverDraft(data);$('#import-error').textContent='Artwork selected. Save the deck to keep it.';
 }catch(error){$('#import-error').textContent=error.message || 'This image could not be read.';}
};
function renderDeckBrowser(){
 renderCommanderCheck();
 const browser=$('#deck-browser');browser.replaceChildren();const cover=$('#analysis-cover');cover.src=coverSource(deck);cover.hidden=!deck;cover.onerror=()=>{cover.hidden=true;};cover.onload=()=>{cover.hidden=false;};
 if(!deck){browser.append(make('p','Choose a deck from the sidebar or upload your first list.','empty-state'));return;}
 document.querySelectorAll('[data-view]').forEach(button=>{button.classList.toggle('selected',button.dataset.view===deckView);button.setAttribute('aria-pressed',String(button.dataset.view===deckView));});
 if(deckView==='stats'){renderStatistics(browser);return;}
 const filter=$('#deck-filter').value.toLowerCase();const cards=deck.cards.filter(c=>c.name.toLowerCase().includes(filter));browser.className='deck-browser '+(deckView==='images'?'image-grid':'text-list');
 cards.forEach(card=>{
  const item=make('button','',deckView==='images'?'gallery-card':'text-card');item.onclick=()=>showCard(card.name);
  if(deckView==='images'){const image=make('img','');image.alt=card.name;image.loading='lazy';image.src='/api/card-image?name='+encodeURIComponent(card.name);image.onerror=()=>{image.classList.add('image-failed');};item.append(image);}
  item.append(make('span',`${card.quantity} × ${card.name}`));browser.append(item);
 });
 if(!cards.length)browser.append(make('p','No cards match your search.','muted'));
}
function renderStatistics(container){
 container.className='deck-browser stats-view';const stats=deck?.statistics;
 if(!stats){container.append(make('p','Fetch Scryfall data for land counts, mana curve, and exact opening-hand odds.','empty-state'));return;}
 const summary=make('div','','stat-grid');[['Library',stats.library_size],['Front-face lands',stats.lands],['Cheap nonland spells',stats.cheap_nonland_spells],['Known cards',`${stats.known_cards}/${stats.library_size}`]].forEach(([label,value])=>{const box=make('div','','stat');box.append(make('strong',String(value)),make('span',label));summary.append(box);});container.append(summary);
 const odds=stats.opening_hand_odds;container.append(make('h2','Seven-card opening hands'));
 if(odds)container.append(make('p',`Exactly 3 lands and at least one spell with mana value ≤2: ${odds.exactly_three_lands_and_cheap_spell}%. At least 3 lands and such a spell: ${odds.at_least_three_lands_and_cheap_spell}%.`));else container.append(make('p','Odds are unavailable until all card data is known.'));
 container.append(make('h2','Mana curve · nonland cards'));
 const curve=make('div','','curve');stats.curve.forEach((value,index)=>{const bar=make('div','','curve-column');bar.append(make('strong',String(value)),make('span',index===7?'7+':String(index)));curve.append(bar);});container.append(curve,make('p',stats.method,'muted'));
 if(stats.unknown_cards.length)container.append(make('p','Card data unavailable: '+stats.unknown_cards.join(', '),'muted'));
}
async function refreshStatistics(){
 if(!deck||statsPending)return;statsPending=true;const current=deck;$('#refresh-stats').disabled=true;$('#analysis-status').textContent='Fetching card data…';
 renderCommanderCheck();document.querySelectorAll('.identity-banner button').forEach(button=>{button.disabled=true;button.textContent='Checking…';});
 try{const response=await fetch('/api/deck-analysis',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({deck:{cards:current.cards,commander:current.commander,partner:current.partner || ''}})});const result=await response.json();if(!response.ok)throw new Error(result.error);if(deck!==current)return;current.statistics=result;current.commanderCheck=result.commander_check;saveLibrary();$('#analysis-status').textContent=result.unknown_cards.length?'Some card data is missing; incomplete odds are not shown.':'Card data refreshed. Opening-hand odds use exact probabilities.';renderDeckBrowser();}
 catch(error){const text=error.message || 'Could not fetch card data. Try again.';$('#analysis-status').textContent=text;if(deck===current)$('#libby-deck-check').append(make('span',text));}
 finally{statsPending=false;$('#refresh-stats').disabled=false;document.querySelectorAll('.identity-banner button').forEach(button=>{button.disabled=false;button.textContent='Check deck';});}
}
document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>{deckView=button.dataset.view;renderDeckBrowser();});$('#deck-filter').oninput=renderDeckBrowser;$('#refresh-stats').onclick=refreshStatistics;
function startNewDeck(){if(window.location.pathname==='/upload'){activateDeck(null);setCoverDraft('');$('#deck-name').focus();}else{sessionStorage.setItem('mtg-new-deck','true');tab('deck');}}
$('#sidebar-add').onclick=$('#quick-add').onclick=$('#new-deck').onclick=startNewDeck;
if(window.location.pathname==='/upload'&&sessionStorage.getItem('mtg-new-deck')){sessionStorage.removeItem('mtg-new-deck');activateDeck(null);}
setCoverDraft(deck?.coverData || '');renderDeckBrowser();

$('#test-libby').onclick=async()=>{const button=$('#test-libby');button.disabled=true;$('.notice').textContent='Testing a short AI reply…';try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:'Reply with only: Ready.',context:{},history:[]})});const result=await response.json();$('.notice').textContent=response.ok?'Libby’s AI connection works. Choose your deck and ask a question.':result.error+(result.provider_code?' (Provider code: '+result.provider_code+')':'');}catch{$('.notice').textContent='The server could not be reached. Check the deployment and try again.';}finally{button.disabled=false;}};
