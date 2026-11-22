import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const source = readFileSync(
  new URL("../../api/app/static/batch-runner.js", import.meta.url), "utf8"
);
const globals={window:{}};
runInNewContext(source,globals);
const runner=globals.window.FormFlowBatchRunner;

test("Ten batch files start at most three actual requests at a time", async()=>{
  assert.equal(runner.MAX_FILES,10);
  assert.equal(runner.MAX_PARALLEL,3);
  const started=[], pending=new Map();
  let active=0,peak=0;
  const job=runner.processAll(Array.from({length:10},(_,i)=>i), async (value,index)=>{
    active++;peak=Math.max(peak,active);started.push(index);
    return new Promise(resolve=>{
      pending.set(index,()=>{active--;pending.delete(index);resolve(value);});
    });
  },10);
  assert.deepEqual(started,[0,1,2]);
  assert.equal(peak,3);
  // As soon as any request finishes, another document begins immediately.
  pending.get(1)();
  await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(started,[0,1,2,3]);
  assert.equal(active,3);
  while(started.length<10){
    pending.get(Math.min(...pending.keys()))();
    await new Promise(resolve=>setImmediate(resolve));
  }
  for(const resolve of [...pending.values()])resolve();
  const outcome=await job;
  assert.equal(peak,3);
  assert.equal(outcome.length,10);
  assert(outcome.every(x=>x.ok));
  assert.deepEqual(Array.from(outcome,x=>x.value),Array.from({length:10},(_,i)=>i));
});

test("One failed conversion does not stop nine remaining documents",async()=>{
  const started=[];
  const data=await runner.processAll(Array.from({length:10},(_,i)=>i),async i=>{
    started.push(i);
    if(i===2)throw Error("OCR unavailable");
    return i*2;
  },3);
  assert.equal(started.length,10);
  assert.equal(data.length,10);
  assert.equal(data[2].ok,false);
  assert.match(data[2].error.message,/OCR unavailable/);
  assert(data.filter(result=>result.ok).length===9);
  assert.equal(data[9].value,18);
});

test("Rejects an eleventh document and prevents an unbounded worker pool",async()=>{
  await assert.rejects(runner.processAll(Array(11).fill(0),async()=>1),/10/);
  await assert.rejects(runner.processAll([],async()=>1),/10/);
  let active=0,peak=0;
  await runner.processAll(Array.from({length:10},(_,i)=>i),async i=>{
    active++;peak=Math.max(peak,active);
    await Promise.resolve();active--;
    return i;
  },999);
  assert.equal(peak,3);
});
