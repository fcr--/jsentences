drop table if exists temp_sentences, temp_links;
create unlogged table temp_sentences(id int, lang text, txt text);
create unlogged table temp_links(sid int, tid int, primary key(sid, tid));

\copy temp_sentences from 'sentences.csv' delimiter E'\t';
\copy temp_links from 'links.csv' delimiter E'\t';

delete from temp_sentences where lang not in('jpn', 'spa', 'eng') or lang is null;

create index on temp_sentences(id, lang);
create index on temp_links(tid, sid);
analyze temp_sentences;
analyze temp_links;

insert into sentences select id, txt, a from temp_sentences t1, lateral (select coalesce(array_agg(txt)) a from temp_sentences t2 join temp_links on tid=t2.id where sid=t1.id) s where lang='jpn' and a is not null;

drop table temp_sentences, temp_links;
