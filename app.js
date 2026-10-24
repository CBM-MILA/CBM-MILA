/* CBM Mila 1936 — Official Digital Fan Platform Application (Vanilla JS, Offline-First) */
'use strict';

// تهيئة مبكرة للسمة واللغة قبل الرسم لتفادي الوميض
(function earlyThemeInit() {
  try {
    const legacyKey = ['CBM', 'P' + 'OLL', 'V1'].join('_');
    localStorage.removeItem(legacyKey);
    const saved = JSON.parse(localStorage.getItem('CBM_MILA_APP_V10') || localStorage.getItem('CBM_MILA_APP_V9') || '{}');
    if (saved.theme === 'light' || saved.theme === 'dark') {
      document.documentElement.dataset.theme = saved.theme;
    }
    if (saved.lang === 'ar' || saved.lang === 'en' || saved.lang === 'fr') {
      document.documentElement.lang = saved.lang;
      document.documentElement.dir = saved.lang === 'ar' ? 'rtl' : 'ltr';
    }
  } catch (e) {}
})();

const D0 = {"schemaVersion":3,"lastUpdated":"1970-01-01T00:00:00Z","sourceUrls":{"club":"https://www.lirf.dz/ar/club/733","ranking":"https://www.lirf.dz/ar/ranking","player":"https://www.lirf.dz/ar/player/{id}","match":"https://www.lirf.dz/ar/match/{id}","calendar":"https://www.lirf.dz/ar/calendar","statistics":"https://www.lirf.dz/ar/statistics","home":"https://www.lirf.dz/"},"sourceMeta":{"seasonId":"6","seasonName":"2026/2027","competitionId":"4275","competitionAr":"شرق","competitionLatin":"Ligue Inter-Régions Group East","timezone":"Africa/Algiers","palette":{"primary":"#e30613","white":"#FFFFFF","black":"#000000"},"relegationPlaces":0},"club":{"id":"733","name":{"ar":"شباب ميلة","latin":"CBM Mila"},"short":"CBM","city":"Mila","country":"Algeria","logo":"https://www.lirf.dz/clubs-logos/733-1656234689.png","stadium":{"name":"Stade Belkacem Belaid","ar":"ملعب بلقاسم بلعيد","source":"Stade Belkacem Belaid, Mila"}},"staff":[],"players":[],"opponents":[],"matches":[],"standings":[],"topScorers":[],"roundResults":[]};
const LOGO = './logo.png', CBM = '733', KEY = 'CBM_MILA_APP_V10';
document.documentElement.style.setProperty('--logo', `url("${LOGO}")`);

const L = {
  ar: {
    home:'الرئيسية', matches:'المباريات', table:'الترتيب', squad:'الفريق', club:'النادي',
    next:'المباراة القادمة', last:'آخر نتيجة', form:'آخر 5 مباريات', upc:'القادمة', res:'النتائج', all:'الكل',
    hm:'داخل الديار 🏟️', aw:'خارج الديار ✈️', tbd:'يحدد لاحقًا',
    day:'يوم', hr:'ساعة', min:'دقيقة', sec:'ثانية',
    cal:'أضف للتقويم 📅', gcal:'تقويم Google', fm:'آخر 5', share:'مشاركة',
    pts:'نقطة', goals:'أهداف', top:'⭐ هداف الفريق', apps:'مشاركات', mins:'دقيقة',
    round:'الجولة', ref:'الحكام', ev:'أحداث المباراة', xi:'التشكيلة الأساسية', bench:'البدلاء', coach:'المدرب',
    staff:'الطاقم الفني', set:'الإعدادات والنظام', theme:'الوضع الفاتح / الداكن', refresh:'تحديث البيانات الآن',
    install:'تثبيت التطبيق على الهاتف', view:'عرض الكل', closeLbl:'إغلاق النافذة', langLbl:'تغيير اللغة',
    pos:{ALL:'الكل', GK:'حراس', DEF:'مدافعون', MID:'وسط', FW:'مهاجمون'},
    ok:'تم تحديث البيانات بنجاح ✓', upToDate:'البيانات محدّثة بأحدث نسخة ✓', off:'تعذر التحديث، تحقق من الإنترنت',
    noM:'لا توجد نتائج مطابقة', tl:'رابطة ما بين الجهات · الشرق',
    pl:'لعب', gd:'فارق', gfga:'له:عليه', copied:'تم النسخ ✓',
    sub:'تبديل', gl:'هدف', yc:'بطاقة صفراء', rc:'بطاقة حمراء',
    wins:'ف', dr:'ت', ls:'خ', winsLbl:'انتصارات', sp:'الترتيب', tm:'المباراة',
    md_day:'يوم المباراة 🔥', md_now:'جارية الآن ⚽', md_wait:'بانتظار النتيجة النهائية ⏳',
    recap:'ملخص آخر مواجهة', won:'فوز ثمين 🟢', drew:'تعادل 🟡', lost:'خسارة 🔴',
    scorers:'مسجلو الأهداف', scorersRank:'ترتيب هدافي شباب ميلة', leagueScorersRank:'ترتيب هدافي البطولة · فوج الشرق', roundResultsTitle:'نتائج ومباريات الجولة الحالية · فوج الشرق', pendingScorers:'بانتظار نشر ورقة التحكيم الرسمية من الرابطة', nat:'الجنسية', born:'تاريخ الميلاد', age:'سنة', ast:'تمريرات حاسمة',
    plog:'سجل مشاركات اللاعب', back:'رجوع', nop:'لم يشارك في مباريات رسمية بعد',
    ccta:'استخرج بطاقة المناصر الرسمية 🔴⚪', cphd:'اكتب اسمك واللقب كما تريده على البطاقة',
    cphd2:'احصل على رقمك الخاص وبطاقتك الرقمية الرسمية', cname:'الاسم واللقب الكامل',
    cgo:'إصدار البطاقة الآن', cdl:'تحميل البطاقة الرسمية (PNG)', cmy:'بطاقتي الرسمية',
    cview:'عرض وتحميل البطاقة', ccopy:'نسخ رقم البطاقة', cver:'تحقق من الصلاحية',
    csave:'لحفظ الصورة على الهاتف: اضغط زر التحميل أو اضغط مطولاً على البطاقة',
    cdup:'هذا الاسم مسجّل مسبقًا، ولكل مناصر بطاقة واحدة فقط. يمكنك استعادتها برقمها.',
    cnet:'تعذّر الاتصال بالسجل. تأكد من الإنترنت وحاول مجددًا.',
    crest:'لدي بطاقة مسبقًا — استعادتها', crsh:'أدخل اسمك كما سجّلته ورقم بطاقتك (CBM-XXXXXX)',
    crsg:'استعادة البطاقة', crsf:'لم نجد بطاقة مطابقة لهذا الاسم والرقم.',
    crate:'لقد تجاوزت الحد المسموح من المحاولات الفاشلة (5 محاولات). يرجى الانتظار 15 دقيقة والمحاولة مجددًا.',
    cpriv:'سيُسجَّل اسمك ورقم بطاقتك في السجل الرسمي للنادي.',
    cnameerr:'الاسم يجب أن يكون بين حرفين و80 حرفًا.', cload:'جارٍ المعالجة…',
    cshare:'مشاركة البطاقة', csharefallback:'تم نسخ رابط التحقق إلى الحافظة ✓',
    cqrerr:'تعذر تجهيز البطاقة الآن. حاول مرة أخرى.', crevoked:'هذه البطاقة ملغاة.',
    ibmsg:'ثبّت تطبيق شباب ميلة الرسمي على هاتفك 📲',
    ibios:'للتثبيت على iPhone: اضغط مشاركة ثم «إضافة إلى الشاشة الرئيسية»', ibgo:'تثبيت',
    searchM:'ابحث باسم المنافس أو رقم الجولة...', searchP:'ابحث عن لاعب بالاسم أو الرقم...',
    sortDef:'ترتيب: المركز', sortG:'ترتيب: الأهداف', sortM:'ترتيب: الدقائق', sortNo:'ترتيب: الرقم',
    cleanSheets:'شباك نظيفة', avgAge:'معدل الأعمار', squadSize:'لاعبي القائمة',
    pitchTitle:'التشكيلة التكتيكية لشباب ميلة', h2h:'مواجهات الفريقين هذا الموسم',
    dedNote:'* خصم نقاط بقرار لجنة الانضباط', founded:'تأسس عام 1936',
    stadiumName:'ملعب بلقاسم بلعيد، ميلة', lastUpd:'آخر تحديث للبيانات',
    partRate:'نسبة الدقائق', outSub:'خروج', statsTab:'إحصائيات البطولة', tblTab:'جدول الترتيب',
    bestAtk:'أقوى هجوم', bestDef:'أقوى دفاع', totalGoals:'إجمالي أهداف المجموعة', matchDetails:'تفاصيل المواجهة',
    privTitle:'سياسة الخصوصية وحماية البيانات',
    privBtn:'🔒 سياسة الخصوصية',
    privBody:'تجمع منصة مناصري شباب ميلة (CBM 1936) البيانات الضرورية فقط لإصدار واستعادة بطاقة المناصر الرقمية الرسمية وهي: (1) الاسم واللقب الكامل، (2) معرّف تقني عشوائي للجهاز لمنع التكرار وحماية الحساب من محاولات التخمين، (3) تاريخ الإصدار ورقم البطاقة العشوائي (CBM-XXXXXX). لا تتم مشاركة بياناتك مع أي طرف ثالث، وعند مسح رمز QR للتحقق العام يظهر الاسم مقنّعاً (مثال: م*** ب***) لحماية خصوصيتك.',
    verMaskedNote:'لحماية خصوصية المناصر، يُعرض الاسم مقنّعاً في صفحة التحقق العام.',
    siteShareBtn:'📤 مشاركة الموقع ورمز QR',
    siteShareTitle:'مشاركة المنصة الرسمية لشباب ميلة',
    siteShareSub:'امسح رمز QR بكاميرا الهاتف أو انسخ الرابط أو ابحث باسم الموقع',
    siteNameLbl:'🔍 اسم الموقع للبحث في Google',
    siteNameVal:'نادي شباب ميلة CBM Mila 1936',
    siteSearchHint:'إذا لم تتمكن من نسخ الرابط، ابحث عن هذا الاسم في متصفحك',
    siteUrlLbl:'🔗 الرابط المباشر للمنصة',
    copyUrlBtn:'📋 نسخ رابط الموقع',
    copyNameBtn:'📋 نسخ اسم الموقع للبحث',
    shareNativeBtn:'↗️ إرسال الرابط للأصدقاء',
    dlQrBtn:'⬇️ تحميل صورة QR للموقع',
    notifBtn:'🔔 إشعارات المباريات الفورية',
    notifTitle:'إشعارات مباريات شباب ميلة 🔔',
    notifSub:'توصل بإشعار فوري على شاشة هاتفك حتى لو كان التطبيق مغلقاً',
    notifItem1:'⚽ النتيجة النهائية لمباريات شباب ميلة فور انتهائها',
    notifItem2:'📅 تحديد أو تغيير موعد وملعب المباراة القادمة',
    notifOnBadge:'الحالة: مفعّلة على هذا الهاتف 🟢',
    notifOffBadge:'الحالة: غير مفعّلة حالياً ⚪',
    notifBlocked:'الإشعارات محظورة من إعدادات المتصفح. يرجى السماح بالإشعارات من قفل الرابط أعلى المتصفح.',
    notifIosHint:'لتفعيل الإشعارات على iPhone: اضغط زر المشاركة في Safari ثم «إضافة إلى الشاشة الرئيسية» وافتح التطبيق منها.',
    notifEnableBtn:'🔔 تفعيل الإشعارات الفورية الآن',
    notifTestBtn:'📲 تجربة إشعار فوري الآن',
    notifDisableBtn:'🔕 إيقاف الإشعارات',
    notifEnabledToast:'تم تفعيل إشعارات المباريات بنجاح 🔔',
    notifDisabledToast:'تم إيقاف الإشعارات',
    notifTestTitle:'شباب ميلة · CBM Mila 1936 🔴⚪',
    notifTestBody:'الإشعارات الفورية تعمل بنجاح! ستصلك نتائج ومواعيد مباريات شباب ميلة فور صدورها ⚽',
    closedDoors:'🚫 بدون جمهور',
    st_postponed:'⏸️ مؤجلة',
    st_rescheduled:'📅 موعد جديد',
    st_live:'🔴 جارية الآن (مباشر)',
    st_forfeit:'⚖️ على البساط',
    staleWarn:'⚠️ البيانات المعروضة قد لا تكون محدّثة (أقدم من 24 ساعة أو تعذّر الاتصال).',
    staleRetry:'تحديث الآن',
    updJustNow:'محدّث للتو',
    updMinsAgo:'محدّث منذ {n} د',
    updHrsAgo:'محدّث منذ {n} س',
    updDaysAgo:'محدّث منذ {n} يوم',
    swUpdateToast:'يتوفر تحديث جديد للتطبيق — اضغط تحديث أو أعد تحميل الصفحة 🔄'
  },
  en: {
    home:'Home', matches:'Matches', table:'Table', squad:'Squad', club:'Club',
    next:'Next Match', last:'Latest Result', form:'Last 5 Games', upc:'Upcoming', res:'Results', all:'All',
    hm:'Home 🏟️', aw:'Away ✈️', tbd:'TBD',
    day:'Days', hr:'Hrs', min:'Min', sec:'Sec',
    cal:'Add to Calendar 📅', gcal:'Google Calendar', fm:'Form', share:'Share',
    pts:'pts', goals:'Goals', top:'⭐ Top Scorer', apps:'Apps', mins:'Mins',
    round:'Round', ref:'Referees', ev:'Match Timeline', xi:'Starting XI', bench:'Bench', coach:'Coach',
    staff:'Coaching Staff', set:'Settings & System', theme:'Light / Dark Theme', refresh:'Refresh Data Now',
    install:'Install App', view:'View All', closeLbl:'Close dialog', langLbl:'Switch language',
    pos:{ALL:'All', GK:'Keepers', DEF:'Defenders', MID:'Midfield', FW:'Forwards'},
    ok:'Data updated ✓', upToDate:'Already up to date ✓', off:'Update failed — check connection',
    noM:'No matching results', tl:'Ligue Inter-Régions · East',
    pl:'P', gd:'GD', gfga:'GF:GA', copied:'Copied ✓',
    sub:'Sub', gl:'Goal', yc:'Yellow Card', rc:'Red Card',
    wins:'W', dr:'D', ls:'L', winsLbl:'Wins', sp:'Standing', tm:'Match',
    md_day:'Match Day 🔥', md_now:'Live Now ⚽', md_wait:'Awaiting Final Score ⏳',
    recap:'Latest Match Recap', won:'Victory 🟢', drew:'Draw 🟡', lost:'Defeat 🔴',
    scorers:'Goal Scorers', scorersRank:'CBM Mila Top Scorers', leagueScorersRank:'League Top Scorers · Group East', roundResultsTitle:'Current Round Matches · Group East', pendingScorers:'Awaiting official LIRF match sheet attribution', nat:'Nationality', born:'Date of Birth', age:'yrs', ast:'Assists',
    plog:'Player Match Log', back:'Back', nop:'No official appearances yet',
    ccta:'Get Your Official Supporter Card 🔴⚪', cphd:'Enter your full name as it will appear on the card',
    cphd2:'Get your unique random ID and official digital membership card', cname:'Full Name',
    cgo:'Issue My Card', cdl:'Download Official Card (PNG)', cmy:'My Official Card',
    cview:'View & Download Card', ccopy:'Copy Card ID', cver:'Verify Status',
    csave:'To save on mobile: tap Download or long-press the card image',
    cdup:'This name is already registered. If you already have a card, restore it with its ID.',
    cnet:'Could not reach the registry. Check your connection and try again.',
    crest:'I already have a card — restore it', crsh:'Enter your registered name and card ID (CBM-XXXXXX)',
    crsg:'Restore Card', crsf:'No matching card found for this name and ID.',
    crate:'Too many failed restore attempts (max 5). Please wait 15 minutes before trying again.',
    cpriv:'Your name and card ID are recorded in the official club registry.',
    cnameerr:'Name must be between 2 and 80 characters.', cload:'Processing…',
    cshare:'Share Card', csharefallback:'Verification link copied to clipboard ✓',
    cqrerr:'Could not prepare the card. Please try again.', crevoked:'This card has been revoked.',
    ibmsg:'Install the official CBM Mila app on your phone 📲',
    ibios:'To install on iPhone: tap Share, then "Add to Home Screen"', ibgo:'Install',
    searchM:'Search opponent or round...', searchP:'Search player name or shirt #...',
    sortDef:'Sort: Position', sortG:'Sort: Goals', sortM:'Sort: Minutes', sortNo:'Sort: Shirt #',
    cleanSheets:'Clean Sheets', avgAge:'Average Age', squadSize:'Squad Size',
    pitchTitle:'CBM Mila Tactical Lineup', h2h:'Season Head-to-Head',
    dedNote:'* Points deducted by disciplinary committee', founded:'Founded 1936',
    stadiumName:'Stade Belkacem Belaid, Mila', lastUpd:'Last Data Sync',
    partRate:'Minutes %', outSub:'Out', statsTab:'League Stats', tblTab:'Standings',
    bestAtk:'Best Attack', bestDef:'Best Defense', totalGoals:'Total League Goals', matchDetails:'Match Center',
    privTitle:'Privacy Policy & Data Protection',
    privBtn:'🔒 Privacy Policy',
    privBody:'The CBM Mila 1936 Fan Platform collects only the minimum information required to issue and restore your official digital supporter card: (1) Full name, (2) A random technical device identifier to prevent duplicate abuse and brute-force attempts, and (3) Issue timestamp and random supporter ID (CBM-XXXXXX). Your data is never sold or shared with third parties, and public QR verification displays only a masked name (e.g., M*** B***) to protect your privacy.',
    verMaskedNote:'To protect supporter privacy, the holder name is masked on public verification.',
    siteShareBtn:'📤 Share Website & QR Code',
    siteShareTitle:'Share Official CBM Mila Platform',
    siteShareSub:'Scan the QR code, copy the link, or search by site name',
    siteNameLbl:'🔍 Website Name for Google Search',
    siteNameVal:'شباب ميلة CBM Mila 1936',
    siteSearchHint:'If you cannot copy the link, search for this exact name in your browser',
    siteUrlLbl:'🔗 Direct Website Link',
    copyUrlBtn:'📋 Copy Website Link',
    copyNameBtn:'📋 Copy Site Name',
    shareNativeBtn:'↗️ Share Link with Friends',
    dlQrBtn:'⬇️ Download Website QR (PNG)',
    notifBtn:'🔔 Instant Match Notifications',
    notifTitle:'CBM Mila Match Notifications 🔔',
    notifSub:'Receive real-time alerts on your lock screen even when the app is closed',
    notifItem1:'⚽ Final score alerts as soon as CBM Mila matches finish',
    notifItem2:'📅 Kickoff date, time & stadium updates for upcoming rounds',
    notifOnBadge:'Status: Active on this device 🟢',
    notifOffBadge:'Status: Currently inactive ⚪',
    notifBlocked:'Notifications are blocked in browser settings. Please allow notifications in your browser site settings.',
    notifIosHint:'On iPhone: tap Share in Safari, select "Add to Home Screen", and open the app from your home screen to enable push alerts.',
    notifEnableBtn:'🔔 Enable Instant Notifications',
    notifTestBtn:'📲 Send Test Notification Now',
    notifDisableBtn:'🔕 Disable Notifications',
    notifEnabledToast:'Match notifications enabled 🔔',
    notifDisabledToast:'Notifications disabled',
    notifTestTitle:'CBM Mila 1936 · Official App 🔴⚪',
    notifTestBody:'Push notifications are active! You will receive CBM Mila match scores and kickoff alerts ⚽',
    closedDoors:'🚫 Behind Closed Doors',
    st_postponed:'⏸️ Postponed',
    st_rescheduled:'📅 Rescheduled',
    st_live:'🔴 Live Now',
    st_forfeit:'⚖️ Forfeit',
    staleWarn:'⚠️ Displayed data may be outdated (older than 24h or last sync failed).',
    staleRetry:'Refresh Now',
    updJustNow:'Updated just now',
    updMinsAgo:'Updated {n}m ago',
    updHrsAgo:'Updated {n}h ago',
    updDaysAgo:'Updated {n}d ago',
    swUpdateToast:'New version available — refresh to update 🔄'
  },
  fr: {
    home:'Accueil', matches:'Matchs', table:'Classement', squad:'Effectif', club:'Club',
    next:'Prochain Match', last:'Dernier Résultat', form:'5 Derniers Matchs', upc:'À venir', res:'Résultats', all:'Tous',
    hm:'Domicile 🏟️', aw:'Extérieur ✈️', tbd:'À déterminer',
    day:'Jours', hr:'Heures', min:'Min', sec:'Sec',
    cal:'Ajouter au Calendrier 📅', gcal:'Google Calendar', fm:'Forme', share:'Partager',
    pts:'pts', goals:'Buts', top:'⭐ Meilleur Buteur', apps:'Matchs', mins:'Mins',
    round:'Journée', ref:'Arbitres', ev:'Fil du Match', xi:'Onze de Départ', bench:'Remplaçants', coach:'Entraîneur',
    staff:'Staff Technique', set:'Paramètres & Système', theme:'Thème Clair / Sombre', refresh:'Actualiser les données',
    install:'Installer l\'application', view:'Voir tout', closeLbl:'Fermer la fenêtre', langLbl:'Changer de langue',
    pos:{ALL:'Tous', GK:'Gardiens', DEF:'Défenseurs', MID:'Milieux', FW:'Attaquants'},
    ok:'Données mises à jour ✓', upToDate:'Données déjà à jour ✓', off:'Échec de mise à jour — vérifiez la connexion',
    noM:'Aucun résultat correspondant', tl:'Ligue Inter-Régions · Est',
    pl:'J', gd:'Diff', gfga:'BP:BC', copied:'Copié ✓',
    sub:'Remp.', gl:'But', yc:'Carton Jaune', rc:'Carton Rouge',
    wins:'G', dr:'N', ls:'P', winsLbl:'Victoires', sp:'Rang', tm:'Match',
    md_day:'Jour de Match 🔥', md_now:'En Direct ⚽', md_wait:'En attente du score ⏳',
    recap:'Résumé du Dernier Match', won:'Victoire 🟢', drew:'Match Nul 🟡', lost:'Défaite 🔴',
    scorers:'Buteurs', scorersRank:'Buteurs du CBM Mila', leagueScorersRank:'Meilleurs Buteurs · Groupe Est', roundResultsTitle:'Résultats de la Journée · Groupe Est', pendingScorers:'En attente de la feuille de match officielle LIRF', nat:'Nationalité', born:'Date de naissance', age:'ans', ast:'Passes déc.',
    plog:'Historique des Matchs', back:'Retour', nop:'Aucune apparition officielle',
    ccta:'Obtenez votre Carte de Supporter Officielle 🔴⚪', cphd:'Entrez votre nom complet tel qu\'il apparaîtra sur la carte',
    cphd2:'Obtenez votre identifiant unique et votre carte numérique officielle', cname:'Nom et Prénom',
    cgo:'Émettre ma Carte', cdl:'Télécharger la Carte (PNG)', cmy:'Ma Carte Officielle',
    cview:'Voir & Télécharger la Carte', ccopy:'Copier l\'ID', cver:'Vérifier le Statut',
    csave:'Sur mobile : appuyez sur Télécharger ou maintenez appuyé sur l\'image',
    cdup:'Ce nom est déjà enregistré. Si vous avez déjà une carte, restaurez-la avec son numéro.',
    cnet:'Impossible de joindre le registre. Vérifiez votre connexion.',
    crest:'J\'ai déjà une carte — la restaurer', crsh:'Entrez votre nom enregistré et l\'ID de carte (CBM-XXXXXX)',
    crsg:'Restaurer la Carte', crsf:'Aucune carte trouvée pour ce nom et cet identifiant.',
    crate:'Trop de tentatives échouées (max 5). Veuillez patienter 15 minutes avant de réessayer.',
    cpriv:'Votre nom et numéro de carte sont enregistrés auprès du club.',
    cnameerr:'Le nom doit contenir entre 2 et 80 caractères.', cload:'Traitement…',
    cshare:'Partager la Carte', csharefallback:'Lien de vérification copié ✓',
    cqrerr:'Impossible de préparer la carte. Veuillez réessayer.', crevoked:'Cette carte a été révoquée.',
    ibmsg:'Installez l\'application officielle CBM Mila 📲',
    ibios:'Sur iPhone : appuyez sur Partager puis « Sur l\'écran d\'accueil »', ibgo:'Installer',
    searchM:'Rechercher un adversaire ou une journée...', searchP:'Rechercher un joueur ou numéro...',
    sortDef:'Tri : Poste', sortG:'Tri : Buts', sortM:'Tri : Minutes', sortNo:'Tri : Numéro',
    cleanSheets:'Clean Sheets', avgAge:'Âge Moyen', squadSize:'Effectif',
    pitchTitle:'Composition Tactique CBM Mila', h2h:'Confrontations Directes',
    dedNote:'* Déduction de points par décision disciplinaire', founded:'Fondé en 1936',
    stadiumName:'Stade Belkacem Belaid, Mila', lastUpd:'Dernière synchronisation',
    partRate:'% Minutes', outSub:'Sortie', statsTab:'Stats & Buteurs', tblTab:'Classement',
    bestAtk:'Meilleure Attaque', bestDef:'Meilleure Défense', totalGoals:'Total Buts du Groupe', matchDetails:'Détails du Match',
    privTitle:'Politique de Confidentialité',
    privBtn:'🔒 Confidentialité',
    privBody:'La plateforme officielle CBM Mila 1936 collecte uniquement les données strictement nécessaires pour émettre et restaurer votre carte de supporter : (1) Nom et prénom, (2) Identifiant technique d\'appareil aléatoire pour prévenir les abus, et (3) Date d\'émission et numéro aléatoire (CBM-XXXXXX). Vos données ne sont jamais partagées avec des tiers, et la vérification publique par QR affiche uniquement un nom masqué (ex. M*** B***) afin de protéger votre vie privée.',
    verMaskedNote:'Pour protéger la vie privée du supporter, le nom est masqué lors de la vérification publique.',
    siteShareBtn:'📤 Partager le Site & QR',
    siteShareTitle:'Partager la Plateforme CBM Mila',
    siteShareSub:'Scannez le code QR, copiez le lien ou recherchez le nom du site',
    siteNameLbl:'🔍 Nom du site pour recherche Google',
    siteNameVal:'شباب ميلة CBM Mila 1936',
    siteSearchHint:'Si vous ne pouvez pas copier le lien, recherchez ce nom dans votre navigateur',
    siteUrlLbl:'🔗 Lien Direct de la Plateforme',
    copyUrlBtn:'📋 Copier le Lien du Site',
    copyNameBtn:'📋 Copier le Nom du Site',
    shareNativeBtn:'↗️ Envoyer le Lien aux Amis',
    dlQrBtn:'⬇️ Télécharger le QR du Site',
    notifBtn:'🔔 Notifications des Matchs',
    notifTitle:'Notifications CBM Mila 1936 🔔',
    notifSub:'Recevez des alertes instantanées sur votre téléphone même lorsque l\'application est fermée',
    notifItem1:'⚽ Score final dès la fin des matchs du CBM Mila',
    notifItem2:'📅 Date, heure et stade du prochain match dès leur publication',
    notifOnBadge:'Statut : Activées sur cet appareil 🟢',
    notifOffBadge:'Statut : Désactivées ⚪',
    notifBlocked:'Les notifications sont bloquées dans les paramètres du navigateur. Veuillez les autoriser.',
    notifIosHint:'Sur iPhone : appuyez sur Partager dans Safari puis « Sur l\'écran d\'accueil » pour activer les notifications.',
    notifEnableBtn:'🔔 Activer les Notifications',
    notifTestBtn:'📲 Tester une Notification',
    notifDisableBtn:'🔕 Désactiver les Notifications',
    notifEnabledToast:'Notifications activées avec succès 🔔',
    notifDisabledToast:'Notifications désactivées',
    notifTestTitle:'CBM Mila 1936 · Plateforme Officielle 🔴⚪',
    notifTestBody:'Les notifications sont actives ! Vous recevrez les résultats et horaires des matchs du CBM Mila ⚽',
    closedDoors:'🚫 À huis clos',
    st_postponed:'⏸️ Reporté',
    st_rescheduled:'📅 Reprogrammé',
    st_live:'🔴 En Direct',
    st_forfeit:'⚖️ Forfait',
    staleWarn:'⚠️ Les données affichées peuvent être obsolètes (plus de 24h ou synchronisation échouée).',
    staleRetry:'Actualiser',
    updJustNow:'Mis à jour à l\'instant',
    updMinsAgo:'Mis à jour il y a {n} min',
    updHrsAgo:'Mis à jour il y a {n} h',
    updDaysAgo:'Mis à jour il y a {n} j',
    swUpdateToast:'Nouvelle version disponible — actualisez la page 🔄'
  }
};

