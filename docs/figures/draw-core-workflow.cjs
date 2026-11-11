// Run from the repository root with NODE_PATH containing roughjs and @xmldom/xmldom.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root = doc.documentElement;
for (const [k,v] of Object.entries({width:720,height:890,viewBox:'0 0 720 890',role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag,attrs={},text){const n=doc.createElementNS(root.namespaceURI,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));root.appendChild(n);return n;}
el('title',{id:'title'},'Your agent. Your Chrome. Keep going.');
el('desc',{id:'desc'},'A: the agent sends a task through MCP to Ruin and shared Chrome. B: local login reuse and supported verification continue the original task. C: the site supplies confirmation; Ashby receipts can be saved. Pending verification stays pending.');
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;fill:#302b38;font-size:24px}.h{font-family:Kalam;font-size:31px}.title{font-family:Kalam;font-size:39px}.small{font-size:21px}');
el('rect',{width:720,height:890,fill:'#fffaf0'});
const r=rough.svg(root);let seed=1420;
function path(d,fill='none'){root.appendChild(r.path(d,{seed:seed++,roughness:.8,stroke:'#302b38',strokeWidth:1.8,fill,fillStyle:'solid'}));}
function box(x,y,w,h,fill){path(`M${x+16} ${y}H${x+w-16}Q${x+w} ${y} ${x+w} ${y+16}V${y+h-16}Q${x+w} ${y+h} ${x+w-16} ${y+h}H${x+16}Q${x} ${y+h} ${x} ${y+h-16}V${y+16}Q${x} ${y} ${x+16} ${y}Z`,fill);}
function text(x,y,t,cls=''){el('text',{x,y,class:cls},t);}
function line(x,y,x2,y2){root.appendChild(r.line(x,y,x2,y2,{seed:seed++,roughness:.6,stroke:'#302b38',strokeWidth:1.8}));}
function down(y,label){line(84,y,84,y+42);path(`M75 ${y+31}L84 ${y+42}L93 ${y+31}`);text(110,y+28,label,'small');}
text(30,53,'Your agent. Your Chrome. Keep going.','title');
text(30,88,'A local runtime for the work between clicks.','small');
box(26,117,668,190,'#e8dcfa');
box(47,163,125,96,'#fffaf0');line(49,186,170,186);
for(let i=0;i<3;i++)el('circle',{cx:59+i*12,cy:176,r:3,fill:'#7352a4'});
path('M73 213 L87 226 L111 201');line(72,241,145,241);
text(197,160,'A / Put your agent to work','h');
text(197,201,'Agent → MCP → Ruin → Chrome','small');
text(197,242,'Browse, click, fill and read.');
text(197,278,'Background tabs. Your app stays put.','small');
down(317,'Task reaches login or verification');
box(26,371,668,210,'#fce2e8');
root.appendChild(r.circle(80,425,39,{seed:seed++,stroke:'#302b38',strokeWidth:2,fill:'#ffe5ad',fillStyle:'solid'}));
path('M98 425H154V438H143V447H131V425');
box(48,475,121,70,'#fffaf0');path('M51 480L108 517L167 480');
text(197,416,'B / Get past the interruptions','h');
text(197,458,'Reuse a matching local login.');
text(197,497,'Handle supported codes and puzzles.','small');
text(197,541,'Continue in the original task tab.','small');
down(591,'Site returns a visible result');
box(26,645,668,213,'#d9f1e5');
path('M55 680H158V822L145 812L132 822L119 812L106 822L93 812L80 822L67 812L55 822Z','#fffaf0');
path('M77 711L91 726L128 691');line(73,755,140,755);line(73,776,128,776);
text(197,691,'C / Bring back the evidence','h');
text(197,734,'Read the site’s confirmation.');
text(197,774,'Save Ashby receipts for later.');
text(197,819,'Still pending? Report it as pending.','small');
fs.writeFileSync('docs/figures/core-workflow.svg',new XMLSerializer().serializeToString(doc));
