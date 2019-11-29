# jsentences
Script to build an anki dict from tatoeba sentences, sorted by the knowledge of the user.

## Installing:

You'll need `Mecab`, a simple way to install it, is by doing `apt-get install mecab mecab mecab-naist-jdic`.  Make sure it's on your path if you install it from the source code.

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

TODO
