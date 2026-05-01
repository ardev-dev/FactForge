# Social Media Setup Guide

كل المطلوب منك: إنشاء الحسابات + جلب tokens. ثم run الأوامر.

## 🔧 الإعداد لمرة واحدة

```bash
cp config/social_credentials.json.template config/social_credentials.json
# أكمل ملء tokens حسب الإرشادات أدناه
```

`config/social_credentials.json` في `.gitignore` — لا يُرفع لـ GitHub.

---

## ① Bluesky (الأسهل — ابدأ به)

**الحساب:** https://bsky.app

**Token:**
1. Settings → App Passwords → Add App Password
2. اسم: `factforge-poster`
3. انسخ الـ password (شكل: `xxxx-xxxx-xxxx-xxxx`)

**املأ:**
```json
"bluesky": {
  "handle": "thefactdrop.bsky.social",
  "app_password": "xxxx-xxxx-xxxx-xxxx"
}
```

---

## ② Twitter/X

**الحساب:** https://twitter.com/signup

**Tokens:**
1. https://developer.twitter.com → Sign up (مجاني)
2. Project + App → "Read and Write" permissions
3. Keys and tokens tab:
   - Consumer Keys (API Key + Secret)
   - Access Token + Secret (Generate)
   - Bearer Token

**املأ:**
```json
"twitter": {
  "consumer_key": "...",
  "consumer_secret": "...",
  "access_token": "...",
  "access_token_secret": "...",
  "bearer_token": "..."
}
```

⚠️ Free tier: **17 post/24 ساعة**. كافي لقناتنا.

---

## ③ Mastodon (federated)

**الحساب:** https://joinmastodon.org → اختر instance (mastodon.social الأشهر)

**Token:**
1. Settings → Development → New Application
2. Name: `factforge-poster`
3. Scopes: `write:statuses`
4. Submit → افتح التطبيق → انسخ "Your access token"

**املأ:**
```json
"mastodon": {
  "instance_url": "https://mastodon.social",
  "access_token": "..."
}
```

---

## ④ Reddit

**الحساب:** https://reddit.com → Create account

**⚠️ مهم:** Reddit يحتاج karma قبل النشر في معظم subreddits. اعمل comments عضوية لمدة 7-14 يوم قبل النشر التجاري. وإلا → instant ban.

**Tokens:**
1. https://reddit.com/prefs/apps → Create App
2. Type: **script**
3. Redirect URI: `http://localhost`
4. انسخ: client_id (تحت اسم التطبيق) + secret

**املأ:**
```json
"reddit": {
  "client_id": "...",
  "client_secret": "...",
  "username": "TheFactDrop",
  "password": "كلمة سرّك",
  "user_agent": "TheFactDrop/1.0 by u/TheFactDrop",
  "subreddits": ["pharma", "Bigpharmasucks", "antiwork"]
}
```

⚠️ **لا تنشر في أكثر من subreddit واحد لكل فيديو** — السكريبت يحترم هذا تلقائياً.

---

## 🚀 الاستخدام

### نشر فيديو على كل المنصات
```bash
python3 scripts/social_post.py S02905
```

### نشر على منصات محددة
```bash
python3 scripts/social_post.py S02905 --platforms bluesky,twitter
```

### معاينة بدون نشر
```bash
python3 scripts/social_post.py S02905 --dry-run
```

### نشر آخر فيديو منشور
```bash
python3 scripts/social_post.py lUTy778x0pg
```

---

## ✅ ميزات السكريبت

- **idempotent** — لن ينشر نفس الفيديو مرتين على نفس المنصة
- **state tracking** — `state/social_posts.json` يحفظ كل post URL
- **per-platform text adaptation** — كل منصة بأسلوبها (Twitter قصير، Mastodon أطول)
- **rate-limit aware** — sleep بين المنصات لتجنّب bans
- **graceful degradation** — منصة فاشلة لا توقف الباقي

---

## 🚫 ما لا يفعله

- ❌ ينشر نفس الرابط في عدة subreddits (= spam)
- ❌ يفتح حسابات (مستحيل API)
- ❌ يتجاوز rate limits
- ❌ ينشر بدون token صحيح

---

## 📊 Workflow الموصى به

```
1. فيديو جديد ينشر public على YouTube
   ↓
2. python3 scripts/social_post.py [id]
   ↓
3. ينشر على Bluesky + Twitter + Mastodon فوراً
   ↓
4. Reddit بعد 24 ساعة (للسماح للفيديو بالحصول على engagement أولاً)
   ↓
5. raw views يبدأ تدفقها إلى YouTube → algorithm يلتقط القناة
```
