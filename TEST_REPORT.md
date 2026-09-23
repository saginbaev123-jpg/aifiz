# Test report

Күні: 2026-09-22

`python -m pytest -q` → 16 passed.

Қамтылғаны: registration, class code, permissions, assignments, PISA, notebook history, conversations, routing, slide count, file validation және sanitizing.

Streamlit AppTest login/register бетін exception-сіз жүктеді. Қолданба `0.0.0.0:8501` адресінде іске қосылды. Cloud browser localhost-ты қауіпсіздік себебімен ашпады, сондықтан осы ортада browser screenshot алынбады; live app smoke test AppTest арқылы орындалды.

Icon атаулары пайдаланушы шаблондарында жоқ. Техникалық қате кодтары ішкі classifier/log қабатында ғана сақталып, UI-да қазақша атаумен көрсетіледі.
