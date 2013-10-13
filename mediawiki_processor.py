# -*- coding: utf-8 -*-

import logging
#logging.basicConfig(level=logging.WARNING)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("mwparser.plaintext")

import sys
import datetime
import codecs
import re
import unittest
from unittest import TestCase

from collections import defaultdict
from time import sleep

from mediawiki_token import *

_print_state = False

class BreakException(Exception): pass

class MWProcessor(object):
    def process_template(self, token_stream):
        if _print_state:
            print >> sys.stderr, "# Begin processing template."

        while True:
            token = token_stream.next()
            # print >> sys.stderr, " ", repr(token)
            if isinstance(token, BeginTemplate):
                try:
                    for token in self.process_template(token_stream):
                        pass
                except BreakException, be:
                    pass
            elif isinstance(token, EndTemplate):
                if _print_state:
                    print >> sys.stderr, "# End processing template."
                raise BreakException()

    def process_table(self, token_stream):
        if _print_state:
            print >> sys.stderr, "# Begin processing table."

        while True:
            token = token_stream.next()

            if isinstance(token, BeginTable):
                try:
                    for token in self.process_table(token_stream):
                        pass
                except BreakException, be:
                    pass
            elif isinstance(token, EndTable):
                if _print_state:
                    print >> sys.stderr, "# End processing table."
                raise BreakException()

    def process_wiki_link(self, token_stream):
        if _print_state:
            print >> sys.stderr, "# Begin processing wiki link."

        # https://secure.wikimedia.org/wikipedia/mediawiki/wiki/Help:Links
        link_tokens = []
        while True:
            token = token_stream.next()

            if isinstance(token, BeginWikiLink):
                yield Space(u' ')
                try:
                    for token in self.process_wiki_link(token_stream):
                        yield token
                except BreakException, be:
                    pass
                yield Space(u' ')
            elif isinstance(token, EndWikiLink):
                yieldable = []
                was_newline = False
                for link_token in link_tokens:
                    if isinstance(link_token, NewLine):
                        was_newline = True
                        continue
                    elif isinstance(link_token, Pipe):
                        yieldable = []
                    else:
                        yieldable.append(link_token)

                # Prune out namespaces shortcuts
                no_yield = False
                for y in yieldable:
                    if isinstance(y, Punctuation) and y.text == u':':
                        no_yield = True
                if no_yield:
                    yieldable = []

                # print "!", link_tokens
                # print "!", yieldable
                for y in yieldable:
                    if isinstance(y, EndWikiLink):
                        continue
                    if self.is_ignorable(y):
                        continue
                    yield y
                if was_newline:
                    yield NewLine(u'\n')
                if _print_state:
                    print >> sys.stderr, "# End processing wiki link."
                raise BreakException()
            else:
                link_tokens.append(token)

            # print "W %-50s %-30s" % (str(token).replace('\n', '\\n'),
            #                          repr(token))

    def process_external_link(self, token_stream):
        if _print_state:
            print >> sys.stderr, "# Begin processing external link."

        # https://secure.wikimedia.org/wikipedia/mediawiki/wiki/Help:Links
        link_tokens = []
        while True:
            token = token_stream.next()

            if isinstance(token, EndExternalLink):
                yieldable = []
                for link_token in link_tokens:
                    if isinstance(link_token, NewLine):
                        continue
                    elif isinstance(link_token, URL):
                        yieldable = []
                    elif isinstance(link_token, Space) and len(yieldable) == 0:
                        pass
                    else:
                        yieldable.append(link_token)

                # print link_tokens
                # print yieldable
                for y in yieldable:
                    if isinstance(y, EndExternalLink):
                        continue
                    if self.is_ignorable(y):
                        continue
                    yield y
                if _print_state:
                    print >> sys.stderr, "# End processing external link."
                raise BreakException()
            else:
                link_tokens.append(token)

            # print "W %-50s %-30s" % (str(token).replace('\n', '\\n'),
            #                          repr(token))


    def process_reference(self, token_stream):
        if _print_state:
            print >> sys.stderr, "# Begin processing reference."
        while True:
            token = token_stream.next()
            # print >> sys.stderr, " ", repr(token)
            if isinstance(token, EndReference):
                if _print_state:
                    print >> sys.stderr, "# Begin processing reference."
                raise BreakException()
            elif isinstance(token, BeginTemplate):
                try:
                    for token in self.process_template(token_stream):
                        pass
                except BreakException, be:
                    pass

    def process_listitem(self, token_stream):
        yield NewLine(u'\n')

    def process(self, token_stream):
        try:
            for token in self.process_toplevel(token_stream):
                yield token
        except BreakException, be:
            pass

    def is_ignorable(self, token):
        if isinstance(token, ToggleBold) or \
                isinstance(token, ToggleItalics) or \
                isinstance(token, Reference) or \
                isinstance(token, ClosedHTMLTag):
            return True
        return False

    def process_toplevel(self, token_stream):
        no_yield = False
        while True:
            no_yield = False
            try:
                token = token_stream.next()
            except StopIteration, si:
                break

            if self.is_ignorable(token):
                no_yield = True
            elif isinstance(token, NonBreakingSpace):
                token = Space(u' ')
            elif isinstance(token, Equals):
                # Weed out headings
                level = 0

                # Count begin heading tokens
                while isinstance(token, Equals):
                    level += 1
                    token = token_stream.next()

                def consume_non_equals():
                    '''Return True if NewLine encountered: break a broken heading there.'''
                    token = None
                    while not isinstance(token, Equals):
                        token = token_stream.next()
                        if isinstance(token, NewLine):
                            return True

                # Consume the stuff in between
                if consume_non_equals() == True:
                    pass
                elif level == 1:
                    pass
                elif level > 1:
                    level -= 1
                    while level > 0:
                        token = token_stream.next()
                        if isinstance(token, Equals):
                            level -= 1
                        elif isinstance(token, NewLine):
                            level = 0

                token = Space(u' ')
                no_yield = False

            elif isinstance(token, ListItem):
                try:
                    for token in self.process_listitem(token_stream):
                        yield token
                except BreakException, be:
                    no_yield = True
            elif isinstance(token, BeginTemplate):
                try:
                    for token in self.process_template(token_stream):
                        yield token
                except BreakException, be:
                    no_yield = True
            elif isinstance(token, BeginTable):
                try:
                    for token in self.process_table(token_stream):
                        yield token
                except BreakException, be:
                    no_yield = True
            elif isinstance(token, BeginReference) or isinstance(token, BeginNamedReference):
                try:
                    for token in self.process_reference(token_stream):
                        yield token
                except BreakException, be:
                    no_yield = True
            elif isinstance(token, BeginExternalLink):
                try:
                    for token in self.process_external_link(token_stream):
                        yield token
                except BreakException, be:
                    no_yield = True
            elif isinstance(token, BeginWikiLink):
                try:
                    for token in self.process_wiki_link(token_stream):
                        yield token
                except BreakException, be:
                    no_yield = True

            # print "P %-50s %-30s" % (str(token).replace('\n', '\\n'),
            #                          repr(token))

            if no_yield is False:
                yield token

