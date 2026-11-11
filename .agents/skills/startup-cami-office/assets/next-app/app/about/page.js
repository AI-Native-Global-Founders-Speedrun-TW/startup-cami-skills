import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import About from './about-client';
import {validLocale} from '../display-locale.mjs';
export const dynamic='force-dynamic';
export const metadata={title:'About · Cami Startup Canvas'};
export default async function AboutPage({searchParams}){
 let locale='en';
 // startup101.local.json is the legacy view config from before the rename.
 for(const name of ['startup-cami.local.json','startup101.local.json']){try{const config=JSON.parse(await readFile(resolve(process.cwd(),name),'utf8'));if(validLocale(config.locale))locale=config.locale;break;}catch{}}
 const query=await searchParams;const forcedLocale=validLocale(query?.locale)?query.locale:null;
 return <About defaultLocale={forcedLocale||locale} forcedLocale={forcedLocale}/>;
}