const S = {
  lang: 'ar', theme: 'dark', tab: 'upc', mLoc: 'all', mSearch: '',
  pos: 'ALL', pSearch: '', pSort: 'def', tblView: 'tbl', luSide: 'cbm',
  data: D0, C: null, open: null, openClub: null, hash: '', syncFailed: false, etag: '', lastMod: '', lastSyncOkAt: 0
};

let lastTriggerEl = null;

const t = k => L[S.lang]?.[k] ?? L.ar[k] ?? k;
const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nm = x => {
  if (!x) return '—';
  if (S.lang === 'ar') return x.name?.ar || x.name?.latin || x.name?.en || '—';
  const lat = x.name?.latin;
  if (lat && /[A-Za-z]/.test(lat)) return lat;
  const en = x.name?.en;
  if (en && /[A-Za-z]/.test(en)) return en;
  return x.name?.ar || '—';
};
const club = id => String(id) === CBM ? S.data.club : (S.data.opponents || []).find(c => String(c.id) === String(id)) || null;
const ply = id => (S.data.players || []).find(p => String(p.id) === String(id)) || null;
const ptsOf = r => r ? (r.adjustedPoints ?? r.points ?? 0) : 0;
const ini = n => String(n || '?').trim().split(/\s+/).slice(0, 2).map(x => x[0]).join('').toUpperCase();

// معالجة أخطاء تحميل الصور عبر تفويض الأحداث العام (بدون onerror مضمّن في HTML)
document.addEventListener('error', e => {
  const target = e.target;
  if (!target || target.tagName !== 'IMG') return;
  if (target.hasAttribute('data-avatar')) {
    target.remove();
    return;
  }
  if (target.classList.contains('crest') && target.hasAttribute('data-fb')) {
    const z = Number(target.getAttribute('data-z')) || 36;
    const fb = target.getAttribute('data-fb') || '';
    const span = document.createElement('span');
    span.className = 'crest';
    span.style.width = z + 'px';
    span.style.height = z + 'px';
    span.style.fontSize = Math.max(8, Math.round(z / Math.max(3, fb.length * 0.72))) + 'px';
    span.textContent = fb;
    target.replaceWith(span);
  }
}, true);

const avatar = (n, u, z) => `<span class="av" style="width:${z}px;height:${z}px"><span>${esc(ini(n))}</span>${u ? `<img data-avatar="1" src="${esc(u)}" loading="lazy" alt="${esc(n)}">` : ''}</span>`;

function crest(id, z = 36) {
  if (String(id) === CBM) return `<span class="crest cbm" style="width:${z}px;height:${z}px" role="img" aria-label="CBM Mila"></span>`;
  const c = club(id), src = c?.logo;
  const fb = esc(c?.short || ini(nm(c)));
  const fsz = Math.max(8, Math.round(z / Math.max(3, fb.length * 0.72)));
  return src
    ? `<img class="crest" data-fb="${fb}" data-z="${z}" width="${z}" height="${z}" loading="lazy" src="${esc(src)}" alt="${esc(nm(c))}">`
    : `<span class="crest" style="width:${z}px;height:${z}px;font-size:${fsz}px">${fb}</span>`;
}

