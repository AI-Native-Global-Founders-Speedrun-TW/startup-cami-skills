'use client';
import {useEffect,useRef,useState} from 'react';
const MESSAGES={en:{loading:'Reading project YAML…',title:'Canvas could not update',stale:'Showing the last successful view. Updates will retry automatically.',retry:'Fix the YAML or connection. This page retries automatically.',frame:'Cami Startup Canvas — live YAML view'},'zh-TW':{loading:'正在讀取專案 YAML…',title:'畫布無法更新',stale:'目前顯示最後成功讀取的畫面，正在重試更新。',retry:'修正 YAML 或連線後，頁面會自動重試。',frame:'Cami Startup Canvas — YAML 即時畫面'}};
export default function Page(){
 const [canvas,setCanvas]=useState(null),[error,setError]=useState(null),[locale,setLocale]=useState(null);
 const frame=useRef(null),initialized=useRef(false),reading=useRef(null);
 useEffect(()=>{try{const saved=localStorage.getItem('startup-cami.display-locale')||localStorage.getItem('startup101.display-locale');if(saved==='en'||saved==='zh-TW')setLocale(saved);}catch{}initialized.current=true;},[]);
 useEffect(()=>{
   function onMessage(event) {
     if (event.source !== frame.current?.contentWindow || (event.origin !== location.origin && event.origin !== 'null')) return;
     const message = event.data;
     if (message?.type === 'startup-cami:about') {
       location.assign('/about');
       return;
     }
     if (message?.type !== 'startup-cami:locale' || !['en','zh-TW'].includes(message.locale)) return;
     setLocale(message.locale);

   }
   window.addEventListener('message',onMessage);
   return () => window.removeEventListener('message',onMessage);
 },[]);
 useEffect(()=>{let stopped=false,timer,controller;
 async function refresh(){controller=new AbortController();try{const r=await fetch('/api/canvas'+(locale?'?locale='+encodeURIComponent(locale):''),{cache:'no-store',signal:controller.signal});const data=await r.json();if(!r.ok)throw Error(data.error||'Cannot read YAML.');if(!stopped){try { reading.current=frame.current?.contentWindow?.__studio?.captureReading?.() || null; } catch {} setCanvas(old=>old?.hash===data.hash?old:data);setError(null);try {localStorage.setItem('startup-cami.display-locale',data.locale);} catch {} if(!locale&&['en','zh-TW'].includes(data.locale))setLocale(data.locale);}}catch(e){if(!stopped){setError(e.message);}}finally{if(!stopped)timer=setTimeout(refresh,1500);}}
 if(initialized.current)refresh();return ()=>{stopped=true;clearTimeout(timer);controller?.abort();};},[locale]);
 const t=MESSAGES[canvas?.locale||locale||'en'];
 const nav=<nav aria-label={locale==='zh-TW'?'頁面導覽':'Page navigation'} style={{height:36,boxSizing:'border-box',display:'flex',alignItems:'center',justifyContent:'space-between',padding:'0 16px',background:'#f3efe5',borderBottom:'1px solid #d7d0c0',font:'13px system-ui',color:'#625c51'}}><span>Cami Startup Canvas</span><a href="/about" style={{color:'#2448b6',textUnderlineOffset:3}}>{locale==='zh-TW'?'關於教材與社群':'About the material & community'}</a></nav>;
 if(error && !canvas)return <>{nav}<main role="alert" lang={locale||'en'} style={{padding:32,fontFamily:'system-ui'}}><h1>{t.title}</h1><pre style={{whiteSpace:'pre-wrap'}}>{error}</pre><p>{t.retry}</p></main></>;
 if(!canvas)return <>{nav}<p role="status">{locale?t.loading:'Cami Startup Canvas · 正在讀取 / Loading…'}</p></>;
 return <>{error && <div role="status" style={{position:"fixed",bottom:12,left:12,right:12,zIndex:100,background:"#fff9e9",padding:"8px 12px",border:"1px solid #bcad90",font:"14px system-ui"}}>{t.stale}</div>}<iframe key="canvas" onLoad={()=>{try { if(reading.current) frame.current?.contentWindow?.__studio?.restoreReading?.(reading.current); } catch {}}} ref={frame} title={t.frame} srcDoc={canvas.html} sandbox="allow-scripts allow-same-origin allow-downloads" style={{display:'block',border:0,width:'100vw',height:'100dvh'}}/></>;
}
