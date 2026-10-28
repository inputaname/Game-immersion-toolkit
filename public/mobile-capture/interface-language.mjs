import productCopy from './interface-copy.mjs';
export const interfaceLanguages={'en':'English','nl':'Nederlands','zh-Hans':'简体中文','zh-Hant':'繁體中文'};
const messages = {
 'Settings':['Instellingen','设置','設定'],
 'Capture source':['Bron voor vastleggen','捕获来源','擷取來源'],
 'Read subtitles from':['Ondertitels lezen van','字幕读取来源','字幕讀取來源'],
 'Game window on this PC':['Gamevenster op deze pc','此电脑上的游戏窗口','此電腦上的遊戲視窗'],
 'NDI® video on my local network':['NDI®-video op mijn lokale netwerk','本地网络上的 NDI® 视频','本機網路上的 NDI® 影像'],
 'NDI capture is set to':['NDI-vastleggen staat ingesteld op','NDI 捕获当前设置为','NDI 擷取目前設定為'],
 'Choose NDI here to switch it to this game.':['Kies hier NDI om over te schakelen naar deze game.','在此选择 NDI 即可切换到此游戏。','在此選擇 NDI 即可切換到此遊戲。'],
 'NDI source':['NDI-bron','NDI 来源','NDI 來源'],
 'Searching…':['Zoeken…','正在搜索…','正在搜尋…'],
 'Choose a source':['Kies een bron','选择来源','選擇來源'],
 'not found now':['nu niet gevonden','当前未找到','目前未找到'],
 'Search again':['Opnieuw zoeken','重新搜索','重新搜尋'],
 'Could not search for NDI sources.':['Kan niet naar NDI-bronnen zoeken.','无法搜索 NDI 来源。','無法搜尋 NDI 來源。'],
 'No NDI sources found. Start the broadcast on your phone, tablet or streaming PC, then search again.':['Geen NDI-bronnen gevonden. Start de uitzending op je telefoon, tablet of streaming-pc en zoek opnieuw.','未找到 NDI 来源。请在手机、平板或推流电脑上开始广播，然后重新搜索。','未找到 NDI 來源。請在手機、平板或串流電腦上開始廣播，然後重新搜尋。'],
 'Video goes directly between your devices on this network, without a relay or cloud service. NDI is not encrypted: anyone on the same network can find and watch the stream, so use a home network you trust.':['Video gaat rechtstreeks tussen je apparaten op dit netwerk, zonder relay of clouddienst. NDI is niet versleuteld: iedereen op hetzelfde netwerk kan de stream vinden en bekijken, dus gebruik een thuisnetwerk dat je vertrouwt.','视频直接在此网络中的设备之间传输，不经过中继或云服务。NDI 未加密：同一网络中的任何人都能发现并观看该串流，请使用你信任的家庭网络。','影像直接在此網路中的裝置之間傳輸，不經過中繼或雲端服務。NDI 未加密：同一網路中的任何人都能找到並觀看該串流，請使用你信任的家庭網路。'],
 'is a registered trademark of Vizrt NDI AB.':['is een geregistreerd handelsmerk van Vizrt NDI AB.','是 Vizrt NDI AB 的注册商标。','是 Vizrt NDI AB 的註冊商標。'],
 'Games & Languages':['Games en talen','游戏与语言','遊戲與語言'],
 'Capture':['Ondertitels vastleggen','字幕捕获','字幕擷取'],
 'Reading':['Lezen','阅读','閱讀'],
 'Source language font size':['Lettergrootte brontaal','原文语言字号','原文語言字級'],
 'Target language font size':['Lettergrootte doeltaal','译文语言字号','譯文語言字級'],
 'Game text':['Gametekst','游戏文本','遊戲文字'],
 'Search':['Zoeken','搜索','搜尋'],
 'Translation':['Vertaling','译文','譯文'],
 'Accounts':['Accounts','账户','帳戶'],
 'Storage':['Opslag','存储空间','儲存空間'],
 'General & Updates':['Algemeen en updates','通用与更新','一般與更新'],
 'Interface language':['Interfacetaal','界面语言','介面語言'],
 'Languages':['Talen','语言','語言'],
 'Learning language':['Leertaal','学习语言','學習語言'],
 'Translation language':['Vertaaltaal','翻译语言','翻譯語言'],
 'Search languages':['Talen zoeken','搜索语言','搜尋語言'],
 'Language':['Taal','语言','語言'],
 'Availability':['Beschikbaarheid','可用状态','可用狀態'],
 'Original voice':['Originele stem','原版配音','原版配音'],
 'Prepared table':['Voorbereide tabel','已准备的数据表','已準備的資料表'],
 'Ready':['Gereed','就绪','就緒'],
 'Selected':['Geselecteerd','已选中','已選取'],
 'Expected support':['Verwachte ondersteuning','预计支持','預期支援'],
 'Unsupported':['Niet ondersteund','不支持','不支援'],
 'Installed':['Geïnstalleerd','已安装','已安裝'],
 'Choose game folder':['Kies de gamemap','选择游戏文件夹','選擇遊戲資料夾'],
 'Checked during preparation':['Controle bij voorbereiding','准备时检查','準備時檢查'],
 'Prepare language':['Taal voorbereiden','准备语言','準備語言'],
 'Prepare translation':['Vertaling voorbereiden','准备翻译','準備翻譯'],
 'Use this language':['Deze taal gebruiken','使用此语言','使用此語言'],
 'Advanced':['Geavanceerd','高级','進階'],
 'Rebuild table':['Tabel opnieuw opbouwen','重建数据表','重建資料表'],
 'Remove table and free space':['Tabel verwijderen en ruimte vrijmaken','删除数据表并释放空间','刪除資料表並釋放空間'],
 'Remove prepared table?':['Voorbereide tabel verwijderen?','删除已准备的数据表？','刪除已準備的資料表？'],
 'Cancel':['Annuleren','取消','取消'],
 'Remove':['Verwijderen','删除','刪除'],
 'Reading and dictionaries':['Lezen en woordenboeken','阅读与词典','閱讀與字典'],
 'Language tables':['Taaltabellen','语言数据表','語言資料表'],
 'Shared audio cache':['Gedeelde audiocache','共享音频缓存','共用音訊快取'],
 'Shared tools':['Gedeelde hulpmiddelen','共享工具','共用工具'],
 'Game packs':['Taalpakketten van de game','游戏语言包','遊戲語言包'],
 'Managed by game launcher':['Beheerd door de gamelauncher','由游戏启动器管理','由遊戲啟動器管理'],
 'External exports':['Externe exports','外部导出文件','外部匯出檔案'],
 'Not measured':['Niet gemeten','未测量','未測量'],
 'Back':['Terug','返回','返回'],
 'Next':['Volgende','下一步','下一步'],
 'Finish setup':['Installatie afronden','完成设置','完成設定'],
 'Setup':['Instellen','设置向导','設定精靈'],
 'Toolkit setup':['Toolkit instellen','工具设置','工具設定'],
 'Game files':['Gamebestanden','游戏文件','遊戲檔案'],
 'Capture setup':['Opname instellen','捕获设置','擷取設定'],
 'Reading options':['Leesopties','阅读选项','閱讀選項'],
 'Account settings':['Accountinstellingen','账户设置','帳戶設定'],
 'Pause':['Pauzeren','暂停','暫停'],
 'Start':['Starten','开始','開始'],
 'History':['Geschiedenis','历史记录','歷史紀錄'],
 'Favorites':['Favorieten','收藏','收藏'],
 'Reader':['Lezer','阅读器','閱讀器'],
 'Library':['Bibliotheek','资料库','資料庫'],
 'Connection':['Verbinding','连接','連線'],
 'General':['Algemeen','通用','一般'],
 'Save':['Opslaan','保存','儲存'],
 'Close':['Sluiten','关闭','關閉'],
 'Retry':['Opnieuw proberen','重试','重試'],
 'Download':['Downloaden','下载','下載'],
 'Offline':['Offline','离线','離線'],
 'OCR language packs':['OCR-taalpakketten','OCR 语言包','OCR 語言包'],
 'Download selected pack':['Geselecteerd pakket downloaden','下载所选语言包','下載所選語言包'],
 'Remove selected pack':['Geselecteerd pakket verwijderen','删除所选语言包','刪除所選語言包'],
 'Available offline':['Offline beschikbaar','可离线使用','可離線使用'],
 'Download required':['Download nodig','需要下载','需要下載'],
 'Learning text requires its matching original voice. Prepare only the languages you use.':['Leertekst vereist de bijbehorende originele stem. Bereid alleen de talen voor die je gebruikt.','学习文本需要对应的原版配音。只准备你使用的语言。','學習文字需要對應的原版配音。只準備你使用的語言。'],
 'Expected support uses the same reader format; it does not require an export of every language.':['Verwachte ondersteuning gebruikt hetzelfde leesformaat; je hoeft niet elke taal te exporteren.','预计支持基于相同的数据读取格式，无需逐一导出所有语言。','預期支援基於相同的資料讀取格式，無需逐一匯出所有語言。'],
 'Enable this learning language in Lexirise to use it with this account.':['Schakel deze leertaal in Lexirise in voor dit account.','请在 Lexirise 中启用此学习语言。','請在 Lexirise 中啟用此學習語言。'],
 'No languages match your search.':['Geen talen gevonden.','没有匹配的语言。','沒有符合的語言。'],
 'Shared storage is counted once, not once per language.':['Gedeelde opslag wordt eenmaal geteld, niet per taal.','共享存储只计算一次，不按语言重复计算。','共用儲存空間只計算一次，不按語言重複計算。'],
 'Game files, history, favorites and credentials are kept. Prepare the table again to restore original-voice lookup.':['Gamebestanden, geschiedenis, favorieten en sleutels blijven behouden. Bereid de tabel opnieuw voor om originele stemmen terug te vinden.','游戏文件、历史记录、收藏和凭据将保留。重新准备数据表即可恢复原版配音查找。','遊戲檔案、歷史紀錄、收藏與憑證將保留。重新準備資料表即可恢復原版配音查找。'],
 'This clears the language selection for all local accounts.':['Dit wist de taalselectie voor alle lokale accounts.','这将清除所有本地账户的此语言选择。','這將清除所有本機帳戶的此語言選擇。'],
 'Reload':['Opnieuw laden','重新加载','重新載入'],
 'Free space':['Vrije ruimte','可用空间','可用空間'],
 'Get the latest toolkit release':['Nieuwste toolkit downloaden','获取最新版本','取得最新版本'],
 'Download setup report':['Installatierapport downloaden','下载设置报告','下載設定報告'],
 'Prepare only your chosen languages. Your game files stay on this PC.':['Bereid alleen je gekozen talen voor. Gamebestanden blijven op deze pc.','只准备所选语言。游戏文件保留在此电脑上。','只準備所選語言。遊戲檔案保留在此電腦上。'],
};
let current='en';
const listeners=new Set();
export function normalizeInterfaceLanguage(value='en'){
 if(value==='zh-Hant'||/^zh-(TW|HK|MO)/i.test(value))return 'zh-Hant';
 if(/^zh/i.test(value))return 'zh-Hans';
 return /^nl/i.test(value)?'nl':'en';
}
export function initializeInterfaceLanguage(){
 if(typeof window==='undefined')return;
 let saved;try{saved=localStorage.getItem('toolkit-interface-language');}catch{}
 current=normalizeInterfaceLanguage(saved||navigator.language);
 document.documentElement.lang=current;
}
export function getInterfaceLanguage(){return current;}
export function subscribeInterfaceLanguage(callback){listeners.add(callback);return()=>listeners.delete(callback);}
export function setInterfaceLanguage(value){
 current=normalizeInterfaceLanguage(value);
 try{localStorage.setItem('toolkit-interface-language',current);}catch{}
 if(typeof document!=='undefined')document.documentElement.lang=current;
 for(const callback of listeners)callback();
 if(typeof window!=='undefined')window.dispatchEvent(new Event('toolkit-interface-language'));
}
export function translate(message,locale=current){
 return locale==='en'?message:(messages[message]??productCopy[message])?.[['nl','zh-Hans','zh-Hant'].indexOf(locale)]??message;
}
export function languageName(code,locale=current){
 try{return new Intl.DisplayNames([locale],{type:'language'}).of(code)||code;}catch{return code;}
}
export function formatBytes(bytes,locale=current){
 if(bytes==null)return translate('Not measured',locale);
 const unit=bytes>=1073741824?'GiB':bytes>=1048576?'MiB':bytes>=1024?'KiB':'B';
 const divisor={GiB:1073741824,MiB:1048576,KiB:1024,B:1}[unit];
 return `${new Intl.NumberFormat(locale,{maximumFractionDigits:1}).format(bytes/divisor)} ${unit}`;
}
/** Bind only original application markup; never walk later user transcript content. */
export function bindStaticTranslation(root){
 const entries=[];
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 for(let node=walker.nextNode();node;node=walker.nextNode()){
  if(node.parentElement?.closest('script,style,code,pre,textarea'))continue;
  const original=node.textContent,trimmed=original.trim();
  if(trimmed&&(messages[trimmed]||productCopy[trimmed])){
   const target=node;let last=original;
   entries.push(()=>{if(target.textContent!==last)return;last=original.replace(trimmed,translate(trimmed));target.textContent=last;});
  }
 }
 const attributes=[];
 for(const element of root.querySelectorAll('[aria-label],[title],[placeholder]')){
  for(const attribute of ['aria-label','title','placeholder']){
   const original=element.getAttribute(attribute);
   if(original){let last=original;attributes.push(()=>{if(element.getAttribute(attribute)!==last)return;last=translate(original);element.setAttribute(attribute,last);});}
  }
 }
 const update=()=>{for(const apply of [...entries,...attributes])apply();};
 update();const unsubscribe=subscribeInterfaceLanguage(update);return unsubscribe;
}
if(typeof window!=='undefined'){
 initializeInterfaceLanguage();
 window.addEventListener('toolkit-interface-language',()=>{
  initializeInterfaceLanguage();for(const callback of listeners)callback();
 });
}
