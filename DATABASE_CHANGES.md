# Database changes v7

Жаңа кестелер: `conversations`, `messages`, `attachments`, `tool_calls`, `tool_results`, `generated_files`, `jobs`.

Миграция автоматты: қолданба ашылғанда `CREATE TABLE IF NOT EXISTS` орындалады. Бұрынғы кестелер мен деректер жойылмайды. Әр оқу әрекетінің толық history кестелері сақталады.
