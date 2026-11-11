// Run with NODE_PATH pointing to roughjs and @xmldom/xmldom.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root=doc.documentElement;
for (const [k,v] of Object.entries({width:720,height:900,viewBox:'0 0 720 900',role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag,attrs={},text){const n=doc.createElementNS(root.namespaceURI,tag);for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));root.appendChild(n);return n;}
el('title',{id:'title'},'One manual login, a local vault');
el('desc',{id:'desc'},'A manual login reaches a private local vault through CDP. Exact-host lookup submits through the Ruin executor. Cookie and Web Storage snapshots survive a browser restart.');
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;fill:#302b38;font-size:18px}.h{font-family:Kalam;font-size:27px}.s{font-size:16px}.hs{font-family:Kalam;font-size:23px}');
el('rect',{width:720,height:900,fill:'#fffaf0'});
const r=rough.svg(root);let seed=710;
function box(x,y,w,h,fill){root.appendChild(r.path(`M${x+12} ${y} H${x+w-12} Q${x+w} ${y} ${x+w} ${y+12} V${y+h-12} Q${x+w} ${y+h} ${x+w-12} ${y+h} H${x+12} Q${x} ${y+h} ${x} ${y+h-12} V${y+12} Q${x} ${y} ${x+12} ${y}Z`,{seed:seed++,roughness:.8,stroke:'#302b38',strokeWidth:1.5,fill,fillStyle:'solid'}));}
function text(x,y,t,cls=''){el('text',{x,y,class:cls},t);}
function arrow(x,y,x2,y2){root.appendChild(r.line(x,y,x2,y2,{seed:seed++,stroke:'#302b38',roughness:.6}));root.appendChild(r.linearPath([[x2-7,y2-5],[x2,y2],[x2-7,y2+5]],{seed:seed++,stroke:'#302b38',roughness:.5}));}
text(24,38,'A / Capture the submit, keep it local','h');
box(24,62,300,138,'#e8dcfa');text(42,94,'Page + nested iframe','hs');text(42,124,'Submit · Enter · login click','s');text(42,152,'Non-empty password','s');text(42,180,'Frame hostname from CDP','s');
arrow(330,132,386,132);text(337,115,'local','s');
box(394,62,302,138,'#d9f1e5');text(412,94,'auth_vault.json','hs');text(412,124,'Detached singleton listener','s');text(412,152,'Atomic write · mode 0600','s');text(412,180,'Still running after CLI exit','s');
text(24,243,'B / The next selected Ruin task','h');
root.appendChild(r.polygon([[24,271],[310,271],[330,299],[310,370],[24,370]],{seed:seed++,stroke:'#302b38',fill:'#fbe6b2',fillStyle:'solid',roughness:.8}));
text(42,301,'Exact host first','hs');text(42,329,'Then saved root-domain record','s');text(42,355,'Never search sibling tenants','s');
arrow(336,319,386,319);text(337,302,'match','s');
box(394,271,302,99,'#e8dcfa');text(412,301,'Fill → Ruin executor','hs');text(412,329,'One visible login control','s');text(412,355,'Bounded credential retry','s');
box(24,391,672,71,'#fff0d9');text(42,420,'No credential? The active task waits for manual login.','s');text(42,447,'After the form clears, continue the original task.','s');
text(24,508,'C / Restore the next Chrome session','h');
box(24,532,300,132,'#d9f1e5');text(42,563,'cookies_snapshot.json','hs');text(42,591,'CDP cookies + Web Storage','s');text(42,618,'Navigation + five-second cycle','s');text(42,645,'Separate sessionStorage by tab','s');
arrow(330,594,386,594);text(336,577,'restart','s');
box(394,532,302,132,'#e8dcfa');text(412,563,'Same Chrome profile','hs');text(412,591,'Restore missing valid cookies','s');text(412,618,'Restore empty storage','s');text(412,645,'Keep current browser values','s');
box(24,695,672,119,'#fbe6b2');text(42,728,'Boundaries','h');text(42,757,'Background CDP work leaves the OS foreground alone.','s');text(42,783,'Web Storage means localStorage + sessionStorage.','s');text(42,807,'A saved login is not an application receipt.','s');
text(24,861,'HTTPS only · private local files · no credentials in agent output','s');
fs.writeFileSync('docs/figures/local-auth-vault.svg',new XMLSerializer().serializeToString(doc));
