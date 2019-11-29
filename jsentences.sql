drop table if exists sentence_words, features, sentences;

create table sentences(
    id int primary key,
    jpn text not null,
    translations text[] not null default '{}',
);

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