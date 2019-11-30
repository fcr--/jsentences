# jsentences
Script to build an anki dict from tatoeba sentences, sorted by the knowledge of the user.

## Installing:

You'll need `Mecab`, a simple way to install it, is by doing `apt-get install mecab mecab mecab-naist-jdic`.  Make sure it's on your path if you install it from the source code.

Also, make sure you have all the dependencies for building psycopg2, including `python3.7-dev` (or the version you are using), `postgresql-server-dev-10` (or the version you're using)... and don't forget about gcc and friends...

Start by clonning the repo, then `cd` into it.

```bash
# Now we create a virtualenv with the dependencies:
virtualenv -p python3 venv
. venv/bin/activate
pip install -r requirements.txt
```

Go into https://tatoeba.org/eng/downloads, download sentences.tar.bz2 and links.tar.bz2 into the directory where `jsentences-load.sql` is located.

```bash
# We proceed to uncompress the files:
tar -jxf sentences.tar.bz2 && rm sentences.tar.bz2
tar -jxf links.tar.bz2 && rm links.tar.bz2

# Then we create and populate a postgresql database:
psql template1 -c 'create database jsentences'
psql jsentences < jsentences.sql
psql jsentences < jsentences-load.sql

# Finally run mecab over all the japanese sentences:
python3 jsentences.py mecabize
```

## Usage:

Once you understand a sentence, you can add it using:
```bash
python3 jsentences.py add_sentence この文章が分かるようになりました！
```

The `add_sentence` command will impact the database creating a new "knowledge level", whitelisting the sentences that contain a subset of the tagged words and grammars added with `add_sentence` up to that point.

* To list the sentences you should be able to read up to that point:

```sql
select *
  from (select s_id, max(lvl) l
          from sentence_words sw group by s_id
        having count(case when lvl is null then 1 end)=0) t
  join sentences on s_id=id order by l;
```

* Recommended sentences that you *may* understand (ordered by frequency of the new word):
```sql
select freq, jpn, translations
  from (select s_id, sum(case when lvl is null then n else 0 end) freq
          from sentence_words sw join features_count fc on sw.f_id=fc.f_id
         group by s_id
        having count(case when lvl is null then 1 end)=1) t
  join sentences on s_id=id
 order by freq desc;
```
