/* 外部子号管理 —— 点侧边栏菜单在「右侧内容区」内嵌显示(按实际测量左侧菜单宽度/顶栏高度
   定位,只覆盖内容区,绝不遮挡左侧菜单与顶栏);点其它菜单自动收起。菜单项排第一、设置排第二。
   接口:/api/external/*(JWT,取 localStorage.okad_token)。 */
(function () {
  "use strict";
  var TK = "okad_token";
  var NAV_ID = "extm-nav";
  var view = null, mounting = null;
  var viewURL = new URL('./external-members-view.js?v=20261020-custom-groups', document.currentScript.src).href;
  var st = { rows: [], sel: new Set(), page: 1, size: 200, total: 0, loadingSeq: 0, loadError: "", statusF: "", subF: "", stockF: "", syncF: "", healthF: "", statesF: [], stoppingAll: false, importedFrom: "", importedBefore: "", creditsField: "available", creditsMin: "", creditsMax: "", profileF: "", companyF: "", groupF: "", groups: [], q: "", busy: false, open: false, expanded: new Set(), pending: new Set(), profileSaving: new Set(), noteSaving: false, details: {}, loadSeq: 0, polling: false, stock: null, stockPromise: null, stockEpoch: 0 };

  var CSS = [
    // 嵌入右侧内容区:按实际布局测量定位(left=菜单右缘, top=顶栏下缘),只盖内容区、不动左侧菜单/顶栏
    '#extm-embed{position:fixed;right:0;bottom:0;overflow:auto;background:#f5f7fa;color:#333639;z-index:1000;padding:20px 24px 40px;display:none;font:14px/1.6 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}',
    '#extm-embed.on{display:block}',
    '#extm-embed *{box-sizing:border-box}',
    // 页头
    '.extm-hd{display:flex;align-items:center;gap:12px;margin-bottom:16px}',
    '.extm-hd h2{font-size:18px;margin:0;font-weight:600}',
    '.extm-hd .cnt{font-size:13px;color:#909399}.extm-hd .cnt b{color:#18a058;font-variant-numeric:tabular-nums}',
    // 卡片
    '.extm-card{background:#fff;border-radius:6px;box-shadow:0 1px 2px rgba(0,0,0,.04);margin-bottom:16px;border:1px solid #efeff5}.extm-card[hidden]{display:none!important}',
    '.extm-card .hd{padding:12px 18px;font-size:14px;font-weight:500;border-bottom:1px solid #f2f3f5;display:flex;align-items:center;gap:8px}',
    '.extm-card .hd .tip{font-size:12px;color:#c0c4cc;font-weight:400}',
    '.extm-card .bd{padding:16px 18px}',
    '.extm-ta{width:100%;min-height:96px;border:1px solid #e0e0e6;border-radius:4px;padding:10px 12px;font:12.5px/1.7 ui-monospace,Menlo,Consolas,monospace;color:#333639;outline:none;resize:vertical;background:#fff;transition:.15s}',
    '.extm-ta:focus{border-color:#18a058;box-shadow:0 0 0 2px rgba(24,160,88,.16)}',
    '.extm-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:12px}',
    '.extm-in{height:34px;border:1px solid #e0e0e6;border-radius:4px;padding:0 11px;color:#333639;font-size:13px;outline:none;font-family:inherit;background:#fff;transition:.15s}',
    '.extm-in:focus{border-color:#18a058;box-shadow:0 0 0 2px rgba(24,160,88,.16)}',
    'select.extm-in{cursor:pointer;height:32px}',
    '.extm-btn{font:13px system-ui;border-radius:4px;padding:0 15px;height:34px;border:1px solid #18a058;background:#18a058;color:#fff;cursor:pointer;transition:.12s;white-space:nowrap;display:inline-flex;align-items:center;gap:5px}',
    '.extm-btn:hover:not(:disabled){background:#36ad6a;border-color:#36ad6a}.extm-btn:active{background:#0c7a43}',
    '.extm-btn:disabled{opacity:.5;cursor:not-allowed}',
    '.extm-btn.o{background:#fff;color:#18a058}.extm-btn.o:hover:not(:disabled){background:#eef8f2}',
    '#extm-sub2-push{color:#2080f0;border-color:#2080f0}#extm-sub2-push:hover:not(:disabled){color:#4098fc;border-color:#4098fc;background:#edf5ff}#extm-sub2-push:active:not(:disabled){color:#1060c9;border-color:#1060c9;background:#e1eeff}#extm-sub2-push:focus-visible{outline-color:#2080f0}',
    '.extm-btn.dft{background:#fff;color:#606266;border-color:#e0e0e6}.extm-btn.dft:hover:not(:disabled){color:#18a058;border-color:#18a058}',
    '.extm-btn.del{background:#fff;color:#d03050;border-color:#f0b3bf}.extm-btn.del:hover:not(:disabled){background:#fef0f2;border-color:#d03050}',
    '.extm-btn.sm{height:28px;padding:0 10px;font-size:12px}',
    '.extm-batch-controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.extm-detail:not(.extm-manage-history) .extm-history-select,.extm-detail:not(.extm-manage-history) [data-action=delete]{display:none}.extm-pill.info{background:#eaf2ff;color:#3b82f6}',
    '#extm-more-actions:not([open])>div{display:none}#extm-more-actions>summary::-webkit-details-marker{display:none}#extm-more-actions>summary:focus-visible{outline:2px solid #2080f0;outline-offset:3px}#extm-more-actions>div button{color:var(--ws-text,#333639)!important}',
    '.extm-tw{overflow:auto;max-height:60vh}.extm-t>thead>tr>th{position:sticky;top:0;z-index:2}.extm-t>thead>tr>th:last-child{z-index:3}',
    '.extm-pagination{display:flex;align-items:center;justify-content:flex-end;gap:10px;flex-wrap:wrap;padding:14px 18px;background:var(--ws-card,#fff);border-top:1px solid var(--ws-line,#efeff5);border-radius:0 0 12px 12px;color:var(--ws-muted,#909399);font-size:13px}.extm-pagination label,.extm-page-jump{display:inline-flex;align-items:center;gap:6px}.extm-pagination .extm-page-summary{margin-right:auto}.extm-pagination .extm-page-number{width:70px}.extm-pagination .extm-in:disabled{opacity:.55;cursor:not-allowed}html.dark .extm-pagination{background:var(--bg-card);border-color:var(--border)}',
    '.extm-t{border-collapse:collapse;table-layout:fixed;width:100%;font-size:13px;min-width:1816px}',
    '.extm-note-dialog{position:fixed;inset:0;margin:auto;box-sizing:border-box;width:min(480px,calc(100vw - 40px));max-height:calc(100vh - 48px);overflow:auto;border:1px solid var(--ws-line,#e4eaf2);border-radius:14px;padding:24px;background:var(--ws-card,#fff);color:var(--ws-text,#333639);box-shadow:0 20px 80px #18294533}.extm-note-dialog::backdrop{background:#17263d66}.extm-note-dialog .extm-btn[type=submit]{background:#2080f0;border-color:#2080f0}.extm-note-dialog .extm-btn[type=submit]:hover:not(:disabled){background:#4098fc;border-color:#4098fc}.extm-note-dialog .extm-ta:focus{border-color:#2080f0;box-shadow:0 0 0 2px #2080f026}.extm-note-dialog h3{margin:0 0 8px;font-size:18px}.extm-note-dialog p{margin:0 0 18px;color:var(--ws-muted,#7d8797);font-size:13px;overflow-wrap:anywhere}.extm-note-dialog label{display:block;margin-bottom:8px;font-size:13px}.extm-note-dialog .extm-ta{min-height:150px}.extm-note-help{display:flex;justify-content:space-between;gap:12px;font-size:12px;color:var(--ws-muted,#7d8797);margin-top:6px}.extm-note-dialog footer{display:flex;justify-content:flex-end;gap:10px;margin-top:20px}.extm-note-error{color:#d03050;font-size:12px;white-space:pre-wrap;margin-top:10px}.extm-note-error:empty{display:none}',
    '.extm-t th{text-align:left;padding:11px 16px;font-size:13px;font-weight:500;color:#909399;background:#fafafc;border-bottom:1px solid #efeff5;white-space:nowrap}',
    '.extm-t td{padding:12px;border-bottom:1px solid #f2f3f5;color:#333639;vertical-align:middle;white-space:nowrap}.extm-t th{padding:11px 12px}',
    '.extm-t td:last-child{white-space:nowrap}',
    '.extm-t>thead>tr>th:last-child,.extm-t>tbody>tr[data-member]>td:last-child{position:sticky;right:0;box-shadow:-3px 0 5px rgba(0,0,0,.025)}.extm-t>thead>tr>th:last-child{background:#fafafc}',
    '.extm-t>tbody>tr[data-member]{--extm-row-bg:#fff}.extm-t>tbody>tr[data-member]>td{background:var(--extm-row-bg)}.extm-history tbody tr:hover>td{background:#f5f7fa}',
    '.extm-t .mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px}',
    '.extm-t .cr{font-variant-numeric:tabular-nums;font-size:12.5px;color:#606266}',
    '.extm-t .cr b{color:#18a058}',
    '.extm-t input[type=checkbox]{width:15px;height:15px;cursor:pointer;accent-color:#18a058;margin:0;vertical-align:middle}',
    '.extm-pill{display:inline-block;font-size:12px;padding:1px 9px;border-radius:11px;line-height:1.7;white-space:nowrap}',
    '.extm-pill[data-sub2-stock]{padding:0 7px;line-height:18px}',
    '.extm-sub2-state{display:inline-flex;align-items:center;gap:5px}.extm-link.extm-sub2-details{display:inline-flex;align-items:center;justify-content:center;gap:3px;min-height:24px;color:#2080f0;font:12px system-ui;white-space:nowrap}.extm-sub2-dialog{width:min(540px,calc(100vw - 40px))}.extm-sub2-summary{padding:14px;background:var(--ws-soft,#f5f7fa);border:1px solid var(--ws-line,#e4eaf2);border-radius:8px;margin-bottom:16px}.extm-sub2-summary strong{display:block;font-size:15px;margin-bottom:6px}.extm-sub2-summary p{margin:0;line-height:1.7}.extm-sub2-dialog dl{display:grid;grid-template-columns:100px minmax(0,1fr);gap:10px 12px;font-size:13px;margin:0}.extm-sub2-dialog dt{color:var(--ws-muted,#7d8797)}.extm-sub2-dialog dd{margin:0;overflow-wrap:anywhere;white-space:pre-wrap}.extm-sub2-dialog h4{font-size:13px;margin:18px 0 6px}.extm-sub2-dialog p.extm-sub2-help{margin:0;line-height:1.7}.extm-sub2-dialog p.extm-sub2-footnote{margin:16px 0 0;font-size:12px}@media(max-width:800px){.extm-link.extm-sub2-details{min-width:44px;min-height:44px}}',
    '.extm-sub2-dialog,.extm-sub2-dialog .extm-btn.dft{background:var(--ws-paper,#fff);color:var(--ws-text,#273342)}.extm-sub2-dialog p,.extm-sub2-dialog dt{color:var(--text-2,#5a6675)}.extm-link.extm-sub2-details{color:var(--accent,#2080f0)}',
    '.extm-sub2-stamp-layer{position:absolute;inset:0;overflow:hidden;border-radius:inherit;pointer-events:none;z-index:2}.extm-sub2-stamp-layer[hidden]{display:none}.extm-sub2-stamp{position:absolute;left:50%;top:43%;width:min(360px,calc(100% - 54px));height:auto;transform:translate(-50%,-50%) rotate(-12deg);opacity:.42;pointer-events:none;user-select:none}.extm-sub2-dialog .extm-sub2-capacity{margin:12px 0 0;color:var(--text-2,#5a6675);font-size:12px;line-height:1.7}.extm-sub2-capacity[hidden]{display:none}html.dark .extm-sub2-stamp{opacity:.55}',
    '.extm-pill.ok{background:#e8f7f0;color:#18a058}.extm-pill.bad{background:#fce9ec;color:#d03050}.extm-pill.warn{background:#fdf3e6;color:#f0a020}.extm-pill.mut{background:#f0f2f5;color:#909399}',
    '.extm-credit-warning{display:inline-flex;align-items:center;gap:5px;max-width:100%;height:24px;padding:0 8px;border:1px solid #f6dfb9;border-radius:5px;background:#fff7e8;color:#a66310;font:12px/1 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;white-space:nowrap;vertical-align:middle;cursor:pointer;transition:background .15s,border-color .15s}.extm-credit-warning:hover{background:#ffedcf;border-color:#e8c28b}.extm-credit-warning:focus-visible{outline:2px solid #2080f0;outline-offset:2px}.extm-credit-warning .okad-icon{opacity:.75}.extm-credit-dialog .extm-credit-error{color:#b2730f;background:#fff7e8;border-radius:6px;padding:12px;overflow-wrap:anywhere}',
    '.extm-sub2-confirm-dialog{width:min(600px,calc(100vw - 40px))}.extm-sub2-confirm-dialog ul{list-style:none;margin:0;padding:0 12px;max-height:240px;overflow:auto;background:var(--ws-soft,#fff7e8);border:1px solid var(--ws-line,#f3e4c5);border-radius:8px}.extm-sub2-confirm-dialog li{padding:10px 0;overflow-wrap:anywhere}.extm-sub2-confirm-dialog li+li{border-top:1px solid var(--ws-line,#f3e4c5)}.extm-sub2-confirm-dialog li strong,.extm-sub2-confirm-dialog li span{display:block;font-size:13px}.extm-sub2-confirm-dialog li span{color:#b2730f;margin-top:4px}.extm-sub2-confirm-dialog .extm-relink-warning{margin-top:16px}.extm-sub2-confirm-dialog [data-confirm]{background:#2080f0;border-color:#2080f0}',
    '.extm-cap{display:inline-block;font-size:10.5px;padding:1px 6px;border-radius:3px;margin-left:6px;font-family:ui-monospace,Menlo,monospace}',
    '.extm-cap.ok{background:#e8f7f0;color:#18a058}.extm-cap.no{background:#f0f2f5;color:#c0c4cc}',
    '.extm-empty{text-align:center;color:#c0c4cc;padding:48px 0;font-size:13px}',
    '.extm-msg{font-size:12.5px;min-height:18px}.extm-msg.ok{color:#18a058}.extm-msg.err{color:#d03050}.extm-msg.mut{color:#909399}',
    '.extm-clip{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}.extm-email{font:12.5px ui-monospace,Menlo,monospace;text-align:left;width:100%}',
    '.extm-email-row{display:flex;align-items:center;gap:6px;min-width:0}.extm-email-row .extm-email{flex:0 1 auto;width:auto;min-width:0}.extm-company-tag{display:inline-flex;align-items:center;gap:3px;flex-shrink:0;padding:1px 6px;border:1px solid #b7e6cb;border-radius:4px;background:#e8f7f0;color:#18a058;font:12px/1.6 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;white-space:nowrap}',
    '.extm-account-meta{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:3px}.extm-account-meta .extm-pill{margin-top:0!important}.extm-mode-link{display:inline-flex;align-items:center;gap:4px;font:11px system-ui;color:var(--ws-muted,#7d8797)}.extm-mode-link:disabled{cursor:default;opacity:.65}.extm-otp-notice{padding:10px 16px;background:#fff7e8;color:#b2730f;font-size:13px;border-bottom:1px solid #f3e4c5}.extm-otp-notice[hidden]{display:none}.extm-otp-dialog .extm-in{width:100%;height:44px;font-size:22px;letter-spacing:7px}.extm-otp-dialog label{display:block;margin-bottom:10px}.extm-otp-dialog .extm-otp-time{color:var(--ws-muted,#7d8797);font-size:12px;margin:12px 0}',
    '.extm-link{border:0;background:transparent;color:inherit;padding:0;cursor:pointer}.extm-link:hover{color:#18a058}.extm-t>tbody>tr[data-member]>td:nth-child(-n+2){padding:0;text-align:center}.extm-toggle{display:flex;align-items:center;justify-content:center;width:28px;height:28px;margin:0 auto;border-radius:6px;color:#858d99;line-height:1}.extm-toggle:hover{background:#e9edf2}.extm-toggle .okad-icon{display:block;transition:transform .18s}.extm-toggle[aria-expanded=true]{color:#18a058;background:#e8f5ee}.extm-toggle[aria-expanded=true] .okad-icon{transform:rotate(90deg)}',
    '.extm-status{display:flex;align-items:center;gap:8px;min-width:0}.extm-status .extm-pill{flex-shrink:0}.extm-status .extm-cap{flex-shrink:0;margin:0}.extm-status .extm-cap.no{color:#909399}.extm-status .extm-link{font:inherit;font-size:12px;text-align:left;color:#606266}.extm-actions{display:flex;gap:7px}',
    '.extm-success{display:inline-flex;align-items:center;gap:4px;border:0;cursor:pointer;font-family:inherit;border-radius:4px;padding:2px 8px}.extm-success:focus-visible{outline:2px solid #18a058;outline-offset:3px}.extm-success:hover{background:#d8f1e2}',
    '.extm-spin{display:inline-block;width:13px;height:13px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:extm-spin .75s linear infinite;flex-shrink:0}@keyframes extm-spin{to{transform:rotate(360deg)}}',
    '.extm-btn[aria-busy=true]{opacity:.8}.extm-btn:focus-visible,.extm-link:focus-visible{outline:2px solid #18a058;outline-offset:3px}',
    '.extm-t tr.extm-detail-row>td,.extm-t tr.extm-detail-row:hover>td{padding:0 18px;background:#f2f2f2;white-space:normal}',
    '.extm-fold{position:sticky;left:18px;width:var(--extm-detail-width);max-width:100%;display:grid;grid-template-rows:1fr;opacity:1;transition:grid-template-rows .28s cubic-bezier(.2,.7,.2,1),opacity .22s ease}.extm-fold.is-closed{grid-template-rows:0fr;opacity:0;pointer-events:none}.extm-fold-clip{min-height:0;overflow:hidden}.extm-detail{padding:16px 0 18px}.extm-fold.is-closed .extm-detail{visibility:hidden;transition:visibility 0s .28s}@media(prefers-reduced-motion:reduce){.extm-fold,.extm-fold.is-closed .extm-detail{transition:none}}',
    '.extm-task-layout{display:grid;grid-template-columns:440px minmax(0,1fr);gap:16px}.extm-task-card{background:#fff;border:1px solid #e5e9e7;border-radius:6px;min-width:0;overflow:hidden}.extm-task-head{display:flex;align-items:center;gap:10px;padding:12px 14px;border-bottom:1px solid #edf0ee;min-height:51px}.extm-task-head strong{font-size:14px;font-weight:600}.extm-task-head .sp{flex:1}.extm-task-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-left:auto}.extm-task-head{flex-wrap:wrap;background:#fafbfc}.extm-task-head .extm-btn{border-radius:5px}.extm-task-head .extm-auto{margin-right:8px}.extm-auto{font-size:12px;color:#606266;display:flex;align-items:center;gap:5px;white-space:nowrap;cursor:pointer}',
    '.extm-auto input[type=checkbox]{appearance:none;width:28px;height:16px;border-radius:10px;background:#cdd3da;position:relative;transition:background .15s}.extm-auto input[type=checkbox]:checked{background:#18a058}.extm-auto input[type=checkbox]:after{content:"";position:absolute;left:2px;top:2px;width:12px;height:12px;background:#fff;border-radius:50%;transition:transform .15s}.extm-auto input[type=checkbox]:checked:after{transform:translateX(12px)}.extm-auto input[type=checkbox]:focus-visible{outline:2px solid #18a058;outline-offset:2px}',
    '.extm-history-wrap{max-height:366px;overflow:auto}.extm-history{table-layout:fixed;border-collapse:collapse;width:100%;font-size:12px}.extm-history th,.extm-history td{padding:9px 8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.extm-history td:first-child{padding:9px 7px;text-overflow:clip}.extm-history th{font-size:12px;background:#fafcfb;color:#909399}.extm-history tr[data-job]{cursor:pointer}.extm-history tr.active td{background:#edf8f1!important}.extm-history .extm-pill{padding:1px 6px;font-size:11px}.extm-history td:nth-child(2){color:#18a058}',
    '.extm-task-body{padding:14px}.extm-job-title{display:flex;align-items:center;gap:8px}.extm-job-meta{color:#909399;font-size:12px;display:flex;gap:8px 20px;flex-wrap:wrap;margin:12px 0 16px}.extm-job-meta span{display:inline-flex;align-items:center;gap:7px}.extm-job-meta b{font-weight:400;color:#667080;font-variant-numeric:tabular-nums}.extm-job-title{justify-content:space-between;flex-wrap:wrap}.extm-job-title strong{font-size:14px}.extm-counts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.extm-counts>span{display:flex;align-items:center;justify-content:space-between;gap:8px;background:#f6f8fa;border:1px solid #edf0f3;border-radius:6px;padding:8px 12px;color:#7a8492;font-size:12px}.extm-counts b{font-size:16px;font-weight:600;color:#354052;font-variant-numeric:tabular-nums}.extm-counts .extm-count-success b{color:#18a058}.extm-counts .extm-count-fail b{color:#d03050}.extm-counts .extm-count-zero b{color:#99a2ad}.extm-progress{height:6px;background:#eef0f2;border-radius:8px;overflow:hidden;margin:10px 0}.extm-progress>div{height:100%;background:#18a058;transition:width .2s}.extm-progress>div.failed{background:#d03050}',
    '.extm-log-tools{display:flex;align-items:center;gap:8px;margin:12px 0 8px;color:#909399;font-size:12px}.extm-log-tools .sp{flex:1}.extm-log-tools .extm-in{height:28px;font-size:12px}.extm-logs{margin:0;background:#1b2330;color:#cbd5e1;padding:12px;border-radius:5px;font:12px/1.8 ui-monospace,Menlo,Consolas,monospace;height:248px;overflow:auto;white-space:pre;tab-size:2}.extm-scope-note{color:#909399;font-size:12px;margin-top:8px}.extm-detail-error{color:#d03050;font-size:12px;white-space:normal;overflow-wrap:anywhere;margin:8px 0}.extm-detail-error:empty{display:none}',
    '.extm-log-legend{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:0 0 8px;font-size:11px;color:#7a8492}.extm-log-legend span{display:inline-flex;align-items:center;gap:5px}.extm-log-legend i{width:6px;height:6px;border-radius:50%;background:currentColor}.extm-log-line{display:inline-block;min-width:100%;padding:0 6px 0 8px;border-left:2px solid transparent}.extm-log-time{color:#8794a8}.extm-log-account{color:#9baec4}.extm-log-success{color:#86efac}.extm-log-warn{color:#fcd34d}.extm-log-error{color:#fda4af;border-left-color:#f87171;background:rgba(248,113,113,.06)}.extm-log-progress{color:#93c5fd}.extm-log-info{color:#cbd5e1}.extm-log-legend .success{color:#18a058}.extm-log-legend .warn{color:#d49a24}.extm-log-legend .error{color:#d03050}.extm-log-legend .progress{color:#4e8acf}.extm-log-legend .info{color:#94a0af}',
    '@media(max-width:1200px){.extm-task-layout{grid-template-columns:minmax(0,1fr)}.extm-history-wrap{max-height:180px}}',
    '.extm-profile-card{margin-bottom:16px}.extm-profile-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 24px;margin:0 0 12px}.extm-profile-fields dt{font-size:12px;color:#909399;margin-bottom:4px}.extm-profile-fields dd{margin:0;overflow-wrap:anywhere;font-size:13px}.extm-profile-options{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}.extm-profile-option{padding:12px;border:1px solid #edf0f3;border-radius:6px;background:#fafbfc;min-width:0}.extm-profile-option>div:first-child{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.extm-profile-option strong{font-size:13px;overflow-wrap:anywhere}.extm-profile-id,.extm-profile-owners{font:12px/1.7 ui-monospace,Menlo,monospace;color:#667080;overflow-wrap:anywhere;margin-top:8px}.extm-profile-list-title{font-size:13px;font-weight:600;margin:16px 0 10px}@media(max-width:760px){.extm-profile-fields{grid-template-columns:minmax(0,1fr)}}',
    '.extm-fab{position:fixed;right:22px;bottom:74px;z-index:1999;display:inline-flex;align-items:center;gap:7px;padding:10px 16px;border-radius:22px;background:#18a058;color:#fff;font:600 13px system-ui;cursor:pointer;box-shadow:0 6px 16px rgba(24,160,88,.4)}',
    '.extm-mode-dialog{background:var(--ws-paper,#fff)}.extm-mode-dialog .extm-in{width:100%;height:38px;background:var(--ws-paper,#fff);color:var(--ws-text,#333639);border-color:var(--ws-line,#e4eaf2)}.extm-mode-dialog .extm-mode-help{margin-top:12px;margin-bottom:0;font-size:12px}',
  ].join("");

  function injectStyle() { if (document.getElementById("extm-style")) return; var s = document.createElement("style"); s.id = "extm-style"; s.textContent = CSS; (document.head || document.documentElement).appendChild(s); }

  function api(path, opts) {
    opts = opts || {};
    var token = localStorage.getItem(TK) || "";
    var ctrl = opts.controller || new AbortController();
    var timedOut = false;
    var to = setTimeout(function () { timedOut = true; ctrl.abort(); }, opts.timeout || 30000);
    return fetch((opts.base || "/api/external") + path, {
      method: opts.method || "GET", signal: ctrl.signal,
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    }).then(function (r) {
      if (opts.blob && r.ok) return r.blob();
      return r.text().then(function (t) {
        var d; try { d = t ? JSON.parse(t) : {}; } catch (e) { d = { raw: t }; }
        if (r.status === 401) throw new Error("未登录,请重新登录后台");
        if (!r.ok) throw new Error((d && (d.detail || d.message)) || ("HTTP " + r.status));
        return d;
      });
    }).catch(function (e) {
      if (e.name === "AbortError" && timedOut) throw new Error("请求超时(" + Math.round((opts.timeout || 30000) / 1000) + "s)");
      throw e;
    }).finally(function () { clearTimeout(to); });
  }

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function el(id) { return document.getElementById(id); }
  function toast(type, m) { opMsg(m, type === "error" ? "err" : (type === "success" ? "ok" : "mut")); var a = window.$message; if (a && typeof a[type] === "function") a[type](m); }
  function opMsg(t, c) { if (view) view.update({message:t || '', messageTone:c || ''}); }
  function fmtTime(s, seconds) { return window.OKAD_TIME.datetime(s, !!seconds); }

  var STATUS_MAP = {
    ok: ["ok", "正常"], never: ["mut", "未登录"], login_failed: ["bad", "登录失败"],
    account_disabled: ["bad", "已停用"], rate_limited: ["warn", "频繁登录限流"], internal: ["bad", "内部错误"],
  };
  function statusPill(s) { var m = STATUS_MAP[s] || ["mut", s || "—"]; return '<span class="extm-pill ' + m[0] + '">' + esc(m[1]) + "</span>"; }
  function healthPills(row) {
    var stock = st.stock, item = stock && stock.items && stock.items[row.id];
    if (!stock || !stock.ok) return '<span data-sub2-health class="extm-pill mut">Sub2 状态' + (stock ? '暂不可用' : '查询中') + '</span>';
    if (!item || String(item.email || '').trim().toLowerCase() !== String(row.email || '').trim().toLowerCase()) return '<span data-sub2-health class="extm-pill mut">Sub2 状态查询中</span>';
    if (!item.in_stock) return '';
    var health = item.account_health || {}, codes = health.codes || [];
    var checked = 'Sub2 状态 · 核对时间 ' + fmtTime(stock.checked_at);
    if (health.state === 'error') {
      var labels = codes.slice();
      if (!labels.length || (health.errors || []).some(function (e) { return !e.code; })) labels.push('其他异常');
      return labels.map(function (code) {
        var tone = code === 408 || code === 429 ? 'warn' : 'bad';
        return '<span data-sub2-health class="extm-pill ' + tone + '" title="' + esc(checked + ' · 异常待成功验证') + '">Sub2 ' + esc(code) + '</span>';
      }).join('');
    }
    return '<span data-sub2-health class="extm-pill ' + (health.state === 'recovered' ? 'ok' : 'mut') + '" title="' + esc(checked) + '">' + (health.state === 'recovered' ? 'Sub2 已有成功证据' : 'Sub2 待验证') + '</span>';
  }
  function subPill(row) {
    if (row.credits_total == null && (row.credits_error || row.login_status === 'ok' || row.first_login_done)) {
      var reason = row.credits_error || '未保存具体失败原因，重新登录后会再次查询积分。';
      var label = row.credits_error ? '积分查询失败' : '积分未查到';
      return '<button type="button" class="extm-credit-warning" data-credit-error="' + row.id + '" aria-haspopup="dialog" aria-label="' + label + '，订阅状态未知，点击查看详情" title="' + esc('订阅状态未知；' + reason + '；点击查看详情') + '"><span>' + label + '</span>' + window.OKAD_ICONS.svg('info', 14) + '</button>';
    }
    if (row.login_status === "never" || row.credits_total == null) return '<span class="extm-pill mut">待查询</span>';
    return row.subscription_ok ? '<span class="extm-pill ok">订阅正常</span>' : '<span class="extm-pill bad">掉订阅</span>';
  }

  function showCreditError(id) {
    var row = rowById(id); if (!row || el('extm-credit-dialog')) return;
    var dialog = document.createElement('dialog'); dialog.id = 'extm-credit-dialog'; dialog.className = 'extm-note-dialog extm-credit-dialog'; dialog.setAttribute('aria-labelledby', 'extm-credit-title');
    dialog.innerHTML = '<h3 id="extm-credit-title">' + (row.credits_error ? '积分查询失败' : '积分未查到') + '</h3><p>' + esc(row.email) + '</p><p class="extm-credit-error">' + esc(row.credits_error || '这条历史记录未保存具体失败原因。') + '</p><p>积分未查到，暂时无法判断订阅状态，不代表积分为 0 或已掉订阅。「登录成功」仅表示登录及 Cookie 获取成功。</p><p>可关闭此窗口，点击账号行的「重登」重新查询积分；页面「搜索」只更新已保存的结果。</p><footer><button type="button" class="extm-btn dft">知道了</button></footer>';
    dialog.querySelector('button').onclick = function () { dialog.close(); };
    dialog.onclose = function () { dialog.remove(); var button = document.querySelector('[data-credit-error="' + id + '"]'); if (button) button.focus({preventScroll:true}); };
    document.body.appendChild(dialog); dialog.showModal();
  }
  function creditCell(row) {
    function amount(value) { return value == null || !Number.isFinite(Number(value)) ? "—" : String(Number(value)); }
    var a = amount(row.credits_available);
    var t = amount(row.credits_total);
    return '<span class="cr"><b>' + a + "</b> / " + t + "</span>";
  }

  // ---------- 页面主体(route 与 overlay 共用) ----------
  function buildBody(host, mount) {
    var tableHTML =
      '<div id="extm-otp-notice" class="extm-otp-notice" role="status" hidden></div><div class="extm-tw"><table class="extm-t"><colgroup><col class="extm-select-col" style="width:38px"><col style="width:34px"><col style="width:280px"><col style="width:110px"><col style="width:120px"><col><col style="width:168px"><col style="width:158px"><col style="width:158px"><col style="width:180px"><col style="width:270px"></colgroup><thead><tr>' +
          '<th class="extm-select-cell"><input type="checkbox" id="extm-ckall" aria-label="选择本页全部账号"></th><th></th>' +
          '<th>邮箱</th><th>积分(可用/总)</th><th>当前配置</th><th>登录状态</th><th>订阅</th><th>邮箱导入时间</th><th>最后登录</th><th title="最后一次成功推送 Cookie 到当前 Sub2 的时间">最后推送cookie 时间</th><th>操作</th>' +
        '</tr></thead><tbody id="extm-tbody"><tr><td colspan="11" class="extm-empty">加载中…</td></tr></tbody></table></div>' ;
    view = mount(host, {
      filter: function (filters) {
        st.statusF = filters.status; st.subF = filters.sub; st.stockF = filters.stock; st.syncF = filters.sync; st.healthF = filters.health; st.statesF = filters.states || [];
        st.profileF = filters.profile; st.companyF = filters.company; st.groupF = filters.group;
        st.creditsField = filters.creditsField;
        st.creditsMin = filters.creditsMin == null ? '' : String(filters.creditsMin);
        st.creditsMax = filters.creditsMax == null ? '' : String(filters.creditsMax);
        st.importedFrom = dateBoundary(filters.from, false); st.importedBefore = dateBoundary(filters.to, true);
        st.q = filters.keyword; resetPage(1); load();
      },
      refresh: function () {
        view.button('extm-refresh', {loading:true, disabled:true});
        return Promise.all([refreshStock(true), loadGroups()]).then(function () { return refreshAll(true); }).finally(function () {
          view.button('extm-refresh', {loading:false, disabled:false});
        });
      },
      createGroup: createGroup, loadGroups: loadGroups, assignGroup: assignGroup,
      import: doImport, mail: mailAction, stopAll: stopAllTasks, batchLogin: batchLogin, profile: saveSelectedProfilePreference,
      delete: batchDelete, export: exportCookies, exportEmails: exportEmails, push: pushSub2, loginAll: loginAll,
      page: goPage,
      size: function (size) {
        if (st.profileSaving.size || st.noteSaving || !window.OKAD_PAGINATION.valid(size)) return;
        st.size = size; resetPage(1); load();
      }
    }, tableHTML);
    el("extm-ckall").onchange = function () {
      var on = this.checked; st.sel.clear();
      if (on) st.rows.forEach(function (r) { st.sel.add(r.id); });
      Array.prototype.forEach.call(document.querySelectorAll(".extm-rowck"), function (c) { c.checked = on; });
      updSel();
    };
    loadMailConfig(); loadGroups(); load();
  }

  function dateBoundary(value, nextDay) {
    if (!value) return "";
    var date = new Date(value + 'T00:00:00+08:00');
    if (nextDay) date.setUTCDate(date.getUTCDate() + 1);
    return date.toISOString();
  }
  function extraFilters() {
    var filters = {};
    if (st.stockF !== "") filters.in_stock = st.stockF === "true";
    if (st.syncF) filters.sub2_status = st.syncF;
    if (st.statesF.length) filters.account_states = st.statesF;
    if (st.healthF) filters.sub2_health = st.healthF;
    if (st.importedFrom) filters.imported_from = st.importedFrom;
    if (st.importedBefore) filters.imported_before = st.importedBefore;
    if (st.creditsMin !== "" || st.creditsMax !== "") {
      filters.credits_field = st.creditsField;
      if (st.creditsMin !== "") filters.credits_min = Number(st.creditsMin);
      if (st.creditsMax !== "") filters.credits_max = Number(st.creditsMax);
    }
    if (st.profileF) filters.current_profile = st.profileF;
    if (st.companyF === "true" || st.companyF === "false") filters.is_company = st.companyF === "true";
    if (st.companyF) filters.account_type = {true:'company',false:'non_company',vietnam:'vietnam'}[st.companyF];
    if (st.groupF !== "" && st.groupF != null) filters.group_id = Number(st.groupF);
    return filters;
  }
  function qs() {
    var a = [];
    if (st.statusF) a.push("login_status=" + encodeURIComponent(st.statusF));
    if (st.subF !== "") a.push("subscription_ok=" + st.subF);
    if (st.q) a.push("keyword=" + encodeURIComponent(st.q));
    var filters = extraFilters();
    Object.keys(filters).forEach(function (key) { (Array.isArray(filters[key]) ? filters[key] : [filters[key]]).forEach(function (value) { a.push(key + "=" + encodeURIComponent(value)); }); });
    return a;
  }

  function jobApi(path, opts) { opts = opts || {}; opts.base = "/api/adobe-accounts/jobs"; return api(path, opts); }
  function spinner() { return '<span class="extm-spin" aria-hidden="true"></span>'; }
  function setLoading(btn, busy, text, spinning) { if (!btn) return; if (view && view.ownsButton(btn.id)) { view.button(btn.id, {disabled:busy, loading:spinning === undefined ? busy : spinning, text:text}); return; } btn.disabled = busy; btn.setAttribute("aria-busy", String(busy)); btn.innerHTML = ((spinning === undefined ? busy : spinning) ? spinner() : "") + esc(text); }
  function rowById(id) { return st.rows.find(function (r) { return r.id === id; }); }
  function activeJob(j) { return !!j && ["running", "pausing", "paused", "cancelling"].includes(j.status); }
  function running(r) { return st.pending.has(r.id) || activeJob(r.latest_job) || !!r.otp_challenge; }
  function loginProgress(r) {
    var job = r.latest_job, item = job && job.extra && (job.extra.items || []).find(function (i) { return i.id === r.id; });
    var phase = st.pending.has(r.id) ? 'submitting' : r.otp_challenge ? 'otp' : job && (job.item_status || (item && item.status));
    if (activeJob(job) && (!phase || ['pending', 'running'].includes(phase))) {
      phase = ['paused', 'pausing', 'cancelling'].includes(job.status) ? job.status : (phase || 'running');
    }
    if (job && !activeJob(job) && ['pending', 'running'].includes(phase)) {
      phase = job.status === 'cancelled' ? 'cancelled' : job.status === 'error' ? 'failed' : 'interrupted';
    }
    var states = {submitting:['提交中','info',true], pending:['排队中','warn',false], running:['登录中','info',true],
      otp:['等待验证码','warn',false], done:['本轮成功','ok',false], failed:['本轮失败','bad',false],
      interrupted:['已中断','warn',false], cancelled:['已终止','mut',false], paused:['已暂停','warn',false],
      pausing:['暂停中','info',false], cancelling:['终止中','info',false]};
    var state = states[phase];
    return state ? {label:state[0], tone:state[1], spinning:state[2],
      message:st.pending.has(r.id) ? '正在提交任务…' : r.otp_challenge ? '等待手动验证码' :
        (job && job.item_message) || (item && item.message) || ''} : null;
  }
  function detailState(id) { return st.details[id] || (st.details[id] = { jobs: [], historyPage: 1, historySize: 200, checked: new Set(), manage: false, closing: false, closeTimer: null, selected: null, job: null, auto: true, scope: "member", loading: false, action: false, error: "" }); }
  function jobPill(job) {
    var m = { running: ["info", "运行中"], pausing: ["info", "暂停中"], paused: ["warn", "已暂停"], cancelling: ["info", "终止中"], done: [job.fail ? "bad" : "ok", job.fail ? (job.success ? "部分失败" : "失败") : "已完成"], error: ["bad", "失败"], cancelled: ["mut", "已终止"] }[job.status] || ["mut", job.status];
    return '<span class="extm-pill ' + m[0] + '">' + esc(m[1]) + '</span>';
  }
  function setHTML(node, html) { if (node && node._html !== html) { node.innerHTML = html; node._html = html; } }
  function setText(node, value) { if (node && node.textContent !== String(value)) node.textContent = value; }

  function pageCount() { return Math.max(1, Math.ceil(st.total / st.size)); }
  function renderPagination() {
    if (!view) return;
    var pages = pageCount(), busy = !!st.loadingSeq || st.profileSaving.size > 0 || st.noteSaving;
    var start = st.rows.length ? (st.page - 1) * st.size + 1 : 0;
    view.update({total:st.total, loading:!!st.loadingSeq});
    view.pagination({page:st.page, pages:pages, size:st.size, total:st.total, start:start, end:st.rows.length ? start + st.rows.length - 1 : 0, busy:busy});
    ['extm-first','extm-prev'].forEach(function (id) { view.button(id, {disabled:busy || st.page <= 1}); });
    ['extm-last','extm-next'].forEach(function (id) { view.button(id, {disabled:busy || st.page >= pages}); });
    view.button('extm-page-go', {disabled:busy});
  }
  function resetPage(page) {
    ++st.loadSeq; st.page = page; st.rows = []; st.loadError = ""; st.sel.clear(); st.expanded.clear();
    Object.keys(st.details).forEach(function (id) { clearTimeout(st.details[id].closeTimer); });
    st.details = {};
    renderRows();
  }
  function goPage(page) {
    if (st.loadingSeq || st.profileSaving.size || st.noteSaving || !Number.isInteger(page)) return;
    page = Math.max(1, Math.min(page, pageCount()));
    if (page === st.page) return;
    resetPage(page); load();
  }

  function load(silent) {
    var body = el("extm-tbody"); if (!body) return Promise.resolve();
    if (st.profileSaving.size || st.noteSaving || (silent && st.loadingSeq)) return Promise.resolve();
    var seq = ++st.loadSeq;
    if (st.loadController) st.loadController.abort();
    var controller = st.loadController = new AbortController();
    if (!silent) st.loadingSeq = seq;
    renderPagination();
    if (!st.rows.length && !silent) body.innerHTML = '<tr><td colspan="11" class="extm-empty" aria-hidden="true"></td></tr>';
    return api("/members?" + qs().concat(["page=" + st.page, "size=" + st.size]).join("&"), {controller:controller}).then(function (d) {
      if (seq !== st.loadSeq) return;
      st.loadError = "";
      st.total = d.total != null ? d.total : (d.items || []).length;
      view.update({total:st.total});
      if (st.page > pageCount()) { resetPage(pageCount()); return load(); }
      var previousRows = new Map(st.rows.map(function (row) { return [row.id, row]; }));
      var rows = d.items || [];
      // A delivery receipt can be newer than the 30-second inventory cache.
      // Recheck remotely once per changed receipt; never infer stock from it.
      var deliveryChanged = rows.some(function (row) {
        var previous = previousRows.get(row.id);
        return previous && (
          (row.sub2_synced_at && row.sub2_synced_at !== previous.sub2_synced_at) ||
          (row.sub2_account_id && row.sub2_account_id !== previous.sub2_account_id) ||
          (row.sub2_status === 'synced' && previous.sub2_status !== 'synced')
        );
      });
      st.rows = rows;
      var visible = new Set(st.rows.map(function (r) { return r.id; }));
      st.sel.forEach(function (id) { if (!visible.has(id)) st.sel.delete(id); });
      renderRows();
      if (deliveryChanged) refreshStock(true);
    }).catch(function (e) {
      if (seq !== st.loadSeq || e.name === 'AbortError') return;
      if (!st.rows.length) { st.loadError = e.message; renderRows(); }
      else opMsg("搜索失败: " + e.message + "，当前显示上次结果", "err");
    }).finally(function () {
      if (st.loadController === controller) st.loadController = null;
      if (st.loadingSeq === seq) st.loadingSeq = 0;
      if (seq === st.loadSeq && !st.rows.length) renderRows();
      else renderPagination();
    });
  }

  async function refreshAll(force) {
    if (st.polling) return;
    st.polling = true;
    try {
      await load(!force);
    } finally { st.polling = false; }
    // Slow history/log requests must not hold the account list's polling lock.
    // Each detail already coalesces its own requests in refreshDetail.
    await Promise.all(Array.from(st.expanded).filter(function (id) { return rowById(id) && (force || detailState(id).auto); }).map(function (id) { return refreshDetail(id); }));
  }

  function refreshStock(force) {
    if (!st.open || document.hidden) return Promise.resolve();
    if (st.stockPromise) return force ? st.stockPromise.then(function () { return refreshStock(true); }) : st.stockPromise;
    var epoch = st.stockEpoch;
    st.stockPromise = api('/members/sub2-stock' + (force ? '?refresh=true' : '')).then(function (data) {
      if (epoch === st.stockEpoch) st.stock = data;
    }).catch(function () {
      if (epoch === st.stockEpoch) st.stock = {ok: false, configured: true, message: 'Sub2 库存查询失败，请检查连接后重试'};
    }).finally(function () {
      st.stockPromise = null;
      if (epoch === st.stockEpoch && st.open) renderRows();
    });
    return st.stockPromise;
  }

  function renderRows() {
    var body = el("extm-tbody"); if (!body) return;
    var waiting = st.rows.filter(function (r) { return !!r.otp_challenge; }).length;
    el('extm-otp-notice').hidden = !waiting;
    setText(el('extm-otp-notice'), '当前列表有 ' + waiting + ' 个账号等待手动验证码，请点击账号行的「填验证码」继续登录。');
    updateOtpDialog();
    if (!st.rows.length) { body.innerHTML = '<tr><td colspan="11" class="extm-empty"' + (st.loadError ? ' style="color:#d03050"' : '') + '>' + esc(st.loadError || (st.loadingSeq ? '' : '暂无匹配的外部子号')) + '</td></tr>'; updSel(); return; }
    Array.prototype.forEach.call(body.querySelectorAll(":scope > tr"), function (tr) {
      var id = Number(tr.dataset.member || tr.dataset.detail);
      if (!rowById(id) || (tr.dataset.detail && !st.expanded.has(id) && !detailState(id).closing)) tr.remove();
    });
    // Keep unchanged rows attached in place so polling cannot interrupt a fold transition.
    var cursor = body.firstElementChild;
    st.rows.forEach(function (r) {
      var tr = body.querySelector('tr[data-member="' + r.id + '"]');
      if (!tr) { tr = document.createElement("tr"); tr.dataset.member = r.id; }
      var busy = running(r), saving = st.profileSaving.has(r.id), expanded = st.expanded.has(r.id), progress = loginProgress(r);
      tr.className = expanded ? "extm-expanded" : "";
      var message = progress ? progress.message : r.message;
      var hideMessage = !message || (r.login_status === 'ok' && /^登录成功(?:；已提交 Sub2 推送(?:，可查看账号同步状态)?)?$/.test(message.trim()));
      setHTML(tr,
        '<td class="extm-select-cell"><input type="checkbox" class="extm-rowck" data-id="' + r.id + '" aria-label="选择 ' + esc(r.email) + '"' + (st.sel.has(r.id) ? ' checked' : '') + '></td>' +
        '<td><button class="extm-link extm-toggle" data-expand="' + r.id + '" aria-label="' + (expanded ? '收起' : '展开') + ' ' + esc(r.email) + ' 的任务详情" aria-expanded="' + expanded + '" aria-controls="extm-detail-' + r.id + '">' + window.OKAD_ICONS.svg('chevron', 16) + '</button></td>' +
        '<td><div class="extm-email-row"><button class="extm-link extm-clip extm-email" data-copy-email="' + r.id + '" title="点击复制账号：' + esc(r.email) + '" aria-label="复制账号 ' + esc(r.email) + '">' + esc(r.email) + '</button>' + (r.group_name ? '<span class="extm-group-tag" title="自定义分组：' + esc(r.group_name) + '">' + esc(r.group_name) + '</span>' : '') + (r.uses_supply_mail ? '<span class="extm-company-tag" title="验证码通过 supply.ink 取信">' + window.OKAD_ICONS.svg('tag', 12) + '公司</span>' : '') + '</div><div class="extm-account-meta">' + sub2Pill(r) + '<button class="extm-link extm-mode-link" data-otp-settings="' + r.id + '" aria-label="修改 ' + esc(r.email) + ' 的验证码获取方式" title="点击修改验证码获取方式"' + (busy || saving ? ' disabled' : '') + '>' + window.OKAD_ICONS.svg('settings', 11) + (r.otp_mode === 'vietnam' ? '越南登录' : r.otp_mode === 'manual' ? '手动验证码' : '自动取码') + '</button></div></td>' +
        '<td>' + creditCell(r) + '</td><td><button class="extm-link extm-profile-toggle" data-expand="' + r.id + '" title="' + esc(r.account_profile && r.account_profile.fallback_reason ? '回退个人配置原因：' + r.account_profile.fallback_reason : '展开查看账号配置') + '">' + profilePill(r.account_profile) + '</button></td>' +
        '<td><div class="extm-status" style="flex-wrap:wrap">' + healthPills(r) +
          '<span class="extm-cap ' + (r.has_cookie ? 'ok' : 'no missing') + '">' + (r.has_cookie ? '有 Cookie' : '无 Cookie') + '</span>' +
          '<span class="extm-cap ' + (r.has_adobe_password ? 'ok' : 'no') + '" title="Adobe 密码">' + (r.has_adobe_password ? '有密码' : '无密码') + '</span>' +
          (progress ? '<span class="extm-pill ' + progress.tone + '">' + esc(progress.label) + '</span>' : r.login_status === 'ok' ? '<button class="extm-pill ok extm-success" data-expand="' + r.id + '" title="' + esc(r.message || '登录成功，展开查看任务详情') + '">' + window.OKAD_ICONS.svg('check', 14) + '登录成功</button>' : statusPill(r.login_status)) +
          (hideMessage ? '' : '<button class="extm-link extm-clip" data-expand="' + r.id + '" title="' + esc(message || "展开查看任务详情") + '">' + esc(message || "展开查看详情") + '</button>') + '</div></td>' +
        '<td data-subscription>' + subPill(r) + '</td>' +
        '<td class="cr">' + esc(fmtTime(r.created_at)) + '</td><td class="cr">' + esc(fmtTime(r.last_login_at)) + '</td>' +
        '<td class="cr" data-sub2-pushed-at>' + esc(fmtTime(r.sub2_synced_at, true)) + '</td>' +
        '<td><div class="extm-actions"><button class="extm-btn dft sm" data-note="' + r.id + '" aria-label="编辑 ' + esc(r.email) + ' 的备注">备注</button><button class="extm-btn dft sm" data-mail="' + r.id + '" aria-label="查看 ' + esc(r.email) + ' 的邮件">邮件</button>' + (r.otp_challenge ? '<button class="extm-btn sm" data-otp="' + r.id + '">填验证码</button>' : '<button class="extm-btn o sm" data-login="' + r.id + '" aria-busy="' + !!(progress && progress.spinning) + '"' + (busy || saving ? ' disabled' : '') + '>' + (busy ? (progress && progress.spinning ? spinner() : '') + (progress ? progress.label : '排队中') : '重登') + '</button>') +
        '<button class="extm-btn del sm" data-del="' + r.id + '"' + (busy || saving ? ' disabled' : '') + '>删除</button></div></td>');
      var cb = tr.querySelector(".extm-rowck"); cb.checked = st.sel.has(r.id);
      if (tr !== cursor) body.insertBefore(tr, cursor);
      cursor = tr.nextElementSibling;
      if (expanded || detailState(r.id).closing) {
        var fresh = false;
        var detail = body.querySelector('tr[data-detail="' + r.id + '"]');
        if (!detail) { fresh = true; detail = document.createElement("tr"); detail.dataset.detail = r.id; detail.className = "extm-detail-row"; detail.innerHTML = '<td><div class="extm-fold is-closed"><div class="extm-fold-clip"><div class="extm-detail" id="extm-detail-' + r.id + '"></div></div></div></td>'; }
        detail.firstElementChild.colSpan = 11;
        if (detail !== cursor) body.insertBefore(detail, cursor);
        cursor = detail.nextElementSibling;
        renderDetail(r.id);
        if (expanded) {
          var state = detailState(r.id), fold = detail.querySelector('.extm-fold');
          clearTimeout(state.closeTimer); state.closing = false;
          if (fresh) fold.getBoundingClientRect();
          fold.classList.remove('is-closed'); fold.removeAttribute('aria-hidden'); fold.inert = false;
        }
      }
    });
    body.onchange = function (e) {
      if (!e.target.matches(".extm-rowck")) return;
      var id = Number(e.target.dataset.id); if (e.target.checked) st.sel.add(id); else st.sel.delete(id); updSel();
    };
    body.onclick = function (e) {
      var b = e.target.closest("button"); if (!b || b.disabled) return;
      if (b.hasAttribute("data-expand")) toggleDetail(Number(b.dataset.expand));
      if (b.hasAttribute("data-credit-error")) showCreditError(Number(b.dataset.creditError));
      if (b.hasAttribute('data-sub2-details')) showSub2Details(Number(b.dataset.sub2Details));
      if (b.hasAttribute("data-copy-email")) copyEmail(Number(b.dataset.copyEmail));
      if (b.hasAttribute('data-otp-settings')) editOtpMode(Number(b.dataset.otpSettings));
      if (b.hasAttribute("data-note")) editNote(Number(b.dataset.note));
      if (b.hasAttribute('data-mail')) showMail(Number(b.dataset.mail));
      if (b.hasAttribute('data-otp')) showOtp(Number(b.dataset.otp));
      if (b.hasAttribute("data-login")) reloginOne(Number(b.dataset.login));
      if (b.hasAttribute("data-del")) doDelete([Number(b.dataset.del)]);
    };
    updSel();
    renderSub2Details();
  }

  function editOtpMode(id) {
    var row = rowById(id); if (!row || running(row) || st.profileSaving.has(id) || el('extm-mode-dialog')) return;
    var dialog = document.createElement('dialog'); dialog.id = 'extm-mode-dialog'; dialog.className = 'extm-note-dialog extm-mode-dialog'; dialog.setAttribute('aria-labelledby', 'extm-mode-title');
    dialog.innerHTML = '<form><h3 id="extm-mode-title">验证码获取方式</h3><p>' + esc(row.email) + '</p><label for="extm-member-mode">取码方式</label><select id="extm-member-mode" class="extm-in" data-otp-mode="' + id + '"><option value="auto">自动取码</option><option value="manual">手动填写验证码</option><option value="vietnam">越南登录（密码 + 自动接码）</option></select><p class="extm-mode-help">自动取码使用已有邮箱配置或 supply.ink；普通邮箱可手动填写。越南登录需要已保存的 Adobe 密码，出现邮箱验证时自动接码，仅适用于越南取码站支持的账号。</p><div class="extm-note-error" role="alert"></div><footer><button type="button" class="extm-btn dft" data-close>取消</button><button type="submit" class="extm-btn">保存设置</button></footer></form>';
    var select = dialog.querySelector('select'), save = dialog.querySelector('[type=submit]'), cancel = dialog.querySelector('[data-close]'), error = dialog.querySelector('[role=alert]'), busy = false;
    select.value = row.otp_mode || 'auto';
    cancel.onclick = function () { dialog.close(); };
    dialog.oncancel = function (event) { if (busy) event.preventDefault(); };
    dialog.onclose = function () { dialog.remove(); var button = document.querySelector('[data-otp-settings="' + id + '"]'); if (st.open && button && !button.disabled) button.focus({preventScroll:true}); };
    dialog.querySelector('form').onsubmit = async function (event) {
      event.preventDefault(); if (busy) return;
      busy = true; select.disabled = cancel.disabled = true; setLoading(save, true, '保存中');
      var result = await saveOtpMode(id, select.value);
      busy = false;
      if (!dialog.isConnected) return;
      if (result.ok) dialog.close();
      else { error.textContent = result.message; select.disabled = cancel.disabled = false; setLoading(save, false, '保存设置'); }
    };
    document.body.appendChild(dialog); dialog.showModal(); select.focus();
  }

  async function saveOtpMode(id, mode) {
    var row = rowById(id);
    if (!row || running(row) || st.profileSaving.has(id)) { renderRows(); return {ok:false, message:'该账号正在登录，请等待任务结束后修改'}; }
    st.profileSaving.add(id); renderRows();
    try {
      var data = await api('/members/' + id + '/otp-mode', {method:'PATCH', body:{otp_mode:mode}});
      row.otp_mode = data.otp_mode; toast('success', data.message); return {ok:true};
    } catch (e) { toast('error', e.message); return {ok:false, message:e.message}; }
    finally { st.profileSaving.delete(id); await load(true); }
  }

  function updateOtpDialog() {
    if (!st.otpDialog) return;
    var row = rowById(st.otpDialog.id);
    if (row) st.otpDialog.update(row.otp_challenge);
  }
  async function showOtp(id) {
    if (el('extm-otp-dialog') || st.otpOpening) return;
    st.otpOpening = true;
    var challenge;
    try {
      challenge = (await api('/members/' + id + '/otp')).challenge;
      if (!st.open) return;
      if (!challenge) { toast('warning', '该账号当前没有等待验证码，请刷新查看登录结果'); await load(true); return; }
    } catch (e) { toast('error', e.message); return; }
    finally { st.otpOpening = false; }
    var dialog = document.createElement('dialog'); dialog.id = 'extm-otp-dialog'; dialog.className = 'extm-note-dialog extm-otp-dialog';
    dialog.setAttribute('aria-labelledby', 'extm-otp-title');
    dialog.innerHTML = '<form><h3 id="extm-otp-title">输入邮箱验证码</h3><p></p><label for="extm-otp-input">Adobe 邮件中的 6 位验证码</label><input id="extm-otp-input" class="extm-in" type="text" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" required placeholder="6 位数字"><div class="extm-otp-time" role="status"></div><div class="extm-note-error" role="alert"></div><footer><button type="button" class="extm-btn dft" data-close>稍后填写</button><button type="submit" class="extm-btn">提交并继续登录</button></footer></form>';
    dialog.querySelector('p').textContent = challenge.email;
    var form = dialog.querySelector('form'), input = form.querySelector('input'), submit = form.querySelector('[type=submit]'), countdown = form.querySelector('[role=status]'), error = form.querySelector('[role=alert]');
    var expired = false, submitting = false;
    function invalidate(message) { expired = true; input.value = ''; input.disabled = true; submit.disabled = true; error.textContent = message; }
    function tick() {
      var remaining = Math.max(0, Math.ceil(challenge.expires_at - Date.now()/1000));
      countdown.textContent = remaining ? '剩余 ' + remaining + ' 秒；可关闭后从账号行重新填写。' : '请求已过期';
      if (!remaining) invalidate('验证码等待已过期，请重新登录获取新验证码');
    }
    st.otpDialog = {id:id, update:function (current) {
      if (!submitting && (!current || current.request_id !== challenge.request_id)) invalidate('本次验证码请求已结束，请关闭窗口查看登录结果');
    }};
    form.onsubmit = async function (e) {
      e.preventDefault(); if (expired || submitting) return;
      if (!/^[0-9]{6}$/.test(input.value)) { error.textContent = '请输入 6 位数字验证码'; return; }
      submitting = true; setLoading(submit, true, '正在提交…'); error.textContent = '';
      try {
        var data = await api('/members/' + id + '/otp', {method:'POST', body:{request_id:challenge.request_id, code:input.value}});
        input.value = ''; toast('success', data.message); dialog.close(); await load(true);
      } catch (e) { error.textContent = e.message; }
      finally { submitting = false; if (!expired) setLoading(submit, false, '提交并继续登录'); }
    };
    var timer = setInterval(tick, 1000);
    form.querySelector('[data-close]').onclick = function () { dialog.close(); };
    dialog.addEventListener('close', function () { clearInterval(timer); input.value = ''; st.otpDialog = null; dialog.remove(); });
    document.body.appendChild(dialog); dialog.showModal(); tick(); input.focus();
  }

  function mailState(config) {
    view.update({mailState:config.configured ? '已配置' : '未配置', mailPlaceholder:config.configured ? '已保存；粘贴新 Token 可替换' : '粘贴 supply.ink Token'});
  }
  function loadMailConfig() {
    return api('/mail/config').then(mailState).catch(function () { view.update({mailState:'配置读取失败'}); });
  }
  async function mailAction(action) {
    if (st.mailSaving) return;
    if (action === 'save' && !view.form.mailToken.trim()) { view.update({mailResult:'请先粘贴 supply.ink Token'}); return; }
    st.mailSaving = true;
    ['save', 'test', 'clear'].forEach(function (key) { view.button('extm-mail-' + key, {disabled:true, loading:key === action}); });
    view.update({mailResult:action === 'test' ? '正在测试已保存的邮件连接…' : '正在保存…'});
    try {
      if (action === 'test') {
        var data = await api('/mail/test', {method:'POST'});
        view.update({mailResult:data.message + ' · 可查询 ' + data.total + ' 个账号'});
      } else {
        var config = await api('/mail/config', {method:'PUT', body:action === 'clear' ? {clear_token:true} : {token:view.form.mailToken.trim()}});
        mailState(config); view.form.mailToken = '';
        view.update({mailResult:action === 'clear' ? '邮件 Token 已清除' : '邮件 Token 已保存'});
      }
    } catch (e) { view.update({mailResult:e.message}); }
    finally {
      st.mailSaving = false;
      ['save', 'test', 'clear'].forEach(function (key) { view.button('extm-mail-' + key, {disabled:false, loading:false}); });
    }
  }
  function showMail(id) {
    var row = rowById(id); if (!row || el('extm-mail-dialog')) return;
    var dialog = document.createElement('dialog'); dialog.id = 'extm-mail-dialog'; dialog.className = 'extm-note-dialog';
    dialog.style.width = 'min(760px,calc(100vw - 40px))'; dialog.setAttribute('aria-labelledby', 'extm-mail-title');
    dialog.innerHTML = '<h3 id="extm-mail-title">最近邮件</h3><p></p><div data-messages role="status"></div><footer><button type="button" class="extm-btn dft" data-refresh>刷新邮件</button><button type="button" class="extm-btn" data-close>关闭</button></footer>';
    dialog.querySelector('p').textContent = row.email + ' · supply.ink 最近 5 封邮件';
    var refresh = dialog.querySelector('[data-refresh]'), messages = dialog.querySelector('[data-messages]');
    async function fetchMessages() {
      if (refresh.disabled) return;
      refresh.disabled = true; messages.textContent = '正在获取邮件…';
      try {
        var data = await api('/members/' + id + '/mail');
        if (!dialog.isConnected) return;
        messages.replaceChildren();
        if (!data.messages.length) messages.textContent = '该账号暂无邮件，稍后点击刷新。';
        data.messages.forEach(function (mail) {
          var details = document.createElement('details'), summary = document.createElement('summary'), pre = document.createElement('pre');
          summary.textContent = (mail.subject || '（无主题）') + ' · ' + fmtTime(mail.date);
          pre.textContent = mail.body || '接口未返回正文'; pre.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.7 system-ui';
          details.style.cssText = 'padding:12px 0;border-bottom:1px solid var(--ws-line,#e4eaf2)';
          details.append(summary, pre); messages.appendChild(details);
        });
      } catch (e) { if (dialog.isConnected) messages.textContent = e.message; }
      finally { refresh.disabled = false; }
    }
    refresh.onclick = fetchMessages; dialog.querySelector('[data-close]').onclick = function () { dialog.close(); };
    dialog.addEventListener('close', function () { dialog.remove(); });
    document.body.appendChild(dialog); dialog.showModal(); fetchMessages();
  }

  function editNote(id) {
    var row = rowById(id); if (!row || el('extm-note-dialog')) return;
    var dialog = document.createElement('dialog'); dialog.id = 'extm-note-dialog'; dialog.className = 'extm-note-dialog';
    dialog.setAttribute('aria-labelledby', 'extm-note-title');
    dialog.innerHTML = '<form><h3 id="extm-note-title">编辑备注</h3><p>' + esc(row.email) + '</p>' +
      '<label for="extm-note-input">备注内容</label><textarea id="extm-note-input" class="extm-ta" maxlength="1000" placeholder="填写这个账号的备注…"></textarea>' +
      '<div class="extm-note-help"><span>最多 1000 字，清空后保存即可删除备注</span><span id="extm-note-count"></span></div>' +
      '<div class="extm-note-error" role="alert"></div><footer><button class="extm-btn dft" type="button">取消</button><button class="extm-btn" type="submit">保存备注</button></footer></form>';
    el(HOST_ID).appendChild(dialog);
    var form = dialog.querySelector('form'), input = dialog.querySelector('textarea'), error = dialog.querySelector('[role=alert]');
    var cancel = dialog.querySelector('[type=button]'), save = dialog.querySelector('[type=submit]'), busy = false;
    input.value = row.note || '';
    input.oninput = function () { setText(el('extm-note-count'), input.value.length + '/1000'); }; input.oninput();
    cancel.onclick = function () { if (!busy) dialog.close(); };
    dialog.addEventListener('cancel', function (event) { if (busy) event.preventDefault(); });
    dialog.addEventListener('close', function () {
      dialog.remove();
      var button = document.querySelector('[data-note="' + id + '"]');
      if (st.open && button) button.focus({ preventScroll: true });
    });
    form.onsubmit = async function (event) {
      event.preventDefault(); if (busy) return;
      busy = true; st.noteSaving = true; ++st.loadSeq; error.textContent = '';
      input.disabled = cancel.disabled = true; setLoading(save, true, '保存中…');
      try {
        var result = await api('/members/' + id + '/note', { method: 'PATCH', body: { note: input.value } });
        var current = rowById(id); if (current) current.note = result.note;
        renderRows(); dialog.close(); toast('success', result.note ? '备注已保存' : '备注已清空');
      } catch (e) { error.textContent = '保存失败：' + e.message; }
      finally { busy = false; st.noteSaving = false; input.disabled = cancel.disabled = false; setLoading(save, false, '保存备注'); await load(true); }
    };
    dialog.showModal(); input.focus();
  }

  async function saveSelectedProfilePreference(preference) {
    var ids = selIds(), rows = ids.map(rowById);
    if (!ids.length || !['', 'personal', 'organization'].includes(preference) || st.profileSaving.size || st.loginAllSubmitting) return;
    if (rows.some(function (row) { return !row || running(row); })) { updSel(); toast('warning', '请等待所选账号的登录任务结束'); return; }
    ids.forEach(function (id) { st.profileSaving.add(id); }); ++st.loadSeq; renderRows();
    try {
      var result = await api('/members/login-profile', { method: 'PATCH', body: { ids: ids, profile_preference: preference } });
      rows.forEach(function (row) { row.profile_preference = result.profile_preference; });
      toast('success', result.message);
    } catch (e) {
      toast('error', '登录配置保存失败：' + e.message);
    } finally { ids.forEach(function (id) { st.profileSaving.delete(id); }); renderRows(); await load(true); }
  }

  function toggleDetail(id) {
    var d = detailState(id), panel = el('extm-detail-' + id);
    clearTimeout(d.closeTimer);
    if (st.expanded.has(id) && panel) {
      st.expanded.delete(id); d.closing = true;
      var row = panel.closest('tr[data-detail]'), fold = panel.closest('.extm-fold');
      renderRows();
      fold.getBoundingClientRect();
      fold.classList.add('is-closed');
      fold.setAttribute('aria-hidden', 'true'); fold.inert = true;
      var finish = function () {
        if (st.expanded.has(id)) return;
        d.closing = false; row.remove();
      };
      d.closeTimer = setTimeout(finish, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 300);
    } else {
      st.expanded.add(id); d.closing = false;
      renderRows();
      var openFold = el('extm-detail-' + id).closest('.extm-fold');
      openFold.classList.remove('is-closed'); openFold.removeAttribute('aria-hidden'); openFold.inert = false;
      refreshDetail(id, true);
    }
  }

  function logLevel(line) {
    // Failure counts of zero in task summaries are not errors.
    if (/✗|×|失败(?!\s*[:：=]?\s*0(?:\D|$))|错误|异常|(?:^|[\s\[])(?:ERROR|FATAL|EXCEPTION)(?:[\s\]:]|$)|\b(?:HTTP|status)[\s=:]+[45]\d{2}\b/i.test(line)) return 'error';
    if (/⚠|警告|\bWARN(?:ING)?\b|超时|重试|限流|掉订阅|额度.*偏低|不可用|未能|无可用/i.test(line)) return 'warn';
    if (/✓|✔|成功|已完成|完成[:：]/.test(line)) return 'success';
    if (/开始|正在|等待|扫描|发送|获取|读取|刷新/.test(line)) return 'progress';
    return 'info';
  }
  function renderLogLine(line) {
    var level = logLevel(line), time = /^(\d{2}:\d{2}:\d{2})(\s+)([\s\S]*)$/.exec(line);
    var body = esc(time ? time[3] : line).replace(/\[[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\]/g, '<span class="extm-log-account">$&</span>');
    return '<span class="extm-log-line extm-log-' + level + '" data-level="' + level + '">' +
      (time ? '<span class="extm-log-time">' + time[1] + '</span>' + time[2] : '') + body + '</span>';
  }

  function profilePill(p) {
    var kind = p && p.current_kind;
    return '<span class="extm-pill ' + (kind === 'organization' ? 'organization' : kind === 'personal' ? 'personal' : 'mut') + '">' +
      (kind === 'organization' ? '组织配置' : kind === 'personal' ? '个人配置' : '未获取') + '</span>' +
      (kind === 'personal' && p.fallback_reason ? '<span class="extm-pill warn" data-profile-fallback title="' + esc(p.fallback_reason) + '">已回退个人</span>' : '');
  }
  function profileDetail(row) {
    var p = row.account_profile;
    var head = '<div class="extm-task-head"><strong>账号配置</strong>' + profilePill(p) + '<span class="sp"></span>' +
      (p ? '<span class="extm-msg mut">更新于 ' + esc(fmtTime(p.fetched_at)) + '</span>' : '') + '</div>';
    if (!p) return head + '<div class="extm-task-body extm-msg mut">尚未获取账号配置，重新登录后自动更新。</div>';
    function field(label, value) { return '<div><dt>' + esc(label) + '</dt><dd>' + esc(value || '未获取') + '</dd></div>'; }
    var html = head + '<div class="extm-task-body"><dl class="extm-profile-fields">' +
      field('当前配置名称', p.current_profile_name) + field('当前组织 ID', p.current_org_id || (p.current_kind === 'personal' ? '不适用（当前为个人配置）' : '')) +
      field('当前配置 ID', p.current_profile_id) + field('积分查询身份 ID', p.credits_account_id) + '</dl>' +
      (p.requested_preference ? '<p class="extm-msg mut">本次登录选择：' + (p.requested_preference === 'organization' ? '组织配置优先' : '个人配置') + '</p>' : '') +
      (p.fallback_reason ? '<p class="extm-profile-fallback-reason"><strong>回退个人配置原因：</strong>' + esc(p.fallback_reason) + '</p>' : '') +
      '<p class="extm-msg mut">以下为最近一次登录获取的资料。' + (p.profiles_complete ? '' : '部分资料未获取，列表可能不完整。') +
      (row.login_status !== 'ok' ? '本次未登录成功，保留上次资料。' : '') + '</p>' +
      '<div class="extm-profile-list-title">已获取的配置</div><div class="extm-profile-options">';
    html += (p.profiles || []).map(function (item) {
      var current = !!item.profile_id && item.profile_id === p.current_profile_id;
      return '<div class="extm-profile-option"><div>' + profilePill({current_kind:item.kind}) +
        '<strong>' + esc(item.name || '名称未获取') + '</strong>' + (current ? '<span class="extm-pill ok">当前使用</span>' : '') +
        '<span class="extm-msg mut">' + esc(({active:'已启用',disabled:'已停用',inactive:'未激活',invited:'邀请待激活',suspected_deleted:'疑似已删除',expired:'授权已过期'}[item.status]) || item.status || '状态未获取') + '</span></div>' +
        '<div class="extm-profile-id">配置 ID：' + esc(item.profile_id || '未获取') + (item.org_id ? ' · 组织 ID：' + esc(item.org_id) : '') + '</div></div>';
    }).join('') || '<p class="extm-msg mut">未获取配置列表</p>';
    html += '</div>';
    if ((p.subscription_owners || []).length) {
      html += '<div class="extm-profile-list-title">订阅关联身份</div><p class="extm-msg mut">仅表示订阅关联方，不代表当前正在使用该组织配置。</p><div class="extm-profile-owners">' +
        p.subscription_owners.map(function (owner) { return '<div>' + esc(owner.owner_id) + ' · ' + esc(owner.status || '状态未获取') + '</div>'; }).join('') + '</div>';
    }
    return html + '</div>';
  }

  function renderDetail(id) {
    var panel = el("extm-detail-" + id), row = rowById(id); if (!panel || !row) return;
    var d = detailState(id);
    if (!panel.dataset.ready) {
      panel.dataset.ready = "1";
      panel.innerHTML = '<section class="extm-profile-card extm-task-card" aria-label="账号配置详情"></section><div class="extm-detail-error" role="status"></div><div class="extm-task-layout">' +
        '<section class="extm-task-card"><div class="extm-task-head"><strong>任务历史</strong><span class="sp"></span><button class="extm-btn dft sm" data-action="manage" aria-pressed="false">管理历史</button><button class="extm-btn del sm" data-action="delete">删除选中</button></div>' +
        '<div class="extm-history-wrap"><table class="extm-history"><colgroup><col class="extm-history-select" style="width:30px"><col style="width:48px"><col style="width:92px"><col style="width:55px"><col></colgroup>' +
        '<thead><tr><th class="extm-history-select"></th><th>ID</th><th>状态</th><th>进度</th><th>时间</th></tr></thead><tbody></tbody></table></div><nav class="extm-history-pager"></nav></section>' +
        '<section class="extm-task-card"><div class="extm-task-head"><strong>任务详情</strong><div class="extm-task-actions"><label class="extm-auto"><input type="checkbox" data-auto checked>自动刷新</label><button class="extm-btn dft sm" data-action="refresh">刷新</button><button class="extm-btn dft sm" data-action="pause">暂停任务</button><button class="extm-btn del sm" data-action="cancel">终止任务</button></div></div>' +
        '<div class="extm-task-body"><div class="extm-job-title"></div><div class="extm-job-meta"></div><div class="extm-counts"></div><div class="extm-progress" role="progressbar" aria-label="任务进度"><div></div></div><div class="extm-detail-error extm-job-error"></div>' +
        '<div class="extm-log-tools"><span data-log-count>实时日志</span><span class="sp"></span><select class="extm-in" data-log-scope aria-label="日志范围"><option value="member">当前账号日志</option><option value="all">整批任务日志</option></select><button class="extm-btn dft sm" data-action="clear-logs">清空日志</button></div>' +
        '<div class="extm-log-legend" aria-label="日志颜色说明"><span><i class="success"></i>成功</span><span><i class="warn"></i>警告</span><span><i class="error"></i>错误</span><span><i class="progress"></i>进度</span><span><i class="info"></i>普通</span></div><pre class="extm-logs" tabindex="0" aria-label="任务日志"></pre><div class="extm-scope-note"></div></div></section></div>';
      d.updateHistoryPager = window.OKAD_PAGINATION.mountPager(panel.querySelector('.extm-history-pager'), {id:'extm-history-size-' + id,
        state:function () { return {page:d.historyPage, size:d.historySize, total:d.jobs.length, busy:d.action}; },
        onPage:function (value) { d.historyPage = value; d.checked.clear(); renderDetail(id); },
        onSize:function (value) { d.historySize = value; d.historyPage = 1; d.checked.clear(); renderDetail(id); }});
      panel.onclick = function (e) {
        var action = e.target.closest("[data-action]");
        if (action && !action.disabled) { taskAction(id, action.dataset.action); return; }
        var tr = e.target.closest("tr[data-job]");
        if (tr && !e.target.matches("input")) { d.selected = Number(tr.dataset.job); renderDetail(id); refreshDetail(id, true); }
      };
      panel.onchange = function (e) {
        if (e.target.hasAttribute("data-job-check")) { var jid = Number(e.target.dataset.jobCheck); if (e.target.checked) d.checked.add(jid); else d.checked.delete(jid); renderDetail(id); }
        if (e.target.hasAttribute("data-auto")) { d.auto = e.target.checked; if (d.auto) refreshDetail(id, true); }
        if (e.target.hasAttribute("data-log-scope")) { d.scope = e.target.value; renderDetail(id); }
      };
    }
    setHTML(panel.querySelector('.extm-profile-card'), profileDetail(row));
    panel.classList.toggle('extm-manage-history', d.manage);
    var manage = panel.querySelector('[data-action="manage"]');
    manage.setAttribute('aria-pressed', String(d.manage));
    setText(manage, d.manage ? '结束管理' : '管理历史');
    setText(panel.querySelector(":scope > .extm-detail-error"), d.error);
    var history = panel.querySelector(".extm-history tbody");
    d.historyPage = Math.min(d.historyPage, Math.max(1, Math.ceil(d.jobs.length / d.historySize)));
    if (d.updateHistoryPager) d.updateHistoryPager();
    setHTML(history, d.jobs.length ? d.jobs.slice((d.historyPage - 1) * d.historySize, d.historyPage * d.historySize).map(function (j) {
      return '<tr data-job="' + j.id + '" class="' + (j.id === d.selected ? 'active' : '') + '" aria-selected="' + (j.id === d.selected) + '">' +
        '<td class="extm-history-select"><input type="checkbox" data-job-check="' + j.id + '" aria-label="选择任务 #' + j.id + '"' + (d.checked.has(j.id) ? ' checked' : '') + (activeJob(j) ? ' disabled' : '') + '></td>' +
        '<td><button class="extm-link" title="查看任务 #' + j.id + '">#' + j.id + '</button></td><td>' + jobPill(j) + '</td>' +
        '<td title="成功 ' + j.success + '，失败 ' + j.fail + '">' + (j.success + j.fail) + '/' + j.target + '</td>' +
        '<td title="' + esc(fmtTime(j.created_at)) + '">' + esc(fmtTime(j.created_at).slice(5)) + '</td></tr>';
    }).join("") : '<tr><td colspan="' + (d.manage ? 5 : 4) + '" class="extm-empty">' + (d.loading ? '正在读取任务…' : '暂无关联任务，点击重登开始') + '</td></tr>');
    panel.querySelector("[data-auto]").checked = d.auto;
    panel.querySelector("[data-log-scope]").value = d.scope;
    var job = d.job && d.job.id === d.selected ? d.job : d.jobs.find(function (j) { return j.id === d.selected; });
    var selectedJobs = d.jobs.filter(function (j) { return d.checked.has(j.id) && !activeJob(j); });
    var del = panel.querySelector('[data-action="delete"]'); del.disabled = !selectedJobs.length || d.action; setText(del, '删除选中 (' + selectedJobs.length + ')');
    panel.querySelector('[data-action="refresh"]').disabled = d.loading || d.action;
    panel.querySelector('[data-action="cancel"]').disabled = !activeJob(job) || job.status === 'cancelling' || d.action;
    var pause = panel.querySelector('[data-action="pause"], [data-action="resume"]');
    var resumable = job && ['paused', 'pausing'].includes(job.status);
    pause.dataset.action = resumable ? 'resume' : 'pause';
    setText(pause, resumable ? '继续任务' : '暂停任务');
    pause.disabled = !job || !['running','pausing','paused'].includes(job.status) || d.action;
    pause.title = '暂停会等待当前账号完成，排队账号不再启动';
    panel.querySelector('[data-action="clear-logs"]').disabled = !job || !job.log_total || d.action;
    setHTML(panel.querySelector(".extm-job-title"), job ? '<strong>外部子号登录 · #' + job.id + '</strong>' + jobPill(job) : '<span class="extm-msg mut">' + (d.loading ? '正在加载…' : '选择历史任务查看详情') + '</span>');
    setHTML(panel.querySelector(".extm-job-meta"), job ? '<span>开始 <b>' + esc(fmtTime(job.created_at)) + '</b></span>' + (job.finished_at ? '<span>结束 <b>' + esc(fmtTime(job.finished_at)) + '</b></span>' : '') : '');
    var batch = job && job.extra && job.extra.batch;
    var oldBatch = panel.querySelector('[data-login-batch]'); if (oldBatch) oldBatch.remove();
    if (batch) panel.querySelector('.extm-job-meta').insertAdjacentHTML('beforeend', '<span data-login-batch>批次 <b>' + esc(batch.index) + '/' + esc(batch.total) + ' · 每批最多 ' + esc(batch.size) + ' 个</b></span>');
    var pct = job && job.target ? Math.min(100, Math.round((job.success + job.fail) / job.target * 100)) : 0;
    var progress = panel.querySelector('.extm-progress'); progress.setAttribute('aria-valuenow', pct); progress.setAttribute('aria-valuemin', '0'); progress.setAttribute('aria-valuemax', '100');
    progress.firstElementChild.style.width = pct + '%'; progress.firstElementChild.className = job && (job.fail || job.status === 'error') ? 'failed' : '';
    setHTML(panel.querySelector('.extm-counts'), job ? '<span>总进度 <b>' + (job.success + job.fail) + '/' + job.target + '</b></span><span class="extm-count-success">成功 <b>' + job.success + '</b></span><span class="' + (job.fail ? 'extm-count-fail' : 'extm-count-zero') + '">失败 <b>' + job.fail + '</b></span>' : '');
    setText(panel.querySelector('.extm-job-error'), job ? job.error || '' : '');
    var lines = job && job.logs || [];
    if (d.scope === 'member') lines = lines.filter(function (line) { return line.toLowerCase().includes(row.email.toLowerCase()) || line.includes('[id=' + id + ']') || !(/[\w.+-]+@[\w.-]+\.[a-z]{2,}|\[id=\d+\]/i.test(line)); });
    setText(panel.querySelector('[data-log-count]'), '实时日志 · ' + lines.length + ' / ' + (job ? job.log_total : 0) + ' 条');
    var logs = panel.querySelector('.extm-logs'), text = lines.join('\n') || (d.loading && (!d.job || d.job.id !== d.selected) ? '正在读取日志…' : '暂无日志');
    if (logs.textContent !== text) { var bottom = logs.scrollHeight - logs.scrollTop - logs.clientHeight < 35, top = logs.scrollTop; logs.innerHTML = lines.length ? lines.map(renderLogLine).join('\n') : esc(text); logs.scrollTop = bottom ? logs.scrollHeight : top; }
    setText(panel.querySelector('.extm-scope-note'), job && job.target > 1 ? '此任务包含 ' + job.target + ' 个账号；进度、暂停、终止、清空日志和删除均作用于整批任务。' : '任务历史显示最近 50 条，可在此查看完整日志和登录结果。');
  }

  function refreshDetail(id, force) {
    var d = detailState(id);
    if (d.loading) return d.promise.then(function () { if (force) return refreshDetail(id); });
    d.loading = true; d.error = ''; renderDetail(id);
    d.promise = api('/members/' + id + '/jobs?limit=10000').then(function (jobs) {
      d.jobs = jobs;
      d.checked.forEach(function (jid) { if (!jobs.some(function (j) { return j.id === jid && !activeJob(j); })) d.checked.delete(jid); });
      if (!jobs.some(function (j) { return j.id === d.selected; })) d.selected = jobs.length ? jobs[0].id : null;
      renderDetail(id);
      var selected = d.selected;
      if (!selected) { d.job = null; return; }
      return jobApi('/' + selected).then(function (job) { if (selected === d.selected) d.job = job; });
    }).catch(function (e) { d.error = '任务刷新失败: ' + e.message; }).finally(function () { d.loading = false; renderDetail(id); });
    return d.promise;
  }

  async function stopAllTasks() {
    if (st.stoppingAll) return;
    st.stoppingAll = true;
    setLoading(el('extm-stop-all'), true, '正在终止…');
    updSel();
    try {
      var result = await api('/members/cancel-all-jobs', {method:'POST'});
      toast(result.failed ? 'warning' : 'success', result.message);
      await load(true);
      await Promise.all(Array.from(st.expanded).filter(rowById).map(function (mid) { return refreshDetail(mid, true); }));
    } catch (e) { toast('error', '终止失败：' + e.message); }
    finally { st.stoppingAll = false; setLoading(el('extm-stop-all'), false, '终止所有任务'); updSel(); }
  }

  async function taskAction(id, action) {
    var d = detailState(id);
    if (d.action) return;
    if (action === 'manage') { d.manage = !d.manage; d.checked.clear(); renderDetail(id); return; }
    if (action === 'refresh') { await load(true); await refreshDetail(id, true); return; }
    var ids = action === 'delete' ? d.jobs.filter(function (j) { return d.checked.has(j.id) && !activeJob(j); }).map(function (j) { return j.id; }) : [d.selected];
    if (!ids.length || !ids[0]) return;
    var shared = d.jobs.some(function (j) { return ids.includes(j.id) && j.target > 1; });
    var verb = { delete: '删除任务及其日志', cancel: '终止任务（取消排队账号，当前请求返回后退出，保留已完成结果）', 'clear-logs': '清空日志' }[action];
    if (action !== 'pause' && action !== 'resume' && !confirm('确认' + verb + '？' + (shared ? '这些操作会影响同一批次中的所有账号。' : ''))) return;
    d.action = true; renderDetail(id);
    try {
      var result = await jobApi(action === 'delete' ? '/batch-delete' : '/' + ids[0] + '/' + action, { method: 'POST', body: action === 'delete' ? { ids: ids } : undefined });
      if (result.success === false) throw new Error(result.message);
      toast('success', result.message || '操作完成');
      if (action === 'delete') { d.checked.clear(); d.job = null; }
      await load(true);
      await Promise.all(Array.from(st.expanded).filter(rowById).map(function (mid) { return refreshDetail(mid, true); }));
    } catch (e) { d.error = e.message; toast('error', e.message); }
    finally { d.action = false; renderDetail(id); }
  }

  function updSel() {
    if (!view) return;
    renderPagination();
    var busy = st.rows.some(function (r) { return st.sel.has(r.id) && running(r); });
    var saving = Array.from(st.sel).some(function (id) { return st.profileSaving.has(id); });
    var selectedRows = st.rows.filter(function (row) { return st.sel.has(row.id); });
    var preferences = new Set(selectedRows.map(function (row) { return row.profile_preference || ''; }));
    view.button("extm-stop-all", {disabled:st.stoppingAll, loading:st.stoppingAll, text:st.stoppingAll ? "正在终止…" : "终止所有任务"});
    view.update({selected:st.sel.size,
      group:'__mixed__', groupSaving:!!st.groupSaving,
      profilePlaceholder:st.profileSaving.size ? '保存中…' : !st.sel.size ? '请先勾选账号' : '所选配置不一致',
      profile:!st.profileSaving.size && preferences.size === 1 ? selectedRows[0].profile_preference || '' : '__mixed__',
      profileDisabled:!st.sel.size || busy || st.profileSaving.size > 0 || !!st.loginAllSubmitting});
    view.button('extm-export', {disabled:!!st.exporting, loading:!!st.exporting, text:st.exporting ? '导出中…' : st.sel.size ? '导出选中 Cookie（' + st.sel.size + '）' : qs().length ? '导出筛选 Cookie' : '导出全部 Cookie'});
    view.button('extm-export-emails', {disabled:!!st.exportingEmails || !st.sel.size, loading:!!st.exportingEmails, text:st.exportingEmails ? '邮箱导出中…' : '导出选中邮箱' + (st.sel.size ? '（' + st.sel.size + '）' : '')});
    var all = el('extm-ckall'); if (all) { all.checked = !!st.rows.length && st.sel.size === st.rows.length; all.indeterminate = st.sel.size > 0 && st.sel.size < st.rows.length; }
    view.button('extm-batch-login', {disabled:busy || saving || !!st.loginAllSubmitting || st.stoppingAll || !st.sel.size,
      loading:busy && st.rows.some(function (r) {return st.sel.has(r.id) && running(r) && (!r.latest_job || r.latest_job.status !== 'paused');}),
      text:saving ? '配置保存中…' : busy ? '任务未结束' : '选中批量重登' + (st.sel.size ? '（' + st.sel.size + '）' : '')});
    view.button('extm-login-all', {disabled:!!st.loginAllSubmitting || st.stoppingAll || st.pending.size > 0 || st.profileSaving.size > 0, loading:!!st.loginAllSubmitting,
      text:st.loginAllSubmitting ? '提交重登中…' : qs().length ? '一键重登筛选结果' : '一键重登全部'});
    view.button('extm-batch-del', {disabled:busy || saving || !st.sel.size});
    var pushing = st.sub2Submitting || st.rows.some(function (r) {return st.sel.has(r.id) && ['pending','syncing'].includes(r.sub2_status);});
    ['extm-sub2-push','extm-sub2-relink'].forEach(function (id) {
      view.button(id, {disabled:!!pushing || !!st.sub2Confirming || !st.sel.size || busy, loading:!!pushing,
        text:pushing ? 'Sub2 同步中…' : id === 'extm-sub2-push' ? '推送 Sub2' : '重新关联 / 推送'});
    });
  }
  function selIds() { return Array.from(st.sel); }

  function sub2Stock(row) {
    var stock = st.stock, item = stock && stock.items && stock.items[row.id];
    if (item && String(item.email || '').trim().toLowerCase() !== row.email.trim().toLowerCase()) item = null;
    var tone = 'info', label = 'Sub2 库存查询中', tip = '正在按完整邮箱核对 Sub2 当前库存';
    if (stock && stock.ok && item) {
      tone = item.in_stock ? 'ok' : 'mut'; label = item.in_stock ? '在库 Sub2' : '未在库 Sub2';
      tip = (item.in_stock ? 'Sub2 中已存在此邮箱账号，可能由号池或其他入口导入' : '当前 Sub2 中未找到此邮箱账号') + ' · 核对时间 ' + fmtTime(stock.checked_at);
      if (item.account_ids && item.account_ids.length) tip += ' · 账号 #' + item.account_ids.join('、#');
    } else if (stock && !stock.ok) {
      tone = stock.configured === false ? 'mut' : 'warn';
      label = stock.configured === false ? 'Sub2 未配置' : 'Sub2 状态暂不可用';
      tip = stock.message || '暂时无法确认 Sub2 库存，请稍后刷新';
    }
    return {tone: tone, label: label, tip: tip};
  }

  function sub2Pill(row) {
    var stock = sub2Stock(row), tip = stock.tip;
    var detail = row.sub2_message || '';
    if (row.sub2_account_id) detail += ' · 账号 #' + row.sub2_account_id;
    if (row.sub2_synced_at) detail += ' · 上次同步 ' + fmtTime(row.sub2_synced_at);
    if (row.sub2_status === 'synced') tip += ' · 本页 Cookie 上次同步成功' + detail;
    var html = '<span data-sub2-stock class="extm-pill ' + stock.tone + '" style="margin-top:4px" title="' + esc(tip) + '">' + stock.label + '</span>';
    var state = { pending: ['warn', 'Sub2 待同步'], syncing: ['info', 'Sub2 同步中'], failed: ['bad', 'Sub2 同步失败'] }[row.sub2_status];
    var button = '<button type="button" class="extm-link extm-sub2-details" data-sub2-details="' + row.id + '" aria-haspopup="dialog" aria-label="查看 ' + esc(row.email) + ' 的 Sub2 同步详情">' + window.OKAD_ICONS.svg('info', 12) + '详情</button>';
    if (!state) return '<span class="extm-sub2-state">' + html + button + '</span>';
    return html + ' <span class="extm-sub2-state"><span class="extm-pill ' + state[0] + '" style="margin-top:4px" title="' + esc(detail) + '">' + state[1] + '</span>' + button + '</span>' +
      (row.sub2_status === 'failed' ? '<span class="extm-clip" style="font-size:12px;color:#d03050" title="' + esc(detail) + '">' + esc(row.sub2_message || '请重新推送') + '</span>' : '');
  }

  function sub2Explanation(row) {
    var status = row.sub2_status || 'not_pushed', message = (row.sub2_message || '').trim();
    if (status === 'pending' && message === 'Cookie 已写入，等待 Sub2 代理就绪') return {
      title: '已发送到 Sub2，正在等可用线路',
      reason: '账号的登录信息已经送到 Sub2。这个账号使用的网络线路暂时没有准备好，所以还不能检查账号能否使用。',
      action: '不用重新登录，也不用重复推送。请管理员在 Sub2 检查线路是否正常、有没有空位。线路准备好后，系统会自动继续检查。'
    };
    if (status === 'pending' && message === 'Cookie 已写入，等待重新验证') return {
      title: '已发送到 Sub2，正在等再次检查',
      reason: '账号的登录信息已经送到 Sub2，但这次还没能检查完账号是否可用。系统会保留登录信息，稍后再试。',
      action: '先等待系统自动重试，不用重新登录。若一直没有变化，请管理员查看 Sub2 中这个账号的检查结果和网络连接。'
    };
    if (status === 'pending' || status === 'syncing') return {
      title: status === 'syncing' ? '正在发送登录信息' : '正在排队处理',
      reason: '系统已收到同步请求，还没有返回完成结果。「在库 Sub2」只表示 Sub2 里有这个账号，不代表这次登录信息已经更新。',
      action: '先等一会儿，页面会自动更新。若一直没有变化，请管理员到「联动中心」查看这个账号的处理进度。'
    };
    if (status === 'failed') return {
      title: '这次没有完成，需要处理一下',
      reason: '发送登录信息或检查账号时遇到了问题。之前保存的登录信息还在，具体原因见下方「系统提示」。',
      action: /404|关联账号不存在|关联账号已删除/.test(message) ? '请管理员先确认 Sub2 中的账号是否被删除。确定要恢复时，再点击「更多操作 → 重新关联 / 推送」。' : '请管理员按系统提示处理问题，再勾选账号点击「推送 Sub2」重试。已有登录信息时，不用先重新登录。'
    };
    if (status === 'synced') return {
      title: '登录信息已更新',
      reason: 'Sub2 已收到登录信息。账号能不能正常使用，还要看 Sub2 中的检查结果。',
      action: '可以到 Sub2 查看这个账号。若显示暂停或异常，请按那里的提示处理。'
    };
    return {
      title: status === 'not_pushed' ? '还没有同步记录' : '暂时无法确认是否已完成',
      reason: '当前页面还不能确认登录信息是否已成功发送。Sub2 中即使已有这个邮箱，也可能还没收到这里的登录信息。',
      action: row.has_cookie ? '需要发送到 Sub2 时，勾选这个账号，再点击「推送 Sub2」。' : '先点击账号行的「重登」完成登录，再查看发送结果。'
    };
  }

  function renderSub2Details() {
    var dialog = el('extm-sub2-detail-dialog'); if (!dialog || !dialog.open) return;
    var row = rowById(Number(dialog.dataset.member));
    if (!row) { dialog.close(); return; }
    var info = sub2Explanation(row);
    var stockText = {'在库 Sub2': '已添加到 Sub2', '未在库 Sub2': 'Sub2 中还没有这个账号', 'Sub2 库存查询中': '正在查询', 'Sub2 状态暂不可用': '暂时查不到，请稍后再看', 'Sub2 未配置': '尚未设置 Sub2 连接'}[sub2Stock(row).label];
    var messageText = {
      'Cookie 已写入，等待 Sub2 代理就绪': '登录信息已收到，网络线路还没准备好。',
      'Cookie 已写入，等待重新验证': '登录信息已收到，稍后会再检查账号是否可用。',
      '等待同步 Cookie': '已排队，等待发送登录信息。',
      '正在同步 Cookie': '正在发送登录信息。',
      '等待版本同步与验证': '已排队，等待更新登录信息并检查账号。',
      'Cookie 已保存，等待同步与验证': '登录信息已保存，等待发送和检查。',
      'Cookie 已保存，等待同步': '登录信息已保存，等待发送。',
      'Cookie 已同步，重登成功后自动更新': '登录信息已更新，下次登录成功后会自动发送新的信息。',
      '凭据已验证，可调度；模型尚未验证': '登录信息检查通过，账号已启用；还没确认能否正常出图。',
      '凭据已验证，保持暂停或等待代理分配': '登录信息检查通过，账号仍暂停或在等待网络线路。'
    }[row.sub2_message] || row.sub2_message || '暂无说明';
    setHTML(dialog.querySelector('[data-sub2-detail-content]'),
      '<p>' + esc(row.email) + '</p><div class="extm-sub2-summary"><strong>' + esc(info.title) + '</strong><p>' + esc(info.reason) + '</p></div>' +
      '<dl><dt>Sub2 中的账号</dt><dd>' + esc(stockText) + '</dd><dt>Sub2 账号编号</dt><dd>' + (row.sub2_account_id ? '#' + esc(row.sub2_account_id) : '暂无编号') + '</dd>' +
      '<dt>系统提示</dt><dd>' + esc(messageText) + '</dd><dt>最近记录时间</dt><dd>' + esc(fmtTime(row.sub2_synced_at, true)) + '</dd></dl>' +
      '<h4>接下来怎么做</h4><p class="extm-sub2-help">' + esc(info.action) + '</p><p class="extm-sub2-footnote">这里会随列表自动更新。打开详情只是查看说明，不会重新登录或发送账号信息。</p>');
    refreshSub2Capacity(dialog, row);
  }

  function drawSub2Stamp(canvas) {
    var ctx = canvas.getContext('2d'); if (!ctx) return;
    canvas.width = 880; canvas.height = 360;
    ctx.scale(2, 2);
    ctx.strokeStyle = ctx.fillStyle = '#c72b35';
    ctx.lineWidth = 5;
    ctx.beginPath(); ctx.roundRect(13, 15, 414, 150, 9); ctx.stroke();
    ctx.lineWidth = 1.8;
    ctx.strokeRect(22, 24, 396, 132);
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = '800 29px "PingFang SC","Microsoft YaHei",sans-serif';
    ctx.fillText('账号已经超出', 220, 68);
    ctx.fillText('节点容量限制，老铁。', 220, 111);
    // A fixed texture avoids flickering or redrawing random marks on every poll.
    ctx.globalCompositeOperation = 'destination-out';
    for (var i = 0; i < 380; i++) {
      ctx.globalAlpha = .15 + (i % 5) * .1;
      ctx.fillRect((i * 97 + 31) % 440, (i * 53 + 11) % 180, 1 + i % 3, .7 + i % 2);
    }
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
  }

  function refreshSub2Capacity(dialog, row) {
    var layer = dialog.querySelector('.extm-sub2-stamp-layer'), note = dialog.querySelector('[data-sub2-capacity]');
    var key = [row.email, row.sub2_status, row.sub2_message, row.sub2_account_id, row.sub2_synced_at].join('|');
    if (key !== dialog._capacityKey) {
      dialog._capacityKey = key; dialog._capacityChecked = 0; layer.hidden = note.hidden = true;
    }
    if (row.sub2_status !== 'pending' || row.sub2_message !== 'Cookie 已写入，等待 Sub2 代理就绪') return;
    if (dialog._capacityLoading || Date.now() - (dialog._capacityChecked || 0) < 30000) return;
    dialog._capacityLoading = true;
    // Hide old evidence while refreshing, and ignore responses for a closed or changed account.
    layer.hidden = note.hidden = true;
    api('/members/' + row.id + '/sub2-capacity', {timeout: 55000}).then(function (data) {
      if (el('extm-sub2-detail-dialog') !== dialog || !dialog.open || dialog._capacityKey !== key) return;
      var confirmed = data.confirmed === true && data.account_id === row.sub2_account_id;
      layer.hidden = note.hidden = !confirmed;
      if (confirmed) note.textContent = '刚刚核对：' + data.accounts + ' 个账号，' + data.nodes + ' 个节点，每个最多 ' + data.per_node + ' 个账号，合计最多 ' + data.capacity + ' 个。请管理员增加节点或减少需要分配线路的账号。';
    }).catch(function () { /* An unavailable check never means capacity exceeded. */ }).finally(function () {
      dialog._capacityLoading = false;
      if (dialog._capacityKey === key) dialog._capacityChecked = Date.now();
    });
  }

  function showSub2Details(id) {
    if (!rowById(id) || el('extm-sub2-detail-dialog')) return;
    var dialog = document.createElement('dialog'); dialog.id = 'extm-sub2-detail-dialog'; dialog.className = 'extm-note-dialog extm-sub2-dialog'; dialog.dataset.member = id;
    dialog.setAttribute('aria-labelledby', 'extm-sub2-detail-title');
    dialog.innerHTML = '<h3 id="extm-sub2-detail-title">Sub2 同步详情</h3><div data-sub2-detail-content></div><p class="extm-sub2-capacity" data-sub2-capacity hidden></p><div class="extm-sub2-stamp-layer" hidden><canvas class="extm-sub2-stamp" role="img" aria-label="账号已经超出节点容量限制，老铁。">账号已经超出节点容量限制，老铁。</canvas></div><footer><button type="button" class="extm-btn dft">知道了</button></footer>';
    drawSub2Stamp(dialog.querySelector('canvas'));
    dialog.querySelector('button').onclick = function () { dialog.close(); };
    dialog.onclose = function () { dialog.remove(); var button = document.querySelector('[data-sub2-details="' + id + '"]'); if (st.open && button) button.focus({preventScroll:true}); };
    document.body.appendChild(dialog); dialog.showModal(); renderSub2Details();
  }

  function sub2SubscriptionWarnings(ids) {
    return ids.map(function (id) {
      var row = rowById(id);
      if (!row) throw new Error('所选账号已发生变化，请重新勾选后推送');
      var reason = row.credits_error ? '积分查询失败：' + row.credits_error
        : row.login_status === 'never' ? '订阅状态未知：尚未查询积分'
        : row.credits_total == null ? '订阅状态未知：积分未查到'
        : row.subscription_ok !== true ? '订阅状态异常：掉订阅' : '';
      return reason ? {id:id, email:row.email, reason:reason} : null;
    }).filter(Boolean);
  }

  function confirmSub2Subscription(ids, warnings, relink) {
    return new Promise(function (resolve) {
      var dialog = document.createElement('dialog'); dialog.id = 'extm-sub2-confirm-dialog'; dialog.className = 'extm-note-dialog extm-sub2-confirm-dialog';
      dialog.setAttribute('aria-labelledby', 'extm-sub2-confirm-title'); dialog.setAttribute('aria-describedby', 'extm-sub2-confirm-summary');
      dialog.innerHTML = '<h3 id="extm-sub2-confirm-title">订阅状态异常，是否继续推送？</h3><p id="extm-sub2-confirm-summary">已选 ' + ids.length + ' 个账号，其中 ' + warnings.length + ' 个订阅异常或状态未知。确认后将继续推送本次选中的 ' + ids.length + ' 个账号到 Sub2。</p><ul aria-label="订阅异常或状态未知的账号">' + warnings.map(function (item) { return '<li><strong>' + esc(item.email) + '</strong><span>' + esc(item.reason) + '</span></li>'; }).join('') + '</ul>' +
        (relink ? '<p class="extm-relink-warning">本次将重新关联：按邮箱查找 Sub2 账号，不存在时创建新账号并推送 Cookie。这可能恢复其他管理员已删除的账号。</p>' : '') +
        '<footer><button type="button" class="extm-btn dft" data-cancel>取消</button><button type="button" class="extm-btn" data-confirm>确认推送</button></footer>';
      dialog.querySelector('[data-cancel]').onclick = function () { dialog.close(); };
      dialog.querySelector('[data-confirm]').onclick = function () { dialog.close('confirm'); };
      dialog.onclose = function () { var approved = dialog.returnValue === 'confirm'; dialog.remove(); resolve(approved); };
      document.body.appendChild(dialog); dialog.showModal(); dialog.querySelector('[data-cancel]').focus();
    });
  }

  async function pushSub2(relink) {
    var ids = selIds(); if (!ids.length || st.sub2Submitting || st.sub2Confirming) return;
    st.sub2Confirming = true; updSel();
    try {
      var warnings = sub2SubscriptionWarnings(ids), relinkConfirmed = false;
      while (warnings.length) {
        var shown = JSON.stringify(warnings);
        if (!await confirmSub2Subscription(ids, warnings, relink)) return;
        relinkConfirmed = !!relink;
        warnings = sub2SubscriptionWarnings(ids);
        // Polling may discover another abnormal account while the dialog is open.
        // Consent applies only to the accounts and reasons actually shown.
        if (JSON.stringify(warnings) === shown) break;
      }
      if (relink && !relinkConfirmed && !confirm('重新关联选中的 ' + ids.length + ' 个账号？将按邮箱查找 Sub2 账号，不存在时创建新账号并推送 Cookie。这可能恢复其他管理员已删除的账号。')) return;
      if (ids.some(function (id) { var row = rowById(id); return !row || running(row); })) throw new Error('所选账号状态已变化，请等待任务结束后重新推送');
      st.sub2Confirming = false; st.sub2Submitting = true; updSel();
      var result = await api('/members/' + (relink ? 'relink-sub2' : 'push-sub2'), { method: 'POST', body: { ids: ids } });
      toast(result.queued ? 'success' : 'warning', result.message);
      await load(true);
    } catch (e) { toast('error', e.message); }
    finally { st.sub2Confirming = false; st.sub2Submitting = false; updSel(); }
  }

  async function loadGroups() {
    try { var groups = await api('/groups'); if (!Array.isArray(groups)) throw new Error('分组列表格式无效'); st.groups = groups; view.groups(st.groups); }
    catch (error) { view.update({groupsError:'分组加载失败：' + error.message}); }
  }
  async function createGroup(name) {
    var group = await api('/groups', {method:'POST', body:{name:name}});
    st.groups = st.groups.concat([group]); view.groups(st.groups); return group;
  }
  async function assignGroup(value) {
    var ids = selIds(); if (!ids.length || st.groupSaving || value === '__mixed__') return;
    st.groupSaving = true; updSel();
    try {
      var data = await api('/members/group', {method:'PATCH', body:{ids:ids, group_id:value === '0' ? null : Number(value)}});
      toast('success', data.message); st.sel.clear(); await load();
    } catch (error) { toast('error', error.message); }
    finally { st.groupSaving = false; updSel(); }
  }

  async function doImport() {
    if (st.importing) return;
    var btn = el('extm-do-import'), content = view.form.content.trim();
    if (!content) { view.importResult('请粘贴要导入的子号', 'err'); return; }
    st.importing = true; setLoading(btn, true, '导入中'); view.importResult('导入中…', 'mut');
    try {
      var payload = {content:content, on_duplicate:view.form.duplicate};
      if (view.form.otpMode) payload.otp_mode = view.form.otpMode;
      if (view.form.group) payload.group_id = view.form.group === '0' ? null : Number(view.form.group);
      var r = await api('/members/import', { method: 'POST', body: payload });
      var msg = '导入完成: 新增 ' + r.created + ' · 更新 ' + r.updated + ' · 跳过 ' + r.skipped + ' · 失败 ' + r.failed;
      if (r.job_id) msg += ' · 登录任务 #' + r.job_id + '，每批最多 50 个，成功后自动推送 Sub2';
      if (r.sequential_login) msg += ' · 按导入顺序逐个自动取码登录';
      if (r.errors && r.errors.length) msg += ' · ' + r.errors.join('；');
      view.importResult(msg, r.failed ? 'err' : 'ok'); if (!r.failed) view.form.content = ''; await load(true);
    } catch (e) { view.importResult(e.message, 'err'); }
    finally { st.importing = false; setLoading(btn, false, '批量导入'); }
  }

  async function startLogin(ids, expandFirst) {
    if (st.loginAllSubmitting || st.stoppingAll) return;
    if (ids.some(function (id) { return st.profileSaving.has(id); })) { toast('warning', '请等待登录配置保存完成'); return; }
    if (ids.some(function (id) { var row = rowById(id); return row && running(row); })) { toast('warning', '所选账号正在登录，请等待任务完成'); return; }
    ids.forEach(function (id) { st.pending.add(id); });
    ++st.loadSeq; renderRows();
    try {
      var job = await api('/members/batch-login', { method: 'POST', body: { ids: ids } });
      ids.forEach(function (id) { var row = rowById(id); if (row) row.latest_job = job; });
      if (expandFirst) st.expanded.add(ids[0]);
      ids.forEach(function (id) { detailState(id).selected = job.id; });
      toast('success', '已提交登录任务 #' + job.id + '，每批最多 50 个，成功后自动推送 Sub2');
    } catch (e) { toast('error', e.message); }
    finally { ids.forEach(function (id) { st.pending.delete(id); }); renderRows(); await load(true); }
    if (st.expanded.has(ids[0])) await refreshDetail(ids[0], true);
  }
  function reloginOne(id) { return startLogin([id], true); }
  function batchLogin() {
    var ids = selIds(); if (!ids.length) { toast('warning', '请先勾选账号'); return; }
    return startLogin(ids);
  }

  async function loginAll() {
    if (st.loginAllSubmitting || st.stoppingAll || st.pending.size || st.profileSaving.size) return;
    var filters = Object.assign({ login_status: st.statusF || null, subscription_ok: st.subF === '' ? null : st.subF === 'true', keyword: st.q }, extraFilters());
    var ids = st.rows.filter(function (r) { return !running(r); }).map(function (r) { return r.id; });
    st.loginAllSubmitting = true;
    ids.forEach(function (id) { st.pending.add(id); });
    ++st.loadSeq; renderRows();
    try {
      var result = await api('/members/batch-login-filter', { method: 'POST', body: filters });
      toast(result.queued ? 'success' : 'warning', result.message + (result.job ? ' · 任务 #' + result.job.id + '，可展开账号查看进度' : ''));
    } catch (e) { toast('error', e.message); }
    finally {
      await load(true);
      ids.forEach(function (id) { st.pending.delete(id); });
      st.loginAllSubmitting = false; renderRows();
    }
  }

  async function copyEmail(id) {
    var row = rowById(id); if (!row) return;
    var copied = false;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try { await navigator.clipboard.writeText(row.email); copied = true; } catch (e) { /* Try the fallback below. */ }
    }
    if (!copied) {
      var input = document.createElement('textarea'), focused = document.activeElement;
      input.value = row.email; input.readOnly = true;
      input.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
      document.body.appendChild(input); input.select();
      try { copied = document.execCommand('copy'); } catch (e) { copied = false; }
      finally { input.remove(); if (focused && focused.isConnected) focused.focus({ preventScroll: true }); }
    }
    toast(copied ? 'success' : 'error', copied ? '已复制账号：' + row.email : '复制失败，请手动复制账号：' + row.email);
  }

  async function exportEmails() {
    if (st.exportingEmails) return;
    var ids = selIds();
    if (!ids.length) { toast('warning', '请先勾选要导出的账号'); return; }
    st.exportingEmails = true; updSel();
    try {
      var blob = await api('/members/export-emails', { method: 'POST', body: { ids: ids }, blob: true });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a'); a.href = url; a.download = 'external-emails.xlsx';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      toast('success', '已导出 ' + ids.length + ' 个邮箱（Excel）');
    } catch (e) { toast('error', e.message); }
    finally { st.exportingEmails = false; updSel(); }
  }

  function exportCookies() {
    if (st.exporting) return;
    var ids = selIds(), filters = qs();
    st.exporting = true; updSel();
    api("/members/export" + (!ids.length && filters.length ? "?" + filters.join("&") : ""), ids.length ? { method: "POST", body: { ids: ids } } : {}).then(function (data) {
      if (!data.length) { toast("warning", ids.length ? "选中账号暂无可导出的 Cookie" : "当前范围暂无可导出的 Cookie"); return; }
      var blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a"); a.href = url; a.download = "external-cookies.json"; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      toast("success", "已导出 " + data.length + " 条 Cookie" + (ids.length ? "（选中 " + ids.length + " 个账号，跳过 " + (ids.length - data.length) + " 个无 Cookie 或已不存在的账号）" : ""));
    }).catch(function (e) { toast("error", e.message); }).finally(function () { st.exporting = false; updSel(); });
  }

  function batchDelete() {
    var ids = selIds(); if (!ids.length) { toast("warning", "请先勾选账号"); return; }
    if (!confirm("确认删除选中的 " + ids.length + " 个外部子号?不可恢复。")) return;
    doDelete(ids);
  }
  function doDelete(ids) {
    api("/members/batch-delete", { method: "DELETE", body: { ids: ids } }).then(function (r) {
      toast("success", (r && r.message) || "已删除"); load();
    }).catch(function (e) { toast("error", e.message); });
  }

  // ---------- 嵌入右侧内容区(按实际布局测量定位,只盖内容区) ----------
  var HOST_ID = "extm-embed";
  function positionPanel(w) {
    var r = window.OKAD_NAV.rect(); w.style.left = r.left + "px"; w.style.top = r.top + "px";
    w.style.setProperty("--extm-detail-width", Math.max(320, window.innerWidth - r.left - 86) + "px");
  }
  async function show() {
    injectStyle(); st.open = true;
    var w = el(HOST_ID);
    if (!w) {
      // Logging out removes the shell (and its panel); remount against the new shell on login.
      if (view) { view.destroy(); view = null; mounting = null; st.total = 0; resetPage(1); }
      w = document.createElement('div'); w.id = HOST_ID; document.body.appendChild(w);
    }
    positionPanel(w); w.classList.add('on');
    if (!view) {
      if (!mounting) mounting = import(viewURL).then(function (module) { buildBody(w, module.mountExternalMembers); }).catch(function (error) {
        console.error('外部子号组件加载失败', error);
        w.textContent = '页面组件加载失败，请刷新后重试'; mounting = null;
      });
      await mounting;
    }
    if (!st.open || !view) return;
    refreshAll(false); refreshStock(true);
  }
  function hide() { if (st.loadController) st.loadController.abort(); var w = el(HOST_ID); if (w) w.classList.remove("on"); var more = el("extm-more-actions"); if (more) more.open = false; st.open = false; if (view) view.close(); var note = el('extm-note-dialog'); if (note) note.close(); var mail = el('extm-mail-dialog'); if (mail) mail.close(); var otp = el('extm-otp-dialog'); if (otp) otp.close(); var mode = el('extm-mode-dialog'); if (mode) mode.close(); var push = el('extm-sub2-confirm-dialog'); if (push) push.close(); var detail = el('extm-sub2-detail-dialog'); if (detail) detail.close(); st.stock = null; st.stockEpoch++; }
  window.OKAD_NAV.register({
    id: NAV_ID, route: "external-members", panel: HOST_ID, label: "外部子号", icon: "external", first: true,
    open: show, close: hide,
    layout: function () { var w = el(HOST_ID); if (w) positionPanel(w); }
  });
  // A mobile-to-desktop sidebar transform can finish after ResizeObserver's last measurement.
  document.addEventListener('transitionend', function (event) {
    if (st.open && event.target.matches('.n-layout-sider')) positionPanel(el(HOST_ID));
  });

  setInterval(function () {
    if (st.open && !document.hidden) { refreshAll(false); refreshStock(false); }
  }, 3000);
  document.addEventListener('visibilitychange', function () { if (st.open && !document.hidden) { refreshAll(false); refreshStock(true); } });
  window.addEventListener('okad:sub2-stock-changed', function () { refreshStock(true); });

})();
