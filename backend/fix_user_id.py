import os
import re

tests_dir = 'app/tests'
for root, _, files in os.walk(tests_dir):
    for f in files:
        if not f.endswith('.py'): continue
        path = os.path.join(root, f)
        with open(path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        models = ['Document', 'Collection', 'Tag', 'Source', 'LearningPath', 'TopicCluster', 'GraphNode', 'GraphEdge', 'IngestionJob']
        for model in models:
            def replacer(match):
                inner = match.group(1)
                if 'user_id' not in inner and inner.strip():
                    return f'{model}(user_id="dev-user-id", {inner})'
                elif 'user_id' not in inner and not inner.strip():
                    return f'{model}(user_id="dev-user-id")'
                return match.group(0)
            
            content = re.sub(rf'\b{model}\((.*?)\)', replacer, content, flags=re.DOTALL)
        
        with open(path, 'w', encoding='utf-8') as file:
            file.write(content)

print('Done fixing tests user_id')
