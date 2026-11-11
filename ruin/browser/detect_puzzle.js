// Return references to the visible widget and its controls in this document.
// Scan from visual anchors up to their nearest shared overlay, including open shadow trees.
(inFrame) => {
    const hint = /captcha|jigsaw|puzzle|slide[r ]|drag|滑块|拖动|拼图|安全验证|机器人|select all (?:images|squares)|请选择.*图/i;
    const gridHint = /select all|select (?:the )?images|click (?:on )?(?:all|every)|选择.*图|点[击选].*图/i;
    const rect = e => e.getBoundingClientRect();
    const visible = e => {
        const r = rect(e);
        return r.width >= 2 && r.height >= 2 && r.bottom > 0 && r.right > 0 &&
            r.top < innerHeight && r.left < innerWidth && e.checkVisibility({opacityProperty:true, visibilityProperty:true});
    };
    const label = e => [e.getAttribute('aria-label'), e.title, e.getAttribute('class')].join(' ');
    const parent = e => e.parentElement || e.getRootNode().host;
    const elevated = e => {
        if (inFrame) return true;
        for (let a=e; a && a !== document.body; a=parent(a)) {
            const s = getComputedStyle(a);
            if (a.matches('dialog[open], [role=dialog], [aria-modal=true], :popover-open') ||
                s.position === 'fixed' || /(?:popup|modal|overlay)/i.test(label(a)) || (s.position !== 'static' && Number(s.zIndex) > 0)) return true;
        }
        return false;
    };
    const actionable = e => {
        const r = rect(e);
        const hit = e.getRootNode().elementFromPoint(r.x + r.width/2, r.y + r.height/2);
        return hit && (e === hit || e.contains(hit));
    };
    // Provider markup takes precedence over generic slider heuristics. hCaptcha
    // also renders two-dimensional drag tasks in a canvas, not a slider rail.
    if (/(^|\.)hcaptcha\.com$/.test(location.hostname)) {
        const mode = new URLSearchParams(location.hash.slice(1)).get('frame');
        if (mode === 'checkbox') {
            const checkbox = document.querySelector('#checkbox, [role=checkbox]');
            if (checkbox && visible(checkbox) && checkbox.getAttribute('aria-checked') !== 'true')
                return {kind:'hcaptcha_checkbox', scope:document.body, checkbox};
            return null;
        }
        if (mode === 'challenge') {
            const scope = document.body;
            const verify = [...scope.querySelectorAll('.button-submit')].filter(visible);
            const cells = [...scope.querySelectorAll('.task-image')].filter(visible);
            if (!verify.length && !cells.length && !scope.querySelector('.challenge-container')) return null;
            if (verify.length !== 1) return {kind:'hcaptcha_pending', scope};
            if ([9,16].includes(cells.length))
                return {kind:'hcaptcha_grid', scope, cells, verify:verify[0]};
            const boards = [...scope.querySelectorAll('.challenge-container canvas')].filter(visible);
            if (boards.length === 1 && /drag/i.test(scope.innerText))
                return {kind:'hcaptcha_drag', scope, board:boards[0], verify:verify[0]};
            if (boards.length === 1 && /click|select/i.test(scope.innerText))
                return {kind:'hcaptcha_points', scope, board:boards[0], verify:verify[0]};
            return {kind:'hcaptcha_pending', scope};
        }
        return null;
    }
    let fallback = null;
    const roots = [document];
    for (const root of roots) {
        for (const e of root.querySelectorAll('*')) if (e.shadowRoot) roots.push(e.shadowRoot);
        const anchors = root.querySelectorAll('img,canvas,[role=slider],[draggable=true],input[type=range],[class*=slider i],[role=grid], [style*="background-image"]');
        const seen = new Set();
        for (const anchor of anchors) {
            if (!visible(anchor) || !elevated(anchor)) continue;
            for (let scope=parent(anchor); scope && !seen.has(scope); scope=parent(scope)) {
                seen.add(scope);
                if (scope === document.documentElement || (scope === document.body && !inFrame)) break;
                if (!visible(scope) || !elevated(scope)) continue;
                const nodes = [...scope.querySelectorAll('*')].filter(visible);
                const text = (scope.innerText || '').trim();
                const media = nodes.filter(e => e.matches('img,canvas') || e.style.backgroundImage);
                const buttons = nodes.filter(e => e.matches('button,[role=button],input[type=button]'));
                const caption = e => (e.innerText || e.value || e.title || e.getAttribute('aria-label') || '').trim();
                const verify = buttons.find(e => /^(verify|confirm|next|skip|验证|确认|下一步|跳过)$/i.test(caption(e)) && actionable(e));
                const refresh = buttons.find(e => /refresh|reload|换一|刷新/i.test(caption(e)+' '+label(e)) && actionable(e));
                if (verify && gridHint.test(text)) {
                    const tiles = nodes.filter(e => e.matches('td,[role=gridcell],button,[role=button],img,canvas') &&
                        rect(e).width >= 30 && rect(e).height >= 30 && actionable(e));
                    // Prefer the clickable outer cell when an image is nested in it.
                    const cells = tiles.filter(e => !tiles.some(p => p !== e && p.contains(e)));
                    if ([9,16].includes(cells.length)) {
                        cells.sort((a,b) => Math.abs(rect(a).top-rect(b).top) > 3 ?
                            rect(a).top-rect(b).top : rect(a).left-rect(b).left);
                        return {kind:'grid', scope, cells, verify, refresh};
                    }
                    if (media.length === 1 && media[0].matches('canvas') && actionable(media[0]))
                        return {kind:'grid', scope, board:media[0], verify, refresh};
                }
                const board = media.filter(e => rect(e).width >= 90 && rect(e).height >= 45)
                    .sort((a,b) => rect(b).width-rect(a).width)[0];
                const piece = board && media.find(e => {
                    const b=rect(board), r=rect(e);
                    return e !== board && r.width < b.width * .7 && r.width >= 12 &&
                        r.left >= b.left-3 && r.right <= b.right+3 && r.top < b.bottom && r.bottom > b.top;
                });
                const semantic = hint.test(text+' '+label(scope)) || nodes.some(e => hint.test(label(e)));
                if (!semantic && !piece && !board?.matches('canvas')) continue;
                if (scope.matches('.vc-captcha-verify.whirl') && scope.querySelector('.whirl-img-inner-base'))
                    return {kind:'rotation', scope, refresh};
                const range = nodes.find(e => e.matches('input[type=range]') && actionable(e));
                if (range && (/captcha|验证|puzzle|slide.*right|向右|drag.*end/i.test(text) || piece))
                    return {kind:'range', scope, board, piece, knob:range, track:range, refresh};
                const knobs = nodes.filter(e => {
                    const r = rect(e);
                    if (r.width < 12 || r.width > 100 || r.height < 12 || r.height > 95) return false;
                    return (e.matches('[draggable=true],[role=slider]') || /slider|drag|thumb|handle/i.test(label(e)) ||
                        /^(grab|grabbing|ew-resize|move|pointer)$/.test(getComputedStyle(e).cursor)) &&
                        !e.closest('button[title*="refresh" i]') && actionable(e);
                });
                for (const knob of knobs) {
                    const k = rect(knob);
                    if (board && k.top < rect(board).bottom - 4) continue;
                    let track = parent(knob);
                    while (track && scope.contains(track) && rect(track).width < k.width*2.2) track=parent(track);
                    if (!track || !scope.contains(track) || rect(track).height > k.height*2.2) continue;
                    if (!board && !/slide.*(?:right|end)|drag.*(?:right|end)|向右|拖.*(?:最右|尽头)/i.test(text)) continue;
                    return {kind:piece?'jigsaw':board?'visual_slider':'slider', scope, board, piece, knob, track, refresh};
                }
                if (board?.matches('canvas') && actionable(board) && /drag|slide|拼图|滑块|拖动/i.test(text))
                    fallback = {kind:'canvas_drag',scope,board,refresh};
                else if (!fallback && (board?.matches('canvas') || (semantic && (board || knobs.length))))
                    fallback = {kind:'unresolved',scope,refresh};

            }
        }
    }
    return fallback;
}
