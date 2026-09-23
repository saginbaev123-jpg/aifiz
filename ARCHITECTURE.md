# AI Physics KZ v7 архитектурасы

`app.py` — интерфейс; `ai_core/` — ортақ AI Core; `core/database.py` — SQLite және server-side ownership; `ai/` — модель клиенті; `rag/` — файл оқу; `reports/` — экспорт.

Teacher AI және Student AI бір `AICore` қолданады. `PermissionManager` әр құралды рөл бойынша серверде тексереді. Әр чат жеке `conversation_id` алады; хабарламалар, тіркемелер, tool журналдары және жасалған файлдар осы ID арқылы байланысады.

Соңғы хабарламалар (`AI_CONTEXT_MESSAGES`) және бұрын жасалған файл metadata-сы контекстке қосылады. Conversation қайта ашылғанда тарих SQLite-дан қалпына келеді. `jobs` кестесі ұзақ жұмыс үшін `queued/running/completed/failed` күйлерін сақтайды.
