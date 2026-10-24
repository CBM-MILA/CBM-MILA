// إصدار البناء الموحد للتطبيق و Service Worker. غيّر هذا الرقم يدوياً مع كل إصدار جديد لتنظيف الكاش القديم.
// (الملفات الأساسية تُحمَّل network-first، لذلك لا يحجب نسيان تغييره وصول التحديثات للمستخدمين المتصلين.)
self.CBM_BUILD_VERSION = '2026.10.23.v4';
// ضع رابط Google Apps Script (الذي ينتهي بـ /exec) بين علامتي الاقتباس، ثم احفظ.
self.CBM_REG_URL = 'https://script.google.com/macros/s/AKfycbznRLxP55SP_MrRMrod1IkOO2zrIars5IK_1cbnezFtgho7xdrBG0VoQJAB5bKYFfWG/exec';
// المفتاح العام لإشعارات الهاتف الفورية (Web Push VAPID Public Key)
self.CBM_VAPID_PUBLIC_KEY = 'BLaOIDO2GOGdZavfB3Xclhbq7fe2vOOwaBRsUc-Qa-_C4KaxJcGr8BOI4xODnUR_xYhbaQNGG-Z3Eo7RworiGZs';
