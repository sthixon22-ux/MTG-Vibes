const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const elements = new Map();
function element() { return {value:'',children:[],classList:{toggle(){}},append(...items){this.children.push(...items)},replaceChildren(...items){this.children=items}}; }
const context = vm.createContext({
  document: {querySelector(s){ if(!elements.has(s)) elements.set(s,element()); return elements.get(s); },querySelectorAll(){return []},createElement:element},
  localStorage:{getItem(){return null}}, crypto:globalThis.crypto, Uint32Array,
  fetch:async()=>({json:async()=>({ai_configured:false})}), console,
});
vm.runInContext(fs.readFileSync('static/app.js','utf8'),context);
vm.runInContext(String.raw`
  const parsed = parseList('Commander\n1 Test Commander\nDeck\n1 Sol Ring (CMM) 396\n98 Forest\nSideboard\n1 Mountain');
  if (parsed.length !== 3 || parsed[1].name !== 'Sol Ring') throw new Error('Export parsing failed');
  deck = {name:'Test',commander:'Test Commander',cards:parsed};
  newHand();
  if(hand.length!==7 || library.length!==92 || hand.includes('Test Commander') || library.includes('Test Commander')) throw new Error('Commander exclusion failed');
  newHand(true);
  if(bottomNeeded!==0 || hand.length!==7) throw new Error('First mulligan must be free');
  newHand(true);
  if(bottomNeeded!==1) throw new Error('Second mulligan requires one bottom');
  document.querySelector('#hand').children[0].onclick();
  if(hand.length!==6 || library.length!==93 || bottomNeeded!==0) throw new Error('Bottom failed');
  document.querySelector('#draw').onclick();
  if(hand.length!==7 || library.length!==92) throw new Error('Draw failed');
`,context);
assert.throws(()=>vm.runInContext("parseList('Not a deck line')",context));
assert.throws(()=>vm.runInContext("parseList('0 Forest')",context));
console.log('Deck import, commander exclusion, mulligans, bottoming, and draws passed.');
context.window={location:{pathname:'/',search:''},addEventListener(){}};
context.URLSearchParams=URLSearchParams;
context.sessionStorage={getItem(){return null},setItem(){},removeItem(){}};
context.prompt=()=> 'Test token';
// Complete the small DOM stub for the new table's accessibility attributes.
for(const el of elements.values()) el.setAttribute=()=>{};
const originalCreate=context.document.createElement;
context.document.createElement=()=>({...originalCreate(),setAttribute(){}});
vm.runInContext(fs.readFileSync('static/table.js','utf8'),context);
vm.runInContext(`
  const totalCards=()=>library.length+hand.length+Object.values(zones).reduce((n,cards)=>n+cards.filter(c=>!c.token).length,0);
  const before=totalCards();
  selectGameCard('hand',0);moveSelected('battlefield');
  if(hand.length!==6||zones.battlefield.length!==1||totalCards()!==before)throw new Error('Play duplicated or lost a card');
  selectGameCard('battlefield',0);document.querySelector('#tap-card').onclick();
  if(!zones.battlefield[0].tapped)throw new Error('Tap failed');
  document.querySelector('#counter-plus').onclick();
  if(zones.battlefield[0].counters!==1)throw new Error('Counter failed');
  moveSelected('graveyard');
  if(zones.graveyard.length!==1||zones.battlefield.length!==0||totalCards()!==before)throw new Error('Graveyard move failed');
  document.querySelector('#undo-game').onclick();
  if(zones.battlefield.length!==1||zones.graveyard.length!==0)throw new Error('Undo failed');
  document.querySelector('#next-turn').onclick();
  if(turn!==2||zones.battlefield[0].tapped||hand.length!==7||totalCards()!==before)throw new Error('Turn advance failed');
  selectGameCard('command',0);moveSelected('battlefield');
  if(zones.command.length!==0||zones.battlefield.length!==2||totalCards()!==before)throw new Error('Commander move failed');
`,context);
console.log('Goldfish zones, card conservation, tap, counters, undo, turn advance, and commander checks passed.');
