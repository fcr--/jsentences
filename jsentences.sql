drop table if exists sentence_words, features, sentences, added_sentences;

create table sentences(
    id int primary key,
    jpn text not null,
    translations text[] not null default '{}',
    lvl int  -- calculated as: (select max(lvl) from sentence_words where s_id=? group by s_id having count(case when lvl is null then 1 end)=0)
);
create index on sentences(lvl, id);

create table features(
    id serial primary key,
    feature text unique not null
);

create table sentence_words(
    s_id int not null references sentences(id),
    idx int not null,
    word text not null,
    f_id int not null references features(id),
    lvl int,
    primary key(s_id, idx)
);
create index on sentence_words(lvl);

create table added_sentences(
    lvl int primary key,
    jpn text not null
);

create or replace function feature(jptext text) returns int as $$
    declare
        rec int;
    begin
        select id into rec from features where feature=jptext;
        if not found then
            insert into features(feature) values(jptext) returning id into rec;
        end if;
        return rec;
    end;
$$ language plpgsql;
