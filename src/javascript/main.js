(function() {
    "use strict"

    var $menu = $('#menu')
    $$('h2,h3', $('#documentation')).forEach(function($el) {
        var $a = $.create('a', {
            href: '#' + $el.id,
            className: 'menu-' + $el.tagName.toLowerCase()
        })
        $a.textContent = $el.textContent
        $menu.appendChild($a)
    })

    var $btnContainer = $('#download-buttons');

    $.fetch('https://api.github.com/repos/nzblnk/nzb-monkey/releases/latest', {
        responseType: 'json',
        headers: {'If-None-Match': localStorage.getItem('git_tag')}
    }).then(function(xhr){
        var dl = {}
        if (xhr.status == 200) {
            xhr.response.assets.forEach(function(el){
                var name = el.name.match(/nzbmonkey-v([\d.]+)-(\w+)\.(\w+)/)
                dl[name[2]] = {
                    'version': name[1],
                    'url': el.browser_download_url,
                    'size': el.size,
                    'ext': name[3].toUpperCase()
                }
            })
            localStorage.setItem('git_tag', xhr.getResponseHeader('ETag'))
            localStorage.setItem('git_dl', JSON.stringify(dl))

        } else {
            dl = JSON.parse(localStorage.getItem('git_dl'))
        }

        ['win', 'linux', 'macos'].forEach(function(os) {
            var obj = dl[os]
            if (!obj) return

            var $btn = $.create('a', {
                className: 'btn-' + os,
                href: obj.url,
                title: obj.ext + '-file, ' + obj.size + ' bytes'

            })
            $btnContainer.appendChild($btn)
        })

        $btnContainer.classList.remove('is-loading')
    }).catch(function(error){
        console.error(error, 'Status: ' + error.status)
    });
}());