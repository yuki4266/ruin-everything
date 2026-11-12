// NODE_PATH must contain roughjs. The SVG remains directly editable.
const fs = require('fs');
const rough = require('roughjs/bundled/rough.cjs.js');
const gen = rough.generator();
const out = [];
let seed = 320;
const escape = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;');
function shape(d) {for (const p of gen.toPaths(d)) out.push(`<path d="${p.d}" stroke="${p.stroke}" stroke-width="${p.strokeWidth}" fill="${p.fill || 'none'}"/>`);}
function box(x,y,w,h,fill) {shape(gen.rectangle(x,y,w,h,{seed:seed++,roughness:.7,stroke:'#302b38',fill,fillStyle:'solid'}));}
function text(x,y,s,cls='') {out.push(`<text x="${x}" y="${y}" class="${cls}">${escape(s)}</text>`);}
function arrow(x,y,x2,y2) {shape(gen.line(x,y,x2,y2,{seed:seed++,stroke:'#302b38'}));shape(gen.linearPath([[x2-7,y2-5],[x2,y2],[x2-7,y2+5]],{seed:seed++,stroke:'#302b38'}));}
const font=fs.readFileSync('docs/figures/autofill.svg','utf8').match(/@font-face\{[^}]+\}/)[0];
out.push(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 470" width="920" height="470" role="img" aria-labelledby="title desc"><title id="title">GeeTest: match order, then click</title><desc id="desc">A: crop the icon board, detect candidate boxes and match the prompt using local vision. B: map bitmap centers to CSS coordinates, click in order and confirm. Retry only the widget up to three attempts.</desc><style>${font}text{font-family:Arial,sans-serif;fill:#302b38;font-size:18px}.h{font-family:Kalam;font-size:28px}.s{font-size:16px}</style><rect width="920" height="470" fill="#fffaf0"/>`);
text(24,38,'A / Read the visible icons','h');
box(25,59,245,154,'#e8dcfa');text(41,89,'Prompt: left → right');
text(41,120,'Square board, not footer');
box(47,139,39,42,'#c7ecd9');box(104,144,35,36,'#f8d5e1');box(157,140,41,42,'#c6ddfa');
text(57,169,'1');text(114,170,'2');text(170,170,'3');
arrow(278,135,323,135);
box(332,59,252,154,'#e8dcfa');text(347,91,'ddddocr bounding boxes');text(347,124,'Number exact icon crops');text(347,158,'Templates / local vision');text(347,188,'Match one target at a time');
arrow(593,135,632,135);
box(641,59,252,154,'#fbe6b2');text(657,91,'Validate the order');text(657,124,'One ID per target icon');text(657,158,'No duplicate / extra IDs');text(657,188,'Changed image? Stop');
text(24,258,'B / Click in the original tab','h');
box(25,277,418,82,'#e8dcfa');text(41,307,'CSS x = left + centerX / bitmapW × CSS width','s');text(41,339,'Same mapping for y; include iframe transforms','s');
arrow(451,317,490,317);
box(500,277,192,82,'#e8dcfa');text(515,308,'Ordered mouse clicks');text(515,338,'Wait, then press OK','s');
arrow(701,317,737,317);
box(747,277,146,82,'#c7ecd9');text(760,307,'Site result');text(760,338,'Check again','s');
box(25,384,868,57,'#fbe6b2');text(40,409,'Still visible → refresh the widget; at most 3 attempts. Never replay the form.','s');text(40,431,'Verification cleared ≠ login complete ≠ application received.','s');
out.push('</svg>');fs.writeFileSync('docs/figures/geetest-icons.svg',out.join('\n'));