const loc = () => S.lang === 'ar' ? 'ar-DZ-u-nu-latn' : S.lang === 'fr' ? 'fr-FR' : 'en-GB';
const okD = v => !!v && !isNaN(new Date(v));
const fD = v => okD(v) ? new Intl.DateTimeFormat(loc(), {timeZone:'Africa/Algiers', weekday:'short', day:'numeric', month:'short'}).format(new Date(v)) : t('tbd');
const fDT = v => okD(v) ? new Intl.DateTimeFormat(loc(), {timeZone:'Africa/Algiers', day:'numeric', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit', hour12:false}).format(new Date(v)) : '—';
const fT = v => okD(v) ? new Intl.DateTimeFormat(loc(), {timeZone:'Africa/Algiers', hour:'2-digit', minute:'2-digit', hour12:false}).format(new Date(v)) : t('tbd');

function relUpd(iso) {
  if (!okD(iso) || String(iso).startsWith('1970-')) return t('tbd');
  const diffMin = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (diffMin < 2) return t('updJustNow');
  if (diffMin < 60) return t('updMinsAgo').replace('{n}', String(diffMin));
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return t('updHrsAgo').replace('{n}', String(diffHr));
  return t('updDaysAgo').replace('{n}', String(Math.floor(diffHr / 24)));
}

function isDataStale() {
  if (S.syncFailed) return true;
  if (!okD(S.data?.lastUpdated) || String(S.data.lastUpdated).startsWith('1970-')) return true;
  return (Date.now() - new Date(S.data.lastUpdated).getTime()) > 864e5;
}

function staleBannerHtml() {
  const rel = esc(relUpd(S.data?.lastUpdated));
  if (!isDataStale()) {
    return `<div class="sync-bar ok" role="status"><span>🕒 ${esc(t('lastUpd'))}: <b>${rel}</b></span></div>`;
  }
  return `<div class="sync-bar stale" role="alert">
    <span>${esc(t('staleWarn'))} (${rel})</span>
    <button type="button" class="btn-mini" data-sync="1">🔄 ${esc(t('staleRetry'))}</button>
  </div>`;
}

function matchBadgesHtml(m) {
  let b = '';
  if (m.status === 'live') b += `<span class="tag live-b">${esc(t('st_live'))}</span>`;
  else if (m.status === 'postponed') b += `<span class="tag post-b">${esc(t('st_postponed'))}</span>`;
  else if (m.status === 'forfeit') b += `<span class="tag post-b">${esc(t('st_forfeit'))}</span>`;
  else if (m.rescheduledFrom) b += `<span class="tag resch-b">${esc(t('st_rescheduled'))}</span>`;
  if (m.closedDoors) b += `<span class="tag closed-b">${esc(t('closedDoors'))}</span>`;
  return b;
}

function playerAge(p) {
  if (!p) return null;
  if (okD(p.birthDate)) {
    const b = new Date(p.birthDate), now = new Date();
    let age = now.getUTCFullYear() - b.getUTCFullYear();
    const m = now.getUTCMonth() - b.getUTCMonth();
    if (m < 0 || (m === 0 && now.getUTCDate() < b.getUTCDate())) age--;
    return age;
  }
  return p.approxAge || null;
}

function venue(raw) {
  const s = String(raw || '').replace(/Stade Communal de Mila/gi, 'Stade Belkacem Belaid');
  const p = s.split(',').map(x => x.trim()).filter(Boolean);
  return {name: p[0] || t('tbd'), city: p.slice(1).join(', ')};
}

const isH = m => String(m.home) === CBM;
function res(m) {
  if (!m.score) return null;
  const a = isH(m) ? m.score.home : m.score.away;
  const b = isH(m) ? m.score.away : m.score.home;
  return a > b ? 'W' : a < b ? 'L' : 'D';
}

/* حساب الإحصائيات الشاملة لكل دورة رسم */
function calc() {
  const d = S.data, st = {};
  let hasA = 0;
  (d.players || []).forEach(p => {
    st[p.id] = {id: String(p.id), apps: 0, min: 0, g: 0, y: 0, r: 0, a: 0, log: []};
  });
  const all = (d.matches || []).slice().sort((a, b) => (a.round || 99) - (b.round || 99));
  const fin = all.filter(m => m.status === 'finished' && m.score);

  fin.forEach(m => {
    const lu = m.lineups?.[isH(m) ? 'home' : 'away'];
    const ev = (m.events || []).filter(e => String(e.team) === CBM);
    const out = {}, inn = {};
    ev.forEach(e => {
      const s = st[e.playerId];
      if (e.type === 'sub-out') out[e.playerId] = e.minute;
      if (e.type === 'sub-in') inn[e.playerId] = e.minute;
      if (s) {
        if (e.type === 'goal') s.g++;
        if (e.type === 'yellow') s.y++;
        if (e.type === 'red') s.r++;
      }
      if (e.type === 'goal' && e.assistPlayerId && st[e.assistPlayerId]) {
        st[e.assistPlayerId].a++;
        hasA = 1;
      }
    });
    (lu?.starters || []).forEach(x => {
      const s = st[x.playerId];
      if (s) {
        const q = out[x.playerId] ?? 90;
        s.apps++;
        s.min += q;
        s.log.push({m, min: q});
      }
    });
    Object.keys(inn).forEach(id => {
      const s = st[id];
      if (s && !(lu?.starters || []).some(x => String(x.playerId) === String(id))) {
        const q = Math.max(1, 90 - inn[id]);
        s.apps++;
        s.min += q;
        s.log.push({m, min: q});
      }
    });
  });

  (d.players || []).forEach(p => {
    const s = st[p.id], ps = p.stats;
    if (!s || !ps) return;
    if ((ps.goals || 0) > s.g) s.g = ps.goals;
    if ((ps.yellowCards || 0) > s.y) s.y = ps.yellowCards;
    if ((ps.redCards || 0) > s.r) s.r = ps.redCards;
    if ((ps.appearances || 0) > s.apps) {
      s.apps = ps.appearances;
      if (!s.min) s.min = s.apps * 60;
    }
  });

  let teamGoalsFor = 0;
  const pendingGoalMatches = [];
  fin.forEach(m => {
    const cbmG = isH(m) ? (m.score?.home || 0) : (m.score?.away || 0);
    teamGoalsFor += cbmG;
    const evG = (m.events || []).filter(e => String(e.team) === CBM && e.type === 'goal').length;
    if (cbmG > evG) {
      pendingGoalMatches.push({m, count: cbmG - evG});
    }
  });
  const meRow = (d.standings || []).find(r => String(r.clubId) === CBM);
  if (meRow && (meRow.goalsFor || 0) > teamGoalsFor) teamGoalsFor = meRow.goalsFor;

  const mx = Math.max(0, ...Object.values(st).map(s => s.g));
  const top = new Set(mx > 0 ? Object.values(st).filter(s => s.g === mx).map(s => s.id) : []);
  const byTime = fin.slice().sort((a, b) => new Date(a.kickoff || 0) - new Date(b.kickoff || 0));

  const cf = {};
  (d.standings || []).forEach(r => {
    cf[String(r.clubId)] = {W: r.wins || 0, D: r.draws || 0, L: r.losses || 0, k: []};
  });
  const seenMatchPairs = new Set();
  const allFinForForm = byTime.concat((d.roundResults || []).filter(m => m.status === 'finished' && m.score));
  allFinForForm.forEach(m => {
    const pairKey = `${m.round}:${m.home}:${m.away}`;
    if (seenMatchPairs.has(pairKey)) return;
    seenMatchPairs.add(pairKey);
    [m.home, m.away].forEach(id => {
      const c = cf[String(id)];
      if (!c) return;
      const h = String(m.home) === String(id);
      const a = h ? m.score.home : m.score.away, b = h ? m.score.away : m.score.home;
      c.k.push(a > b ? 'W' : a < b ? 'L' : 'D');
    });
  });
  const fm = {};
  Object.keys(cf).forEach(id => {
    const c = cf[id], rem = {W: c.W, D: c.D, L: c.L};
    c.k.forEach(r => rem[r]--);
    fm[id] = ['W', 'D', 'L'].flatMap(x => Array(Math.max(0, rem[x])).fill(x)).concat(c.k).slice(-5);
  });

  const form = byTime.slice(-5);
  const next = all.find(m => m.status !== 'finished');
  const last = byTime[byTime.length - 1] || null;
  let pts = 0, gf = 0, ga = 0, cs = 0;
  fin.forEach(m => {
    const conceded = isH(m) ? m.score.away : m.score.home;
    if (conceded === 0) cs++;
  });
  form.forEach(m => {
    const r = res(m);
    pts += r === 'W' ? 3 : r === 'D' ? 1 : 0;
    gf += isH(m) ? m.score.home : m.score.away;
    ga += isH(m) ? m.score.away : m.score.home;
  });

  const ages = (d.players || []).map(playerAge).filter(Boolean);
  const avgAge = ages.length ? (ages.reduce((a, b) => a + b, 0) / ages.length).toFixed(1) : '—';
  const totalMinutes = fin.length * 90;

  return {st, top, all, fin, form, fm, next, last, pts, gf, ga, cs, avgAge, totalMinutes, hasA, teamGoalsFor, pendingGoalMatches};
}

const gb = id => S.C.top.has(String(id)) ? `<span class="gb">${t('top')}</span>` : '';
const star = id => S.C.top.has(String(id)) ? ' ⭐' : '';
function pName(e) {
  const p = e.playerId ? ply(e.playerId) : null;
  return p ? nm(p) + star(p.id) : (e.playerName || '—');
}
function pRelName(e) {
  const p = e.relatedPlayerId ? ply(e.relatedPlayerId) : null;
  return p ? nm(p) : (e.relatedPlayerName || '');
}

function formHtml() {
  return `<div class="form">${S.C.form.map(m => {
    const r = res(m);
    return `<div class="f ${r}"><span>${r}</span></div>`;
  }).join('') || '<span class="lab">—</span>'}</div>`;
}

const scr = s => `<span>${esc(s.home)}</span><span>-</span><span>${esc(s.away)}</span>`;
const mid = m => m.status === 'postponed' ? `<div class="num">${esc(t('st_postponed'))}</div>` : (m.score ? `<div class="scr">${scr(m.score)}</div>` : `<div class="num">${esc(fT(m.kickoff))}</div>`);
const tag = m => (isH(m) ? `<span class="tag h">${esc(t('hm'))}</span>` : `<span class="tag a">${esc(t('aw'))}</span>`) + matchBadgesHtml(m);

function mItem(m) {
  const r = res(m), v = venue(m.venue), cls = r === 'W' ? 'w' : r === 'L' ? 'l' : r === 'D' ? 'd' : 'u';
  const goals = (m.events || []).filter(e => e.type === 'goal').map(e => `⚽ ${esc(pName(e))} (${e.minute}')`).join(' · ');
  return `<a class="mi ${cls}" data-m="${esc(m.id)}" role="button" tabindex="0" aria-label="${esc(nm(club(m.home)) + ' vs ' + nm(club(m.away)))}">
    <div class="mr">
      <div class="tm">${crest(m.home, 34)}<span>${esc(nm(club(m.home)))}</span></div>
      <div class="sc ${cls}">${m.score ? scr(m.score) : `<span class="num">${fT(m.kickoff)}</span>`}</div>
      <div class="tm">${crest(m.away, 34)}<span>${esc(nm(club(m.away)))}</span></div>
    </div>
    <div class="mf">
      <span>${t('round')} ${m.round} · ${fD(m.kickoff)}</span>
      ${tag(m)}
    </div>
    <div class="mf"><span>📍 ${esc(v.name)}${v.city ? ' · ' + esc(v.city) : ''}</span></div>
    ${goals ? `<div class="goals-inline">${goals}</div>` : ''}
  </a>`;
}

/* التقويم والمشاركة */
const pad = n => String(n).padStart(2, '0');
const utc = d => new Date(d).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');
function calData(m) {
  const s = new Date(m.kickoff), e = new Date(s.getTime() + (m.durationMinutes || 120) * 6e4), v = venue(m.venue);
  return {
    title: `${nm(club(m.home))} vs ${nm(club(m.away))}`,
    s, e,
    loc: [v.name, v.city].filter(Boolean).join(', '),
    desc: `${t('round')} ${m.round} · ${t('tl')}`
  };
}
function gcal(m) {
  const c = calData(m);
  return 'https://calendar.google.com/calendar/render?' + new URLSearchParams({
    action: 'TEMPLATE', text: c.title, dates: utc(c.s) + '/' + utc(c.e), details: c.desc, location: c.loc
  });
}

/* مؤشرات المقارنة */
function meters(n) {
  const R = S.data.standings || [];
  const g = id => R.find(r => String(r.clubId) === String(id));
  const pg = (r, k) => r && r.played ? r[k] / r.played : 0;
  const mA = Math.max(.01, ...R.map(r => pg(r, 'goalsFor')));
  const mD = Math.max(.01, ...R.map(r => pg(r, 'goalsAgainst')));
  const v = (id, k) => {
    const r = g(id);
    if (!r || !r.played) return 0.15;
    return Math.max(0.08, Math.min(1, k === 'p' ? Math.max(0, ptsOf(r)) / (3 * r.played) : k === 'a' ? pg(r, 'goalsFor') / mA : 1 - pg(r, 'goalsAgainst') / mD));
  };
  const row = (l, k) => `<div class="mtr"><div><i style="transform:scaleX(${v(n.home, k).toFixed(3)})"></i></div><span>${l}</span><div><i style="transform:scaleX(${v(n.away, k).toFixed(3)})"></i></div></div>`;
  return row('PWR', 'p') + row('ATK', 'a') + row('DEF', 'd');
}

/* جدول ترتيب هدافي شباب ميلة وهدافي البطولة (فوج الشرق) */
function renderScorersBox() {
  const sc = Object.values(S.C.st).filter(x => x.g > 0).sort((a, b) => (b.g - a.g) || (a.min - b.min));
  const pend = S.C.pendingGoalMatches || [];
  if (!sc.length && !pend.length) return '';
  return `<div class="h2">⚽ ${t('scorersRank')}</div>
  <div class="glass">${sc.map((s, idx) => {
    const p = ply(s.id);
    if (!p) return '';
    return `<a class="row" href="#/player/${esc(p.id)}">
      <b class="num" style="width:22px;color:var(--gold)">#${idx + 1}</b>
      ${avatar(nm(p), p.photoUrl, 38)}
      <div style="flex:1"><b>${esc(nm(p))}</b><small>#${p.shirt ?? '–'} · ${t('pos')[p.position] || ''} · ${s.apps} ${t('apps')}</small></div>
      <span class="tag h num">${s.g} ${t('gl')}</span>
    </a>`;
  }).join('')}${pend.map(({m, count}) => {
    const opp = isH(m) ? club(m.away) : club(m.home);
    return `<div class="row" data-m="${esc(m.id)}" role="button" tabindex="0" style="cursor:pointer">
      <b class="num" style="width:22px;color:var(--red)">+${count}</b>
      ${crest(CBM, 36)}
      <div style="flex:1"><b>${t('round')} ${esc(m.round)} · ${esc(nm(opp))} (${esc(m.score.home)}-${esc(m.score.away)})</b><small>${esc(t('pendingScorers'))}</small></div>
      <span class="tag a num">+${count} ${t('gl')}</span>
    </div>`;
  }).join('')}</div>`;
}

function renderLeagueScorersBox() {
  const list = (S.data.topScorers || []).slice(0, 15);
  if (!list.length) return '';
  return `<div class="h2">🏆 ${t('leagueScorersRank')}</div>
  <div class="glass">${list.map((item, idx) => {
    const isCbm = String(item.clubId) === CBM;
    const p = item.playerId ? ply(item.playerId) : null;
    const c = club(item.clubId);
    const dispName = p ? nm(p) : nm(item);
    const subLine = `${nm(c)}${item.shirt ? ' · #' + item.shirt : ''}${item.matches ? ' · ' + item.matches + ' ' + t('apps') : ''}`;
    const tagAttr = p ? `href="#/player/${esc(p.id)}"` : `data-club="${esc(item.clubId)}" role="button" tabindex="0" style="cursor:pointer"`;
    return `<a class="row${isCbm ? ' me-row' : ''}" ${tagAttr}>
      <b class="num" style="width:24px;color:${idx < 3 ? 'var(--gold)' : 'var(--mu)'}">#${idx + 1}</b>
      ${crest(item.clubId, 34)}
      <div style="flex:1"><b>${esc(dispName)}</b><small>${esc(subLine)}</small></div>
      <span class="tag ${isCbm ? 'h' : 'a'} num">${esc(item.goals)} ${t('gl')}</span>
    </a>`;
  }).join('')}</div>`;
}

function renderRoundResultsBox() {
  const rr = S.data.roundResults || [];
  if (!rr.length) return '';
  return `<div class="h2">🏟️ ${t('roundResultsTitle')}</div>
  <div class="glass">${rr.map(m => {
    const isCbmMatch = String(m.home) === CBM || String(m.away) === CBM;
    const scHtml = m.score ? `${m.score.home} - ${m.score.away}` : fT(m.kickoff);
    return `<div class="row" ${isCbmMatch && m.id ? `data-m="${esc(m.id)}"` : `data-club="${esc(m.home)}"`} role="button" tabindex="0" style="cursor:pointer">
      <div style="display:flex;align-items:center;gap:6px;flex:1;min-width:0">${crest(m.home, 26)}<b style="font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(nm(club(m.home)))}</b></div>
      <span class="tag ${m.score ? 'h' : 'a'} num" style="min-width:54px;text-align:center">${esc(scHtml)}</span>
      <div style="display:flex;align-items:center;justify-content:flex-end;gap:6px;flex:1;min-width:0"><b style="font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:end">${esc(nm(club(m.away)))}</b>${crest(m.away, 26)}</div>
    </div>`;
  }).join('')}</div>`;
}

/* الرئيسية */
function vHome() {
  const {next: n, last: l} = S.C;
  const rows = (S.data.standings || []).slice().sort((a, b) => (a.position || 99) - (b.position || 99));
  const i = rows.findIndex(r => String(r.clubId) === CBM);
  const me = rows[i];
  const rcp = recap();
  let h = rcp ? `<div style="margin-bottom:12px">${rcp}</div>` : '';
  h += '<div class="bn">';

  if (n) {
    const v = venue(n.venue), ph = mdPhase(n), z = ph ? 84 : 72;
    h += `<div class="pw"><div class="pass${ph ? ' md' : ''}"><div class="pi">
      <i class="cn a"></i><i class="cn b"></i><i class="cn c"></i><i class="cn d"></i>
      <div class="pbar"><b>${t('next')}</b><span>${t('round')} ${n.round}</span><em>${esc(t('tl'))}</em></div>
      ${ph ? `<div style="text-align:center"><span class="mdb">${t('md_' + ph)}</span></div><div class="slg">العام عام الطلعة 🔴⚪</div>` : ''}
      <div class="pvs">
        <div class="pt" data-club="${esc(n.home)}" role="button" tabindex="0">${crest(n.home, z)}<b>${esc(nm(club(n.home)))}</b><code>${esc((club(n.home) || {}).short || '')}</code></div>
        <div class="pm">${mid(n)}<small>${fD(n.kickoff)}</small></div>
        <div class="pt" data-club="${esc(n.away)}" role="button" tabindex="0">${crest(n.away, z)}<b>${esc(nm(club(n.away)))}</b><code>${esc((club(n.away) || {}).short || '')}</code></div>
      </div>
      ${meters(n)}
      ${okD(n.kickoff) && ph !== 'now' && ph !== 'wait' ? `<div class="cd num" aria-label="Countdown">
        <div><b id="cd-d">0</b><i>${t('day')}</i><u id="cd-bd"></u></div>
        <div><b id="cd-h">00</b><i>${t('hr')}</i><u id="cd-bh"></u></div>
        <div><b id="cd-m">00</b><i>${t('min')}</i><u id="cd-bm"></u></div>
        <div><b id="cd-s">00</b><i>${t('sec')}</i><u id="cd-bs"></u></div>
      </div>` : ''}
      <div class="meta">${tag(n)}<span>📍 ${esc(v.name)}${v.city ? ' · ' + esc(v.city) : ''}</span></div>
      <div class="btns">
        ${okD(n.kickoff) ? `<a class="btn p" target="_blank" rel="noopener" href="${esc(gcal(n))}">${t('gcal')} 📅</a>` : ''}
        <button class="btn" type="button" data-m="${esc(n.id)}">📊 ${t('matchDetails')}</button>
        <button class="btn" type="button" data-sharem="${esc(n.id)}" aria-label="${esc(t('share'))}" style="flex:none;padding:12px 14px">↗️</button>
      </div>
    </div></div></div>`;
  }

  const sc = Object.values(S.C.st).filter(x => x.g > 0).sort((a, b) => b.g - a.g || b.min - a.min);
  const tp = sc[0] && ply(sc[0].id);

  if (me) {
    h += `<a class="t rk" href="#/table">
      <span class="tl">${t('table')}</span>
      <b class="big num">#${me.position}</b>
      <span class="sub"><b class="num">${ptsOf(me)}</b> ${t('pts')} · <span class="num">${me.played}</span> ${t('pl')}</span>
    </a>`;
  }
  h += `<div class="t">
    <span class="tl">${t('form')}</span>
    ${formHtml()}
    <span class="sub"><span class="num">${S.C.gf}:${S.C.ga}</span> ${t('goals')} · <span class="num">${S.C.cs}</span> ${t('cleanSheets')}</span>
  </div>`;

  if (tp) {
    const others = sc.length > 1 && sc[1].g === sc[0].g ? ` (+${sc.filter(x => x.g === sc[0].g).length - 1})` : '';
    h += `<a class="t" href="#/player/${tp.id}">
      <span class="tl">${t('top')}</span>
      <b class="big num">${sc[0].g}</b>
      <span class="sub">${esc(nm(tp))}${others}</span>
      <i class="ghost">${tp.shirt ?? ''}</i>
    </a>`;
  }
  h += `<a class="t" href="#/squad">
    <span class="tl">${t('squad')}</span>
    <b class="big num">${(S.data.players || []).length}</b>
    <span class="sub">${t('avgAge')}: <b class="num">${S.C.avgAge}</b></span>
  </a>`;

  if (l && !rcp) h += `<div class="s2">${mItem(l)}</div>`;

  const fx = S.C.all.filter(m => m.status !== 'finished' && m.id !== (n && n.id)).slice(0, 5);
  if (fx.length) {
    h += `<div class="t s2 fx">
      <span class="tl">${t('upc')}</span>
      <div class="fxs">${fx.map(m => {
        const o = isH(m) ? m.away : m.home;
        return `<a class="fxi" data-m="${esc(m.id)}" role="button" tabindex="0">
          <small>${t('round')} ${m.round} · ${isH(m) ? '🏟️' : '✈️'}</small>
          ${crest(o, 34)}
          <b>${esc(nm(club(o)))}</b>
          <small>${fD(m.kickoff)}</small>
        </a>`;
      }).join('')}</div>
    </div>`;
  }

  if (me) {
    const a = Math.max(0, Math.min(i - 1, rows.length - 4));
    h += `<div class="t sf tb">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span class="tl">${t('table')}</span>
        <a href="#/table" class="sub" style="color:var(--red)">${t('view')} ←</a>
      </div>
      <div class="tbl">${rows.slice(a, a + 4).map(r => trow(r, true)).join('')}</div>
    </div>`;
  }
  return h + '</div>';
}

/* المباريات */
function vMatches() {
  const me = (S.data.standings || []).find(r => String(r.clubId) === CBM) || {played: S.C.fin.length, wins: 0, draws: 0, losses: 0, goalsFor: S.C.gf, goalsAgainst: S.C.ga};
  let list = S.tab === 'upc'
    ? S.C.all.filter(m => m.status !== 'finished')
    : S.tab === 'res'
      ? S.C.fin.slice().reverse()
      : S.C.all.slice();

  if (S.mLoc === 'home') list = list.filter(m => isH(m));
  if (S.mLoc === 'away') list = list.filter(m => !isH(m));
  if (S.mSearch.trim()) {
    const q = S.mSearch.trim().toLowerCase();
    list = list.filter(m => {
      const hName = nm(club(m.home)).toLowerCase(), aName = nm(club(m.away)).toLowerCase();
      return hName.includes(q) || aName.includes(q) || String(m.round) === q;
    });
  }

  return `<div class="kpis">
    <div class="kpi"><b class="num">${me.played}</b><small>${t('pl')}</small></div>
    <div class="kpi"><b class="num" style="color:var(--w)">${me.wins}</b><small>${t('winsLbl')}</small></div>
    <div class="kpi"><b class="num">${me.goalsFor}:${me.goalsAgainst}</b><small>${t('gfga')}</small></div>
    <div class="kpi"><b class="num" style="color:var(--gold)">${S.C.cs}</b><small>${t('cleanSheets')}</small></div>
  </div>
  <div class="seg">
    <button type="button" class="${S.tab === 'upc' ? 'on' : ''}" data-tab="upc">${t('upc')} (${S.C.all.length - S.C.fin.length})</button>
    <button type="button" class="${S.tab === 'res' ? 'on' : ''}" data-tab="res">${t('res')} (${S.C.fin.length})</button>
    <button type="button" class="${S.tab === 'all' ? 'on' : ''}" data-tab="all">${t('all')} (${S.C.all.length})</button>
  </div>
  <div class="sbar">
    <input class="sinp" id="m-search" type="search" value="${esc(S.mSearch)}" placeholder="${esc(t('searchM'))}" aria-label="${esc(t('searchM'))}">
  </div>
  <div class="chips">
    <button type="button" class="${S.mLoc === 'all' ? 'on' : ''}" data-mloc="all">${t('all')}</button>
    <button type="button" class="${S.mLoc === 'home' ? 'on' : ''}" data-mloc="home">${t('hm')}</button>
    <button type="button" class="${S.mLoc === 'away' ? 'on' : ''}" data-mloc="away">${t('aw')}</button>
  </div>
  <div id="m-list">${list.map(mItem).join('') || `<div class="empty">${t('noM')}</div>`}</div>`;
}

/* جدول الترتيب */
const mxp = () => Math.max(1, ...(S.data.standings || []).map(r => Math.max(0, ptsOf(r))));
function trow(r, mini = false) {
  const me = String(r.clubId) === CBM;
  const p = ptsOf(r);
  const hasDed = r.adjustedPoints != null && r.adjustedPoints !== r.points;
  const barRatio = Math.max(0, p) / mxp();
  if (mini) {
    return `<div class="tr mini ${me ? 'me' : ''}" data-club="${esc(r.clubId)}" role="button" tabindex="0" style="--v:${barRatio.toFixed(3)}">
      <span class="num">${r.position}</span>
      <div class="cl">${crest(r.clubId, 24)}<span>${esc(nm(club(r.clubId)))}</span></div>
      <span class="num">${r.played}</span>
      <span class="num">${r.goalDifference > 0 ? '+' : ''}${r.goalDifference}</span>
      <div class="mf5">${(S.C.fm[String(r.clubId)] || []).map(x => `<div class="f s ${x}"><span>${x}</span></div>`).join('')}</div>
      <b class="num">${p}${hasDed ? '*' : ''}</b>
    </div>`;
  }
  return `<div class="tr ${me ? 'me' : ''}" data-club="${esc(r.clubId)}" role="button" tabindex="0" style="--v:${barRatio.toFixed(3)}">
    <span class="num">${r.position}</span>
    <div class="cl">${crest(r.clubId, 24)}<span>${esc(nm(club(r.clubId)))}</span></div>
    <span class="num">${r.played}</span>
    <span class="num">${r.wins}</span>
    <span class="num">${r.draws}</span>
    <span class="num">${r.losses}</span>
    <span class="num">${r.goalsFor}:${r.goalsAgainst}</span>
    <span class="num">${r.goalDifference > 0 ? '+' : ''}${r.goalDifference}</span>
    <div class="mf5">${(S.C.fm[String(r.clubId)] || []).map(x => `<div class="f s ${x}"><span>${x}</span></div>`).join('')}</div>
    <b class="num">${p}${hasDed ? '*' : ''}</b>
  </div>`;
}

function vTable() {
  const rows = (S.data.standings || []).slice().sort((a, b) => (a.position || 99) - (b.position || 99));
  const hasDed = rows.some(r => r.adjustedPoints != null && r.adjustedPoints !== r.points);
  const bestAtk = rows.slice().sort((a, b) => b.goalsFor - a.goalsFor)[0];
  const bestDef = rows.slice().sort((a, b) => a.goalsAgainst - b.goalsAgainst)[0];
  const totalGoals = rows.reduce((s, r) => s + (r.goalsFor || 0), 0);

  return `<div class="seg">
    <button type="button" class="${S.tblView === 'tbl' ? 'on' : ''}" data-tblv="tbl">📊 ${t('tblTab')}</button>
    <button type="button" class="${S.tblView === 'stats' ? 'on' : ''}" data-tblv="stats">📈 ${t('statsTab')}</button>
  </div>
  ${S.tblView === 'stats' ? `<div class="bn" style="margin-bottom:14px">
    ${bestAtk ? `<div class="t" data-club="${esc(bestAtk.clubId)}" role="button" tabindex="0" style="cursor:pointer"><span class="tl">🔥 ${t('bestAtk')}</span><b class="big num">${bestAtk.goalsFor}</b><span class="sub">${esc(nm(club(bestAtk.clubId)))}</span></div>` : ''}
    ${bestDef ? `<div class="t" data-club="${esc(bestDef.clubId)}" role="button" tabindex="0" style="cursor:pointer"><span class="tl">🛡️ ${t('bestDef')}</span><b class="big num">${bestDef.goalsAgainst}</b><span class="sub">${esc(nm(club(bestDef.clubId)))}</span></div>` : ''}
    <div class="t s2"><span class="tl">⚽ ${t('totalGoals')}</span><b class="big num">${totalGoals}</b><span class="sub">${esc(t('tl'))} · ${esc(S.data.sourceMeta?.seasonName || '')}</span></div>
  </div>${renderLeagueScorersBox()}${renderScorersBox()}${renderRoundResultsBox()}<div style="height:14px"></div>` : ''}
  <div class="glass tbl">
    <div class="tr hd">
      <span>#</span><span style="text-align:start">${t('club')}</span><span>${t('pl')}</span>
      <span>${t('wins')}</span><span>${t('dr')}</span><span>${t('ls')}</span>
      <span>${t('gfga')}</span><span>${t('gd')}</span><span>${t('fm')}</span><span>${t('pts')}</span>
    </div>
    ${rows.map(r => trow(r, false)).join('') || `<div class="empty">—</div>`}
  </div>
  ${hasDed ? `<p style="margin:8px 6px 0;font-size:11px;color:var(--mu);font-weight:700">${t('dedNote')}</p>` : ''}`;
}

/* الفريق والهدافون */
function vSquad() {
  const _s = Object.values(S.C.st);
  const mA = Math.max(1, ..._s.map(x => x.apps));
  const mM = Math.max(1, ..._s.map(x => x.min));
  const mG = Math.max(1, ..._s.map(x => x.g));
  const totalG = Math.max(S.C.teamGoalsFor || 0, _s.reduce((a, b) => a + b.g, 0));

  let ps = (S.data.players || []).filter(p => S.pos === 'ALL' || p.position === S.pos);
  if (S.pSearch.trim()) {
    const q = S.pSearch.trim().toLowerCase();
    ps = ps.filter(p => nm(p).toLowerCase().includes(q) || (p.name?.ar || '').includes(q) || String(p.shirt || '') === q);
  }
  ps = ps.slice().sort((a, b) => {
    const sa = S.C.st[a.id] || {g:0, min:0, apps:0}, sb = S.C.st[b.id] || {g:0, min:0, apps:0};
    if (S.pSort === 'g') return (sb.g - sa.g) || (sb.min - sa.min) || ((a.shirt || 99) - (b.shirt || 99));
    if (S.pSort === 'm') return (sb.min - sa.min) || (sb.apps - sa.apps) || ((a.shirt || 99) - (b.shirt || 99));
    if (S.pSort === 'no') return ((a.shirt || 99) - (b.shirt || 99));
    return (sb.g - sa.g) || ((a.shirt || 99) - (b.shirt || 99));
  });

  return `<div class="kpis">
    <div class="kpi"><b class="num">${(S.data.players || []).length}</b><small>${t('squadSize')}</small></div>
    <div class="kpi"><b class="num">${S.C.avgAge}</b><small>${t('avgAge')}</small></div>
    <div class="kpi"><b class="num" style="color:var(--gold)">${totalG}</b><small>${t('goals')}</small></div>
    <div class="kpi"><b class="num">${S.C.fin.length}</b><small>${t('matches')}</small></div>
  </div>
  ${renderScorersBox()}
  <div style="height:12px"></div>
  <div class="sbar">
    <input class="sinp" id="p-search" type="search" value="${esc(S.pSearch)}" placeholder="${esc(t('searchP'))}" aria-label="${esc(t('searchP'))}">
    <select class="ssel" id="p-sort" aria-label="${esc(t('sortDef'))}">
      <option value="def" ${S.pSort === 'def' ? 'selected' : ''}>${t('sortDef')}</option>
      <option value="m" ${S.pSort === 'm' ? 'selected' : ''}>${t('sortM')}</option>
      <option value="g" ${S.pSort === 'g' ? 'selected' : ''}>${t('sortG')}</option>
      <option value="no" ${S.pSort === 'no' ? 'selected' : ''}>${t('sortNo')}</option>
    </select>
  </div>
  <div class="chips">${Object.keys(t('pos')).map(k => `<button type="button" class="${S.pos === k ? 'on' : ''}" data-pos="${k}">${t('pos')[k]}</button>`).join('')}</div>
  <div class="tg">${ps.map(p => {
    const s = S.C.st[p.id] || {apps:0, min:0, g:0}, top = S.C.top.has(String(p.id)), age = playerAge(p);
    return `<a class="tc${top ? ' top' : ''}" data-p="${p.position}" href="#/player/${p.id}">
      <i class="tn">${p.shirt ?? ''}</i>
      <div class="ph"><span>${esc(ini(nm(p)))}</span>${p.photoUrl ? `<img data-avatar="1" src="${esc(p.photoUrl)}" loading="lazy" alt="${esc(nm(p))}">` : ''}</div>
      ${top ? `<div class="tgb">${gb(p.id)}</div>` : ''}
      <div class="ti">
        <div class="tp-row">
          <span class="tp">${t('pos')[p.position] || ''}</span>
          ${age ? `<span class="tage">${age} ${t('age')}</span>` : ''}
        </div>
        <h4>${esc(nm(p))}</h4>
        <div class="bs">${[[t('apps'), s.apps, mA], [t('mins'), s.min, mM], [t('gl'), s.g, mG]].map(([l, v, m]) => `<div><span>${l}</span><u><i style="transform:scaleX(${(v / m).toFixed(3)})"></i></u><b class="num">${v}</b></div>`).join('')}</div>
      </div>
    </a>`;
  }).join('') || `<div class="empty" style="grid-column:1/-1">${t('noM')}</div>`}</div>`;
}

const H24 = 864e5, winMs = m => (m.durationMinutes || 120) * 6e4;
function mdPhase(m) {
  if (!m || !okD(m.kickoff)) return '';
  const d = new Date(m.kickoff).getTime() - Date.now();
  if (d > H24) return '';
  if (d > 0) return 'day';
  if (d > -winMs(m)) return 'now';
  if (d > -winMs(m) - 3 * 36e5) return 'wait';
  return '';
}

function recap() {
  const l = S.C.last;
  if (!l || !okD(l.kickoff)) return '';
  if (Date.now() - new Date(l.kickoff).getTime() > winMs(l) + 96 * 36e5) return '';
  const r = res(l), k = r === 'W' ? 'won' : r === 'L' ? 'lost' : 'drew', v = venue(l.venue), g = {};
  (l.events || []).filter(e => e.type === 'goal').forEach(e => {
    const n = pName(e), key = `${e.team}:${n}`;
    if (!g[key]) g[key] = {team: e.team, name: n, mins: []};
    g[key].mins.push(e.minute);
  });
  const sc = Object.values(g).map(x => `<div class="ev">${crest(x.team, 20)}<span class="mn num">${x.mins.join("', ")}'</span>⚽ ${esc(x.name)}</div>`).join('');
  return `<div class="hero" data-m="${esc(l.id)}" role="button" tabindex="0" style="cursor:pointer">
    <i class="wm">1936</i>
    <div class="lab">${t('recap')} · ${t('round')} ${l.round}</div>
    <div class="vs">
      <div class="tm">${crest(l.home, 60)}${esc(nm(club(l.home)))}</div>
      <div class="mid">${mid(l)}<small>${fD(l.kickoff)}</small></div>
      <div class="tm">${crest(l.away, 60)}${esc(nm(club(l.away)))}</div>
    </div>
    <div style="text-align:center;margin-top:8px"><span class="mdb ${r}">${t(k)}</span></div>
    <div class="meta">${tag(l)}<span>📍 ${esc(v.name)}${v.city ? ' · ' + esc(v.city) : ''}</span></div>
    ${sc ? `<div class="h2" style="font-size:12px;margin:12px 4px 4px">${t('scorers')}</div>${sc}` : ''}
  </div>`;
}

/* ملف اللاعب */
function vPlayer() {
  const p = ply(getHash().split('/')[1] || '');
  const back = `<div class="btns" style="margin:0 0 12px"><a class="btn" href="#/squad">${S.lang === 'ar' ? '→' : '←'} ${t('back')}</a></div>`;
  if (!p) return back + `<div class="empty">${t('noM')}</div>`;

  const s = S.C.st[p.id] || {apps:0, min:0, g:0, y:0, r:0, a:0, log:[]};
  const age = playerAge(p);
  const bd = okD(p.birthDate)
    ? new Intl.DateTimeFormat(loc(), {timeZone:'UTC', day:'numeric', month:'long', year:'numeric'}).format(new Date(p.birthDate)) + (age ? ` (${age} ${t('age')})` : '')
    : (age ? `~${age} ${t('age')}` : '');
  const partPct = S.C.totalMinutes > 0 ? Math.round((s.min / S.C.totalMinutes) * 100) + '%' : '0%';
  const info = [[t('nat'), p.nationality], [t('born'), bd]].filter(x => x[1]);
  const cell = (v, l) => `<div><b class="num">${v}</b><i>${l}</i></div>`;
  const lg = s.log.slice().sort((a, b) => new Date(b.m.kickoff || 0) - new Date(a.m.kickoff || 0));

  return back + `<div class="hero" style="text-align:center">
    <i class="wm">${p.shirt ?? '1936'}</i>
    <div style="display:flex;justify-content:center">${avatar(nm(p), p.photoUrl, 96)}</div>
    <h2 style="margin:10px 0 2px">${esc(nm(p))}</h2>
    <div class="lab">#${p.shirt ?? '–'} · ${t('pos')[p.position] || ''}</div>
    ${gb(p.id)}
    <div class="st">${cell(s.apps, t('apps'))}${cell(s.min, t('mins'))}${cell(s.g, t('gl'))}</div>
    <div class="st">${cell(partPct, t('partRate'))}${cell(s.y, t('yc'))}${cell(s.r, t('rc'))}</div>
  </div>
  ${info.length ? `<div class="glass" style="margin-top:12px">${info.map(x => `<div class="row"><div style="flex:1"><small>${x[0]}</small></div><b>${esc(x[1])}</b></div>`).join('')}</div>` : ''}
  <div class="h2">${t('plog')}</div>
  ${lg.length ? `<div class="glass">${lg.map(({m, min}) => {
    const o = isH(m) ? m.away : m.home, r = res(m);
    const ev = (m.events || []).filter(e => String(e.playerId) === String(p.id));
    const n = k => ev.filter(e => e.type === k).length;
    return `<div class="row" data-m="${esc(m.id)}" role="button" tabindex="0" style="cursor:pointer">
      ${crest(o, 32)}
      <div style="flex:1"><b>${esc(nm(club(o)))}</b><small>${fD(m.kickoff)} · ${t('round')} ${m.round}</small></div>
      <div style="text-align:end">
        <b class="num" style="color:var(--${r === 'W' ? 'w' : r === 'L' ? 'l' : 'd'})">${m.score.home}-${m.score.away}</b>
        <small>${min}'${n('goal') ? ' ⚽' + n('goal') : ''}${n('yellow') ? ' 🟨' : ''}${n('red') ? ' 🟥' : ''}</small>
      </div>
    </div>`;
  }).join('')}</div>` : `<div class="empty">${t('nop')}</div>`}`;
}

/* النادي والإعدادات */
function vClub() {
  const c = S.data.club;
  return cardBox() + `<div class="hero" style="text-align:center">
    <i class="wm">1936</i>
    <div style="display:flex;justify-content:center">${crest(CBM, 84)}</div>
    <h2 style="margin:12px 0 4px;font-weight:900">${esc(nm(c))}</h2>
    <div class="lab">${esc(t('tl'))} · ${esc(S.data.sourceMeta?.seasonName || '')}</div>
    <div class="meta" style="margin-top:10px">
      <span class="tag h">🔴⚪ ${t('founded')}</span>
      <span class="tag a">📍 ${esc(t('stadiumName'))}</span>
    </div>
  </div>
  <div class="h2">${t('staff')}</div>
  <div class="glass">${(S.data.staff || []).map(s => {
    const sName = nm(s);
    return `<div class="row">${avatar(sName, s.photoUrl, 44)}<div><b>${esc(sName)}</b><small>${esc(s.role?.[S.lang] || s.role?.en || s.role?.ar || '')}</small></div></div>`;
  }).join('')}</div>
  <div class="h2">${t('set')}</div>
  <div class="btns" style="flex-wrap:wrap">
    <button class="btn p" type="button" data-notif="1">${t('notifBtn')}</button>
    <button class="btn" type="button" data-sharesite="1">${t('siteShareBtn')}</button>
    <button class="btn" type="button" id="b-theme">🌗 ${t('theme')}</button>
    <button class="btn" type="button" data-sync="1">🔄 ${t('refresh')}</button>
    <button class="btn" type="button" data-priv="1">${t('privBtn')}</button>
    <button class="btn p" type="button" id="b-inst" style="display:${S.inst ? 'inline-flex' : 'none'}">📲 ${t('install')}</button>
  </div>
  <p class="empty" style="font-size:11.5px;padding:18px 10px">${t('lastUpd')}: <span class="num">${esc(fDT(S.data.lastUpdated))}</span></p>`;
}

/* الملعب التكتيكي وتفاصيل المباراة */
function renderPitch(starters) {
  if (!starters || starters.length < 7) return '';
  const resolved = starters.map(x => {
    const p = x.playerId ? ply(x.playerId) : null;
    return {
      id: p?.id || null,
      shirt: p?.shirt ?? x.shirt ?? '',
      name: p ? nm(p) : (x.playerName || '—'),
      pos: p?.position || 'MID'
    };
  });
  const gk = resolved.filter(p => p.pos === 'GK');
  const def = resolved.filter(p => p.pos === 'DEF');
  const mid = resolved.filter(p => p.pos === 'MID');
  const fw = resolved.filter(p => p.pos === 'FW');
  const lines = [fw, mid, def, gk].filter(row => row.length > 0);

  return `<div class="h2">${t('pitchTitle')}</div>
  <div class="pitch">${lines.map(row => `<div class="pitch-row">${row.map(p => {
    const shortName = p.name.split(/\s+/).slice(0, 2).join(' ');
    return `<a class="p-node" ${p.id ? `href="#/player/${esc(p.id)}" data-close` : ''}>
      <div class="p-dot ${p.pos === 'GK' ? 'gk' : ''}">${esc(p.shirt)}</div>
      <span>${esc(shortName)}</span>
    </a>`;
  }).join('')}</div>`).join('')}</div>`;
}

function vMatch(m) {
  const v = venue(m.venue);
  const ev = (m.events || []).slice().sort((a, b) => a.minute - b.minute).filter(e => ['goal', 'yellow', 'red', 'sub-in'].includes(e.type));
  const cbmKey = isH(m) ? 'home' : 'away';
  const oppKey = isH(m) ? 'away' : 'home';
  const cbmLu = m.lineups?.[cbmKey];
  const oppLu = m.lineups?.[oppKey];
  const hasBothLu = (cbmLu?.starters?.length || 0) > 0 && (oppLu?.starters?.length || 0) > 0;
  const activeLu = S.luSide === 'opp' && oppLu?.starters?.length ? oppLu : (cbmLu?.starters?.length ? cbmLu : oppLu);

  const renderLuList = arr => (arr || []).map(x => {
    const p = x.playerId ? ply(x.playerId) : null;
    if (p) return `<a class="ev" href="#/player/${esc(p.id)}" data-close><span class="mn num">#${p.shirt ?? ''}</span>${esc(nm(p))}${star(p.id)}</a>`;
    if (x.playerName) return `<div class="ev"><span class="mn num">${x.shirt ? '#' + x.shirt : '•'}</span>${esc(x.playerName)}</div>`;
    return '';
  }).join('');

  const ic = {goal: '⚽', yellow: '🟨', red: '🟥', 'sub-in': '🔁'};

  return `<div class="grab"></div>
  <div class="vs">
    <div class="tm" data-club="${esc(m.home)}" role="button" tabindex="0">${crest(m.home, 54)}${esc(nm(club(m.home)))}</div>
    <div class="mid">${mid(m)}<small>${fD(m.kickoff)}</small></div>
    <div class="tm" data-club="${esc(m.away)}" role="button" tabindex="0">${crest(m.away, 54)}${esc(nm(club(m.away)))}</div>
  </div>
  <div class="meta">${tag(m)}<span>${t('round')} ${m.round}</span><span>📍 ${esc(v.name)}${v.city ? ' · ' + esc(v.city) : ''}</span></div>
  ${okD(m.kickoff) && m.status !== 'finished' ? `<div class="btns"><a class="btn p" target="_blank" rel="noopener" href="${esc(gcal(m))}">${t('gcal')} 📅</a></div>` : ''}
  ${ev.length ? `<div class="h2">${t('ev')}</div><div class="glass" style="padding:4px 12px">${ev.map(e => {
    const outName = e.type === 'sub-in' ? pRelName(e) : '';
    return `<div class="ev">
      <span class="mn num">${e.minute}'</span>
      ${crest(e.team, 20)}
      <span>${ic[e.type]} ${esc(pName(e))}${outName ? ` <small style="color:var(--mu)">(${t('outSub')}: ${esc(outName)})</small>` : ''}</span>
    </div>`;
  }).join('')}</div>` : ''}
  ${cbmLu?.starters?.length ? renderPitch(cbmLu.starters) : ''}
  ${activeLu?.starters?.length ? `
    ${hasBothLu ? `<div class="seg" style="margin-top:14px">
      <button type="button" class="${S.luSide !== 'opp' ? 'on' : ''}" data-luside="cbm">${esc(nm(club(CBM)))}</button>
      <button type="button" class="${S.luSide === 'opp' ? 'on' : ''}" data-luside="opp">${esc(nm(club(isH(m) ? m.away : m.home)))}</button>
    </div>` : ''}
    ${activeLu.coach ? `<div class="glass" style="margin-top:10px"><div class="row"><small>${t('coach')}</small><b style="margin-inline-start:auto">${esc(activeLu.coach)}</b></div></div>` : ''}
    <div class="h2">${t('xi')}</div><div class="glass" style="padding:4px 12px">${renderLuList(activeLu.starters)}</div>
    ${activeLu.bench?.length ? `<div class="h2">${t('bench')}</div><div class="glass" style="padding:4px 12px">${renderLuList(activeLu.bench)}</div>` : ''}
  ` : ''}
  ${m.referees?.length ? `<p class="empty" style="font-size:12px;padding:14px 8px">⚖️ ${t('ref')}: ${esc(m.referees.join(' · '))}</p>` : ''}
  <div class="btns"><button class="btn" type="button" data-close aria-label="${esc(t('closeLbl'))}">✕</button></div>`;
}

function vClubSheet(cid) {
  const c = club(cid);
  const r = (S.data.standings || []).find(x => String(x.clubId) === String(cid));
  const h2h = S.C.all.filter(m => String(m.home) === String(cid) || String(m.away) === String(cid));
  const cell = (v, l) => `<div><b class="num">${v}</b><i>${l}</i></div>`;
  return `<div class="grab"></div>
  <div style="text-align:center;padding:8px 0">
    <div style="display:flex;justify-content:center">${crest(cid, 72)}</div>
    <h3 style="margin:10px 0 4px;font-size:18px;font-weight:900">${esc(nm(c))}</h3>
    <div class="lab">${esc(c?.short || '')} · ${t('tl')}</div>
    ${r ? `<div class="st">
      ${cell('#' + r.position, t('sp'))}
      ${cell(ptsOf(r), t('pts'))}
      ${cell(r.played, t('pl'))}
      ${cell(r.goalsFor + ':' + r.goalsAgainst, t('gfga'))}
    </div>
    <div style="display:flex;justify-content:center;margin-top:10px">
      <div class="mf5">${(S.C.fm[String(cid)] || []).map(x => `<div class="f ${x}"><span>${x}</span></div>`).join('')}</div>
    </div>` : ''}
  </div>
  ${String(cid) !== CBM && h2h.length ? `<div class="h2">${t('h2h')}</div>${h2h.map(mItem).join('')}` : ''}
  <div class="btns"><button class="btn" type="button" data-close aria-label="${esc(t('closeLbl'))}">✕</button></div>`;
}

/* التحقق من البطاقة (البند 2 و 3: يدعم path و hash ويعرض الاسم المقنّع) */
function verifyIdFromLocation() {
  const p = location.pathname.match(/\/verify\/(CBM-\d{6})\/?$/i);
  if (p) return p[1].toUpperCase();
  const h = getHash().match(/^verify\/(CBM-\d{6})$/i);
  return h ? h[1].toUpperCase() : '';
}

function maskNameClient(name) {
  return String(name || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map(w => Array.from(w)[0] + '***')
    .join(' ') || '***';
}

function vVerify() {
  const id = verifyIdFromLocation(), ar = S.lang === 'ar', fr = S.lang === 'fr';
  if (!id) {
    return `<div class="hero"><h2>${ar ? 'التحقق من بطاقة المناصر' : fr ? 'Vérification de Carte' : 'Supporter Verification'}</h2><div class="empty">${ar ? 'معرّف غير صالح' : fr ? 'Identifiant invalide' : 'Invalid supporter ID'}</div></div>`;
  }
  const box = `<div class="hero" style="text-align:center">
    <div class="lab">${ar ? 'التحقق الرسمي · CBM MILA' : fr ? 'VÉRIFICATION OFFICIELLE' : 'OFFICIAL VERIFICATION'}</div>
    <h2 style="margin:10px 0" class="num">${esc(id)}</h2>
    <div id="verify-result" class="glass" style="padding:18px;margin-top:14px">${ar ? 'جارٍ التحقق من السجل الرسمي…' : fr ? 'Vérification en cours…' : 'Verifying with official registry…'}</div>
    <p style="margin-top:10px;font-size:11.5px;color:var(--mu);font-weight:700">🔒 ${esc(t('verMaskedNote'))}</p>
    <div class="btns"><a class="btn" href="#/home">${ar ? 'العودة للرئيسية' : fr ? 'Retour à l\'accueil' : 'Back to Home'}</a></div>
  </div>`;

  setTimeout(async () => {
    const el = $('verify-result');
    if (!el) return;
    try {
      const r = await regCall({v: 2, a: 'verify', supporterId: id, dev: devId()});
      el.replaceChildren();
      if (r?.ok) {
        const masked = r.maskedName || maskNameClient(r.name);
        [
          [ar ? 'النادي' : 'Club', 'شباب بلدية ميلة · CBM Mila'],
          [ar ? 'المناصر (مقنّع)' : fr ? 'Supporter (masqué)' : 'Supporter (masked)', masked],
          [ar ? 'رقم البطاقة' : fr ? 'N° de Carte' : 'Supporter ID', r.supporterId || id],
          [ar ? 'الحالة' : fr ? 'Statut' : 'Status', String(r.status || 'active').toUpperCase()],
          [ar ? 'تاريخ الإصدار' : fr ? 'Date d\'émission' : 'Issued', new Date(r.createdAt).toLocaleDateString(loc())]
        ].forEach(([k, v]) => {
          const d = document.createElement('div'); d.className = 'row';
          const a = document.createElement('small'); a.textContent = k;
          const b = document.createElement('b'); b.style.marginInlineStart = 'auto'; b.textContent = String(v);
          d.append(a, b); el.append(d);
        });
      } else {
        const h = document.createElement('h3');
        h.textContent = r?.code === 'revoked'
          ? (ar ? 'بطاقة ملغاة (REVOKED)' : 'REVOKED')
          : r?.code === 'inactive'
            ? (ar ? 'بطاقة غير نشطة (INACTIVE)' : 'INACTIVE')
            : (ar ? 'البطاقة غير موجودة (NOT FOUND)' : 'NOT FOUND');
        el.append(h);
      }
    } catch (e) {
      el.textContent = ar ? 'تعذر الاتصال بخدمة التحقق. حاول مرة أخرى.' : fr ? 'Service de vérification indisponible.' : 'Verification service unavailable. Please try again.';
    }
  }, 0);
  return box;
}

/* الراوتر والهيكل العام */
const TABS = [['home','🏠'],['matches','⚽'],['table','📊'],['squad','👕'],['club','🛡️']];
function setRoute(h) {
  S.hash = h.startsWith('#') ? h : '#/' + h.replace(/^\/+/, '');
  try { location.hash = S.hash; } catch (e) {}
  closeM();
  render();
  scrollTo(0, 0);
}
const getHash = () => (location.hash && location.hash !== '#' ? location.hash : (S.hash || '#/home')).replace(/^#\/?/, '');
const rt = () => verifyIdFromLocation() ? 'verify' : (getHash() || 'home').split('/')[0];

function render() {
  try {
    S.C = calc();
    const r = rt();
    const V = {home: vHome, matches: vMatches, table: vTable, squad: vSquad, club: vClub, player: vPlayer, verify: vVerify}[r] || vHome;
    $('app').innerHTML = staleBannerHtml() + V();
    $('nav').innerHTML = TABS.map(([k, i]) => {
      const label = t(k);
      const isOn = k === (V === vHome ? 'home' : r === 'player' ? 'squad' : r);
      return `<a href="#/${k}" class="${isOn ? 'on' : ''}" aria-label="${esc(label)}" ${isOn ? 'aria-current="page"' : ''}><span>${i}</span>${esc(label)}${k === 'club' && !getCard() ? '<u class="pdot"></u>' : ''}</a>`;
    }).join('');
    tick();
    if (S.open) {
      const m = S.data.matches.find(x => String(x.id) === S.open);
      if (m) $('sbody').innerHTML = vMatch(m);
      else closeM();
    } else if (S.openClub) {
      $('sbody').innerHTML = vClubSheet(S.openClub);
    }
  } catch (e) {
    console.error(e);
    $('app').innerHTML = '<div class="empty">⚠️ ' + esc(e.message) + '</div>';
  }
}

function shell() {
  document.title = S.lang === 'ar' ? 'شباب ميلة · CBM Mila 1936' : 'CBM Mila 1936 · Official App';
  $('theme').setAttribute('aria-label', t('theme'));
  $('b-sync').setAttribute('aria-label', t('refresh'));
  const shBtn = $('b-share-site'); if (shBtn) shBtn.setAttribute('aria-label', t('siteShareBtn'));
  const nfBtn = $('b-notif'); if (nfBtn) { nfBtn.setAttribute('aria-label', t('notifBtn')); nfBtn.classList.toggle('notif-on', isPushEnabled()); }
  $('lang').setAttribute('aria-label', t('langLbl'));
  document.documentElement.lang = S.lang;
  document.documentElement.dir = S.lang === 'ar' ? 'rtl' : 'ltr';
  document.documentElement.dataset.theme = S.theme;
  const nextLangLabel = S.lang === 'ar' ? 'FR' : S.lang === 'fr' ? 'EN' : 'AR';
  $('lang').textContent = nextLangLabel;
  $('theme').textContent = S.theme === 'dark' ? '☀️' : '🌙';
  $('bt').textContent = nm(S.data.club);
  $('bs').textContent = t('tl');
  const metaTheme = document.querySelector('meta[name=theme-color]');
  if (metaTheme) metaTheme.content = S.theme === 'dark' ? '#040406' : '#eef0f6';
}

function toast(m) {
  const e = $('toast');
  e.textContent = m;
  e.classList.add('show');
  clearTimeout(toast.t);
  toast.t = setTimeout(() => e.classList.remove('show'), 2400);
}

/* العدّاد التنازلي للمباراة القادمة */
let cdT = 0;
function tick() {
  const n = S.C?.next;
  S.ph = mdPhase(n);
  cdT = n && okD(n.kickoff) ? new Date(n.kickoff).getTime() : 0;
  upd();
}
function upd() {
  if (S.C?.next && mdPhase(S.C.next) !== S.ph) { render(); return; }
  if (!Number.isFinite(cdT) || !cdT) return;
  const e = document.getElementById('cd-d');
  if (!e) return;
  let s = Math.max(0, Math.floor((cdT - Date.now()) / 1e3));
  e.textContent = Math.floor(s / 86400);
  s %= 86400;
  document.getElementById('cd-h').textContent = pad(Math.floor(s / 3600));
  document.getElementById('cd-m').textContent = pad(Math.floor(s % 3600 / 60));
  document.getElementById('cd-s').textContent = pad(s % 60);
  const B = (i, v) => { const x = document.getElementById(i); if (x) x.style.transform = 'scaleX(' + Math.max(0, Math.min(1, v)).toFixed(4) + ')'; };
  B('cd-bd', (+e.textContent) / 14);
  B('cd-bh', Math.floor(s / 3600) / 24);
  B('cd-bm', Math.floor(s % 3600 / 60) / 60);
  B('cd-bs', (s % 60) / 60);
}
setInterval(upd, 1000);

/* إدارة النوافذ المنبثقة وحبس التركيز (Focus Trap - البند 12) */
function focusFirstIn(container) {
  const focusable = container.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])');
  if (focusable.length) focusable[0].focus();
}

function handleFocusTrap(e) {
  if (e.key !== 'Tab') return;
  const activeModal = $('cm').classList.contains('open') ? $('cmb') : ($('sheet').classList.contains('open') ? $('sbody') : null);
  if (!activeModal) return;
  const focusable = Array.from(activeModal.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'));
  if (!focusable.length) return;
  const first = focusable[0], last = focusable[focusable.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
}

function openM(id) {
  const m = S.data.matches.find(x => String(x.id) === String(id));
  if (!m) return;
  lastTriggerEl = document.activeElement;
  S.openClub = null;
  S.open = String(id);
  S.luSide = 'cbm';
  $('sbody').innerHTML = vMatch(m);
  $('sheet').classList.add('open');
  setTimeout(() => focusFirstIn($('sbody')), 40);
}

function openClubSheet(cid) {
  if (!cid) return;
  lastTriggerEl = document.activeElement;
  S.open = null;
  S.openClub = String(cid);
  $('sbody').innerHTML = vClubSheet(cid);
  $('sheet').classList.add('open');
  setTimeout(() => focusFirstIn($('sbody')), 40);
}

function closeM() {
  const wasOpen = $('sheet').classList.contains('open');
  S.open = null;
  S.openClub = null;
  $('sheet').classList.remove('open');
  if (wasOpen && lastTriggerEl && typeof lastTriggerEl.focus === 'function') {
    try { lastTriggerEl.focus(); } catch (e) {}
  }
}

const cmOpen = h => {
  if (!$('cm').classList.contains('open')) lastTriggerEl = document.activeElement;
  $('cmb').innerHTML = h;
  $('cm').classList.add('open');
  setTimeout(() => focusFirstIn($('cmb')), 50);
};

const cmClose = () => {
  const wasOpen = $('cm').classList.contains('open');
  $('cm').classList.remove('open');
  if (wasOpen && lastTriggerEl && typeof lastTriggerEl.focus === 'function') {
    try { lastTriggerEl.focus(); } catch (e) {}
  }
};

function openPrivacy() {
  cmOpen(`<h3>${esc(t('privTitle'))}</h3>
    <p style="margin-top:10px;font-size:13px;line-height:1.65;color:var(--mu);font-weight:600">${esc(t('privBody'))}</p>
    <div class="btns"><button class="btn p" type="button" data-cclose aria-label="${esc(t('closeLbl'))}">✕</button></div>`);
}

function getOfficialSiteUrl() {
  if (/^https?:$/i.test(location.protocol) && !/^(localhost|127\.|0\.0\.0\.0)/.test(location.hostname)) {
    return location.origin + location.pathname.replace(/\/index\.html$/i, '').replace(/\/+$/, '') + '/';
  }
  return 'https://cbm-mila.github.io/CBM-MILA/';
}


const PUSH_KEY = 'CBM_PUSH_ON_V1';
function isPushEnabled() {
  try {
    return typeof Notification !== 'undefined' && Notification.permission === 'granted' && localStorage.getItem(PUSH_KEY) === '1';
  } catch (e) { return false; }
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
  return outputArray;
}

const NOTIFIED_TAGS_KEY = 'CBM_NOTIFIED_TAGS_V1';
function wasTagNotified(tag) {
  if (!tag) return false;
  try {
    const arr = JSON.parse(localStorage.getItem(NOTIFIED_TAGS_KEY) || '[]');
    return Array.isArray(arr) && arr.includes(tag);
  } catch (e) { return false; }
}
function markTagNotified(tag) {
  if (!tag) return;
  try {
    const arr = JSON.parse(localStorage.getItem(NOTIFIED_TAGS_KEY) || '[]');
    const list = Array.isArray(arr) ? arr.filter(x => x !== tag) : [];
    list.push(tag);
    localStorage.setItem(NOTIFIED_TAGS_KEY, JSON.stringify(list.slice(-100)));
  } catch (e) {}
}
async function hasActivePushSubscription() {
  try {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return false;
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager?.getSubscription();
    return Boolean(sub && sub.endpoint);
  } catch (e) { return false; }
}
async function showLocalNotification(title, body, url = './#/home', tag = '') {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return false;
  const finalTag = tag || ('cbm-local-' + Date.now());
  try {
    if ('serviceWorker' in navigator) {
      const reg = await navigator.serviceWorker.ready;
      if (reg && reg.showNotification) {
        await reg.showNotification(title, {
          body,
          icon: './icon-192.png',
          badge: './icon-192.png',
          dir: 'auto',
          vibrate: [200, 100, 200],
          tag: finalTag,
          data: { url }
        });
        return true;
      }
    }
    new Notification(title, { body, icon: './icon-192.png', tag: finalTag });
    return true;
  } catch (e) { return false; }
}

async function enablePushNotifications() {
  const er = $('nf-err'), btn = $('nf-enable');
  if (er) er.textContent = '';
  if (typeof Notification === 'undefined') {
    if (er) er.textContent = isIOS && !isSA ? t('notifIosHint') : t('notifBlocked');
    return;
  }
  if (btn) { btn.disabled = true; btn.textContent = t('cload'); }
  try {
    const perm = await Notification.requestPermission();
    if (perm !== 'granted') {
      if (er) er.textContent = t('notifBlocked');
      if (btn) { btn.disabled = false; btn.textContent = t('notifEnableBtn'); }
      return;
    }
    let subJson = null;
    const vapidPub = String(window.CBM_VAPID_PUBLIC_KEY || '').trim();
    if ('serviceWorker' in navigator && 'PushManager' in window && vapidPub) {
      try {
        const reg = await navigator.serviceWorker.ready;
        let sub = await reg.pushManager.getSubscription();
        if (!sub) {
          sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidPub)
          });
        }
        if (sub) subJson = sub.toJSON();
      } catch (pushErr) {
        console.warn('[CBM Push] pushManager subscribe fallback to local notifications', pushErr);
      }
    }
    if (subJson && REG_ON()) {
      try { await regCall({ v: 2, a: 'push_sub', sub: subJson, dev: devId(), lang: S.lang }); } catch (e) {}
    }
    try { localStorage.setItem(PUSH_KEY, '1'); } catch (e) {}
    shell();
    toast(t('notifEnabledToast'));
    await showLocalNotification(t('notifTestTitle'), t('notifTestBody'), './#/home');
    openNotifModal();
  } catch (e) {
    if (er) er.textContent = t('off');
    if (btn) { btn.disabled = false; btn.textContent = t('notifEnableBtn'); }
  }
}

async function disablePushNotifications() {
  try {
    if ('serviceWorker' in navigator) {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager?.getSubscription();
      if (sub) {
        const ep = sub.endpoint;
        await sub.unsubscribe().catch(() => {});
        if (REG_ON()) regCall({ v: 2, a: 'push_unsub', endpoint: ep, dev: devId() }).catch(() => {});
      }
    }
  } catch (e) {}
  try { localStorage.removeItem(PUSH_KEY); } catch (e) {}
  shell();
  toast(t('notifDisabledToast'));
  openNotifModal();
}

function openNotifModal() {
  const on = isPushEnabled();
  const blocked = typeof Notification !== 'undefined' && Notification.permission === 'denied';
  const needIosInstall = isIOS && !isSA && typeof Notification === 'undefined';

  cmOpen(`<h3>${esc(t('notifTitle'))}</h3>
    <small style="color:var(--mu);font-weight:700">${esc(t('notifSub'))}</small>
    <div style="margin-top:10px">
      <span class="tag ${on ? 'h' : 'a'}" style="${on ? 'color:#4ade80;border-color:#22c55e;background:rgba(34,197,94,.16)' : ''}">${esc(t(on ? 'notifOnBadge' : 'notifOffBadge'))}</span>
    </div>
    <div class="nf-list">
      <div>${esc(t('notifItem1'))}</div>
      <div>${esc(t('notifItem2'))}</div>
    </div>
    ${needIosInstall ? `<p class="cerr" style="color:var(--gold)">${esc(t('notifIosHint'))}</p>` : ''}
    ${blocked ? `<p class="cerr">${esc(t('notifBlocked'))}</p>` : ''}
    <p class="cerr" id="nf-err"></p>
    <div class="btns v" style="margin-top:12px">
      ${!on ? `<button class="btn p" type="button" id="nf-enable">${esc(t('notifEnableBtn'))}</button>` : ''}
      ${on ? `<button class="btn p" type="button" id="nf-test">${esc(t('notifTestBtn'))}</button>` : ''}
      ${on ? `<button class="btn" type="button" id="nf-disable">${esc(t('notifDisableBtn'))}</button>` : ''}
      <button class="btn" type="button" data-cclose aria-label="${esc(t('closeLbl'))}">✕</button>
    </div>`);
}

let siteQrUrl = '';
function openSiteShare() {
  const siteUrl = getOfficialSiteUrl();
  const siteName = t('siteNameVal');
  let qrData = '';
  try {
    if (window.CBMQR && typeof window.CBMQR.toCanvas === 'function') {
      const cv = window.CBMQR.toCanvas(siteUrl, 512, 2);
      qrData = cv.toDataURL('image/png');
      siteQrUrl = qrData;
    }
  } catch (e) {}

  cmOpen(`<h3>🔴⚪ ${esc(t('siteShareTitle'))}</h3>
    <small style="color:var(--mu);font-weight:700">${esc(t('siteShareSub'))}</small>
    ${qrData ? `<div class="sh-qr-wrap"><img src="${esc(qrData)}" alt="QR Code CBM Mila" width="210" height="210"></div>` : ''}
    <div class="sh-card">
      <small>${esc(t('siteNameLbl'))}</small>
      <b>${esc(siteName)}</b>
      <small style="margin-top:4px;margin-bottom:0;color:var(--gold)">${esc(t('siteSearchHint'))}</small>
    </div>
    <div class="sh-card" style="margin-top:8px">
      <small>${esc(t('siteUrlLbl'))}</small>
      <code>${esc(siteUrl)}</code>
    </div>
    <div class="btns v" style="margin-top:12px">
      <button class="btn p" type="button" id="sh-copy-url">${esc(t('copyUrlBtn'))}</button>
      <button class="btn" type="button" id="sh-copy-name">${esc(t('copyNameBtn'))}</button>
      <button class="btn" type="button" id="sh-native">${esc(t('shareNativeBtn'))}</button>
      ${qrData ? `<button class="btn" type="button" id="sh-dl-qr">${esc(t('dlQrBtn'))}</button>` : ''}
      <button class="btn" type="button" data-cclose aria-label="${esc(t('closeLbl'))}">✕</button>
    </div>`);
}

async function shareMatch(id) {
  const m = S.data.matches.find(x => String(x.id) === String(id));
  if (!m) return;
  const v = venue(m.venue);
  const text = `${nm(club(m.home))} ${m.score ? m.score.home + ' - ' + m.score.away : 'VS'} ${nm(club(m.away))} · ${t('round')} ${m.round} (${fD(m.kickoff)}) — 📍 ${v.name}`;
  try {
    if (navigator.share) return await navigator.share({title: 'CBM Mila 1936', text, url: location.origin + location.pathname});
    if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); toast(t('copied')); }
  } catch (e) {}
}

