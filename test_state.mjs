import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomBytes} from 'node:crypto';
import {seal, unseal} from './state.mjs';
test('authenticated state round trip, randomized encryption, no plaintext',()=>{
  const key=randomBytes(32).toString('base64'), original=JSON.stringify({refresh_token:'test-secret-token'});
  const first=seal(original,key), second=seal(original,key);
  assert.equal(unseal(first,key),original); assert.notEqual(first,second); assert.ok(!first.includes('test-secret-token'));
});
test('wrong key and modified ciphertext fail closed',()=>{
  const key=randomBytes(32).toString('base64'), encrypted=seal('private',key);
  assert.throws(()=>unseal(encrypted,randomBytes(32).toString('base64')));
  const changed=JSON.parse(encrypted);const bytes=Buffer.from(changed.data,'base64');bytes[0]^=1;changed.data=bytes.toString('base64');
  assert.throws(()=>unseal(JSON.stringify(changed),key));
});
