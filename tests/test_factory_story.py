from types import SimpleNamespace

import pytest

import factory_story


@pytest.mark.parametrize('output', [
    'not json',
    '["Only one idea"]',
    '["Same funny idea", "Same funny idea", "Another funny idea"]',
    '["A", "Second funny idea", "Third funny idea"]',
])
def test_idea_generation_rejects_invalid_model_output(monkeypatch, output):
    closed = []
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: SimpleNamespace(text=output)),
                             close=lambda: closed.append(True))
    monkeypatch.setattr(factory_story.genai, 'Client', lambda **kwargs: client)
    with pytest.raises(ValueError):
        factory_story.generate_ideas('Dry office humor', 3, 'key')
    assert closed == [True]


def test_idea_generation_uses_style_and_closes_client(monkeypatch):
    calls, closed = [], []
    def generate_content(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text='["A chaotic staff meeting", "A lunch break mixup", "An unexpected promotion"]')
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content), close=lambda: closed.append(True))
    monkeypatch.setattr(factory_story.genai, 'Client', lambda **kwargs: client)
    assert len(factory_story.generate_ideas('Dry humor', 3, 'key')) == 3
    assert 'Dry humor' in calls[0]['contents']
    assert closed == [True]
