"""Read-only checks of the delivered article grain and coverage denominators."""
import argparse, collections, datetime, json, sqlite3
from pathlib import Path
import fulltext_pilot as p


def main(snapshot):
    folder = p.ROOT / 'analysis/global_expansion_20261106' / snapshot
    db = sqlite3.connect(f'file:{(folder / "climate_governance.sqlite").as_posix()}?mode=ro', uri=True)
    counts = dict(db.execute('SELECT eligible,count(*) FROM articles GROUP BY eligible'))
    invalid_dates = []
    lengths = []
    languages = collections.Counter()
    precision = collections.Counter()
    for ident, date, unit, language, length in db.execute(
            'SELECT article_id,published_date,date_precision,language,length(source_text) FROM articles WHERE eligible=1'):
        try:
            if unit == 'month': datetime.datetime.strptime(date, '%Y-%m')
            elif unit == 'year': datetime.datetime.strptime(date, '%Y')
            else: datetime.date.fromisoformat(date)
        except ValueError: invalid_dates.append({'article_id': ident, 'date': date, 'precision': unit})
        lengths.append(length); languages[language] += 1; precision[unit] += 1
    lengths.sort()
    def scalar(sql): return db.execute(sql).fetchone()[0]
    unique = scalar('SELECT count(DISTINCT normalized_sha256) FROM articles')
    total = sum(counts.values())
    missing = scalar("SELECT count(*) FROM articles WHERE eligible=1 AND (source_text='' OR title='' OR url='' OR published_date='')")
    unmatched = scalar("SELECT count(*) FROM articles a WHERE eligible=1 AND NOT EXISTS (SELECT 1 FROM labels l WHERE l.article_id=a.article_id AND l.dimension='subcategory')")
    orphan = scalar('SELECT count(*) FROM labels l LEFT JOIN articles a USING(article_id) WHERE a.article_id IS NULL')
    sources = list(db.execute('SELECT publisher,count(*) n FROM articles WHERE eligible=1 GROUP BY publisher ORDER BY n DESC'))
    result = {'checked_at': p.stamp(), 'article_grain': 'normalized fulltext or canonical URL deduplicated article',
              'counts': {'total': total, 'eligible': counts.get(1, 0), 'review': counts.get(0, 0)},
              'duplicate_normalized_bodies': total - unique, 'missing_required_values': missing,
              'orphan_labels': orphan, 'invalid_dates': invalid_dates,
              'eligible_without_subtopic': unmatched, 'language_counts': dict(languages),
              'date_precision_counts': dict(precision),
              'body_characters': {str(q): lengths[min(len(lengths)-1, int((len(lengths)-1)*q))] for q in [0, .1, .5, .9, .99, 1]} if lengths else {},
              'publisher_counts': dict(sources),
              'largest_publisher_share': sources[0][1] / counts[1] if sources else None,
              'interpretation': 'Automated extraction and label evidence checks do not measure semantic label precision or recall. Publisher and year concentration must accompany trend analysis.'}
    p.dump(folder / 'quality_audit.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ['publisher_counts', 'language_counts']}, ensure_ascii=False))
    assert total == unique and not missing and not orphan and not invalid_dates


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--snapshot', required=True)
    main(parser.parse_args().snapshot)
