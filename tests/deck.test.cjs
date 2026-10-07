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
