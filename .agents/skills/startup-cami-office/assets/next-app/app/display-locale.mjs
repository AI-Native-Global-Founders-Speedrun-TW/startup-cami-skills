export const LOCALE_KEY='startup-cami.display-locale';
// Preference saved before the rename; read as a fallback, never written.
export const LEGACY_LOCALE_KEY='startup101.display-locale';
export function validLocale(value){return value==='en'||value==='zh-TW';}
export function readDisplayLocale(storage,fallback='en'){
 for(const key of [LOCALE_KEY,LEGACY_LOCALE_KEY]){try{const saved=storage?.getItem(key);if(validLocale(saved))return saved;}catch{}}
 return validLocale(fallback)?fallback:'en';
}
export function saveDisplayLocale(storage,value){if(!validLocale(value))return false;try{storage?.setItem(LOCALE_KEY,value);}catch{}return true;}
