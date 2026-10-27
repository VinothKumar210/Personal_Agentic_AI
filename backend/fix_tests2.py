import os
import re

files_to_fix = {
    'app/tests/test_chat.py': [(r'side_effect=Exception\("Chroma error"\)$', r'side_effect=Exception("Chroma error"))')],
    'app/tests/test_chat_import.py': [(r'assert len\(chunks\)\) > 0', r'assert len(chunks) > 0')],
    'app/tests/test_knowledge_graph.py': [(r'character_count=len\(text\)$', r'character_count=len(text))')],
    'app/tests/test_search.py': [(r'side_effect=Exception\("Chroma down":', r'side_effect=Exception("Chroma down")):'), (r'len\(data\["results"\] == 0', r'len(data["results"]) == 0')],
    'app/tests/test_summaries.py': [(r'col_id = str\(uuid.uuid4\(\)\s+assert response.status_code', r'col_id = str(uuid.uuid4())\n    assert response.status_code')],
}

for path, fixes in files_to_fix.items():
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # fix missing trailing paren on lines ending with (text or (Chroma error"
        content = re.sub(r'Exception\("Chroma error"\)\n', r'Exception("Chroma error"))\n', content)
        content = re.sub(r'character_count=len\(text\)\n', r'character_count=len(text))\n', content)
        content = re.sub(r'assert len\(chunks\)\) > 0', r'assert len(chunks) > 0', content)
        content = re.sub(r'Exception\("Chroma down":', r'Exception("Chroma down")):', content)
        
        # for test_summaries.py
        if "test_summaries.py" in path:
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if "client.get(f\"/api/summaries/documents/{doc_id}\"" in line and not line.endswith(")"):
                    lines[i] = line + ")"
            content = "\n".join(lines) + "\n"
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

print('Done fixing')
