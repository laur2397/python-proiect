"""Motorul JavaScript pentru PDF (faza 11, pasul 11.3): B-038…B-041, H-006, H-058.

QuickJS (MIT), ales de utilizator. Scripturile ruleaza fara apeluri inapoi in
Python (`docs/plan/faza_11_pasi.md`, decizia 3): limita de timp a motorului nu
se poate combina cu functii Python. Starea formularului intra in script ca JSON,
iar ce schimba scriptul (valori de campuri, `event.value`, `event.rc`, mesajele
`app.alert`, comenzile pentru fereastra) iese tot ca JSON.

Obiectele Acrobat sunt un subset: `this`/documentul (`getField`, `numPages`,
`pageNum`, `resetForm`, `print`, `saveAs`, `closeDoc`, `submitForm`), `event`,
`app` (`alert`, `beep`), `util.printd`, `console.println`, si functiile `AF*`
folosite de formulare pentru format, validare si calcul (`AFNumber_*`,
`AFPercent_*`, `AFDate_*`, `AFSpecial_*`, `AFRange_Validate`,
`AFSimple_Calculate`). Mesajele functiilor `AF*` ies ca coduri (`format`,
`range`), pe care interfata le traduce.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

SCRIPT_TIMEOUT_S = 2.0
"""B-041: un script care depaseste 2 secunde se opreste si se noteaza."""
MEMORY_LIMIT = 64 * 1024 * 1024

_PRELUDE = r"""
var __in = JSON.parse(__input);
var __fields = __in.fields, __changes = {}, __alerts = [], __commands = [];
function __num(v) {
  if (typeof v === 'string' && /^\s*-?(\d+([.,]\d*)?|[.,]\d+)\s*$/.test(v))
    return Number(v.replace(',', '.'));
  return v;
}
function __str(v) { return v === null || v === undefined ? '' : String(v); }
function Field(name) { this.name = name; }
Object.defineProperty(Field.prototype, 'value', {
  get: function () { return __num(__fields[this.name].value); },
  set: function (v) { __fields[this.name].value = __str(v); __changes[this.name] = __str(v); }
});
Object.defineProperty(Field.prototype, 'valueAsString', {
  get: function () { return __str(__fields[this.name].value); }
});
['type', 'readonly', 'required'].forEach(function (k) {
  Object.defineProperty(Field.prototype, k, {
    get: function () { return __fields[this.name][k]; }, set: function () {} });
});
Field.prototype.setFocus = function () { __commands.push(['focus', this.name]); };
var __doc = {
  numPages: __in.numPages,
  getField: function (n) { return Object.prototype.hasOwnProperty.call(__fields, n)
                                  ? new Field(n) : null; },
  resetForm: function () { __commands.push(['reset_form']); },
  print: function () { __commands.push(['print_form']); },
  saveAs: function () { __commands.push(['save_form_as']); },
  closeDoc: function () { __commands.push(['close_document']); },
  submitForm: function (a) { __commands.push(['send_form', typeof a === 'object' && a
                                              ? __str(a.cURL) : __str(a)]); },
  calculateNow: function () {}
};
Object.defineProperty(__doc, 'pageNum', {
  get: function () { return __in.pageNum; },
  set: function (n) { __commands.push(['go_to_page', Number(n) + 1]); }
});
var app = {
  viewerType: 'Reader', viewerVersion: 11, platform: 'DocuLens',
  alert: function (m) { __alerts.push(['text', __str(m && typeof m === 'object'
                                                    ? m.cMsg : m)]); return 1; },
  beep: function () {}
};
var console = { println: function () {}, show: function () {}, clear: function () {} };
var event = __in.event || {};
event.rc = true;
if (event.value === undefined) event.value = '';
if (event.target_name && __fields[event.target_name]) event.target = new Field(event.target_name);
event.source = event.target;

