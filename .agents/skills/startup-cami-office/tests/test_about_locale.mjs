// Exercise the production preference helper; no browser or canvas render.
import assert from 'node:assert/strict';
import {LOCALE_KEY,LEGACY_LOCALE_KEY,readDisplayLocale,saveDisplayLocale} from '../assets/next-app/app/display-locale.mjs';
const data=new Map();const storage={getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value)};
assert.equal(readDisplayLocale(storage,'zh-TW'),'zh-TW');
assert.equal(saveDisplayLocale(storage,'en'),true);assert.equal(data.get(LOCALE_KEY),'en');assert.equal(readDisplayLocale(storage,'zh-TW'),'en');
assert.equal(saveDisplayLocale(storage,'zh-TW'),true);assert.equal(readDisplayLocale(storage,'en'),'zh-TW');
assert.equal(saveDisplayLocale(storage,'invalid'),false);assert.equal(data.get(LOCALE_KEY),'zh-TW');
data.set(LOCALE_KEY,'corrupt');assert.equal(readDisplayLocale(storage,'zh-TW'),'zh-TW');
const blocked={getItem(){throw Error('storage denied');},setItem(){throw Error('storage denied');}};
assert.equal(readDisplayLocale(blocked,'zh-TW'),'zh-TW');assert.equal(saveDisplayLocale(blocked,'en'),true);
assert.equal(readDisplayLocale(null,'unknown'),'en');
assert.deepEqual([...data.keys()],[LOCALE_KEY]);
// A preference saved before the rename is still honored, and never rewritten under the old key.
const legacy=new Map([[LEGACY_LOCALE_KEY,'zh-TW']]);const legacyStorage={getItem:key=>legacy.get(key)??null,setItem:(key,value)=>legacy.set(key,value)};
assert.equal(readDisplayLocale(legacyStorage,'en'),'zh-TW');saveDisplayLocale(legacyStorage,'en');
assert.equal(readDisplayLocale(legacyStorage,'zh-TW'),'en');assert.equal(legacy.get(LEGACY_LOCALE_KEY),'zh-TW');
console.log('PASS: config fallback, saved language priority, reversible preference, corrupt/blocked storage, locale-only persistence, legacy key fallback');
