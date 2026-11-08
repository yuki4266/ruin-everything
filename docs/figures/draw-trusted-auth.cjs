// Run with NODE_PATH pointing to installed roughjs and @xmldom/xmldom packages.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root = doc.documentElement;
root.setAttribute('width','720');root.setAttribute('height','500');root.setAttribute('viewBox','0 0 720 500');
root.setAttribute('role','img');root.setAttribute('aria-labelledby','title desc');
function el(tag,attrs,text){let n=doc.createElementNS(root.namespaceURI,tag);for(let [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));root.appendChild(n);return n;}
el('title',{id:'title'},'Trusted login: one selected task');
el('desc',{id:'desc'},'A local configuration matches exact login actions. A separate opt-in sends Chrome password keys once, without guaranteeing a suggestion.');
const old=fs.readFileSync('docs/figures/autofill.svg','utf8');
const font=old.match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{fill:#302b38;font-family:Arial,sans-serif;font-size:17px}.heading{font-family:Kalam;font-size:25px}.small{font-size:15px}');
el('rect',{width:720,height:500,fill:'#fffaf0'});
const r=rough.svg(root);let seed=410;
function box(x,y,w,h,color){
 const options={seed:seed++,roughness:0.8,stroke:'#302b38',strokeWidth:1.5,fill:color,fillStyle:'solid'};
 if(color==='#fbe6b2') root.appendChild(r.polygon([[x,y],[x+w-15,y],[x+w,y+15],[x+w,y+h],[x,y+h]],options));
 else root.appendChild(r.path(`M${x+10} ${y} H${x+w-10} Q${x+w} ${y} ${x+w} ${y+10} V${y+h-10} Q${x+w} ${y+h} ${x+w-10} ${y+h} H${x+10} Q${x} ${y+h} ${x} ${y+h-10} V${y+10} Q${x} ${y} ${x+10} ${y} Z`,options));
}
function line(x,y,a,b){root.appendChild(r.line(x,y,a,b,{seed:seed++,roughness:0.5,stroke:'#302b38'}));root.appendChild(r.line(a-7,b-4,a,b,{seed:seed++,roughness:0.5}));root.appendChild(r.line(a-7,b+4,a,b,{seed:seed++,roughness:0.5}));}
function text(x,y,t,cls){el('text',{x,y,...(cls?{class:cls}:{})},t);}
text(24,34,'A / Only the selected task', 'heading');
box(24,55,190,92,'#e8dcfa');text(38,83,'--autofill task');text(38,108,'Exact HTTPS origin');text(38,132,'Original tab only','small');
line(216,101,253,101);el('text',{x:219,y:88,style:'font-size:12px'},'read');
box(256,55,205,92,'#fbe6b2');text(270,83,'trusted-auth.json');text(270,108,'Path + button name');text(270,132,'No wildcard tenants','small');
line(463,101,500,101);el('text',{x:463,y:88,style:'font-size:12px'},'match');
box(503,55,193,92,'#d9f1e5');text(517,83,'One visible button');text(517,108,'Click once per rule');text(517,132,'Keep control labels','small');
box(24,171,672,106,'#fff1cf');text(40,198,'B / GitHub OAuth: match the application', 'heading');text(40,226,'Client ID + exact callback + exact requested scopes');text(40,253,'Missing or changed? No configured click; keep the tab open.');
text(24,315,'C / Chrome password dropdown (explicit opt-in)', 'heading');
box(24,335,305,92,'#e8dcfa');text(40,362,'Same-origin, empty login field');text(40,388,'No keyring password');text(40,412,'Exclude new-password forms','small');
line(332,382,376,382);el('text',{x:339,y:368,style:'font-size:12px'},'keys');
box(379,335,317,92,'#d9f1e5');text(395,362,'Focus → ArrowDown → Enter');text(395,388,'One attempt in this task');text(395,412,'Existing values stay untouched','small');
text(24,461,'Chrome owns the popup. Enter may submit if no suggestion appears.','small');
text(24,484,'No background watcher. No promise of permanent sign-in.','small');
fs.writeFileSync('docs/figures/trusted-auth.svg',new XMLSerializer().serializeToString(doc));