document.addEventListener('click', e => {
  const g = s => e.target.closest(s);
  let x;
  const aHref = g('a[href^="#/"]');
  if (aHref) {
    e.preventDefault();
    if (aHref.hasAttribute('data-close')) closeM();
    return setRoute(aHref.getAttribute('href'));
  }
  if (g('[data-close]') || e.target === $('sheet')) return closeM();
  if (g('[data-priv]')) return openPrivacy();
  if (g('#b-notif') || g('[data-notif]')) return openNotifModal();
  if (g('#nf-enable')) return enablePushNotifications();
  if (g('#nf-test')) { showLocalNotification(t('notifTestTitle'), t('notifTestBody'), './#/home'); return; }
  if (g('#nf-disable')) return disablePushNotifications();
  if (g('#b-share-site') || g('[data-sharesite]')) return openSiteShare();
  if (g('#sh-copy-url')) {
    const u = getOfficialSiteUrl();
    if (navigator.clipboard?.writeText) navigator.clipboard.writeText(u).then(() => toast(t('copied'))).catch(() => {});
    return;
  }
  if (g('#sh-copy-name')) {
    const n = t('siteNameVal');
    if (navigator.clipboard?.writeText) navigator.clipboard.writeText(n).then(() => toast(t('copied'))).catch(() => {});
    return;
  }
  if (g('#sh-native')) {
    const u = getOfficialSiteUrl(), n = t('siteNameVal');
    if (navigator.share) navigator.share({title: n, text: n, url: u}).catch(() => {});
    else if (navigator.clipboard?.writeText) navigator.clipboard.writeText(u).then(() => toast(t('copied'))).catch(() => {});
    return;
  }
  if (g('#sh-dl-qr')) {
    if (!siteQrUrl) return;
    const a = document.createElement('a');
    a.href = siteQrUrl;
    a.download = 'CBM-Mila-Website-QR.png';
    document.body.appendChild(a); a.click(); a.remove();
    return;
  }
  if (x = g('[data-sharem]')) { e.stopPropagation(); return shareMatch(x.dataset.sharem); }
  if (x = g('[data-luside]')) { S.luSide = x.dataset.luside; if (S.open) { const m = S.data.matches.find(z => String(z.id) === S.open); if (m) $('sbody').innerHTML = vMatch(m); } return; }
  if (x = g('[data-m]')) return openM(x.dataset.m);
  if (x = g('[data-club]')) return openClubSheet(x.dataset.club);
  if (x = g('[data-tab]')) { S.tab = x.dataset.tab; return render(); }
  if (x = g('[data-mloc]')) { S.mLoc = x.dataset.mloc; return render(); }
  if (x = g('[data-tblv]')) { S.tblView = x.dataset.tblv; return render(); }
  if (x = g('[data-pos]')) { S.pos = x.dataset.pos; return render(); }
  if (g('#b-sync') || g('[data-sync]')) return sync(true, true);
  if (g('#b-theme')) return toggleTheme();
  if (g('[data-cnew]')) return cardForm();
  if (g('[data-cview]')) return cardShow(getCard());
  if (g('[data-ccopy]')) { const c = getCard(); if (c && navigator.clipboard?.writeText) { navigator.clipboard.writeText(c.supporterId); toast(t('copied')); } return; }
  if (g('#c-go')) return cardIssue();
  if (g('#c-rg')) return cardRestoreGo();
  if (g('[data-crest]')) return cardRestore();
  if (g('#c-dl')) return cardDl();
  if (g('#c-share')) return cardShare();
  if (g('[data-cclose]') || e.target === $('cm')) return cmClose();
  if (g('#b-inst') || g('#ib-go')) return install();
  if (g('#ib-x')) { try { localStorage.setItem(IBK, Date.now()); } catch (err) {} return ibHide(); }
});