function __pad(n, w) { n = String(n); while (n.length < w) n = '0' + n; return n; }
function __parseDate(value, fmt) {
  var nums = __str(value).match(/\d+/g);
  if (!nums || nums.length !== 3) return null;
  var order = [], toks = fmt.toLowerCase().match(/yyyy|yy|mm|m|dd|d/g) || [];
  toks.forEach(function (t) { if (order.indexOf(t[0]) < 0) order.push(t[0]); });
  if (nums[0].length === 4) order = ['y', 'm', 'd'];
  else if (order.slice().sort().join('') !== 'dmy') order = ['d', 'm', 'y'];
  var p = {}; for (var i = 0; i < 3; i++) p[order[i]] = Number(nums[i]);
  if (p.y < 100) p.y += p.y < 50 ? 2000 : 1900;
  var d = new Date(p.y, p.m - 1, p.d);
  if (d.getFullYear() !== p.y || d.getMonth() !== p.m - 1 || d.getDate() !== p.d) return null;
  return d;
}
function __formatDate(d, fmt) {
  return fmt.toLowerCase().replace(/yyyy|yy|mm|m|dd|d/g, function (t) {
    return { yyyy: __pad(d.getFullYear(), 4), yy: __pad(d.getFullYear() % 100, 2),
             mm: __pad(d.getMonth() + 1, 2), m: String(d.getMonth() + 1),
             dd: __pad(d.getDate(), 2), d: String(d.getDate()) }[t];
  });
}
var util = { printd: function (fmt, d) { return __formatDate(d, fmt); } };

function __reject(code) { event.rc = false; __alerts.push([code, event.target_name || '']); }
function __number(v) {
  if (typeof v === 'number') return v;
  var s = __str(v).replace(/\s/g, '').replace(/[^\d.,\-]/g, '');
  if (s.indexOf(',') >= 0 && s.indexOf('.') >= 0) s = s.replace(/\./g, '').replace(',', '.');
  else s = s.replace(',', '.');
  return s === '' || s === '-' ? NaN : Number(s);
}
function AFMakeNumber(v) { var n = __number(v); return isNaN(n) ? null : n; }
function __group(intPart, sep) {
  return intPart.replace(/\B(?=(\d{3})+(?!\d))/g, sep);
}
function AFNumber_Format(nDec, sepStyle, negStyle, currStyle, strCurrency, bPrepend) {
  if (__str(event.value) === '') return;
  var n = __number(event.value); if (isNaN(n)) return;
  var neg = n < 0, s = Math.abs(n).toFixed(nDec), parts = s.split('.');
  var seps = [[',', '.'], ['', '.'], ['.', ','], ['', ','], ["'", '.']][sepStyle || 0];
  s = __group(parts[0], seps[0]) + (parts[1] ? seps[1] + parts[1] : '');
  if (strCurrency) s = bPrepend ? strCurrency + s : s + strCurrency;
  if (neg) s = (negStyle === 2 || negStyle === 3) ? '(' + s + ')' : '-' + s;
  event.value = s;
}
function AFNumber_Keystroke(nDec, sepStyle) {
  if (!event.willCommit) return;
  if (__str(event.value) !== '' && isNaN(__number(event.value))) __reject('format');
}
function AFPercent_Format(nDec, sepStyle) {
  if (__str(event.value) === '') return;
  var n = __number(event.value); if (isNaN(n)) return;
  event.value = (n * 100).toFixed(nDec) + '%';
}
function AFPercent_Keystroke(nDec, sepStyle) { AFNumber_Keystroke(nDec, sepStyle); }
function AFDate_FormatEx(fmt) {
  var d = __parseDate(event.value, fmt); if (d) event.value = __formatDate(d, fmt);
}
function AFDate_KeystrokeEx(fmt) {
  if (!event.willCommit || __str(event.value) === '') return;
  var d = __parseDate(event.value, fmt);
  if (!d) __reject('format'); else event.value = __formatDate(d, fmt);
}
var __dateFormats = ['m/d', 'm/d/yy', 'mm/dd/yy', 'mm/yy', 'd-mmm', 'd-mmm-yy', 'dd-mmm-yy',
                     'yy-mm-dd', 'mmm-yy', 'mmmm-yy', 'mmm d, yyyy', 'mmmm d, yyyy',
                     'm/d/yy h:MM tt', 'm/d/yy HH:MM'];
