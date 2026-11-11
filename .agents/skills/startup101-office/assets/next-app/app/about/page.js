import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import About from './about-client';
import {validLocale} from '../display-locale.mjs';
export const dynamic='force-dynamic';
export const metadata={title:'About · Startup 101'};
export default async function AboutPage({searchParams}){
 let locale='en';
 try{const config=JSON.parse(await readFile(resolve(process.cwd(),'startup101.local.json'),'utf8'));if(validLocale(config.locale))locale=config.locale;}catch{}
 const query=await searchParams;const forcedLocale=validLocale(query?.locale)?query.locale:null;
 return <About defaultLocale={forcedLocale||locale} forcedLocale={forcedLocale}/>;
}
