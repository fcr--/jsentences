#!/usr/bin/env python3
import argparse
import basicweb
import psycopg2
import psycopg2.extras
import psycopg2.extensions
import subprocess
import urllib.parse

from typing import Dict, List, Tuple
from psycopg2.extensions import connection
from html import escape


# Redefine configuration parameters in `jsentences_config.py` to override them.
def cfg(param, default):
    try:
        import jsentences_config
        return getattr(jsentences_config, 'param', default)
    except ModuleNotFoundError:
        return default


class MecabEntry():
    def __init__(self, word: str, features: str):
        self.word = word
        self.features = features

    def normalized(self) -> str:
        parts = self.features.split(',')
        # if the word is unknown by mecab, then an * will appear on the 7th field
        # that's why we substitute it by the specific word with an asterisk in front.
        if parts[6] == '*':
            parts[6] = '*' + self.word
        return ','.join(parts)


class Mecab():
    def __init__(self, mecab_args=[], encoding='utf-8'):
        self.encoding = encoding
        self.proc = subprocess.Popen(
            ['mecab', *mecab_args],
            stdout=subprocess.PIPE, stdin=subprocess.PIPE
        )

    def __call__(self, japanese_text: str) -> List[MecabEntry]:
        japanese_text += '\n'
        line_count = japanese_text.count('\n')
        self.proc.stdin.write(japanese_text.encode(self.encoding))
        self.proc.stdin.flush()

        res = []
        while line_count > 0:
            line = self.proc.stdout.readline().decode(self.encoding).strip('\n')
            if line == 'EOS':
                line_count -= 1
                continue
            word, features = line.split('\t')
            res.append(MecabEntry(word, features))
        return res


def mecabize(m: Mecab, db):
    with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as read_cur:
        with db.cursor() as write_cur:
            read_cur.execute('select id, jpn from sentences')
            for i, record in enumerate(read_cur):
                entries: List[MecabEntry] = m(record['jpn'])
                print(i, record['jpn'])
                assert ''.join(e.word for e in entries) == record['jpn'].replace(' ', '')
                write_cur.execute("""
                    insert into sentence_words(s_id, idx, word, f_id) values
                """ + ','.join(['(%s, %s, %s, feature(%s))'] * len(entries)), tuple(
                    x 
                    for idx, entry in enumerate(entries)
                    for x in (record['id'], idx, entry.word, entry.normalized())
                ))
                # We don't want a wall too big
                if i % 1000 == 0:
                    db.commit()
            write_cur.execute("""
                drop table if exists features_count;
                select f_id, count(*) n into features_count from sentence_words group by f_id;
                alter table features_count add primary key(f_id);
            """)
            db.commit()

def add_sentence(m: Mecab, db: connection, jpn: str) -> Tuple[int, int]:
    entries = m(jpn)
    with db.cursor() as cur:
        cur.execute('select coalesce(max(lvl)+1, 0) from added_sentences')
        new_level = cur.fetchone()[0]
        cur.execute(
            'with known as (select id from features where feature in (' +
            ','.join(['%s'] * len(entries)) + ') order by id)'
            'update sentence_words '
            '   set lvl = %s '
            ' where f_id in (select * from known) and lvl is null',
            (*[e.normalized() for e in entries], new_level),
        )
        rowcount = cur.rowcount
        if rowcount > 0:
            cur.execute(
                'insert into added_sentences(lvl, jpn) values(%s, %s)',
                (new_level, jpn),
            )
        db.commit()
        print('Updated {} words with new level {}'.format(rowcount, new_level))
        return rowcount, new_level

def get_added_sentences(db: connection) -> Dict[int, str]:
    """ Return added sentences associated to its level """
    with db.cursor() as cur:
        cur.execute('select lvl, jpn from added_sentences')
        return { lvl: jpn for lvl, jpn in cur.fetchall() }

def sentences_you_should_know(db: connection) -> List[Tuple[int, str, List[str]]]:
    with db.cursor() as cur:
        cur.execute("""select l, jpn, translations
            from (select s_id, max(lvl) l
                  from   sentence_words sw group by s_id
                  having count(case when lvl is null then 1 end) = 0) t
            join sentences on s_id=id order by l
        """)
        return cur.fetchall()

