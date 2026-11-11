// Run with NODE_PATH pointing to roughjs and @xmldom/xmldom.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root=doc.documentElement;
for (const [k,v] of Object.entries({width:720,height:338,viewBox:'0 0 720 338',role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag,attrs={},text){const n=doc.createElementNS(root.namespaceURI,tag);for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));root.appendChild(n);return n;}
el('title',{id:'title'},'Attach a local file');
el('desc',{id:'desc'},'One local file goes to a unique control across the tab and its frames. File inputs select the file, and drop areas receive a drag and drop. The site confirms the attachment.');
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;fill:#302b38;font-size:18px}.h{font-family:Kalam;font-size:27px}.s{font-size:16px}');
el('rect',{width:720,height:338,fill:'#fffaf0'});
const r=rough.svg(root);let seed=710;
function box(x,y,w,h,fill){root.appendChild(r.path(`M${x+12} ${y} H${x+w-12} Q${x+w} ${y} ${x+w} ${y+12} V${y+h-12} Q${x+w} ${y+h} ${x+w-12} ${y+h} H${x+12} Q${x} ${y+h} ${x} ${y+h-12} V${y+12} Q${x} ${y} ${x+12} ${y}Z`,{seed:seed++,roughness:.8,stroke:'#302b38',strokeWidth:1.5,fill,fillStyle:'solid'}));}
function text(x,y,t,cls=''){el('text',{x,y,class:cls},t);}
function arrow(x,y,x2,y2){root.appendChild(r.line(x,y,x2,y2,{seed:seed++,stroke:'#302b38',roughness:.6}));root.appendChild(r.linearPath([[x2-7,y2-5],[x2,y2],[x2-7,y2+5]],{seed:seed++,stroke:'#302b38',roughness:.5}));}

text(24,39,'A / Locate the attachment field','h');
root.appendChild(r.path('M34 69 L107 69 L130 92 L130 151 L34 151 Z M107 69 V92 H130',{seed:560,fill:'#fff0d9',fillStyle:'solid',stroke:'#302b38'}));
text(47,122,'Local file');
arrow(141,113,226,113);text(151,96,'path','s');
box(233,65,457,93,'#e8dcfa');text(252,97,'Current tab and nested frames');
text(252,128,'One file input, or an explicit selector','s');
text(24,203,'B / Deliver the file','h');
box(24,219,322,74,'#e8dcfa');text(41,248,'File input (visible or hidden)');text(41,277,'Select file → input and change','s');
box(370,219,320,74,'#fbe6b2');text(387,248,'Drop area');text(387,277,'Drag over → drop if accepted','s');
text(26,325,'Check the attachment name on the site before submitting.','s');
fs.writeFileSync('docs/figures/upload.svg',new XMLSerializer().serializeToString(doc));
