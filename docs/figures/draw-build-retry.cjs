// Run from the repository root with NODE_PATH containing roughjs and @xmldom/xmldom.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root = doc.documentElement;
for (const [k,v] of Object.entries({width:720,height:1010,viewBox:'0 0 720 1010',role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag,attrs={},text){const n=doc.createElementNS(root.namespaceURI,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));root.appendChild(n);return n;}
el('title',{id:'title'},'A failed install gets a bounded retry.');
el('desc',{id:'desc'},'A: install Chromium and system dependencies. B: retry failures up to three attempts, waiting 15 then 30 seconds; persistent failure stops the build. C: successful installation proceeds to tests and distribution checks before PyPI publishing.');
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;fill:#302b38;font-size:24px}.h{font-family:Kalam;font-size:31px}.title{font-family:Kalam;font-size:39px}.small{font-size:21px}');
el('rect',{width:720,height:1010,fill:'#fffaf0'});
const r=rough.svg(root);let seed=1420;
function path(d,fill='none'){root.appendChild(r.path(d,{seed:seed++,roughness:.8,stroke:'#302b38',strokeWidth:1.8,fill,fillStyle:'solid'}));}
function box(x,y,w,h,fill){path(`M${x+16} ${y}H${x+w-16}Q${x+w} ${y} ${x+w} ${y+16}V${y+h-16}Q${x+w} ${y+h} ${x+w-16} ${y+h}H${x+16}Q${x} ${y+h} ${x} ${y+h-16}V${y+16}Q${x} ${y} ${x+16} ${y}Z`,fill);}
function text(x,y,t,cls=''){el('text',{x,y,class:cls},t);}
function line(x,y,x2,y2){root.appendChild(r.line(x,y,x2,y2,{seed:seed++,roughness:.6,stroke:'#302b38',strokeWidth:1.8}));}
function down(y,label){line(84,y,84,y+42);path(`M75 ${y+31}L84 ${y+42}L93 ${y+31}`);text(110,y+28,label,'small');}

text(30,53,'A failed install gets a bounded retry.','title');
text(30,88,'GitHub Actions / browser setup → checked package','small');
box(26,117,668,180,'#e8dcfa');
box(47,168,125,91,'#fffaf0');line(49,191,170,191);
for(let i=0;i<3;i++)el('circle',{cx:59+i*12,cy:181,r:3,fill:'#7352a4'});
path('M85 213L73 225L85 237M125 213L137 225L125 237');
text(197,160,'A / Install browser dependencies','h');
text(197,204,'Playwright installs Chromium');
text(197,240,'and its system libraries.');
text(197,277,'The step has a 30-minute timeout.','small');
down(307,'Installer result');
box(26,361,668,250,'#ffe5ad');
path('M108 394L163 449L108 504L53 449Z','#fffaf0');
text(97,460,'?','h');
text(197,405,'B / Check the outcome','h');
text(197,449,'Failed? Wait 15s, then retry.');
text(197,488,'Failed again? Wait 30s, retry.');
text(197,527,'Three attempts maximum.');
box(49,552,621,40,'#fffaf0');
text(67,579,'Still failing / timed out → stop; no publish','small');
down(621,'Install succeeded → run checks');
box(26,675,668,300,'#d9f1e5');
path('M55 718H158V886L145 876L132 886L119 876L106 886L93 876L80 886L67 876L55 886Z','#fffaf0');
path('M77 749L91 764L128 729');line(73,793,140,793);line(73,814,128,814);
text(197,720,'C / Check before publishing','h');
text(197,763,'Regression tests → build → Twine','small');
text(197,803,'All pass → upload distributions','small');
text(197,843,'Successful build → PyPI publish','small');
text(49,928,'Failed builds leave existing PyPI files unchanged.','small');
fs.writeFileSync('docs/figures/build-retry.svg',new XMLSerializer().serializeToString(doc));
