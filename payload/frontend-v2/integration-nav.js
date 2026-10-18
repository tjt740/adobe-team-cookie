/* Use the same authenticated route, sidebar and lifecycle as other Okad pages. */
(function () {
  'use strict';
  window.OKAD_NAV.register({
    id:'integration-nav', route:'integration', panel:'integration-panel',
    label:'联动中心', icon:'integration',
    open:window.OKAD_INTEGRATION.open,
    close:window.OKAD_INTEGRATION.close,
    layout:window.OKAD_INTEGRATION.layout
  });
})();
