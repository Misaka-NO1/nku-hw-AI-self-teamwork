import test from 'node:test';
import assert from 'node:assert/strict';
import {handleScenic} from './scenic-service.mjs';

function response(){
  return {
    statusCode:null,payload:null,
    writeHead(status){this.statusCode=status;return this;},
    end(payload){this.payload=payload;return this;}
  };
}

test('public mode advertises read-only access',async()=>{
  const res=response();
  const handled=await handleScenic({method:'GET',headers:{}},res,
    new URL('http://localhost/api/scenic/config'));
  assert.equal(handled,true);
  assert.equal(res.statusCode,200);
  assert.deepEqual(JSON.parse(res.payload),{authoring:false});
});

test('public mode rejects photo uploads and spot changes before reading bodies',async()=>{
  for(const [method,route] of [['POST','photos'],['PUT','spots']]){
    const res=response();
    await handleScenic({method,headers:{}},res,
      new URL('http://localhost/api/scenic/'+route));
    assert.equal(res.statusCode,403);
    assert.match(JSON.parse(res.payload).error,/只允许浏览/);
  }
});

test('local authoring is an explicit server setting',async()=>{
  const res=response();
  await handleScenic({method:'GET',headers:{}},res,
    new URL('http://localhost/api/scenic/config'),{authoring:true});
  assert.deepEqual(JSON.parse(res.payload),{authoring:true});
});
