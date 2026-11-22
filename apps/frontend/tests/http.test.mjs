import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const source=readFileSync(new URL("../../api/app/static/app.js",import.meta.url),"utf8");
const from=source.indexOf("async function readAPIResponse(response){");
const until=source.indexOf("function userFacingError(",from);
assert(from>=0 && until>from,"Browser HTTP parser must remain present.");
const window={};
runInNewContext(source.slice(from,until),{window,Error,JSON});
const parse=window.FormFlowHTTP.readAPIResponse;

test("PDF conversion: empty gateway response gives clear HTTP error instead of JSON SyntaxError",async()=>{
  const response=new Response("",{status:504,headers:{"X-Request-ID":"0123456789abcdef0123456789abcdef"}});
  await assert.rejects(parse(response),error=>{
    assert.match(error.message,/HTTP 504/);
    assert.match(error.message,/Numer zgłoszenia/);
    assert.doesNotMatch(error.message,/Unexpected end of JSON input/);
    return true;
  });
});

test("PDF conversion: proxy HTML is not incorrectly parsed as JSON",async()=>{
  const response=new Response("<html>Bad Gateway</html>",{
    status:502,headers:{"Content-Type":"text/html"}
  });
  await assert.rejects(parse(response),/niebędącą JSON \(HTTP 502\)/);
});

test("Normal diagnostic JSON response is unchanged",async()=>{
  const response=new Response('{"status":"needs_review","form":{"tabs":[]}}',{
    status:200,headers:{"Content-Type":"application/json"}
  });
  const data=await parse(response);
  assert.equal(data.status,"needs_review");
  assert.deepEqual(JSON.parse(JSON.stringify(data.form)),{tabs:[]});
});
