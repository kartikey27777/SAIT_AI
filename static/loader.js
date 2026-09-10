(function () {
    var NAME_IMG = '/static/name.jpeg';
    var MODEL_NAMES = ['gemma2:2b', 'qwen2:1.5b', 'qwen2:7b', 'SAIT AI'];

    function makeNameImg() {
        var ni = document.createElement('img');
        ni.src = NAME_IMG;
        ni.setAttribute('data-sait-brand', '1');
        ni.style.height = '24px';
        ni.style.maxHeight = '24px';
        ni.style.width = 'auto';
        ni.style.verticalAlign = 'middle';
        ni.style.display = 'inline-block';
        ni.alt = 'SAIT AI';
        return ni;
    }

    function isModelName(text) {
        var t = (text || '').trim();
        for (var i = 0; i < MODEL_NAMES.length; i++) {
            if (t === MODEL_NAMES[i]) return true;
        }
        return false;
    }

    function replaceDirectTextNodes(el) {
        var changed = false;
        var cn = el.childNodes;
        for (var i = cn.length - 1; i >= 0; i--) {
            var c = cn[i];
            if (c.nodeType !== Node.TEXT_NODE) continue;
            if (!isModelName(c.nodeValue)) continue;
            if (c.parentElement.getAttribute('data-sait-brand') !== null) continue;
            var ni = makeNameImg();
            c.parentNode.replaceChild(ni, c);
            changed = true;
        }
        return changed;
    }

    function brandifyNearLogo() {
        var changed = false;
        var imgs = document.querySelectorAll('img[src*="logo.png"], img[id="logo"]');
        for (var i = 0; i < imgs.length; i++) {
            var img = imgs[i];
            if (img.closest('[data-sait-brand]')) continue;
            var el = img;
            var tries = 0;
            while (el && el.tagName !== 'BODY' && tries < 6) {
                if (el.querySelector('[data-sait-brand]')) break;
                if (replaceDirectTextNodes(el)) {
                    changed = true;
                    break;
                }
                el = el.parentElement;
                tries++;
            }
        }
        return changed;
    }

    function scanAll() {
        var changed = false;
        var all = document.querySelectorAll('*');
        for (var i = 0; i < all.length; i++) {
            var el = all[i];
            if (el.getAttribute && el.getAttribute('data-sait-brand') !== null) continue;
            if (replaceDirectTextNodes(el)) changed = true;
        }
        return changed;
    }

    var runs = 0;

    function run() {
        if (!document.body) return;
        try {
            brandifyNearLogo();
            scanAll();
        } catch (e) {}
        runs++;
        if (runs < 30) {
            setTimeout(run, 1000);
        }
    }

    if (document.readyState === 'loading') {
        window.addEventListener('DOMContentLoaded', run);
    } else {
        setTimeout(run, 500);
    }
})();