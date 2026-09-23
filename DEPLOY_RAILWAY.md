# Railway-ға орналастыру

1. Репозиторийді Railway жобаға қосыңыз.
2. Variables: `OPENAI_API_KEY`, `OPENAI_MODEL`, `APP_MODE=production`, `ALLOW_USER_API_KEY=false`.
3. Бір persistent volume қосыңыз: mount path `/app/storage`.
4. `AI_PHYSICS_DB=/app/storage/ai_physics_kz.db`, `AI_PHYSICS_UPLOAD_DIR=/app/storage/uploads`, `AI_PHYSICS_GENERATED_DIR=/app/storage/generated_files` орнатыңыз.
5. Deploy бастаңыз; `Dockerfile` Railway берген `PORT` арқылы іске қосады.

Құпия кілт браузерге берілмейді. `.env` репозиторийге кірмейді. Бірнеше replica қажет болса PostgreSQL adapter және object storage пайдаланыңыз.
