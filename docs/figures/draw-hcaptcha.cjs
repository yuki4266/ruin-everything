// Run with NODE_PATH pointing to roughjs and @xmldom/xmldom.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root=doc.documentElement;
for (const [k,v] of Object.entries({width:720,height:920,viewBox:'0 0 720 920',role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag,attrs={},text){const n=doc.createElementNS(root.namespaceURI,tag);for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));root.appendChild(n);return n;}
el('title',{id:'title'},'Nested hCaptcha: choose the task, map the input');
el('desc',{id:'desc'},'A nested browser cutaway shows task classification, content-origin coordinates and the boundary between challenge continuation and an application receipt.');
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;fill:#302b38;font-size:18px}.h{font-family:Kalam;font-size:27px}.s{font-size:16px}');
el('rect',{width:720,height:920,fill:'#fffaf0'});
const r=rough.svg(root);let seed=710;
function box(x,y,w,h,fill){root.appendChild(r.path(`M${x+12} ${y} H${x+w-12} Q${x+w} ${y} ${x+w} ${y+12} V${y+h-12} Q${x+w} ${y+h} ${x+w-12} ${y+h} H${x+12} Q${x} ${y+h} ${x} ${y+h-12} V${y+12} Q${x} ${y} ${x+12} ${y}Z`,{seed:seed++,roughness:.8,stroke:'#302b38',strokeWidth:1.5,fill,fillStyle:'solid'}));}
function text(x,y,t,cls=''){el('text',{x,y,class:cls},t);}
function arrow(x,y,x2,y2){root.appendChild(r.line(x,y,x2,y2,{seed:seed++,stroke:'#302b38',roughness:.6}));root.appendChild(r.linearPath([[x2-7,y2-5],[x2,y2],[x2-7,y2+5]],{seed:seed++,stroke:'#302b38',roughness:.5}));}
text(24,38,'A / Read the visible challenge first','h');
box(24,62,672,310,'#e8dcfa');text(42,91,'Original application tab');
box(48,109,304,235,'#fffaf0');text(65,139,'iCIMS content iframe','h');
box(70,158,260,160,'#e8dcfa');text(86,191,'hCaptcha iframe','h');text(86,224,'Cross-origin document','s');text(86,254,'Hidden ancestor? Ignore.','s');text(86,284,'Challenge before checkbox','s');
text(378,138,'Inspect provider markup','h');
text(378,177,'Grid → indexed tiles 0…8','s');text(378,214,'Canvas → points or 2D drag','s');text(378,251,'Checkbox → control center','s');text(378,302,'Unknown → pending','h');
text(24,420,'B / Map every content origin','h');
box(24,445,672,185,'#fbe6b2');
text(42,478,'Start with element bounds in its own frame');
text(42,515,'For each parent: position + border + padding');
text(42,548,'Then add the scaled child coordinate');
text(42,587,'Viewport-relative bounds include scrolling','s');
text(42,612,'Two nested borders (7 + 5 px) must not disappear.','s');
text(24,678,'C / Input, continuation, evidence','h');
box(24,702,305,90,'#e8dcfa');text(42,734,'Ruin executor','h');text(42,766,'Mouse events + widget Verify','s');
arrow(336,746,381,746);text(339,730,'input','s');
box(388,702,308,90,'#d9f1e5');text(406,734,'Watch the original tab','h');text(406,766,'Retry only the widget','s');
box(24,820,672,68,'#fff0d9');text(42,849,'Challenge cleared / redirected ≠ application submitted');text(42,875,'Only the site’s application receipt confirms submission.','s');
fs.writeFileSync('docs/figures/hcaptcha.svg',new XMLSerializer().serializeToString(doc));