document.addEventListener('input', e => {
  if (e.target.id === 'm-search') {
    S.mSearch = e.target.value;
    const pos = e.target.selectionStart;
    render();
    const inp = $('m-search');
    if (inp) { inp.focus(); try { inp.setSelectionRange(pos, pos); } catch (err) {} }
  }
  if (e.target.id === 'p-search') {
    S.pSearch = e.target.value;
    const pos = e.target.selectionStart;
    render();
    const inp = $('p-search');
    if (inp) { inp.focus(); try { inp.setSelectionRange(pos, pos); } catch (err) {} }
  }
});

document.addEventListener('change', e => {
  if (e.target.id === 'p-sort') {
    S.pSort = e.target.value;
    render();
  }
});

function toggleTheme() { S.theme = S.theme === 'dark' ? 'light' : 'dark'; save(); shell(); }
$('theme').addEventListener('click', toggleTheme);
$('lang').addEventListener('click', () => {
  S.lang = S.lang === 'ar' ? 'fr' : S.lang === 'fr' ? 'en' : 'ar';
  save();
  shell();
  render();
});

addEventListener('keydown', e => {
  handleFocusTrap(e);
  if (e.key === 'Escape') { closeM(); cmClose(); }
  if (e.key === 'Enter' && (e.target.id === 'cin' || e.target.id === 'cin-rg' || e.target.id === 'cno')) {
    $('c-rg') ? cardRestoreGo() : cardIssue();
  }
});
document.addEventListener('visibilitychange', () => { if (!document.hidden) { upd(); sync(false); } });
window.addEventListener('hashchange', () => { S.hash = location.hash; closeM(); render(); scrollTo(0, 0); });

