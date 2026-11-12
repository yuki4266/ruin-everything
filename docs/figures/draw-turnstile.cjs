// Run with NODE_PATH pointing to roughjs and @xmldom/xmldom.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root=doc.documentElement;
let parent=root;
for (const [k,v] of Object.entries({width:720,height:1030,viewBox:'0 0 720 1030',role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag,attrs={},text){const n=doc.createElementNS(root.namespaceURI,tag);for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));parent.appendChild(n);return n;}
el('title',{id:'title'},'Turnstile continuation in the original tab');
el('desc',{id:'desc'},'Observe one visible widget, click once using measured geometry, and verify the site receipt separately from verification clearance.');
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;fill:#302b38;font-size:18px}.h{font-family:Kalam;font-size:27px}.s{font-size:16px}.hs{font-family:Kalam;font-size:23px}');
el('rect',{width:720,height:1030,fill:'#fffaf0'});
const r=rough.svg(root);let seed=710;
function box(x,y,w,h,fill){parent.appendChild(r.path(`M${x+12} ${y} H${x+w-12} Q${x+w} ${y} ${x+w} ${y+12} V${y+h-12} Q${x+w} ${y+h} ${x+w-12} ${y+h} H${x+12} Q${x} ${y+h} ${x} ${y+h-12} V${y+12} Q${x} ${y} ${x+12} ${y}Z`,{seed:seed++,roughness:.8,stroke:'#302b38',strokeWidth:1.5,fill,fillStyle:'solid'}));}
function text(x,y,t,cls=''){el('text',{x,y,class:cls},t);}
function arrow(x,y,x2,y2){parent.appendChild(r.line(x,y,x2,y2,{seed:seed++,stroke:'#302b38',roughness:.6}));parent.appendChild(r.linearPath([[x2-7,y2-5],[x2,y2],[x2-7,y2+5]],{seed:seed++,stroke:'#302b38',roughness:.5}));}
text(24,38,'A / One driver for tasks and vault','h');
box(24,64,220,110,'#e8dcfa');text(40,96,'Engine setting','hs');text(40,125,'Environment or file','s');text(40,152,'Restart loaded clients','s');
arrow(250,94,304,86);arrow(250,145,304,150);
box(310,60,386,52,'#e8dcfa');text(328,93,'Task connection + error handling','s');
box(310,126,386,52,'#f8deea');text(328,159,'Matching persistent vault driver','s');
parent=el('g',{transform:'translate(0,180)'});
text(24,38,'B / Continue the original action','h');
box(24,64,200,110,'#e8dcfa');text(40,96,'Original tab','hs');text(40,125,'Exact URL + lock','s');text(40,152,'Do not repeat Submit','s');
arrow(230,118,254,118);
box(260,64,200,110,'#fbe6b2');text(276,96,'Observe widget','hs');text(276,125,'Closed-root iframe','s');text(276,152,'or local image check','s');
arrow(466,118,490,118);
box(496,64,200,110,'#d9f1e5');text(512,96,'One gesture','hs');text(512,125,'Trusted CDP input','s');text(512,152,'Then watch result','s');
text(24,221,'C / Measure before clicking','h');
box(24,245,672,248,'#e8dcfa');
box(70,273,360,78,'#fffaf0');box(89,297,24,24,'#fffaf0');text(130,318,'Verify you are human','s');
text(456,303,'Outer box','hs');text(456,333,'CSS coordinates','s');
text(42,391,'Target: left + 28, vertical center; bounded jitter','s');
text(42,422,'5–8 moves → 120 ms → press → 80 ms → release','s');
text(42,453,'Moved box, overlay or uncertain layout → leave pending','s');
text(42,480,'Native screen coordinates; no hard-coded toolbar height','s');
text(24,537,'D / Clearance is not an application receipt','h');
box(24,561,325,200,'#d9f1e5');text(42,594,'Verification evidence','hs');text(42,625,'One-time response token','s');text(42,653,'or newly issued clearance','s');text(42,685,'Cookie, when issued:','s');text(42,713,'private · same profile · expiry','s');text(42,742,'No token values in tool output','s');
box(371,561,325,200,'#fff0d9');text(389,594,'Employer response','hs');text(389,625,'Check official receipt','s');text(389,653,'before marking submitted','s');text(389,685,'Failed or uncertain?','s');text(389,713,'Preserve form + status','s');text(389,742,'No success promise','s');
text(24,810,'Same Chrome profile and sessions; website decisions still apply.','s');
fs.writeFileSync('docs/figures/turnstile.svg',new XMLSerializer().serializeToString(doc));
