// Run with NODE_PATH pointing to roughjs and @xmldom/xmldom.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root=doc.documentElement;
for (const [k,v] of Object.entries({width:720,height:920,viewBox:'0 0 720 920',role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag,attrs={},text){const n=doc.createElementNS(root.namespaceURI,tag);for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));root.appendChild(n);return n;}
el('title',{id:'title'},'A rejected ATS login has a bounded recovery path');
el('desc',{id:'desc'},'A local private password feeds selected iCIMS and Workday forms. Explicit login errors lead to registration, one configured-password attempt and email recovery. Only the site can confirm completion.');
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;fill:#302b38;font-size:18px}.h{font-family:Kalam;font-size:27px}.s{font-size:16px}');
el('rect',{width:720,height:920,fill:'#fffaf0'});
const r=rough.svg(root);let seed=710;
function box(x,y,w,h,fill){root.appendChild(r.path(`M${x+12} ${y} H${x+w-12} Q${x+w} ${y} ${x+w} ${y+12} V${y+h-12} Q${x+w} ${y+h} ${x+w-12} ${y+h} H${x+12} Q${x} ${y+h} ${x} ${y+h-12} V${y+12} Q${x} ${y} ${x+12} ${y}Z`,{seed:seed++,roughness:.8,stroke:'#302b38',strokeWidth:1.5,fill,fillStyle:'solid'}));}
function text(x,y,t,cls=''){el('text',{x,y,class:cls},t);}
function arrow(x,y,x2,y2){root.appendChild(r.line(x,y,x2,y2,{seed:seed++,stroke:'#302b38',roughness:.6}));root.appendChild(r.linearPath([[x2-(x2>=x?7:-7),y2-5],[x2,y2],[x2-(x2>=x?7:-7),y2+5]],{seed:seed++,stroke:'#302b38',roughness:.5}));}
text(24,38,'A / One private local setting','h');
box(24,62,305,118,'#fff0d9');text(42,94,'~/.ruin/.env','h');text(42,126,'ATS_DEFAULT_PASSWORD','s');text(42,155,'Generated once · mode 0600','s');
arrow(336,121,381,121);text(337,103,'read','s');
box(388,62,308,118,'#e8dcfa');text(406,94,'Selected ATS tenant','h');text(406,126,'iCIMS / Workday','s');text(406,155,'Original Chrome tab','s');
text(24,225,'B / Follow the observed form','h');
box(24,250,305,96,'#d9f1e5');text(42,282,'New-password form','h');text(42,314,'Fill local secret + submit','s');
box(388,250,308,96,'#fbe6b2');text(406,282,'Credential rejected','h');text(406,314,'Visible Create Account?','s');
arrow(388,300,329,300);text(339,283,'Yes','s');
box(388,395,308,104,'#e8dcfa');text(406,427,'No / account exists','h');text(406,460,'Try configured password once','s');text(406,485,'Keep the same tenant','s');
text(24,432,'Current-password form:','s');text(24,462,'reuse saved input first','s');text(24,490,'unless already rejected.','s');
box(24,534,672,75,'#fbe6b2');text(42,565,'Still rejected → visible Forgot / Reset Password','h');text(42,592,'Repeat limits survive reconnects for 15 minutes.','s');
text(24,659,'C / A request is not a receipt','h');
box(24,684,305,101,'#f7dce9');text(42,717,'Email request','h');text(42,747,'Await provider verification','s');text(42,773,'Delivery is not guaranteed','s');
box(388,684,308,101,'#d9f1e5');text(406,717,'Password setup visible','h');text(406,747,'Use the local ATS password','s');text(406,773,'Resume the application','s');
box(24,821,672,67,'#fff0d9');text(42,849,'No secrets in tool arguments, logs or repository.');text(42,875,'Application success still requires the employer’s receipt.','s');
fs.writeFileSync('docs/figures/ats-recovery.svg',new XMLSerializer().serializeToString(doc));
