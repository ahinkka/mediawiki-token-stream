# -*- coding: utf-8 -*-

import logging

import sys
import datetime
import codecs
import re
import unittest
from unittest import TestCase
import signal, errno
from contextlib import contextmanager

class TimedOut(Exception): 
    pass 

@contextmanager
def timeout(seconds):
    def timeout_handler(signum, frame):
        raise TimedOut()

    original_handler = signal.signal(signal.SIGALRM, timeout_handler)

    try:
        signal.alarm(seconds)
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)


_TOKEN_CLASSES = []

class _Token(type):
    def __new__(cls, clsname, clsbases, clsdict):
        t = type.__new__(cls, clsname, clsbases, clsdict)

        test = getattr(t, '__test__', None)
        if clsname != u"Token" and clsname != u"_Token":
            # print clsname
            _TOKEN_CLASSES.append(clsname)

        regexp = getattr(t, '__re__', None)
        if regexp is not None:
            t.__re__ = regexp

        return t


# Token main class; subclasses should be bodyless
class Token(object):
    __metaclass__ = _Token

    def __init__(self, text):
        self.text = text

    @classmethod
    def match(cls, text):
        if not hasattr(cls, "pattern"):
            cls.pattern = re.compile(cls.__re__, re.UNICODE)
        with timeout(1):
            match = cls.pattern.match(text)
        if match is None:
            return None
        else:
            return match.end() - match.start()

    @classmethod
    def token(cls, text):
        return cls(text)

    def __unicode__(self):
        return self.text

    def __repr__(self):
        return "<%s '%s'>" % (self.__class__.__name__, str(self).replace("\n", "\\n"))

    def __str__(self):
        return unicode(self).encode('ASCII', 'backslashreplace')

    def __hash__(self):
        return self.__class__.__name__.__hash__() + self.text.__hash__()

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()


#
# Markup tokens
#
class BeginTemplate(Token): __re__ = ur'\{\{'

class EndTemplate(Token): __re__ = ur'\}\}'

class ToggleBold(Token): __re__ = ur"[']{3}"

class ToggleItalics(Token): __re__ = ur"[']{2}"

class BeginWikiLink(Token): __re__ = ur'[\[]{2}'

class EndWikiLink(Token): __re__ = ur'\]\]'

class BeginExternalLink(Token): __re__ = ur'\['

class EndExternalLink(Token): __re__ = ur'\]'

class BeginTable(Token): __re__ = ur'\n\{\|'

class EndTable(Token): __re__ = ur'\n\|\}'

class Equals(Token): __re__ = ur'='

class Reference(Token): __re__ = ur"<ref name ?= ?['\"]{1}[^'\"]+['\"]{1} ?/>"

class BeginNamedReference(Token): __re__ = ur"<ref name ?= ?['\"]{1}[^'\"]+['\"]{1}>"

class BeginReference(Token): __re__ = ur"<ref>"

class EndReference(Token): __re__ = ur'</ref>'

class ClosedHTMLTag(Token): __re__ = ur'<[a-z]+( [a-z]+=[a-z]+)* ?/>'

class NonBreakingSpace(Token): __re__ = ur"&nbsp;"

class ListItem(Token): __re__ = ur'\n\*'

class NewLine(Token): __re__ = ur'\n'

class Space(Token): __re__ = ur' '

class OtherSpace(Token): __re__ = ur'\s'

class Pipe(Token): __re__ = ur'\|'

# http://daringfireball.net/2010/07/improved_regex_for_matching_urls
class URL(Token): __re__ = ur'(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'".,<>?«»“”‘’]))'

class Word(Token):
    __re__ = ur'[\w]+'

    @classmethod
    def match(cls, text):
        s = super(Word, cls).match(text)
        t = text[:s]
        if u'\&' in t:
            return t.index(u'&') - 1

        return s

class Punctuation(Token): __re__ = ur'[/.,:;\-()"–-]'

#
# Tests
#
class TokenTest(TestCase):
    def test_match(self):
        class FooBar(Token):
            __re__ = ur"foobar"

        self.assertTrue(FooBar.match(u'foobar'))
        self.assertTrue(FooBar.match(u'foobaru'))
        self.assertFalse(FooBar.match(u'afoobar'))

    def test_token_instantiation(self):
        class FooBar(Token):
            __re__ = ur"foobar"

        self.assertTrue(FooBar.match(u'foobar'))
        t = FooBar.token(u'foobar')
        self.assertTrue(isinstance(t, FooBar))


