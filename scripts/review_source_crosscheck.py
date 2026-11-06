"""Resolve only exact-body agreement before explicit republication boilerplate."""
import json
import fulltext_pilot as p

out = p.ROOT / 'analysis/global_expansion_20261106'
evidence = p.ROOT / 'data/private_global_expansion_20261106/source_audit'
reviews = []
for file in out.glob('source_crosscheck*.json'):
    content = json.loads(file.read_text('utf-8'))
    if not isinstance(content, dict): continue
    for row in content.get('samples', []):
        if row['status'] != 'manual_review': continue
        saved = evidence / (row['id'] + '.json')
        if not saved.exists(): continue
        text = json.loads(saved.read_text('utf-8'))['html_extracted_text']
        marker = '\n\nRepublish This Story\n\n'
        if marker in text:
            prefix = text.split(marker, 1)[0].strip()
            if p.digest(prefix.encode()) == row['api_text_sha256']:
                reviews.append({'sample_file': file.name, 'article_id': row['id'],
                                'result': 'exact_API_body_before_republication_terms',
                                'body_sha256': row['api_text_sha256'], 'source_text_changed': False,
                                'html_extra_characters': len(text) - len(prefix)})
p.dump(out / 'source_crosscheck_adjudication.json', {'checked_at': p.stamp(), 'reviews': reviews})
print(json.dumps({'resolved': len(reviews)}))
