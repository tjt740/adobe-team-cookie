/* Keep browser URLs and application routes consistent for root and mounted deployments. */
(function () {
  'use strict';
  var element = document.querySelector('base[href]');
  var base = element ? new URL(element.href).pathname.replace(/\/+$/, '') : '';
  function path(value) {
    var pathname = new URL(value || location.href, document.baseURI).pathname;
    if (base && (pathname === base || pathname.indexOf(base + '/') === 0)) {
      pathname = pathname.slice(base.length);
    }
    return pathname || '/';
  }
  function route(value) {
    var url = new URL(value || location.href, document.baseURI);
    return path(url.href) + url.search + url.hash;
  }
  window.OKAD_ROUTE = {
    path: path,
    route: route,
    href: function (value) { return base + route(value); }
  };
})();
