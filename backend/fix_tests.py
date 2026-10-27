import os

files_to_fix = {
    'app/tests/test_knowledge_graph.py': [('character_count=len(text1)', 'character_count=len(text1))'), ('character_count=len(text2)', 'character_count=len(text2))')],
    'app/tests/test_learning.py': [('len(response.json() >=', 'len(response.json()) >='), ('len(items) ==', 'len(items)) ==')],
    'app/tests/test_search.py': [('side_effect=Exception("Chroma down":', 'side_effect=Exception("Chroma down"):'), ('len(data["results"] == 0', 'len(data["results"]) == 0')],
    'app/tests/test_summaries.py': [('str(uuid.uuid4()', 'str(uuid.uuid4())')],
    'app/tests/test_topics.py': [('character_count=len(t)', 'character_count=len(t))')],
    'app/tests/test_chat.py': [('str(uuid.uuid4()', 'str(uuid.uuid4())'), ('str(conversation.id)', 'str(conversation.id))')],
    'app/tests/test_chat_import.py': [('len(chunks) >', 'len(chunks)) >')]
}

for path, fixes in files_to_fix.items():
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        for old, new in fixes:
            content = content.replace(old, new)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

print('Done fixing missing parentheses')