/* نظام بطاقة المناصر الرقمية (البنود 1، 2، 3) */
const regUrl = () => String(window.CBM_REG_URL || '');
const REG_ON = () => /^https:\/\/script\.google\.com\/.+\/exec$/.test(regUrl());
const cerr = e => t('cnet') + ' [' + ((e && e.code) || 'E1') + ']';
const devId = () => {
  try {
    let d = localStorage.getItem('CBM_DEV');
    if (!d) { d = Math.random().toString(36).slice(2, 10) + Date.now().toString(36); localStorage.setItem('CBM_DEV', d); }
    return d;
  } catch (e) { return 'anon'; }
};

async function regCall(o) {
  const U = regUrl();
  if (!REG_ON()) throw Object.assign(new Error('REGISTRY_NOT_CONFIGURED'), {code: 'REGISTRY_NOT_CONFIGURED'});
  const body = JSON.stringify(o), c = new AbortController(), to = setTimeout(() => c.abort(), 15000);
  try {
    const r = await fetch(U, {method: 'POST', mode: 'cors', credentials: 'omit', redirect: 'follow', headers: {'Content-Type': 'text/plain;charset=utf-8'}, body, signal: c.signal});
    const tx = await r.text();
    let j;
    try { j = JSON.parse(tx); } catch (e) { throw Object.assign(new Error('INVALID_RESPONSE'), {code: 'INVALID_RESPONSE', status: r.status}); }
    if (!r.ok || !j || typeof j !== 'object') throw Object.assign(new Error('SERVER_ERROR'), {code: 'SERVER_ERROR', status: r.status});
    return j;
  } catch (e) {
    if (e.name === 'AbortError') throw Object.assign(new Error('TIMEOUT'), {code: 'TIMEOUT'});
    throw e;
  } finally { clearTimeout(to); }
}

