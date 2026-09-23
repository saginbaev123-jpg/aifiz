from ai_core.math_text import prepare_math
from ai.openai_client import AIClient
from types import SimpleNamespace

def test_math_delimiters():
    assert '$E_p$' in prepare_math('$ E_p $ көп')
    assert '$$' in prepare_math(r'[ 1 \text{км}=1000\text{м} ]')
    assert '$$' in prepare_math(r'\[\frac{gt^2}{2}\]')

def test_math_fence_and_code_preservation():
    value = prepare_math('```text\nБиіктік  Қозғалыс\n$ E_p $ көп  $ E_k $ көп\n```')
    assert '| --- | --- |' in value
    assert '$E_p$' in value
    code = '```python\nprint("$ x $")\n```'
    assert prepare_math(code) == code

def test_client_sends_ordered_roles():
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(output_text='Жауап')
    client = AIClient()
    client.client = SimpleNamespace(responses=SimpleNamespace(create=create))
    client.conversation_messages = [{'role':'user','content':'Қисық сызықты қозғалыс'}, {'role':'assistant','content':'Түсіндірме'}]
    client.text('Нұсқау', 'Осыған мысал бер')
    assert [x['role'] for x in captured['input']] == ['user','assistant','user']
    assert captured['input'][-1]['content'] == 'Осыған мысал бер'
