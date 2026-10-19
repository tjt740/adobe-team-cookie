(function () {
  'use strict';
  var zone = 'Asia/Shanghai';
  function date(value) {
    if (typeof value === 'number') return new Date(value * 1000);
    // SQLite dates omit the timezone; application model dates are stored in UTC.
    if (typeof value === 'string' && /^\d{4}-\d\d-\d\d[T ]\d\d:\d\d(?::\d\d(?:\.\d+)?)?$/.test(value)) {
      value = value.replace(' ', 'T') + 'Z';
    }
    return new Date(value);
  }
  function format(value, options) {
    var parsed = date(value);
    if (value == null || value === '' || isNaN(parsed)) return '—';
    return parsed.toLocaleString('zh-CN', Object.assign({hour12:false}, options, {timeZone:zone}));
  }
  function datetime(value, seconds) {
    var parsed = date(value);
    if (value == null || value === '' || isNaN(parsed)) return '—';
    var parts = {};
    new Intl.DateTimeFormat('zh-CN', {timeZone:zone, year:'numeric', month:'2-digit', day:'2-digit',
      hour:'2-digit', minute:'2-digit', second:'2-digit', hourCycle:'h23'}).formatToParts(parsed).forEach(function (part) { parts[part.type] = part.value; });
    return parts.year + '-' + parts.month + '-' + parts.day + ' ' + parts.hour + ':' + parts.minute + (seconds === false ? '' : ':' + parts.second);
  }
  function clock(value) {
    return format(value, {hour:'2-digit', minute:'2-digit', second:'2-digit'});
  }
  window.OKAD_TIME = {format:format, datetime:datetime, clock:clock, zone:zone};
}());
