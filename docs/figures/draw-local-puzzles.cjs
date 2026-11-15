// Run with NODE_PATH pointing to roughjs and @xmldom/xmldom.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root=doc.documentElement;
for (const [k,v] of Object.entries({width:720,height:610,viewBox:'0 0 720 610',role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag,attrs={},text){const n=doc.createElementNS(root.namespaceURI,tag);for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));root.appendChild(n);return n;}
el('title',{id:'title'},'Local pixels to measured movement');
el('desc',{id:'desc'},'Separate gap and polar seam matching paths produce measured movement. Ambiguous images remain pending; a site SMS countdown confirms the request.');
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;fill:#302b38;font-size:18px}.h{font-family:Kalam;font-size:27px}.s{font-size:16px}');
el('rect',{width:720,height:610,fill:'#fffaf0'});
const r=rough.svg(root);let seed=710;
function box(x,y,w,h,fill){root.appendChild(r.path(`M${x+12} ${y} H${x+w-12} Q${x+w} ${y} ${x+w} ${y+12} V${y+h-12} Q${x+w} ${y+h} ${x+w-12} ${y+h} H${x+12} Q${x} ${y+h} ${x} ${y+h-12} V${y+12} Q${x} ${y} ${x+12} ${y}Z`,{seed:seed++,roughness:.8,stroke:'#302b38',strokeWidth:1.5,fill,fillStyle:'solid'}));}
function text(x,y,t,cls=''){el('text',{x,y,class:cls},t);}
function arrow(x,y,x2,y2){root.appendChild(r.line(x,y,x2,y2,{seed:seed++,stroke:'#302b38',roughness:.6}));root.appendChild(r.linearPath([[x2-7,y2-5],[x2,y2],[x2-7,y2+5]],{seed:seed++,stroke:'#302b38',roughness:.5}));}

text(24,38,'A / Solve from local pixels','h');
box(24,61,315,145,'#e8dcfa');
text(42,91,'Horizontal gap','h');
root.appendChild(r.path('M46 114 H72 V106 H84 V114 H102 V145 H46 Z',{seed:19,stroke:'#302b38',fill:'#bde7d8',fillStyle:'solid'}));
arrow(111,131,147,131);text(159,127,'ddddocr + Canny','s');text(159,151,'Match the outline','s');
text(42,184,'Native X → CSS scale → rail','s');
box(363,61,333,145,'#e8dcfa');
text(380,91,'Circular seam','h');
root.appendChild(r.circle(410,133,56,{seed:12,stroke:'#302b38',fill:'#bde7d8',fillStyle:'solid'}));
root.appendChild(r.circle(410,133,29,{seed:15,stroke:'#302b38',fill:'#fffaf0',fillStyle:'solid'}));
text(453,128,'RGB + gradient','s');text(453,152,'Compare 360 shifts','s');
text(380,184,'Probe degrees / px → drag ratio','s');
text(24,245,'B / Move, hold, then release','h');
box(24,266,672,118,'#fbe6b2');
root.appendChild(r.linearPath([[44,350],[64,320],[92,304],[140,295],[208,292],[298,291]],{seed:22,stroke:'#7151a6',strokeWidth:3}));
text(44,281,'Position over time','s');
text(333,296,'15–25 moves; ease-out','s');text(333,326,'Y jitter up to ±1.5 CSS px','s');text(333,356,'Hold 150–250 ms → mouse up','s');
text(24,427,'C / Confirm the site result','h');
box(24,448,313,101,'#bde7d8');text(42,478,'SMS countdown appears','s');text(42,508,'Observed live on Feishu','s');text(42,534,'Login is a separate step','s');
box(363,448,333,101,'#fbe6b2');text(381,478,'Ambiguous or no reference?','s');text(381,508,'Keep the challenge pending','s');text(381,534,'No model distance guesses','s');
text(26,587,'Provider detection runs before generic piece detection.','s');
fs.writeFileSync('docs/figures/local-puzzles.svg',new XMLSerializer().serializeToString(doc));
