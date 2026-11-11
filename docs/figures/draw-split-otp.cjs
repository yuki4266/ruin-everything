// Run from the repository root with roughjs and @xmldom/xmldom on NODE_PATH.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const ns = 'http://www.w3.org/2000/svg';
const doc = new DOMImplementation().createDocument(ns, 'svg');
const root = doc.documentElement;
for (const [k,v] of Object.entries({viewBox:'0 0 660 556',width:660,height:556,role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag, attrs, value) {
  const node = doc.createElementNS(ns, tag);
  for (const [key, val] of Object.entries(attrs)) node.setAttribute(key, val);
  if (value) node.appendChild(doc.createTextNode(value));
  root.appendChild(node);
}
el('title',{id:'title'},'A code split across six cells');
el('desc',{id:'desc'},'A fresh, matching SMS or supported email supplies the code. The original form receives a paste or individual characters. Entry is checked against the joined cells.');
const font = fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;font-size:22px;fill:#302b38}.title{font-family:Kalam;font-size:36px}.head{font-family:Kalam;font-size:30px}.small{font-size:21px}');
el('rect',{width:660,height:556,fill:'#fffaf0'});
const pen=rough.svg(root);
let seed=1600;
function path(d, fill='none') {
  root.appendChild(pen.path(d,{seed:seed++,stroke:'#302b38',strokeWidth:1.7,roughness:.7,fill,fillStyle:'solid'}));
}
function label(x,y,value,cls='') {el('text',{x,y,class:cls},value);}
label(28,50,'Entering a code across six cells','title');
path('M33 86Q30 70 50 70H615Q632 70 631 88V178Q631 193 615 193H51Q32 193 32 175Z','#f8dfe9');
path('M51 108H141V164H51ZM52 109L96 141L140 109','#fffaf0');
label(166,110,'A / Match the request','head');
label(166,147,'Read a fresh SMS or supported email.');
label(166,174,'Check the site or sender.','small');
path('M94 198V238M83 226L94 239L105 226');
label(122,226,'Code for the original tab','small');
path('M33 269Q32 251 49 251H617Q631 251 631 270V506Q631 523 614 523H50Q32 523 32 504Z','#e9ddfa');
label(55,295,'B / Fill the verification form','head');
label(56,332,'Focus the first cell and paste the code.');
for (let i=0;i<6;i++) {
  const x=62+i*91;
  path(`M${x+7} 353H${x+62}Q${x+69} 353 ${x+69} 361V405Q${x+69} 413 ${x+61} 413H${x+8}Q${x} 413 ${x} 405V361Q${x} 353 ${x+7} 353Z`,'#fffaf0');
  el('circle',{cx:x+34,cy:383,r:6,fill:'#675085'});
}
label(55,459,'If the paste is incomplete, fill each differing cell.');
label(55,495,'Read the cells together to check the code.');
fs.writeFileSync('docs/figures/split-otp.svg',new XMLSerializer().serializeToString(doc));
