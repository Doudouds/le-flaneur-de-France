const assert=require('node:assert/strict');
const {test}=require('node:test');
const rules=require('./coordinate_review/position_rules.js');
const row={latitude:0,longitude:0};
const atMetres=metres=>({latitude:metres/6371008.8*180/Math.PI,longitude:0});
const review=(metres,decision='a_verifier')=>({latitude:0,longitude:0,decision,correction:atMetres(metres)});

test('strict 10 metre boundary uses the unrounded distance',()=>{
  assert.equal(rules.decision(row,review(9.999)),'bon');
  assert.equal(rules.decision(row,review(10)),'a_verifier');
  assert.equal(rules.decision(row,review(10.001)),'a_verifier');
});
test('distance works at French latitudes and across the antimeridian',()=>{
  assert.ok(rules.distanceMeters({latitude:49,longitude:2},{latitude:49,longitude:2.001})>70);
  assert.ok(rules.distanceMeters({latitude:0,longitude:179.999},{latitude:0,longitude:-179.999})<223);
});
test('invalid or missing correction is not mistaken for a small offset',()=>{
  assert.equal(rules.decision(row,undefined),'a_verifier');
  assert.equal(rules.decision(row,{latitude:0,longitude:0,decision:'a_verifier'}),'a_verifier');
  assert.equal(rules.smallCorrection(row,{correction:{latitude:NaN,longitude:0}}),false);
});
test('explicit bad decision and changed catalogue coordinates still require attention',()=>{
  assert.equal(rules.decision(row,review(1,'mauvais')),'mauvais');
  assert.equal(rules.decision(row,{...review(1,'bon'),latitude:1}),'a_verifier');
});
test('existing good decisions and review data are preserved',()=>{
  const saved=review(100,'bon'),before=JSON.stringify(saved);
  assert.equal(rules.decision(row,saved),'bon');
  assert.equal(JSON.stringify(saved),before);
});