def y(seq):
    '''Helper function to make a list into a generator.'''
    for i in seq:
        yield i


class ProcessorTest(TestCase):
    def setUp(self):
        self.p = MWProcessor()

    def test_template(self):
        data = [BeginTemplate(u"{{"), Word(u"foo"), EndTemplate(u"}}")]
        out = list(self.p.process(y(data)))
        self.assertEqual(len(out), 0)

    def test_recursive_template(self):
        data = [BeginTemplate(u"{{"), Word(u"foo"), Equals(u"="),
                BeginTemplate(u"{{"), Word(u"bar"), EndTemplate(u"}}"),
                EndTemplate(u"}}")]
        out = list(self.p.process(y(data)))
        self.assertEqual(len(out), 0)

    def test_remove_single_headings(self):
        data = [Equals(u"="), Word(u"foo"), Equals(u"="), Word(u"foo")]
        out = list(self.p.process(y(data)))
        self.assertEquals(len(out), 2)

    def test_remove_double_headings(self):
        data = [Word(u"baz"), Equals(u"="), Equals(u"="), Word(u"foo"),
                Equals(u"="), Equals(u"="), Word(u"bar")]
        out = list(self.p.process(y(data)))
        self.assertEquals(len(out), 3)

    def test_remove_triple_headings(self):
        data = [Equals(u"="), Equals(u"="), Equals(u"="), Word(u"foo"),
                Equals(u"="), Equals(u"="), Equals(u"="), Word(u"bar")]
        out = list(self.p.process(y(data)))
        self.assertEquals(len(out), 2)

    def test_remove_newline_terminated_heading(self):
        data = [Equals(u"="), Equals(u"="), Equals(u"="), Word(u"foo"),
                NewLine(u'\n'), Word(u"bar")]
        out = list(self.p.process(y(data)))
        self.assertEquals(len(out), 2)


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser()
    parser.add_option("-d", "--debug", dest="debug",
                      help="debug line-by-line",
                      action="store_true", default=False)
    parser.add_option("-s", "--state", dest="state",
                      help="print state",
                      action="store_true", default=False)
    (opts, args) = parser.parse_args()
    if opts.state:
        _print_state = True

    if len(args) == 0:
        unittest.main()

    for item in args:
        with codecs.open(item, 'r', encoding='utf-8') as f:
            a = MWProcessor()
            start = datetime.datetime.now()

            contents = f.read()

            if not opts.debug:
                newlines = 0
                for token in a.process(tokenize(contents, tokens())):
                    if isinstance(token, NewLine):
                        newlines += 1
                    else:
                        newlines = 0
                    if newlines < 3:
                        sys.stdout.write(token.text)
                continue

            toks = []
            for token in a.process(tokenize(contents, tokens())):
                if len(toks) == 30:
                    print toks
                    print u''.join([to.text for to in toks])
                    print
                    toks = [token]
                else:
                    toks.append(token)

            end = datetime.datetime.now()
            d = end - start
            secs = float("%i.%i" % (d.seconds, d.microseconds))
            print "Processing time: %f seconds." % secs



