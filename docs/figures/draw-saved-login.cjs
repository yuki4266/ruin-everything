// Run with NODE_PATH pointing to roughjs and @xmldom/xmldom.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root=doc.documentElement;
for (const [k,v] of Object.entries({width:720,height:850,viewBox:'0 0 720 850',role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag,attrs={},text){const n=doc.createElementNS(root.namespaceURI,tag);for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));root.appendChild(n);return n;}
el('title',{id:'title'},'Restore the session, continue the login');
el('desc',{id:'desc'},'A fixed Chrome profile restores session data. A filled Duke login and Duo device trust advance through the executor. Remaining verification is reported after fifteen seconds.');
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;fill:#302b38;font-size:18px}.h{font-family:Kalam;font-size:27px}.s{font-size:16px}');
el('rect',{width:720,height:850,fill:'#fffaf0'});
const r=rough.svg(root);let seed=710;
function box(x,y,w,h,fill){root.appendChild(r.path(`M${x+12} ${y} H${x+w-12} Q${x+w} ${y} ${x+w} ${y+12} V${y+h-12} Q${x+w} ${y+h} ${x+w-12} ${y+h} H${x+12} Q${x} ${y+h} ${x} ${y+h-12} V${y+12} Q${x} ${y} ${x+12} ${y}Z`,{seed:seed++,roughness:.8,stroke:'#302b38',strokeWidth:1.5,fill,fillStyle:'solid'}));}
function text(x,y,t,cls=''){el('text',{x,y,class:cls},t);}
function arrow(x,y,x2,y2){root.appendChild(r.line(x,y,x2,y2,{seed:seed++,stroke:'#302b38',roughness:.6}));root.appendChild(r.linearPath([[x2-7,y2-5],[x2,y2],[x2-7,y2+5]],{seed:seed++,stroke:'#302b38',roughness:.5}));}
text(24,38,'A / Keep the same browser profile','h');
box(24,62,305,128,'#e8dcfa');text(42,92,'Fixed user-data directory');text(42,123,'~/.ruin-everything/','s');text(42,149,'canvas-browser','s');text(42,175,'No temporary profile','s');
arrow(336,125,381,125);text(338,110,'load','s');
box(388,62,308,128,'#e8dcfa');text(406,92,'Restore the last session');text(406,123,'restore_on_startup = 1','s');text(406,149,'--restore-last-session','s');text(406,175,'Existing cookies + tabs','s');
text(24,225,'Offline: prepare preferences. Running: Chrome Settings.','s');
text(24,275,'B / Advance the selected task tab','h');
box(24,297,305,132,'#e8dcfa');text(42,329,'Duke username + password');text(42,358,'Both already filled?','h');text(42,386,'Unique login button','s');text(42,411,'Same-origin form action','s');
arrow(336,362,381,362);text(337,346,'submit','s');
box(388,297,308,132,'#fbe6b2');text(406,329,'Ruin executor');text(406,358,'Click once per document');text(406,386,'Keep credentials in Chrome','s');text(406,411,'Follow the original tab','s');
box(24,453,672,115,'#e8dcfa');text(42,485,'Duo device trust appears','h');text(42,516,'Confirm “Yes, trust browser” / “Yes, this is my device”');text(42,545,'Duo page or visible Duo iframe inside Duke','s');
text(24,614,'C / Observe before handing off','h');
box(24,638,672,62,'#fbe6b2');text(42,676,'Wait 15 seconds; restart the wait after each automatic click');
box(24,722,305,98,'#d9f1e5');text(42,755,'Page redirected','h');text(42,786,'Return the current URL','s');text(42,807,'Not proof of authentication','s');
box(388,722,308,98,'#fff0d9');text(406,755,'Verification remains','h');text(406,786,'Report pending code / push','s');text(406,807,'School controls trust duration','s');
fs.writeFileSync('docs/figures/saved-login.svg',new XMLSerializer().serializeToString(doc));
