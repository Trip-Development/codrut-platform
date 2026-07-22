export const THEME_PREPAINT_SCRIPT =
  "try{var e=document.documentElement,t=localStorage.getItem('codrut-theme'),m=t==='light'||t==='dark'||t==='system'?t:'system',d=typeof matchMedia==='function'&&matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light',r=m==='system'?d:m;e.dataset.theme=r;e.dataset.themeMode=m;var s=localStorage.getItem('codrut_sidebar_collapsed');if(s==='true'||s==='false')e.dataset.sidebarCollapsed=s}catch(_){}";

export const THEME_PREPAINT_CSP_HASH =
  "'sha256-imiWaVcflD5jY2/XlDhfNZhFQctIqLG4QVY+JCMXvNw='";
