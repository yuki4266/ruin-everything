// Run with NODE_PATH pointing to roughjs and @xmldom/xmldom.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root=doc.documentElement;
for (const [k,v] of Object.entries({width:720,height:670,viewBox:'0 0 720 670',role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag,attrs={},text){const n=doc.createElementNS(root.namespaceURI,tag);for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));root.appendChild(n);return n;}
el('title',{id:'title'},'One local browser for every website');
el('desc',{id:'desc'},'An agent uses Ruin and Python Playwright to navigate shared Chrome. Marked agent tabs are reused in the background; subsequent actions use the returned current URL. Existing sessions and unrelated tabs remain.');
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;fill:#302b38;font-size:18px}.h{font-family:Kalam;font-size:27px}.s{font-size:16px}');
el('rect',{width:720,height:670,fill:'#fffaf0'});
const r=rough.svg(root);let seed=710;
function box(x,y,w,h,fill){root.appendChild(r.path(`M${x+12} ${y} H${x+w-12} Q${x+w} ${y} ${x+w} ${y+12} V${y+h-12} Q${x+w} ${y+h} ${x+w-12} ${y+h} H${x+12} Q${x} ${y+h} ${x} ${y+h-12} V${y+12} Q${x} ${y} ${x+12} ${y}Z`,{seed:seed++,roughness:.8,stroke:'#302b38',strokeWidth:1.5,fill,fillStyle:'solid'}));}
function text(x,y,t,cls=''){el('text',{x,y,class:cls},t);}
function arrow(x,y,x2,y2){root.appendChild(r.line(x,y,x2,y2,{seed:seed++,stroke:'#302b38',roughness:.6}));root.appendChild(r.linearPath([[x2-7,y2-5],[x2,y2],[x2-7,y2+5]],{seed:seed++,stroke:'#302b38',roughness:.5}));}
text(24,38,'A / Any website, one local runtime','h');
box(24,66,155,110,'#fff0d9');text(40,97,'Browser agent');text(40,127,'Target URL');text(40,154,'Task + controls','s');
arrow(183,120,228,120);text(188,105,'call','s');
box(233,66,205,110,'#e8dcfa');text(248,97,'ruin_browser');text(248,127,'Python Playwright');text(248,154,'CDP :9222','s');
arrow(443,120,488,120);text(445,105,'act','s');
box(493,66,203,110,'#e8dcfa');text(508,97,'Local Chrome');text(508,127,'Existing session');text(508,154,'Cookies + extensions','s');
text(24,220,'B / Start from what is already open','h');
box(24,241,672,99,'#fbe6b2');text(42,272,'Exact destination tab exists → reuse that tab');text(42,300,'Otherwise: unchanged agent tab → reuse it');text(42,325,'Otherwise: create a background tab; preserve user tabs','s');
text(24,382,'C / Observe, then continue','h');
box(24,401,307,124,'#e8dcfa');text(42,435,'Current website');text(42,465,'Navigate · click · fill');text(42,493,'Read · press · select');
arrow(336,466,382,466);text(337,449,'state','s');
box(387,401,309,124,'#d9f1e5');text(405,435,'Returned observation');text(405,465,'Current URL + visible text');text(405,493,'Controls without input values','s');
text(24,560,'After a redirect, use the returned URL for the next call.','s');
text(24,590,'Clicks and Enter run through the existing Ruin executor.','s');
text(24,637,'Site adapters are helpers; they do not define the browser’s scope.','s');
fs.writeFileSync('docs/figures/universal-browser.svg',new XMLSerializer().serializeToString(doc));
