/* One private subscription list, two delivery routes. No email persistence. */
(() => {
  "use strict";
  function submit(endpoints, email, action="subscribe", options={}) {
    const routes=[...new Set(endpoints.filter(Boolean))].filter(value=>{try{return new URL(value).protocol==="https:";}catch{return false;}});
    if(!routes.length)return Promise.reject(new Error("subscription_not_configured"));
    const timeout=options.timeout||18000, stagger=options.stagger??700;
    return new Promise((resolve,reject)=>{
      const controller=new AbortController(), timers=[];let settled=false, failed=0, lastError;
      const finish=(error,result)=>{if(settled)return;settled=true;timers.forEach(clearTimeout);controller.abort();error?reject(error):resolve(result);};
      const run=async route=>{
        if(settled)return;
        try {
          const result=await window.GruenBthTransport.request(route,{method:"POST",payload:{email,list:"climate-weekly"},accept:"application/json",signal:controller.signal,timeout});
          const expected=action==="unsubscribe"?"unsubscribed":"subscribed";
          if(result.ok!==true||result.status!==expected)throw new Error("subscription_not_confirmed");
          finish(null,result);
        }catch(error){if(settled)return;lastError=error;if(++failed===routes.length)finish(lastError);}
      };
      // A slow/unreachable route must not delay starting the alternate route.
      routes.forEach((route,index)=>{if(!index)run(route);else timers.push(setTimeout(()=>run(route),index*stagger));});
      timers.push(setTimeout(()=>finish(lastError||new Error("connection_timeout")),timeout+routes.length*stagger+500));
    });
  }
  window.GruenSubscriptions={submit};
})();
