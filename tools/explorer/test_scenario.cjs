// Exercise the actual frontend statistics while leaving its async UI boot pending.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({fetch: () => new Promise(() => {})});
vm.runInContext(fs.readFileSync(__dirname + '/app.js', 'utf8'), context);
const early = () => ({result:'unknown', investigation:{death_clock:120, has_afterbattle:false}});
const rows = [...Array.from({length:158},()=>({result:'win'})),
              ...Array.from({length:133},()=>({result:'loss'})),
              ...Array.from({length:78},early)];
let s=context.stats(rows);
assert.equal(s.wins,158);
assert.equal(s.unknown,78);
assert.equal(s.eligible,78);
assert.ok(Math.abs(s.estimate-(158+78*.3)/369)<1e-12);
assert.equal(s.p,158/291);
assert.equal(context.stats([early()]).estimate,.3);
assert.equal(context.stats([{result:'unknown'}]).estimate,null);
assert.equal(context.stats([early(),{result:'unknown'}]).unassigned,1);
assert.equal(context.stats([{result:'win'}]).estimate,1);
assert.equal(context.stats([]).estimate,null);
assert.equal(rows.filter(r=>r.result==='unknown').length,78);
console.log('30% scenario checks passed; observed outcomes unchanged.');
const metrics=context.stats([
  {result:'win',comp7PrestigePoints:242,rating_delta:43},
  {result:'loss',comp7PrestigePoints:0,rating_delta:-36},
  {result:'win',comp7PrestigePoints:110,rating_delta:0},
  {...early(),comp7PrestigePoints:null,rating_delta:null}
]);
assert.equal(metrics.prestige.count,3);
assert.equal(metrics.prestige.mean,352/3);
assert.equal(metrics.rating.count,3);
assert.equal(metrics.rating.total,7);
assert.equal(metrics.rating.mean,7/3);
assert.equal(context.stats([early()]).prestige.mean,null);
assert.equal(context.stats([early()]).rating.total,null);
assert.equal(context.stats([]).rating.mean,null);
assert.equal(vm.runInContext('signed(43)',context),'+43');
assert.equal(vm.runInContext('signed(0)',context),'0');
assert.equal(vm.runInContext('signed(null)',context),'—');
console.log('Prestige and rating checks passed; missing values excluded, zero and >200 retained.');
