'use client';
import {useEffect,useState} from 'react';
import {readDisplayLocale,saveDisplayLocale} from '../display-locale.mjs';
import styles from './about.module.css';
const COPY={
 en:{back:'Back to canvas',eyebrow:'THE PEOPLE BEHIND THE QUESTIONS',title:'A place to think through your startup.',intro:'From course questions to a local facilitation canvas. Explore your customers, test your assumptions, and build the context for your next decision.',language:'Display language',course:'COURSE MATERIAL',cami:'Cami Lu 呂緗柔',camiCredit:'Course material contributed from Cami’s slides.',camiBio:'A 2024 NCCU interview introduced Cami as STARTUP101’s CEO, with experience in entrepreneurship and venture capital.',camiText:'The questions draw on Cami’s course materials covering customers, validation, growth, and product strategy.',community:'SKILL DEVELOPMENT',communityCredit:'Skill developed through the contributions of the aifounders.tw community.',communityText:'The community’s work brings the material into a guided, question-by-question workflow with evaluation, local YAML records, and this canvas.',profile:'LinkedIn',visitCommunity:'Visit the community',resourceTitle:'Further reading',resourceText:'Startup101 is an information platform under 華陽創新科技. It provides startup guidance and acceleration resources, connecting businesses and investors.',resourceLink:'Explore Startup101',localTitle:'Your project, on your computer.',localText:'YAML is the formal source of your answers. The canvas is a read-only view of those local records.',creditTitle:'Credits'},
 'zh-TW':{back:'回到畫布',eyebrow:'問題背後的人與社群',title:'把創業想清楚的地方。',intro:'從課程問題，到本地 facilitation canvas。理解你的客戶、驗證你的假設，為下一個決策累積 context。',language:'顯示語言',course:'教材貢獻',cami:'Cami Lu 呂緗柔',camiCredit:'教學知識貢獻自 Cami Lu',camiBio:'政大 2024 年專訪介紹 Cami 為 STARTUP101 執行長，具有創業與創投經驗。',camiText:'題目取材自 Cami 的課程教材，涵蓋客戶、驗證、成長與產品策略。',community:'SKILL 製作',communityCredit:'Skill 由 aifounders.tw 社群投入製作',communityText:'社群投入將教材整理成逐題引導、評估、本地 YAML 記錄與 canvas 的使用流程。',profile:'LinkedIn',visitCommunity:'前往社群',resourceTitle:'延伸閱讀',resourceText:'Startup101 是華陽創新科技旗下資訊平台，提供新創輔導及加速資源，鏈結企業與投資人。',resourceLink:'認識 Startup101',localTitle:'你的專案，留在你的電腦。',localText:'YAML 是回答的正式資料來源。Canvas 是這些本地紀錄的唯讀檢視。',creditTitle:'貢獻者'}
};
export default function About({defaultLocale='en',forcedLocale=null}){
 const [locale,setLocale]=useState(defaultLocale);
 useEffect(()=>{try{if(forcedLocale){saveDisplayLocale(window.localStorage,forcedLocale);setLocale(forcedLocale);}else setLocale(readDisplayLocale(window.localStorage,defaultLocale));}catch{setLocale(defaultLocale);}},[defaultLocale,forcedLocale]);
 const t=COPY[locale];
 const change=value=>{try{saveDisplayLocale(window.localStorage,value);}catch{}setLocale(value);};
 return <main className={styles.page} lang={locale}>
  <nav className={styles.nav} aria-label={locale==='zh-TW'?'頁面導覽':'Page navigation'}><a href="/">← {t.back}</a><label>{t.language}<select value={locale} onChange={e=>change(e.target.value)}><option value="en">English</option><option value="zh-TW">繁體中文</option></select></label></nav>
  <header className={styles.hero}><p className={styles.eyebrow}>STARTUP 101 / {t.eyebrow}</p><h1>{t.title}</h1><p className={styles.intro}>{t.intro}</p></header>
  <section className={styles.credits} aria-label={t.creditTitle}>
   <article className={styles.card}><p className={styles.role}>{t.course}</p><h2>{t.cami}</h2><p className={styles.credit}>{t.camiCredit}</p><p>{t.camiText}</p><p>{t.camiBio}</p><div className={styles.links}><a href="https://www.linkedin.com/in/camillialu/">{t.profile} ↗</a></div></article>
   <article className={styles.card}><p className={styles.role}>{t.community}</p><h2>aifounders.tw</h2><p className={styles.credit}>{t.communityCredit}</p><p>{t.communityText}</p><div className={styles.links}><a href="https://aifounders.tw/">{t.visitCommunity} ↗</a></div></article>
  </section>
  <section className={styles.resource}><div><h2>{t.resourceTitle}</h2><p>{t.resourceText}</p></div><a href="https://www.startup101.biz/">{t.resourceLink} ↗</a></section>
  <footer className={styles.footer}><h2>{t.localTitle}</h2><p>{t.localText}</p><a href="/">← {t.back}</a></footer>
 </main>;
}