class TokenizerTest(TestCase):
    def test_simple(self):
        class AoeuToken(Token):
            __re__ = ur'aoeu'
            __test__ = True

        class DhtnToken(Token):
            __re__ = ur'dhtn'
            __test__ = True

        tokens = [AoeuToken, DhtnToken]
        tokenized = list(tokenize(u"aoeudhtn", tokens))

        self.assertEqual(len(tokenized), 2)
        self.assertTrue(isinstance(tokenized[0], AoeuToken))
        self.assertTrue(isinstance(tokenized[1], DhtnToken))

    def test_mw_simple(self):
        text = u"This piece of [[poetry]] starts with some '''bolded''' text."
        t = list(tokenize(text, tokens()))
        self.assertEqual(len(t), 22)
        self.assertTrue(isinstance(t[0], Word))
        self.assertTrue(isinstance(t[1], Space))
        self.assertTrue(isinstance(t[6], BeginWikiLink))
        self.assertTrue(isinstance(t[-4], ToggleBold))
        self.assertTrue(isinstance(t[-1], Punctuation))

    def test_mw_bold(self):
        text = u"'''Bold text.'''"
        tokenized = tokenize(text, tokens())
        self.assertEqual(len(list(tokenized)), 6)

    def test_word(self):
        text = u"[[Amstel|Amstel-joki]]"
        tokenized = list(tokenize(text, tokens()))
        self.assertEqual(len(tokenized), 7, repr(tokenized))

    def test_acm(self):
        text = u"""'''AC''' ({{lyhenne|Adult Contemporary}}) on [[formaattiradio]]ihin liittyvä termi, jolla tarkoitetaan [[pop]]- ja [[rock]]-musiikkia "aikuiseen makuun"; ei kovaa rokkia.
* '''Hot AC''' on musiikkityyli, joka sisältää 0–10 vuotta vanhoja nopeatempoisia aikuishittejä; formaattikuvailu ja musiikki ovat paljon lähempänä AC:tä kuin [[CHR]]:ää. 
* '''MOR''' - Ei-[[rock]]-tyylisiä [[pop|pophittejä]] ja yleensä 15–45 vuotta vanhoja. Sisältää jotain [[soft AC]] -musiikkia; eli yleisesti sanoen tämä on "aikuisstandardi".

== Katso myös ==

* [[The Voice (radioasema)]]

{{Tynkä/Musiikki}}

[[Luokka:Populaarimusiikki]]

[[en:Adult contemporary music]]
[[ko:어덜트 컨템포러리]]
[[ja:アダルトコンテンポラリーミュージック]]
[[sv:Adult contemporary]]"""
        t = tokenize(text, tokens())
        o = u''.join([to.text for to in t])

        self.assertEqual(len(text), len(o))


    def test_timeout_on_insidious_urls(self):
        t1 = u'http://www.unhchr.ch/tbs/doc.nsf/(Symbol/CCPR.CO.82.FIN.En?Opendocument|Julkaisija=|Luettu=}}'
        t2 =  u'http://www.terveyskirjasto.fi/terveyskirjasto/tk.koti?p_artikkeli=dlk00495&p_haku=Sukupuoliset%20kohdeh%E4iri%F6t%20(pedofilia%20ja%20muut%20parafiliat)'

        self.assertRaises(TimedOut, URL.match, t1)
        self.assertRaises(TimedOut, URL.match, t2)


        # def bold(s):
        #     return u"%s%s%s" % ("\033[1m", s, "\033[0;0m")

        # d = u''
        # for i, c in enumerate(text):
        #     try:
        #         if o[i] == c:
        #             d += c
        #         else:
        #             d += bold(c)
        #     except:
        #         pass
        # print d


#
# Other functionality
#
def tokens():
    # return [globals()[clsname] for clsname in _TOKEN_CLASSES]

    ret = []
    for cls_name in _TOKEN_CLASSES:
        try:
            ret.append(globals()[cls_name])
        except KeyError, ke:
            pass
    return ret

class UnrecognizedToken(Exception):
    pass

def tokenize(text, tokens, debug=False):
    idx = 0
    while idx < len(text):
        # print text[idx:]
        for token in tokens:
            try:
                m = token.match(text[idx:])
            except TimedOut, te:
                m = None
            if m:
                ret = token.token(text[idx:idx+m])
                # print idx, m
                # print repr(text[idx:idx+20])
                # print repr(text[idx:idx+m])
                # print repr(ret)
                # print
                if debug:
                    print >> sys.stderr, "++    %-22s match for '%s' (%s)" % (token.__name__, text[idx:idx+50].replace('\n', '\\n'), repr(ret))
                idx += m-1
                yield ret
                break
            else:
                if debug:
                    print >> sys.stderr, "XX No %-22s match for '%s'" % (token.__name__, text[idx:idx+50].replace('\n', '\\n'))
        idx += 1


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-d", "--debug", dest="debug",
                      help="debug line-by-line",
                      action="store_true", default=False)
    (opts, args) = parser.parse_args()

    if len(args) == 1 and args[0] == u'-':
        contents = sys.stdin.read()
        tokens = tokenize(contents, tokens())
        print tokens
        print "Read %i tokens." % len(tokens)
        sys.exit(0)
    elif len(args) > 0:
        for item in args:
            with codecs.open(item, 'r', encoding='utf-8') as f:
                start = datetime.datetime.now()
                contents = f.read()
                t = list(tokenize(contents, tokens(), debug=opts.debug))
                end = datetime.datetime.now()
                d = end - start
                secs = float("%i.%i" % (d.seconds, d.microseconds))
                tokens_per_sec = float(len(t)) / secs
                print "Read %i tokens from %s in %f seconds (%i t/s)." % (len(t), item, secs, tokens_per_sec)
    else:
        unittest.main()
