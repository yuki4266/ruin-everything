// Run with NODE_PATH pointing to roughjs and @xmldom/xmldom.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const {DOMImplementation, XMLSerializer} = require('@xmldom/xmldom');
const doc = new DOMImplementation().createDocument('http://www.w3.org/2000/svg', 'svg');
const root=doc.documentElement;
for (const [k,v] of Object.entries({width:720,height:900,viewBox:'0 0 720 900',role:'img','aria-labelledby':'title desc'})) root.setAttribute(k,v);
function el(tag,attrs={},text){const n=doc.createElementNS(root.namespaceURI,tag);for(const [k,v] of Object.entries(attrs)) n.setAttribute(k,v);if(text)n.appendChild(doc.createTextNode(text));root.appendChild(n);return n;}
el('title',{id:'title'},'A working page without taking the foreground');
el('desc',{id:'desc'},'Agent targets are created in the background. Renderer focus and lifecycle emulation keep browser input and animation active without activating the macOS application. Marked targets survive reconnects; manual navigation prevents implicit reuse.');
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
el('style',{},font+'text{font-family:Arial,sans-serif;fill:#302b38;font-size:18px}.h{font-family:Kalam;font-size:27px}.s{font-size:16px}.hs{font-family:Kalam;font-size:23px}');
el('rect',{width:720,height:900,fill:'#fffaf0'});
const r=rough.svg(root);let seed=710;
function box(x,y,w,h,fill){root.appendChild(r.path(`M${x+12} ${y} H${x+w-12} Q${x+w} ${y} ${x+w} ${y+12} V${y+h-12} Q${x+w} ${y+h} ${x+w-12} ${y+h} H${x+12} Q${x} ${y+h} ${x} ${y+h-12} V${y+12} Q${x} ${y} ${x+12} ${y}Z`,{seed:seed++,roughness:.8,stroke:'#302b38',strokeWidth:1.5,fill,fillStyle:'solid'}));}
function text(x,y,t,cls=''){el('text',{x,y,class:cls},t);}
function arrow(x,y,x2,y2){root.appendChild(r.line(x,y,x2,y2,{seed:seed++,stroke:'#302b38',roughness:.6}));root.appendChild(r.linearPath([[x2-7,y2-5],[x2,y2],[x2-7,y2+5]],{seed:seed++,stroke:'#302b38',roughness:.5}));}
text(24,38,'A / Your foreground stays yours','h');
box(24,61,672,76,'#fff0d9');text(42,92,'Your current app · your current desktop');text(42,119,'Ruin sends no OS activation command.','s');
text(24,172,'Chrome task path — independent of the OS foreground','s');
box(24,190,195,105,'#fbe6b2');text(40,222,'Select task tab','hs');text(40,250,'Exact destination','s');text(40,277,'or owned target','s');
arrow(224,245,254,245);
box(259,190,195,105,'#e8dcfa');text(275,222,'Background tab','hs');text(275,250,'Same profile','s');text(275,277,'background: true','s');
arrow(459,245,489,245);
box(494,190,202,105,'#d9f1e5');text(510,222,'Active renderer','hs');text(510,250,'Virtual focus','s');text(510,277,'Input + screenshots','s');
text(24,339,'B / Ownership is explicit','h');
box(24,360,672,126,'#fbe6b2');text(42,391,'Private registry: target ID + purpose + URL hash');text(42,421,'Unchanged owned URL → reuse across reconnects');text(42,449,'User navigated elsewhere → create a new background tab');text(42,475,'User blank tabs are preserved. Explicit site selection still works.','s');
box(24,510,672,99,'#e8dcfa');text(42,540,'Task page CDP commands','h');text(42,568,'Emulation.setFocusEmulationEnabled → enabled: true','s');text(42,594,'Page.setWebLifecycleState → state: active','s');
text(24,652,'C / Next launch keeps the same profile','h');
box(24,674,672,174,'#e8dcfa');text(42,704,'macOS: open -g -n -a Chrome · restore last session');text(42,734,'--disable-background-timer-throttling','s');text(42,761,'--disable-backgrounding-occluded-windows','s');text(42,788,'--disable-renderer-backgrounding','s');text(42,815,'--disable-ipc-flooding-protection','s');text(42,839,'A running Chrome is left open; startup flags apply on next launch.','s');
text(24,882,'Verified input and rendering; the website still decides verification.','s');
fs.writeFileSync('docs/figures/background.svg',new XMLSerializer().serializeToString(doc));
