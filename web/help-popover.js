(() => {
  'use strict';
  const DELAY=500, LEAVE_DELAY=150;
  let popover,anchor=null,openTimer=0,closeTimer=0,token=0,usingNative=false,openedOnPointerDown=null,ignoreFocus=null;
  const zh=()=>window.JournalI18n?.locale==='zh';
  const text=(en,cn)=>zh()?cn:en;
  const clear=()=>{clearTimeout(openTimer);clearTimeout(closeTimer);openTimer=closeTimer=0};
  const targetOf=node=>node instanceof Element?node.closest('[data-metric][data-metric-value]'):null;
  function create(){if(popover)return popover;popover=document.createElement('section');popover.id='metric-popover';popover.hidden=true;popover.setAttribute('role','dialog');usingNative=typeof popover.showPopover==='function';if(usingNative)popover.setAttribute('popover','manual');popover.addEventListener('mouseenter',()=>clearTimeout(closeTimer));popover.addEventListener('mouseleave',scheduleClose);popover.addEventListener('focusin',()=>clearTimeout(closeTimer));popover.addEventListener('focusout',e=>{if(!popover.contains(e.relatedTarget))scheduleClose()});document.body.append(popover);return popover}
  function infoFor(el){return window.JournalMetricInfo?.get?.(el.dataset.metric,el.dataset.metricValue,el.dataset.metricEdition)||null}
  function render(info){const p=create();p.setAttribute('aria-label',text('Metric information','指标说明'));p.replaceChildren();const head=document.createElement('div');head.className='metric-popover__head';const title=document.createElement('strong');title.className='metric-popover__title';title.textContent=info.title;const close=document.createElement('button');close.type='button';close.className='metric-popover__close';close.setAttribute('aria-label',text('Close','关闭'));close.textContent='×';close.addEventListener('click',closeNow);head.append(title,close);const description=document.createElement('p');description.className='metric-popover__description';description.textContent=info.description;const detail=document.createElement('p');detail.className='metric-popover__detail';detail.textContent=info.detail;p.append(head,description,detail);if(info.sourceUrl){const source=document.createElement('a');source.className='metric-popover__source';source.href=info.sourceUrl;source.target='_blank';source.rel='noopener noreferrer';source.textContent=text(`Official source: ${info.sourceLabel}`,`官方来源：${info.sourceLabel}`);p.append(source)}}
  function place(){if(!anchor||!popover||popover.hidden)return;const r=anchor.getBoundingClientRect(),p=popover.getBoundingClientRect(),gap=8;let top=r.bottom+gap,left=r.left;if(top+p.height>innerHeight-8)top=r.top-p.height-gap;if(left+p.width>innerWidth-8)left=innerWidth-p.width-8;popover.style.top=`${Math.max(8,Math.round(top))}px`;popover.style.left=`${Math.max(8,Math.round(left))}px`}
  function show(el,instant=false){if(!infoFor(el))return;clear();const current=++token;const open=()=>{if(current!==token||!el.isConnected)return;const info=infoFor(el);if(!info)return;if(anchor&&anchor!==el){anchor.setAttribute('aria-expanded','false');anchor.removeAttribute('aria-controls')}anchor=el;render(info);const p=create();const parent=el.closest('dialog[open]')||document.body;if(p.parentNode!==parent)parent.append(p);p.hidden=false;el.setAttribute('aria-expanded','true');el.setAttribute('aria-controls','metric-popover');if(usingNative&&!p.matches(':popover-open'))p.showPopover();place()};if(instant)open();else openTimer=setTimeout(open,DELAY)}
  function closeNow(){clear();token++;const old=anchor,returnFocus=!!old&&popover?.contains(document.activeElement);if(old){old.setAttribute('aria-expanded','false');old.removeAttribute('aria-controls')}if(popover&&usingNative&&popover.matches(':popover-open'))popover.hidePopover();if(popover)popover.hidden=true;anchor=null;if(returnFocus){ignoreFocus=old;old.focus()}}
  function scheduleClose(){clearTimeout(closeTimer);closeTimer=setTimeout(()=>{if(document.activeElement===anchor||popover?.contains(document.activeElement))return;closeNow()},LEAVE_DELAY)}
  function opened(){return !!anchor&&!popover?.hidden}
  document.addEventListener('DOMContentLoaded',()=>{
    document.addEventListener('pointerover',e=>{const el=targetOf(e.target);if(el&&e.pointerType!=='touch')show(el)});
    document.addEventListener('pointerout',e=>{const from=targetOf(e.target),to=targetOf(e.relatedTarget);if(from&&from!==to&&!popover?.contains(e.relatedTarget))scheduleClose()});
    document.addEventListener('pointerdown',e=>{const el=targetOf(e.target);openedOnPointerDown=opened()&&anchor===el?el:null});
    document.addEventListener('click',e=>{const el=targetOf(e.target);if(!el)return;if(openedOnPointerDown===el){closeNow();return}e.preventDefault();show(el,true)});
    document.addEventListener('focusin',e=>{const el=targetOf(e.target);if(el){if(ignoreFocus===el){ignoreFocus=null;return}show(el,true)}});
    document.addEventListener('focusout',e=>{const el=targetOf(e.target);if(el&&!popover?.contains(e.relatedTarget))scheduleClose()});
    document.addEventListener('keydown',e=>{const el=targetOf(e.target);if(el&&(e.key==='Enter'||e.key===' ')){e.preventDefault();show(el,true)}if(el&&e.key==='ArrowDown'){show(el,true);const next=popover?.querySelector('.metric-popover__source,.metric-popover__close');if(next){e.preventDefault();next.focus()}}if(e.key==='Escape'&&opened()){e.preventDefault();closeNow()}});
    addEventListener('resize',place);addEventListener('scroll',place,true);
    new MutationObserver(()=>{if(anchor&&!anchor.isConnected)closeNow()}).observe(document.body,{childList:true,subtree:true});
    addEventListener('journal-locale-change',()=>{if(!anchor)return;if(!anchor.isConnected){closeNow();return}show(anchor,true)})
  });
})();