function AFDate_Format(i) { AFDate_FormatEx(__dateFormats[i] || 'mm/dd/yy'); }
function AFDate_Keystroke(i) { AFDate_KeystrokeEx(__dateFormats[i] || 'mm/dd/yy'); }
function AFSpecial_Format(t) {
  var d = __str(event.value).replace(/\D/g, '');
  if (t === 0) event.value = d.substr(0, 5);
  else if (t === 1) event.value = d.substr(0, 5) + '-' + d.substr(5, 4);
  else if (t === 2) event.value = d.length > 7 ? '(' + d.substr(0, 3) + ') ' + d.substr(3, 3)
                                                 + '-' + d.substr(6, 4)
                                               : d.substr(0, 3) + '-' + d.substr(3, 4);
  else if (t === 3) event.value = d.substr(0, 3) + '-' + d.substr(3, 2) + '-' + d.substr(5, 4);
}
function AFSpecial_Keystroke(t) {
  if (!event.willCommit || __str(event.value) === '') return;
  var n = __str(event.value).replace(/\D/g, '').length;
  var ok = { 0: n === 5, 1: n === 9, 2: n === 7 || n === 10, 3: n === 9 }[t];
  if (!ok) __reject('format');
}
function AFRange_Validate(bGreater, nGreater, bLess, nLess) {
  if (__str(event.value) === '') return;
  var n = __number(event.value);
  if (isNaN(n) || (bGreater && n < nGreater) || (bLess && n > nLess)) __reject('range');
}
function AFSimple_Calculate(op, names) {
  if (typeof names === 'string') names = names.split(/\s*,\s*/);
  var vals = [];
  names.forEach(function (n) {
    if (Object.prototype.hasOwnProperty.call(__fields, n)) {
      var v = __number(__fields[n].value); vals.push(isNaN(v) ? 0 : v);
    }
  });
  var r = 0;
  if (op === 'SUM') r = vals.reduce(function (a, b) { return a + b; }, 0);
  else if (op === 'PRD') r = vals.reduce(function (a, b) { return a * b; }, 1);
  else if (op === 'AVG') r = vals.length ? vals.reduce(function (a, b) { return a + b; }, 0)
                                         / vals.length : 0;
  else if (op === 'MIN') r = vals.length ? Math.min.apply(null, vals) : 0;
  else if (op === 'MAX') r = vals.length ? Math.max.apply(null, vals) : 0;
  event.value = r;
}
"""


@dataclass(frozen=True, slots=True)
class ScriptResult:
    """Ce a facut un script."""

    ran: bool
    """False: JavaScript dezactivat (B-040, H-006) sau motor lipsa."""
    rc: bool = True
    """`event.rc`: False = valoarea e refuzata (verificarile de format, H-006)."""
    value: str | None = None
    """`event.value` dupa script (valoarea formatata sau calculata)."""
    changes: Mapping[str, str] = field(default_factory=dict)
    """Valorile de campuri schimbate de script (`getField(...).value = ...`)."""
    alerts: Sequence[tuple[str, str]] = ()
    """(`text`, mesajul scriptului) sau (`format`/`range`, numele campului)."""
    commands: Sequence[tuple[Any, ...]] = ()
    """Comenzi pentru fereastra: (`print_form`,), (`go_to_page`, n)..."""
    timed_out: bool = False
    error: str | None = None


def run_script(code: str, *, fields: Mapping[str, Mapping[str, Any]] | None = None,
               event: Mapping[str, Any] | None = None, prelude: Sequence[str] = (),
               num_pages: int = 1, page_num: int = 0,
               timeout: float = SCRIPT_TIMEOUT_S) -> ScriptResult:
    """Ruleaza `code` cu `this` = documentul. `fields`: nume → {value, type,
    readonly, required}; `event`: {name, value, willCommit, target_name...};
    `prelude`: scripturile documentului (`/Names/JavaScript`), care definesc
    functiile folosite de campuri. Peste `timeout` secunde scriptul se opreste
    (B-041)."""
    try:
        import quickjs
    except ImportError:
        return ScriptResult(False, error="quickjs lipseste")
    payload = {"fields": dict(fields or {}), "event": dict(event or {}),
               "numPages": num_pages, "pageNum": page_num}
    body = "\n".join([*prelude, code])
    wrapper = ("(function(){ try { (function(){\n" + body + "\n}).call(__doc); }"
               " catch (e) { __error = String(e); }\n"
               " return JSON.stringify({rc: event.rc !== false, value: event.value === undefined"
               " || event.value === null ? null : String(event.value), changes: __changes,"
               " alerts: __alerts, commands: __commands, error: __error}); })()")
    context = quickjs.Context()
    context.set_memory_limit(MEMORY_LIMIT)
    try:
        context.eval("var __input = " + json.dumps(json.dumps(payload))
                     + "; var __error = null;")
        context.eval(_PRELUDE)
        context.set_time_limit(timeout)
        raw = context.eval(wrapper)
    except quickjs.JSException as exc:
        text = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        return ScriptResult(True, timed_out="interrupted" in text, error=text)
    data = json.loads(raw)
    return ScriptResult(True, rc=bool(data["rc"]), value=data["value"],
                        changes={str(k): str(v) for k, v in data["changes"].items()},
                        alerts=[tuple(a) for a in data["alerts"]],
                        commands=[tuple(c) for c in data["commands"]], error=data["error"])
