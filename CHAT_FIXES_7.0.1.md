# Chat repairs 7.0.1

- Real ordered user/assistant messages replace flattened, individually truncated chat text in text-generation requests.
- Follow-up instructions retain the current topic unless the user changes it.
- New and saved answers use the same math normalization/rendering path.
- Math-only text fences are unwrapped; two-column explanations become Markdown tables. Programming code is preserved.
- Removed the expression rendered as None by Streamlit magic.
- Chat history moved to the sidebar; pending answer appears above the composer.
- Explicit avatars, local vector icon fallback, scoped heading sizes and inherited text fonts avoid Material font leakage and KaTeX font overrides.
- Removed malformed status expander and duplicate user message insertion on retry.

Validation: 19 pytest tests passed, Python compilation passed, teacher chat AppTest passed.
No live provider call or browser screenshot validation performed in this repair run. Long chats still use a bounded recent-message window; this is not unlimited memory. Rendering is performed after the provider response, not live token streaming. Broader v7 tool/job features are not certified by these tests.
