export const LOCALE_KEY='startup101.display-locale';
export function validLocale(value){return value==='en'||value==='zh-TW';}
export function readDisplayLocale(storage,fallback='en'){
 try{const saved=storage?.getItem(LOCALE_KEY);if(validLocale(saved))return saved;}catch{}
 return validLocale(fallback)?fallback:'en';
}
export function saveDisplayLocale(storage,value){if(!validLocale(value))return false;try{storage?.setItem(LOCALE_KEY,value);}catch{}return true;}
