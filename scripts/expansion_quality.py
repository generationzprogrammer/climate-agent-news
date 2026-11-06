"""Conservative terminal adjudication with source trace, no generated text."""
import re
from fulltext_review_rules import review_terminal,END

VERSION='expansion-quality-20261106-v1'
TAIL=re.compile(r'^(?:Read more:|Also see:|Related:|News item from |By [A-Z][A-Za-z .\-]{3,65}$|\*?Imagen principal:|\*?Foto:|\*?Liputan ini merupakan|\*{3,}$)',re.I)

def adjudicate(doc):
 prior=review_terminal(doc)
 if prior: return prior
 flags=doc.get('completeness_flags',doc.get('quality_flags',[]))
 if set(flags)!={'last_block_needs_review'}: return None
 if doc.get('source_block_coverage')!=1 or not doc.get('last_block_present'): return None
 blocks=[s.strip() for s in doc['source_text'].split('\n\n') if s.strip()]
 tail=[]
 for block in reversed(blocks[-8:]):
  if TAIL.search(block): tail.append(block); continue
  if tail and len(block)>80 and block.endswith(END):
   return {'version':VERSION,'basis':'source_end_metadata_after_complete_prose','terminal_blocks':tail,'preceding_prose_characters':len(block),'source_block_coverage':1,'text_modified':False}
  return None
 return None

def eligible(doc):
 flags=list(doc.get('quality_flags') or doc.get('completeness_flags') or [])
 review=adjudicate(doc)
 if review: flags=[f for f in flags if f!='last_block_needs_review']
 return not flags and doc.get('document_genre','news_or_commentary')=='news_or_commentary',review,flags