def sentences_you_may_know(db:connection) -> List[Tuple[int, int, str, List[str]]]:
    with db.cursor() as cur:
        # Words that impact too many sentences are somewhat limited by having only 5 rows
        # shown for each freq/d^2 value
        cur.execute("""
            select freq, d, jpn, translations
            from   (
                select   freq, d, jpn, translations,
                         row_number() over (partition by d,freq order by random()) rn
                from     (
                    select   s_id, sum(case when lvl is null then n else 0 end) freq,
                             count(case when lvl is null then 1 end) d
                    from     sentence_words sw join features_count fc on sw.f_id=fc.f_id
                    group by s_id
                    having   count(case when lvl is null then 1 end) > 0) t
                join     sentences on s_id=id
                order by d,freq desc) t
            where  rn <= 5
            limit  5000
        """)
        return cur.fetchall()


class Web(basicweb.BasicWeb):
    m: Mecab
    db: connection

    def tool_add_sentence(self) -> Tuple[int, str]:
        added_sentences: Dict[int, str] = get_added_sentences(Web.db)
        jpn = self.parsed_query.get('jpn', [''])[0]
        res = []
        if jpn:
            if jpn in added_sentences.values():
                res.extend(['The sentence: ', escape(jpn), '\nwas already added.\n\n'])
            else:
                rowcount, new_level = add_sentence(Web.m, Web.db, jpn)
                res.append(('The sentence {jpn}\nwas added at level {new_level} '
                    'affecting {rowcount} rows.\n\n').format(
                        jpn=escape(jpn), new_level=new_level, rowcount=rowcount))

        res.append(
            'Add new grammatically correct japanese sentence, it doesn\'t have to\n'
            'be from any particular source as long as it is perfectly well written:\n'
            '<form action=add_sentence method=get>    <input type=text name=jpn>'
            '<input type=submit value=Add></form>\n')

        res.append('Previously added sentences:\n')
        res.extend('{:5}: {}\n'.format(lvl, escape(jpn)) for lvl, jpn in added_sentences.items())
        return 200, ''.join(res)

    def tool_sentences_you_should_know(self) -> Tuple[int, str]:
        return 200, ''.join((
            'Sentences you should know at this point, sorted by level.  Each time\n'
            'you add a new sentences, this list will gradually increment:\n\n'
            '<table border=1><tr><th>Level</th><th>Japanese</th><th>Translations</th></tr>',
            *('<tr><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
                    lvl, escape(jpn), '<br>'.join(map(escape, translations)))
                for lvl, jpn, translations in sentences_you_should_know(Web.db)),
            '</table>'
        ))

    def tool_sentences_you_may_know(self) -> Tuple[int, str]:
        return 200, ''.join((
            'Sentences you may know at this point, sorted by how much it might help to learn them (frequency)\n'
            'and how many new words (with associated grammar points) you would need to know (d).\n'
            'There is also an [Add] button that will mark that sentence as learned.\n'
            'So make sure you understand that sentence before clicking it!:\n\n'
            '<table border=1><tr><th>Add</th><th>Frequency</th><th>d</th><th>Japanese</th><th>Translations</th></tr>',
            *('<tr><td>[<a href="add_sentence?jpn={}">Add</a>]</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
                urllib.parse.quote(jpn), freq, d, escape(jpn),
                '<br>'.join(map(escape, translations)))
                for freq, d, jpn, translations in sentences_you_may_know(Web.db)),
            '</table>'
        ))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='cmd')
    subparsers.required = True

    mecabize_subparser = subparsers.add_parser('mecabize',
        help='Runs mecab for all the sentences in the database.'
    )

    add_sentence_subparser = subparsers.add_parser('add_sentence',
        help='Given a new sentence that you understand, a new level is created and all known words are marked in the db.'
    )
    add_sentence_subparser.add_argument('sentence',
        help='A gramatically correct, understood japanese sentence.'
    )

    web_subparser = subparsers.add_parser('web',
        help='Start a small web service for the methods exported here (and some additional stuff).'
    )
    web_subparser.add_argument('port', type=int, nargs='?', default=8080,
        help='TCP port where the server will listen to.'
    )

    args = parser.parse_args()
    m = Mecab(
        mecab_args=cfg('mecab_args', [])
    )
    db = psycopg2.connect(cfg('db_dsn', 'dbname=jsentences'))

    if args.cmd == 'mecabize':
        mecabize(m, db)

    elif args.cmd == 'add_sentence':
        add_sentence(db, args.sentence)

    elif args.cmd == 'web':
        Web.m, Web.db = m, db
        Web.start(args.port)

    db.close()
