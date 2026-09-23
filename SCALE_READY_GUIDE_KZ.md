# AI Physics KZ — ауқымға дайындау нұсқаулығы

## Осы нұсқада дайын қосылған жүйелер

1. **Сыныптық тапсырма жүйесі**
   - Мұғалім нақты сыныпқа A/B/C деңгейіндегі 1–5 тапсырманы ЖИ арқылы құрып жібереді.
   - API істемесе, жергілікті тапсырма қорына fallback жасалады.
   - Оқушы тапсырманы орындайды, нәтиже автоматты тексеріледі.
   - Нәтиже `attempts`, `mastery`, `mistakes` жүйелеріне бірден түседі.
   - Мұғалім қанша оқушы бастағанын және орташа ұпайды көреді.
   - Тапсырманы жабуға және қайта ашуға болады.

2. **RAG деректерін сынып бойынша оқшаулау**
   - Материал жүктегенде мұғалім қай сыныптарға қолжетімді болатынын таңдайды.
   - Оқушының ЖИ-мұғалімі тек сол оқушы кіретін сыныптарға бекітілген материалдарды көреді.
   - Бұрынғы `all_chunks()` арқылы барлық мұғалім материалын бірге іздеу тәуекелі жойылды.

3. **Production API-key режимі**
   - `APP_MODE=production` және `ALLOW_USER_API_KEY=false` болса, API key пайдаланушы интерфейсінен енгізілмейді.
   - Кілт сервердің `OPENAI_API_KEY` орта айнымалысында сақталады.

4. **Audit және индекстерге негіз дайын**
   - `audit_log` кестесі қосылды.
   - Жиі қолданылатын оқу кестелеріне индекстер қосылды.

5. **Орналастыру және қызмет көрсету**
   - `Dockerfile` және `docker-compose.yml` бар.
   - SQLite online backup скрипті бар: `python scripts/backup_sqlite.py`.
   - GitHub Actions CI: тест + compile check.
   - Негізгі тесттер 8 сценарийді қамтиды, оның ішінде RAG оқшаулауы және assignment access-control.

## Қазір жоба қай деңгейге дайын?

Бұл нұсқа **бір мектеп, пилоттық желі, байқау демонстрациясы және шағын production** үшін тікелей іске қосуға дайын. Бір Streamlit сервері + бір SQLite база режимінде ондаған/жүздеген белсенді қолданушыға арналған пилотты ұйымдастыруға болады, бірақ нақты шек сервер ресурсына және бір мезеттегі жазу санына байланысты.

## Аудан/облыс/республика масштабы үшін міндетті келесі архитектура

### 1. PostgreSQL
SQLite орнына PostgreSQL енгізу қажет. Себептері:
- бірнеше сервер репликасы бір базаға жаза алады;
- транзакция/индекс/конкуренттік жазу тұрақты;
- резервтік көшіру және мониторинг құралдары成熟;
- кейін pgvector пайдалануға болады.

### 2. Backend API
Streamlit-тің ішінде бизнес-логиканы ұстамай, бөлек FastAPI/Django backend шығару керек:
- `/auth`
- `/classes`
- `/assignments`
- `/attempts`
- `/analytics`
- `/rag`
- `/ai`

Frontend тек API-мен сөйлесуі тиіс. Бұл мобильді қосымша немесе басқа веб-клиентті кейін қосуды жеңілдетеді.

### 3. Ұйым / мектеп / tenant моделі
Кестелерге мына иерархияны қосу керек:
`organization -> school -> teacher -> class -> student`.
Әр сұрау tenant бойынша тексеріледі. Бұл әр мектептің дерегін толық бөледі.

### 4. Рөлдер
Кемінде:
- `super_admin`
- `school_admin`
- `teacher`
- `student`
- қажет болса `parent` / `methodist`

Рөл тек интерфейсте емес, backend endpoint деңгейінде тексерілуі керек.

### 5. RAG-ты векторлық іздеуге көшіру
Қазіргі TF-IDF шағын базаға жақсы. Үлкен қорда:
- embeddings;
- PostgreSQL + pgvector немесе Qdrant;
- metadata filter: school_id, class_id, grade, subject, teacher_id;
- chunk versioning және source citation қажет.

### 6. AI gateway
Барлық OpenAI сұрауын бір серверлік қабаттан өткізу керек:
- бір орталық API key;
- user/class quota;
- сұрау саны мен token/шығын есебі;
- timeout/retry;
- модель fallback;
- журнал және error tracking;
- prompt versioning.

### 7. Фондық тапсырмалар
PDF/DOCX индекстеу, үлкен есеп шығару, bulk analytics сияқты ауыр операциялар queue арқылы орындалуы керек:
- Redis;
- Celery/RQ/Arq тәрізді worker;
- progress/status кестесі.

### 8. Қауіпсіздік
- HTTPS;
- secure session/JWT;
- password policy;
- login rate limit;
- CSRF/XSS қорғанысы (таңдалған web framework-ке сай);
- файл өлшемі және MIME тексеруі;
- prompt injection-ға қарсы RAG policy;
- backup және restore rehearsal;
- audit log.

### 9. Аналитика
Ауқымды нұсқада дайын dashboard-тар:
- оқушы mastery heatmap;
- сынып бойынша әлсіз тақырыптар;
- қате taxonomy тренді;
- тапсырма completion rate;
- диагностика pre/post динамикасы;
- AI usage/cost;
- мектеп/сынып салыстыруы (құпиялылық ережесімен).

## Ұсынылатын 3 кезең

**Кезең 1 — қазір дайын пакет:** бір мектеп/пилот; assignment + secure class RAG + Docker + backup + CI.

**Кезең 2 — platform backend:** PostgreSQL + FastAPI + organization/role model + AI gateway + vector RAG.

**Кезең 3 — үлкен масштаб:** Redis workers + object storage + load balancer + multi-replica backend + monitoring + disaster recovery.

## Іске қосу

### Windows local
`START_WINDOWS.bat`

### Production-like Docker
1. `.env.production.example` файлын `.env` деп көшіріңіз.
2. `OPENAI_API_KEY` мәнін орнатыңыз.
3. `docker compose up --build -d`
4. `http://SERVER_IP:8501`

> Ескерту: осы Docker Compose бір реплика + SQLite пилот конфигурациясы. Көп репликалы нақты масштаб үшін PostgreSQL backend-ке көшу міндетті.
