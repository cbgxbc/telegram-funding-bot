# Telegram Funding Bot — Root Layout

نسخة مصححة ومبسطة لبوت تمويل/مهام Telegram. **لا يوجد مجلد `app`**؛ كل ملفات التشغيل الأساسية موجودة في جذر المستودع حتى يكون رفعها من الهاتف أسهل.

## المزايا
- تسجيل المستخدمين والنقاط.
- إحالات مع مكافأة 10 نقاط.
- عرض حملات القنوات.
- زر فتح القناة والتحقق من العضوية.
- منع تكرار مكافأة نفس المستخدم لنفس الحملة بقاعدة بيانات وUnique Constraint.
- إنشاء حملة ممولة من رصيد المستخدم.
- رصيد وسجل معاملات.
- لوحة مالك: إحصائيات، حملات، مستخدمون، صيانة، تعليمات بث.
- أوامر إدارة: إضافة/خصم نقاط، حظر/إلغاء حظر، صيانة، بث.
- SQLite افتراضي، مع إمكانية PostgreSQL عبر `DATABASE_URL`.
- Docker.

## 1) المتطلبات
Python 3.12 أو أحدث، وبوت Telegram من BotFather.

## 2) التشغيل محليًا
```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# Linux/macOS
source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env
python main.py
```

عدّل `.env` وضع:
- `BOT_TOKEN`: توكن البوت.
- `OWNER_ID`: رقم Telegram الخاص بالمالك.
- `ADMIN_IDS`: أرقام إضافية مفصولة بفواصل، إن أردت.
- `BOT_USERNAME`: اسم البوت بدون @.
- `DATABASE_URL`: اترك SQLite الافتراضي إذا أردت.

**لا ترفع `.env` إلى GitHub.**

## 3) رفع المشروع من الهاتف إلى GitHub
هذه النسخة لا تحتاج إلى إنشاء مجلد `app`.

1. افتح المستودع.
2. اختر **Add file → Upload files**.
3. ارفع الملفات الموجودة داخل هذا المشروع كلها إلى **جذر المستودع**.
4. يجب أن ترى مثلًا:
   - `main.py`
   - `db.py`
   - `config.py`
   - `keyboards.py`
   - `requirements.txt`
   - `Dockerfile`
   - `README.md`
5. اضغط **Commit changes**.
6. لا ترفع `.env`.

لا تحتاج إلى رفع مجلد `data`; البرنامج ينشئه تلقائيًا عند استخدام SQLite.

## 4) إنشاء حملة
بعد أن يملك المستخدم نقاطًا:
```text
/newcampaign chat_id | title | reward | budget | invite_link
```
مثال:
```text
/newcampaign -100123456789 | قناتي | 5 | 100 | https://t.me/example
```

الشروط:
- البوت يجب أن يكون مشرفًا في القناة/المجموعة المستهدفة.
- `budget` يجب أن يكون من مضاعفات `reward`.
- يتم حجز الميزانية من رصيد صاحب الحملة عند إنشائها.
- صاحب الحملة لا يستطيع تنفيذ حملته بنفسه.

## 5) أوامر المالك
```text
/addpoints USER_ID AMOUNT
/ban USER_ID
/unban USER_ID
/maintenance on
/maintenance off
/broadcast نص الرسالة
```

## 6) الاستضافة
يمكن تشغيله كـ Web Service/Worker حسب مزود الاستضافة. التطبيق نفسه يعمل بعملية polling ولا يحتاج إلى منفذ HTTP.

إذا استخدمت مزودًا ينام عند الخمول أو يعيد إنشاء القرص، استخدم PostgreSQL للحالة الدائمة بدل SQLite.

## ملاحظة
هذه نسخة تشغيلية كأساس قوي، وليست نظامًا ماليًا أو ضمانًا لمنع كل أنواع الاحتيال. أي نظام إنتاج حقيقي يحتاج مراقبة، حدود معدل، مكافحة حسابات وهمية، وتدقيق إضافي.