const CK = 'CBM_MILA_CARD_V2';
let memCard = null;
const normalizeCard = c => {
  if (!c || typeof c !== 'object') return null;
  const supporterId = String(c.supporterId || c.no || '').toUpperCase().replace(/\s+/g, '');
  const name = String(c.name || '').replace(/\s+/g, ' ').trim().slice(0, 80);
  if (!name || !/^CBM-\d{6}$/.test(supporterId)) return null;
  return {
    supporterId, name,
    serialNumber: String(c.serialNumber || supporterId).toUpperCase(),
    status: ['active', 'inactive', 'revoked'].includes(c.status) ? c.status : 'active',
    createdAt: c.createdAt || c.d || new Date().toISOString(),
    qrDataUrl: c.qrDataUrl || ''
  };
};
const getCard = () => {
  if (memCard) return memCard;
  try { return normalizeCard(JSON.parse(localStorage.getItem(CK) || 'null')); } catch (e) { return null; }
};

const IMG = {}, li = u => IMG[u] || (IMG[u] = new Promise((ok, no) => {
  const i = new Image();
  if (/^https:/i.test(u)) i.crossOrigin = 'anonymous';
  i.onload = () => ok(i);
  i.onerror = () => { delete IMG[u]; no(new Error('IMG_LOAD_FAILED')); };
  i.src = u;
}));

function put(c, txt, x, y, mw, px, mn) {
  const f = n => `800 ${n}px Cairo,Tahoma,Arial,sans-serif`;
  let n = px; c.font = f(n);
  while (n > mn && c.measureText(txt).width > mw) c.font = f(--n);
  let q = txt;
  if (c.measureText(q).width > mw) {
    while (q.length > 1 && c.measureText(q + '…').width > mw) q = q.slice(0, -1);
    q += '…';
  }
  c.direction = /[\u0600-\u06FF]/.test(txt) ? 'rtl' : 'ltr';
  c.textAlign = 'center';
  c.textBaseline = 'middle';
  c.fillStyle = '#fff';
  c.shadowColor = 'rgba(0,0,0,.75)';
  c.shadowBlur = 5;
  c.fillText(q, x, y + 2);
  c.shadowBlur = 0;
}

/* البند 2: رابط التحقق الصحيح مع دعم المسار الفرعي لـ GitHub Pages */
function verificationUrl(id) {
  const cleanPath = location.pathname.replace(/\/index\.html$/i, '').replace(/\/+$/, '') + '/';
  const defaultBase = location.origin + cleanPath;
  const base = window.CBM_CONFIG?.verificationDomain
    ? String(window.CBM_CONFIG.verificationDomain).replace(/\/+$/, '') + '/'
    : defaultBase;
  return base + '#/verify/' + encodeURIComponent(id);
}

/* البند 1: توليد رمز QR حقيقي محلياً بمستوى تصحيح H وبحجم 512 دون أي خدمة خارجية */
async function qrImageFor(k) {
  const targetUrl = verificationUrl(k.supporterId);
  if (k.qrDataUrl && k.qrTargetUrl === targetUrl) {
    try { return await li(k.qrDataUrl); } catch (e) {}
  }
  if (!window.CBMQR || typeof window.CBMQR.toCanvas !== 'function') {
    throw new Error('QR_LIBRARY_MISSING');
  }
  const qrCanvas = window.CBMQR.toCanvas(targetUrl, 512, 2);
  try {
    k.qrDataUrl = qrCanvas.toDataURL('image/png');
    k.qrTargetUrl = targetUrl;
    memCard = k;
    localStorage.setItem(CK, JSON.stringify(k));
  } catch (e) {}
  return qrCanvas;
}

async function drawCard(k) {
  const tp = await li('./card-template.jpg'), qr = await qrImageFor(k);
  try { await Promise.all([document.fonts.load('800 30px Cairo', 'ا'), document.fonts.load('800 30px Cairo', 'A')]); } catch (e) {}
  const cv = document.createElement('canvas'); cv.width = 1536; cv.height = 1024;
  const c = cv.getContext('2d'); c.imageSmoothingQuality = 'high';
  c.drawImage(tp, 0, 0, 1536, 1024);
  c.fillStyle = '#fff'; c.beginPath();
  c.roundRect ? c.roundRect(1064, 388, 250, 234, 12) : c.rect(1064, 388, 250, 234);
  c.fill();
  c.drawImage(qr, 1072, 392, 234, 226);
  const d = new Date(k.createdAt), dt = pad(d.getDate()) + '/' + pad(d.getMonth() + 1) + '/' + d.getFullYear();
  put(c, k.name, 758, 435, 460, 40, 16);
  put(c, k.supporterId, 758, 548, 440, 38, 18);
  put(c, dt, 566, 657, 118, 22, 12);
  put(c, 'Mila · ميلة', 778, 657, 122, 22, 12);
  put(c, k.status === 'active' ? 'ACTIVE' : k.status === 'revoked' ? 'REVOKED' : 'INACTIVE', 965, 657, 70, 18, 10);
  return cv;
}

function cardBox() {
  const c = getCard();
  if (!c) return `<button class="ccta" type="button" data-cnew><span style="font-size:30px">🎫</span><span>${t('ccta')}<small>${t('cphd2')}</small></span></button>`;
  return `<div class="glass" style="padding:16px;margin-bottom:14px">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
      <div style="font-weight:900;font-size:15px">🔴⚪ ${t('cmy')}</div>
      <span class="tag h num">${esc(c.supporterId)}</span>
    </div>
    <small style="display:block;margin-top:4px;color:var(--mu);font-weight:700">${esc(c.name)} · ${esc(c.status.toUpperCase())}</small>
    <div class="btns" style="flex-wrap:wrap">
      <button class="btn p" type="button" data-cview>🎫 ${t('cview')}</button>
      <button class="btn" type="button" data-ccopy>📋 ${t('ccopy')}</button>
      <a class="btn" href="#/verify/${esc(c.supporterId)}">✅ ${t('cver')}</a>
    </div>
  </div>`;
}

