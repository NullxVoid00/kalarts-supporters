import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';

const aad = Buffer.from('KalArts Patreon state v1');
function keyBytes(encoded) {
  const key = Buffer.from(encoded || '', 'base64');
  if (key.length !== 32) throw new Error('A 256-bit state key is required.');
  return key;
}
export function seal(text, key) {
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', keyBytes(key), iv);
  cipher.setAAD(aad);
  const data = Buffer.concat([cipher.update(text, 'utf8'), cipher.final()]);
  return JSON.stringify({version: 1, iv: iv.toString('base64'), tag: cipher.getAuthTag().toString('base64'), data: data.toString('base64')}) + '\n';
}
export function unseal(text, key) {
  const envelope = JSON.parse(text);
  if (envelope.version !== 1) throw new Error('Unsupported encrypted state version.');
  const iv = Buffer.from(envelope.iv, 'base64');
  const tag = Buffer.from(envelope.tag, 'base64');
  if (iv.length !== 12 || tag.length !== 16) throw new Error('Invalid encrypted state.');
  const cipher = createDecipheriv('aes-256-gcm', keyBytes(key), iv);
  cipher.setAAD(aad);
  cipher.setAuthTag(tag);
  return Buffer.concat([cipher.update(Buffer.from(envelope.data, 'base64')), cipher.final()]).toString('utf8');
}
