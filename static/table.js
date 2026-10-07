// A manual goldfishing table. Card effects and legality stay under the player's control.
let zones={battlefield:[],graveyard:[],exile:[],command:[]}, selected=null, life=40, turn=1, undoStack=[];
const gameCard=name=>({id:crypto.randomUUID(),name,tapped:false,counters:0});
function snapshot(){return JSON.stringify({deckId:deck?.id,library,hand,mulligans,bottomNeeded,playStarted,zones,life,turn});}
function checkpoint(){undoStack.push(snapshot());if(undoStack.length>50)undoStack.shift();}
function gameContext(){return {turn,life,library_count:library.length,battlefield:zones.battlefield,graveyard:zones.graveyard.map(c=>c.name),exile:zones.exile.map(c=>c.name),command_zone:zones.command.map(c=>c.name)};}
function persistGame(){try{sessionStorage.setItem('mtgvibes-game',snapshot());}catch{}}
function resetBoard(){zones={battlefield:[],graveyard:[],exile:[],command:deck?.commander?[gameCard(deck.commander)]:[]};selected=null;life=40;turn=1;undoStack=[];renderBoard();}
function selectedCard(){if(!selected)return null;return selected.zone==='hand' ? (hand[selected.index] ? {name:hand[selected.index]}:null) : zones[selected.zone]?.[selected.index];}
function selectGameCard(zone,index){selected={zone,index};renderBoard();}
function moveSelected(destination){
 const card=selectedCard();if(!card||bottomNeeded||destination===selected.zone)return;
 if(destination==='command' && card.name.toLowerCase()!==deck.commander.toLowerCase())return;
 checkpoint();
 const source=selected.zone;
 if(source==='hand')hand.splice(selected.index,1);else zones[source].splice(selected.index,1);
 if(destination==='hand')hand.push(card.name);
 else if(destination==='top')library.unshift(card.name);
 else if(destination==='bottom')library.push(card.name);
 else zones[destination].push({...gameCard(card.name),token:card.token||false});
 selected=null;renderHand();
}
function renderBoard(){
 $('#library-count').textContent=library.length;$('#life-count').textContent=life+' life';$('#turn-count').textContent='Turn '+turn;
 const card=selectedCard();$('#selection-label').textContent=card ? card.name+(card.counters ? ` · ${card.counters} counter(s)`:'') : 'Select a card to move it';
 document.querySelectorAll('[data-move]').forEach(button=>{button.disabled=!card||bottomNeeded>0||button.dataset.move===selected?.zone||(button.dataset.move==='command'&&card.name.toLowerCase()!==deck?.commander.toLowerCase());});
 $('#tap-card').disabled=!card||selected?.zone!=='battlefield';$('#counter-plus').disabled=$('#counter-minus').disabled=!card||selected?.zone==='hand';$('#zoom-card').disabled=!card;
 $('#undo-game').disabled=!undoStack.length;
 for(const [zone,target] of Object.entries({battlefield:'#battlefield',graveyard:'#graveyard',exile:'#exile',command:'#command-zone'})){
  $(target).replaceChildren();
  if(!zones[zone].length)$(target).append(make('p',zone==='battlefield'?'Your next play goes here.':'Empty','zone-empty'));
  zones[zone].forEach((item,index)=>{
   const button=make('button','','table-card'+(item.tapped?' tapped':'')+(selected?.zone===zone&&selected.index===index?' chosen':''));button.setAttribute('aria-label',item.name);button.onclick=()=>selectGameCard(zone,index);wireGameCard(button,zone,index);
   if(!item.token){const image=make('img','');image.alt=item.name;image.onload=()=>{image.hidden=false;};image.onerror=()=>{image.hidden=true;$('#image-status').textContent='Some images are unavailable. Retry images to try again.';};image.hidden=true;image.src='/api/card-image?name='+encodeURIComponent(item.name);button.append(image);}
   button.append(make('span',item.name+(item.counters ? ` · +${item.counters}`:''),'card-name'));$(target).append(button);
  });
 }
 $('#library-draw').disabled=$('#mill-card').disabled=$('#peek-card').disabled=!playStarted||!library.length||bottomNeeded>0;
 $('#next-turn').disabled=!playStarted||bottomNeeded>0;$('#add-token').disabled=!playStarted;persistGame();
}
function drawGameCard(){if(!library.length||bottomNeeded||!playStarted)return;checkpoint();hand.push(library.shift());selected=null;renderHand();}
document.querySelectorAll('[data-move]').forEach(button=>button.onclick=()=>moveSelected(button.dataset.move));
$('#draw').onclick=$('#library-draw').onclick=drawGameCard;
$('#mill-card').onclick=()=>{if(!library.length||bottomNeeded)return;checkpoint();zones.graveyard.push(gameCard(library.shift()));renderHand();};
$('#peek-card').onclick=()=>{if(library.length)showCard(library[0]);};
$('#shuffle-library').onclick=()=>{if(!playStarted)return;checkpoint();shuffle(library);renderBoard();};
$('#next-turn').onclick=()=>{if(!playStarted||bottomNeeded)return;checkpoint();turn++;zones.battlefield.forEach(c=>c.tapped=false);if(library.length)hand.push(library.shift());selected=null;renderHand();};
$('#life-minus').onclick=()=>{checkpoint();life--;renderBoard();};$('#life-plus').onclick=()=>{checkpoint();life++;renderBoard();};
$('#tap-card').onclick=()=>{const card=selectedCard();if(card&&selected.zone==='battlefield'){checkpoint();card.tapped=!card.tapped;renderBoard();}};
$('#counter-plus').onclick=()=>{const card=selectedCard();if(card&&selected.zone!=='hand'){checkpoint();card.counters++;renderBoard();}};
$('#counter-minus').onclick=()=>{const card=selectedCard();if(card&&selected.zone!=='hand'){checkpoint();card.counters=Math.max(0,card.counters-1);renderBoard();}};
$('#zoom-card').onclick=()=>{const card=selectedCard();if(card&&!card.token)showCard(card.name);};
$('#add-token').onclick=()=>{const name=prompt('Token name','Creature token');if(name?.trim()){checkpoint();zones.battlefield.push({...gameCard(name.trim().slice(0,100)),token:true});renderBoard();}};
$('#undo-game').onclick=()=>{if(!undoStack.length)return;const saved=JSON.parse(undoStack.pop());({library,hand,mulligans,bottomNeeded,playStarted,zones,life,turn}=saved);selected=null;renderHand();};
$('#retry-images').onclick=()=>{$('#image-status').textContent='Retrying card images…';cardCache.clear();renderHand();document.querySelectorAll('#hand img,.table-card img').forEach(image=>{image.src=image.src+'&retry='+Date.now();});};
$('#shuffle').onclick=()=>{if((zones.battlefield.length||zones.graveyard.length||zones.exile.length)&&!confirm('Start a new game? This clears the current table.'))return;newHand();};
$('#mulligan').onclick=()=>{if(zones.battlefield.length||zones.graveyard.length||zones.exile.length){$('#play-status').textContent='Start a new game to mulligan after playing cards.';return;}newHand(true);};
let hovered=null, dragOrigin=null;
function wireGameCard(button,zone,index){
 button.draggable=true;
 button.onmouseenter=()=>{hovered={zone,index};};button.onmouseleave=()=>{hovered=null;};
 button.onfocus=()=>{hovered={zone,index};};button.onblur=()=>{hovered=null;};
 let touchStart=null, touchDragging=false, suppressClickUntil=0;
 button.addEventListener?.('click',event=>{if(Date.now()<suppressClickUntil){event.preventDefault();event.stopImmediatePropagation();}},true);
 button.onpointerdown=event=>{if(event.pointerType==='mouse'||bottomNeeded)return;touchStart={x:event.clientX,y:event.clientY};touchDragging=false;button.setPointerCapture(event.pointerId);};
 button.onpointermove=event=>{if(!touchStart)return;if(Math.hypot(event.clientX-touchStart.x,event.clientY-touchStart.y)>10){touchDragging=true;button.classList.add('dragging');document.querySelectorAll('[data-drop]').forEach(target=>target.classList.toggle('drop-ready',target.contains(document.elementFromPoint(event.clientX,event.clientY))));}};
 button.onpointerup=event=>{if(!touchStart)return;if(touchDragging){suppressClickUntil=Date.now()+500;const target=document.elementFromPoint(event.clientX,event.clientY)?.closest('[data-drop]');if(target){selected={zone,index};moveSelected(target.dataset.drop);}event.preventDefault();}touchStart=null;touchDragging=false;button.classList.remove('dragging');document.querySelectorAll('[data-drop]').forEach(target=>target.classList.remove('drop-ready'));};
 button.onpointercancel=()=>{touchStart=null;touchDragging=false;button.classList.remove('dragging');document.querySelectorAll('[data-drop]').forEach(target=>target.classList.remove('drop-ready'));};
 button.ondragstart=event=>{if(bottomNeeded){event.preventDefault();return;}dragOrigin={zone,index};event.dataTransfer.setData('application/x-mtg-card',JSON.stringify(dragOrigin));event.dataTransfer.effectAllowed='move';button.classList.add('dragging');};
 button.ondragend=()=>{dragOrigin=null;button.classList.remove('dragging');document.querySelectorAll('[data-drop]').forEach(e=>e.classList.remove('drop-ready'));};
}
document.querySelectorAll('[data-drop]').forEach(target=>{
 target.ondragover=event=>{if(dragOrigin&&!bottomNeeded){event.preventDefault();event.dataTransfer.dropEffect='move';target.classList.add('drop-ready');}};
 target.ondragleave=event=>{if(!target.contains(event.relatedTarget))target.classList.remove('drop-ready');};
 target.ondrop=event=>{event.preventDefault();target.classList.remove('drop-ready');if(!dragOrigin||bottomNeeded)return;selected=dragOrigin;const destination=target.dataset.drop==='top'&&event.shiftKey?'bottom':target.dataset.drop;moveSelected(destination);dragOrigin=null;};
});
document.addEventListener?.('keydown',event=>{
 if(window.location.pathname.replace(/\/$/,'')!=='/playtest'||event.ctrlKey||event.metaKey||event.altKey||event.target.closest?.('input,textarea,select,[contenteditable=true]')||$('#card-dialog').open)return;
 const key=event.key.toLowerCase();const shortcuts={p:'battlefield',h:'hand',g:'graveyard',x:'exile',l:'top',b:'bottom',c:'command'};
 if(hovered && selectedCardForHover(hovered)){selected={...hovered};if(shortcuts[key]){event.preventDefault();moveSelected(shortcuts[key]);hovered=null;return;}if(key==='t'){event.preventDefault();$('#tap-card').onclick();}if(key==='v'){event.preventDefault();showCard(selectedCard().name);}if(key==='+'||key==='='){event.preventDefault();$('#counter-plus').onclick();}if(key==='-'){event.preventDefault();$('#counter-minus').onclick();}}
 if(key==='d'){event.preventDefault();drawGameCard();}if(key==='n'){event.preventDefault();$('#next-turn').onclick();}if(key==='u'){event.preventDefault();$('#undo-game').onclick();}
});
function selectedCardForHover(value){return value.zone==='hand'?hand[value.index]:zones[value.zone]?.[value.index];}
// Restore the same table when moving between Libby and /playtest in this tab.
try{
 const saved=JSON.parse(sessionStorage.getItem('mtgvibes-game')||'null');
 if(saved && saved.deckId===deck?.id && saved.playStarted && Array.isArray(saved.hand)&&Array.isArray(saved.library)&&saved.hand.every(n=>typeof n==='string')&&saved.library.every(n=>typeof n==='string')&&saved.hand.length+saved.library.length<=250 && saved.zones && Object.keys(zones).every(z=>Array.isArray(saved.zones[z]) && saved.zones[z].length<=250 && saved.zones[z].every(c=>typeof c.name==='string'))){({library,hand,mulligans,bottomNeeded,playStarted,zones,life,turn}=saved);}
 else zones.command=deck?.commander?[gameCard(deck.commander)]:[];
}catch{zones.command=deck?.commander?[gameCard(deck.commander)]:[];}
renderHand();
const routePage={'/upload':'deck','/analyze':'analyze','/playtest':'play'}[window.location.pathname.replace(/\/$/,'')] || 'chat';tab(routePage);if(routePage==='play'&&deck&&!playStarted)newHand();
if(routePage==='chat'&&sessionStorage.getItem('libby-game-question')){sessionStorage.removeItem('libby-game-question');send('Libby, help me understand this hand and board. What is my best plan from here?');}
window.addEventListener('beforeunload',persistGame);