function cardForm() {
  cmOpen(`<h3>${t('ccta')}</h3>
    <small style="color:var(--mu);font-weight:700">${t('cphd')}</small>
    <input id="cin" dir="auto" maxlength="80" autocomplete="name" placeholder="${esc(t('cname'))}" aria-label="${esc(t('cname'))}">
    <p class="cerr" id="cerr"></p>
    <small style="display:block;margin-top:8px;color:var(--mu)">${t('cpriv')}</small>
    <button type="button" class="priv-link" data-priv="1">${t('privBtn')}</button>
    <div class="btns"><button class="btn p" type="button" id="c-go">${t('cgo')}</button><button class="btn" type="button" data-cclose aria-label="${esc(t('closeLbl'))}">✕</button></div>
    ${REG_ON() ? `<div class="btns" style="margin-top:8px"><button class="btn" type="button" data-crest style="font-size:12px">${t('crest')}</button></div>` : ''}`);
}

function cardRestore() {
  cmOpen(`<h3>${t('crest')}</h3>
    <small style="color:var(--mu);font-weight:700">${t('crsh')}</small>
    <input id="cin-rg" dir="auto" maxlength="80" placeholder="${esc(t('cname'))}" aria-label="${esc(t('cname'))}">
    <input id="cno" dir="ltr" inputmode="text" maxlength="10" placeholder="CBM-104829" aria-label="CBM-XXXXXX">
    <p class="cerr" id="cerr-rg"></p>
    <div class="btns"><button class="btn p" type="button" id="c-rg">${t('crsg')}</button><button class="btn" type="button" data-cclose aria-label="${esc(t('closeLbl'))}">✕</button></div>`);
}

function cardSave(k) {
  const c = normalizeCard(k);
  if (!c) throw new Error('INVALID_CARD');
  memCard = c;
  try { localStorage.setItem(CK, JSON.stringify(c)); } catch (e) {}
  render();
  cardShow(c);
}

async function cardIssue() {
  const i = $('cin'), v = i?.value.replace(/\s+/g, ' ').trim() || '', er = $('cerr'), go = $('c-go');
  if (!i || !er || !go) return;
  er.textContent = ''; i.classList.remove('er');
  if (v.length < 2 || v.length > 80) { i.classList.add('er'); er.textContent = t('cnameerr'); i.focus(); return; }
  if (!REG_ON()) { er.textContent = t('cnet') + ' [REGISTRY_NOT_CONFIGURED]'; return; }
  go.disabled = true; go.setAttribute('aria-busy', 'true'); go.textContent = t('cload');
  const requestId = crypto.randomUUID ? crypto.randomUUID() : devId() + '-' + Date.now();
  try {
    const r = await regCall({v:2, a:'register', name:v, requestId, dev:devId(), lang:S.lang});
    if (r && r.ok) return cardSave({supporterId:r.supporterId, serialNumber:r.serialNumber, name:r.name || v, status:r.status || 'active', createdAt:r.createdAt});
    er.textContent = r && r.code === 'exists' ? t('cdup') : cerr(r || {code:'INVALID_RESPONSE'});
  } catch (e) { er.textContent = cerr(e); }
  go.disabled = false; go.removeAttribute('aria-busy'); go.textContent = t('cgo');
}

async function cardRestoreGo() {
  const v = ($('cin-rg') || $('cin'))?.value.replace(/\s+/g, ' ').trim() || '', id = $('cno')?.value.trim().toUpperCase() || '', er = $('cerr-rg') || $('cerr'), go = $('c-rg');
  if (!er || !go) return;
  er.textContent = '';
  if (!/^CBM-\d{6}$/.test(id) || v.length < 2) { er.textContent = t('crsf'); return; }
  go.disabled = true; go.setAttribute('aria-busy', 'true'); go.textContent = t('cload');
  try {
    const r = await regCall({v:2, a:'restore', name:v, supporterId:id, dev:devId()});
    if (r && r.ok) return cardSave({supporterId:r.supporterId, serialNumber:r.serialNumber, name:r.name, status:r.status, createdAt:r.createdAt});
    er.textContent = r?.code === 'rate_limit' ? t('crate') : t(r?.code === 'revoked' ? 'crevoked' : 'crsf');
  } catch (e) { er.textContent = cerr(e); }
  go.disabled = false; go.removeAttribute('aria-busy'); go.textContent = t('crsg');
}

let cUrl = '';
async function cardShow(k) {
  if (!k) return;
  cmOpen('<div class="empty" role="status">…</div>');
  try {
    const cv = await drawCard(k), b = await new Promise(r => cv.toBlob(r, 'image/png'));
    if (!b) throw new Error('PNG_EXPORT_FAILED');
    if (cUrl) URL.revokeObjectURL(cUrl);
    cUrl = URL.createObjectURL(b);
    const box = $('cmb'); box.replaceChildren();
    const h = document.createElement('h3'); h.textContent = t('cmy') + ' · ' + k.supporterId;
    const img = document.createElement('img'); img.src = cUrl; img.alt = t('cmy'); img.decoding = 'async';
    const btns = document.createElement('div'); btns.className = 'btns v';
    const dl = document.createElement('button'); dl.type = 'button'; dl.className = 'btn p'; dl.id = 'c-dl'; dl.textContent = '⬇️ ' + t('cdl');
    const sh = document.createElement('button'); sh.type = 'button'; sh.className = 'btn'; sh.id = 'c-share'; sh.textContent = '↗️ ' + t('cshare');
    const close = document.createElement('button'); close.type = 'button'; close.className = 'btn'; close.dataset.cclose = ''; close.setAttribute('aria-label', t('closeLbl')); close.textContent = '✕';
    btns.append(dl, sh, close);
    const p = document.createElement('p');
    p.style.cssText = 'margin:10px 0 0;color:var(--mu);font-size:11.5px;font-weight:600;text-align:center';
    p.textContent = t('csave');
    box.append(h, img, btns, p);
    $('cm').classList.add('open');
    setTimeout(() => focusFirstIn(box), 40);
  } catch (e) {
    console.error('[CBM card]', e);
    cmOpen('<div class="empty">' + esc(t('cqrerr')) + '</div><div class="btns"><button class="btn" type="button" data-cclose aria-label="' + esc(t('closeLbl')) + '">✕</button></div>');
  }
}

async function cardShare() {
  if (!cUrl) return;
  try {
    const k = getCard();
    const res = {title: 'CBM Mila Supporter Card', text: k ? `${k.name} · ${k.supporterId}` : 'CBM Mila', url: k ? verificationUrl(k.supporterId) : location.origin};
    if (navigator.share) {
      const blob = await fetch(cUrl).then(r => r.blob());
      const file = new File([blob], 'CBM-Mila-Supporter.png', {type: 'image/png'});
      if (!navigator.canShare || navigator.canShare({files: [file]})) return navigator.share({...res, files: [file]});
      return navigator.share(res);
    }
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(res.url);
    toast(t('csharefallback'));
  } catch (e) { toast(t('csharefallback')); }
}

function cardDl() {
  const k = getCard();
  if (!cUrl || !k) return;
  const a = document.createElement('a');
  a.href = cUrl;
  a.download = 'CBM-Mila-Supporter-' + k.supporterId + '.png';
  document.body.appendChild(a); a.click(); a.remove();
}

/* التخزين المحلي والمزامنة الحية */
function save() {
  try { localStorage.setItem(KEY, JSON.stringify({lang: S.lang, theme: S.theme, data: S.data})); } catch (e) {}
}
const valid = d => d && typeof d === 'object' && d.schemaVersion === 3 && String(d.club?.id) === CBM && Array.isArray(d.matches) && Array.isArray(d.players) && Array.isArray(d.standings);

function load() {
  try {
    const p = JSON.parse(localStorage.getItem(KEY) || localStorage.getItem('CBM_MILA_APP_V9') || '{}');
    if (p.lang === 'en' || p.lang === 'ar' || p.lang === 'fr') S.lang = p.lang;
    if (p.theme === 'dark' || p.theme === 'light') S.theme = p.theme;
    if (valid(p.data) && String(p.data.lastUpdated) > String(D0.lastUpdated)) S.data = p.data;
  } catch (e) {}
}

let syncBusy = 0, syncAt = 0;
async function fetchWithTimeout(url, opts = {}, timeoutMs = 10000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    return await fetch(url, {...opts, signal: ctrl.signal});
  } finally {
    clearTimeout(timer);
  }
}

async function sync(force, showToast = false) {
  if (syncBusy) return;
  if (!force && (!NET || Date.now() - syncAt < 15e3)) return;
  syncBusy = 1; syncAt = Date.now();
  const btn = $('b-sync');
  if (btn && showToast) btn.classList.add('spinning');
  try {
    const reqHeaders = {};
    if (!force && S.etag) reqHeaders['If-None-Match'] = S.etag;
    if (!force && S.lastMod) reqHeaders['If-Modified-Since'] = S.lastMod;
    const r = await fetchWithTimeout('./data/data.json', {cache: 'no-cache', headers: reqHeaders}, 10000);
    if (r.status === 304) {
      S.syncFailed = false;
      S.lastSyncOkAt = Date.now();
      if (showToast) toast(t('upToDate'));
      return;
    }
    if (!r.ok) throw new Error('HTTP_' + r.status);
    if (r.headers.get('ETag')) S.etag = r.headers.get('ETag');
    if (r.headers.get('Last-Modified')) S.lastMod = r.headers.get('Last-Modified');
    const d = await r.json();
    S.syncFailed = false;
    S.lastSyncOkAt = Date.now();
    if (!valid(d)) throw 0;
    if (String(d.lastUpdated) !== String(S.data.lastUpdated)) {
      if (isPushEnabled() && String(S.data.lastUpdated) !== '1970-01-01T00:00:00Z') {
        const webPushActive = await hasActivePushSubscription();
        if (!webPushActive) {
          const oldMap = Object.fromEntries((S.data.matches || []).map(m => [String(m.id), m]));
          (d.matches || []).forEach(m => {
            const prev = oldMap[String(m.id)];
            if (!prev) return;
            if (prev.status !== 'finished' && m.status === 'finished' && m.score) {
              const resTag = `cbm-res-${m.id}`;
              if (!wasTagNotified(resTag)) {
                markTagNotified(resTag);
                showLocalNotification(
                  `${t('round')} ${m.round} · ${nm(club(m.home))} ${m.score.home}-${m.score.away} ${nm(club(m.away))}`,
                  t('notifTestTitle'),
                  './#/matches',
                  resTag
                );
              }
            } else if (prev.kickoff !== m.kickoff && m.kickoff) {
              const koTag = `cbm-ko-${m.id}`;
              if (!wasTagNotified(koTag)) {
                markTagNotified(koTag);
                showLocalNotification(
                  `📅 ${t('next')} · ${t('round')} ${m.round}`,
                  `${nm(club(m.home))} vs ${nm(club(m.away))} — ${fDT(m.kickoff)}`,
                  './#/home',
                  koTag
                );
              }
            }
          });
        }
      }
      S.data = d; save();
      const h = document.documentElement; h.classList.add('nq');
      requestAnimationFrame(() => { render(); shell(); requestAnimationFrame(() => setTimeout(() => h.classList.remove('nq'), 60)); });
      if (showToast) toast(t('ok'));
    } else if (showToast) {
      toast(t('upToDate'));
    }
  } catch (e) {
    S.syncFailed = true;
    render();
    if (showToast) toast(t('off'));
  } finally {
    syncBusy = 0;
    if (btn) btn.classList.remove('spinning');
  }
}

/* تثبيت تطبيق الويب التقدمي (PWA) */
let dip = null;
const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
const isSA = (matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true;
const IBK = 'CBM_IB_V1';
const ibOff = () => { try { return Date.now() - (+localStorage.getItem(IBK) || 0) < 6048e5; } catch (e) { return false; } };
function ibShow() {
  const b = $('ib');
  if (!b || isSA || ibOff()) return;
  b.querySelector('span').textContent = t(dip ? 'ibmsg' : 'ibios');
  const g = $('ib-go'); g.textContent = t('ibgo'); g.style.display = dip ? '' : 'none';
  b.classList.add('on');
}
const ibHide = () => { const b = $('ib'); b && b.classList.remove('on'); };
addEventListener('beforeinstallprompt', e => {
  e.preventDefault(); dip = e; S.inst = 1;
  const b = $('b-inst'); if (b) b.style.display = 'inline-flex';
  ibShow();
});
addEventListener('appinstalled', () => {
  dip = null; S.inst = 0; ibHide();
  const b = $('b-inst'); if (b) b.style.display = 'none';
});
async function install() {
  if (!dip) { if (isIOS) toast(t('ibios')); return; }
  ibHide();
  const p = dip; dip = null;
  try { p.prompt(); await p.userChoice; } catch (e) {}
  S.inst = 0;
  const b = $('b-inst'); if (b) b.style.display = 'none';
}
async function pwa() {
  if (!NET || !('serviceWorker' in navigator)) return;
  try {
    navigator.serviceWorker.addEventListener('message', e => {
      if (e.data && e.data.type === 'CBM_SW_UPDATED') {
        toast(t('swUpdateToast'));
      }
    });
    const hadController = Boolean(navigator.serviceWorker.controller);
    let refreshingToastShown = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (hadController && !refreshingToastShown) {
        refreshingToastShown = true;
        toast(t('swUpdateToast'));
      }
    });
    await navigator.serviceWorker.register('./sw.js');
  } catch (e) {}
}

const NET = /^https?:$/.test(location.protocol) && (!/^(localhost|127\.|0\.0\.0\.0|\[::1\]|.*\.local$)/.test(location.hostname) || /[?&]live=1/.test(location.search));
S.data = D0;
load();
try {
  const old = JSON.parse(localStorage.getItem('CBM_MILA_CARD_V1') || 'null');
  if (old && !getCard() && /^CBM-\d{6}$/.test(String(old.no || ''))) {
    localStorage.setItem(CK, JSON.stringify(normalizeCard({supporterId: old.no, name: old.name, status: 'active', createdAt: old.d})));
  }
} catch (e) {}
shell();
render();
pwa();
sync(false);
if (isIOS) setTimeout(ibShow, 3e3);
function isMatchWindowActive() {
  const now = Date.now();
  return (S.data?.matches || []).some(m => {
    if (m.status === 'live') return true;
    if (!okD(m.kickoff)) return false;
    const diff = Math.abs(new Date(m.kickoff).getTime() - now);
    return diff <= 3 * 3600 * 1000;
  });
}
setInterval(() => {
  if (document.hidden) return;
  const interval = isMatchWindowActive() ? 60e3 : 300e3;
  if (Date.now() - syncAt >= interval - 1000) sync(false);
}, 30e3);
addEventListener('online', () => sync(false));
addEventListener('focus', () => sync(false));

/* تأثيرات الميلان التفاعلية وإخفاء شريط التنقل عند التمرير */
(() => {
  if (matchMedia('(prefers-reduced-motion:reduce)').matches) return;
  let f = 0, E;
  const sel = '.pass,.t,.tc,.mi,.hero';
  const rst = () => document.querySelectorAll('[style*="--rx"]').forEach(n => { n.style.removeProperty('--rx'); n.style.removeProperty('--ry'); });
  addEventListener('pointermove', e => {
    const c = e.target.closest && e.target.closest(sel);
    if (!c) { if (E) { E = null; rst(); } return; }
    E = {e, c};
    if (f) return;
    f = requestAnimationFrame(() => {
      f = 0; if (!E) return;
      const {e, c} = E, r = c.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      c.style.setProperty('--rx', ((.5 - y) * 4.5).toFixed(2) + 'deg');
      c.style.setProperty('--ry', ((x - .5) * 6).toFixed(2) + 'deg');
    });
  }, {passive: true});
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(k => addEventListener(k, () => { E = null; rst(); }, {passive: true}));
})();

(() => {
  let y = scrollY;
  addEventListener('scroll', () => {
    const d = scrollY - y;
    if (Math.abs(d) < 10) return;
    $('nav').classList.toggle('hd', d > 0 && scrollY > 140);
    y = scrollY;
  }, {passive: true});
})();
