#!/usr/bin/env python3
import argparse
import psycopg2
import psycopg2.extras
import subprocess

from typing import List


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

def add_sentence(db, entries: List[MecabEntry]):
    with db.cursor() as cur:
        cur.execute('select coalesce(max(lvl)+1, 0) from sentence_words')
        new_level = cur.fetchone()[0]
        cur.execute(
            'with known as (select id from features where feature in (' +
            ','.join(['%s'] * len(entries)) + ') order by id)'
            'update sentence_words '
            '   set lvl = %s '
            ' where f_id in (select * from known) and lvl is null',
            (*[e.normalized() for e in entries], new_level),
        )
        db.commit()
        print('Updated {} words with new level {}'.format(cur.rowcount, new_level))


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

    args = parser.parse_args()

    if args.cmd == 'mecabize':
        m = Mecab()
        db = psycopg2.connect('dbname=jsentences')
        mecabize(m, db)
        db.close()

    elif args.cmd == 'add_sentence':
        m = Mecab()
        db = psycopg2.connect('dbname=jsentences')
        add_sentence(db, m(args.sentence))
        db.close()
