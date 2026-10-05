import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash, webcrypto} from 'node:crypto';
import {validSecret, secretDigest, freshSecret} from './core.mjs';
test('validation rejects short, whitespace and non-ASCII values', () => {
  assert.equal(validSecret('a'.repeat(39)), false);
  assert.equal(validSecret('a'.repeat(257)), false);
  assert.equal(validSecret('a'.repeat(40) + ' '), false);
  assert.equal(validSecret('中'.repeat(40)), false);
  assert.equal(validSecret('a'.repeat(40)), true);
});
test('digest matches backend SHA-256 UTF-8 without normalization', async () => {
  const fixture = 'TEST-ONLY-not-an-issued-client-secret-20261003';
  assert.equal(await secretDigest(fixture, webcrypto), createHash('sha256').update(fixture, 'utf8').digest('hex'));
  await assert.rejects(secretDigest('short', webcrypto));
});
test('generator uses supplied cryptographic API and returns 96 hex characters', () => {
  let calls = 0;
  const fakeCrypto = {getRandomValues(bytes) {calls++; bytes.fill(171); return bytes;}};
  assert.equal(freshSecret(fakeCrypto), 'ab'.repeat(48));
  assert.equal(calls, 1);
});
