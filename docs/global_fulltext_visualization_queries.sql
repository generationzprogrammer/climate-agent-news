-- Eligible, deduplicated article counts. Multi-label totals may exceed N.
SELECT * FROM annual_source_coverage ORDER BY year,publisher;
SELECT * FROM annual_topic_mentions ORDER BY year,label;
SELECT * FROM annual_country_mentions ORDER BY year,label;

-- Topic co-occurrence; shared reporting, not causality.
WITH edges AS (
 SELECT x.label a,y.label b,COUNT(*) n
 FROM labels x JOIN labels y USING(article_id)
 JOIN articles d USING(article_id)
 WHERE d.eligible=1 AND x.dimension='subcategory'
 AND y.dimension='subcategory' AND x.label<y.label
 GROUP BY x.label,y.label
), totals AS (
 SELECT l.label,COUNT(*) n FROM labels l JOIN articles d USING(article_id)
 WHERE d.eligible=1 AND l.dimension='subcategory' GROUP BY l.label
)
SELECT e.a,e.b,e.n,1.0*e.n/(a.n+b.n-e.n) jaccard
FROM edges e JOIN totals a ON a.label=e.a JOIN totals b ON b.label=e.b;

-- Country--organization joint mentions; count each article once.
SELECT c.label country,o.label organization,COUNT(*) articles
FROM labels c JOIN labels o USING(article_id) JOIN articles a USING(article_id)
WHERE a.eligible=1 AND c.dimension='country' AND o.dimension='organization'
GROUP BY c.label,o.label;

-- Shared-source panel: restrict to publishers represented every study year.
-- Set study years explicitly; do not infer that absent observations mean zero news.
WITH panel AS (
 SELECT publisher FROM articles WHERE eligible=1 AND year BETWEEN 2020 AND 2025
 GROUP BY publisher HAVING COUNT(DISTINCT year)=6
)
SELECT a.year,l.label,COUNT(*) articles FROM articles a
JOIN panel p USING(publisher) JOIN labels l USING(article_id)
WHERE a.eligible=1 AND a.year BETWEEN 2020 AND 2025 AND l.dimension='subcategory'
GROUP BY a.year,l.label;
